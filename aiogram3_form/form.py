import functools
import inspect
from abc import ABC, ABCMeta
from typing import Any, Callable, NamedTuple, Optional, Set, Tuple, Type, Union

from aiogram import Bot, types
from aiogram.dispatcher.router import Router
from aiogram.fsm.context import FSMContext
from aiogram.utils.magic_filter import MagicFilter

from . import filters
from .field import FormFieldData, FormFieldInfo
from .state import FormState

SubmitCallback = Callable[..., Any]
Markup = Union[types.ReplyKeyboardMarkup, types.InlineKeyboardMarkup]


def _get_form_filter_for_type(field_type: Type):
    field_filter = filters.DEFAULT_FORM_FILTERS.get(field_type)

    if field_filter is None:
        raise TypeError(
            f"There is no default filter for type {field_type}. You should consider writing your own filter"  # noqa: E501
        )

    return field_filter


def _form_fields_data_generator(cls: "FormMeta"):
    annotations = inspect.get_annotations(cls)

    for field_name, field_type in annotations.items():
        field_info = getattr(cls, field_name, None)

        if not isinstance(field_info, FormFieldInfo):
            continue

        if field_info.filter is None:
            field_filter = _get_form_filter_for_type(field_type)
        else:
            field_filter = field_info.filter

        if isinstance(field_filter, MagicFilter):
            filter_type = filters._FormFilterType.magic
        elif inspect.iscoroutinefunction(field_filter):
            filter_type = filters._FormFilterType.coro
        elif inspect.isfunction(field_filter):
            filter_type = filters._FormFilterType.func
        else:
            raise TypeError(
                f"Invalid filter of type {field_filter.__class__.__name__} for field {field_name}"  # noqa: E501
            )

        yield FormFieldData(
            name=field_name,
            type=field_type,
            info=field_info,
            filter=filters._FormFilter(field_filter, filter_type),
        )


def _prepare_function(func: Callable, *args, **kwargs):
    arg_spec = inspect.getfullargspec(func)

    prepared_kwargs = {
        k: v
        for k, v in kwargs.items()
        if k in arg_spec.args or k in arg_spec.kwonlyargs
    }

    partial_func = functools.partial(func, *args, **prepared_kwargs)
    return partial_func


class FormMeta(ABCMeta):
    __form_cls_names: Set[str] = set()

    def __new__(cls, cls_name: str, parents: tuple, cls_dict: dict):
        if cls_name in cls.__form_cls_names:
            raise NameError("Form with the same name does exist")

        cls.__form_cls_names.add(cls_name)

        subcls = super().__new__(cls, cls_name, parents, cls_dict)
        setattr(subcls, "fields", tuple(_form_fields_data_generator(subcls)))

        return subcls


class FormSubmitCallback(NamedTuple):
    callback: SubmitCallback
    clear_state: bool


class Form(ABC, metaclass=FormMeta):
    fields: Tuple[FormFieldData, ...]

    __submit_callback: Optional[FormSubmitCallback] = None

    def __init__(self, bot: Bot, chat_id: int):
        self.bot = bot
        self.chat_id = chat_id

    @classmethod
    def submit(cls, *, router: Router, clear_state: bool = True):
        def _decorator(submit_callback: SubmitCallback):
            if cls.__submit_callback is not None:
                raise ValueError(f"{cls.__name__} submit callback already set")

            cls.__submit_callback = FormSubmitCallback(submit_callback, clear_state)

            router.message.register(
                cls.__resolve_callback,
                FormState.waiting_field_value,
                cls.__current_field_filter,
            )

            return submit_callback

        return _decorator

    @classmethod
    def __create_object(cls, handler_data: dict[str, Any], state_data: FormState.Data):
        form_object = cls(handler_data["bot"], handler_data["event_chat"].id)
        form_object.__dict__.update(state_data["__form_values"])
        return form_object

    @classmethod
    async def start(cls, bot: Bot, state_ctx: FSMContext, **data: Any) -> types.Message:
        first_field = cls.fields[0]

        await state_ctx.set_state(FormState.waiting_field_value)

        state_data: FormState.Data = {
            "__form_name": cls.__name__,
            "__form_values": {},
            "__current_field_index": 0,
        }

        await state_ctx.update_data(state_data)  # type: ignore

        if first_field.info.enter_callback:
            return await first_field.info.enter_callback(
                state_ctx.key.chat_id, state_ctx.key.user_id, data
            )

        return await bot.send_message(
            state_ctx.key.chat_id,
            first_field.info.enter_message_text,  # type: ignore
            reply_markup=first_field.info.reply_markup,
        )

    @classmethod
    async def __resolve_callback(
        cls, message: types.Message, state: FSMContext, value: Any, **data
    ):
        state_data: FormState.Data = await state.get_data()  # type: ignore

        current_field = cls.fields[state_data["__current_field_index"]]
        state_data["__form_values"][current_field.name] = value

        next_field_index = state_data["__current_field_index"] + 1

        try:
            next_field = cls.fields[next_field_index]
            state_data["__current_field_index"] = next_field_index
            await state.set_data(state_data)  # type: ignore

            if next_field.info.enter_callback:
                return await next_field.info.enter_callback(
                    state.key.chat_id, state.key.user_id, data | state_data
                )

            return await message.answer(
                next_field.info.enter_message_text,  # type: ignore
                reply_markup=next_field.info.reply_markup,
            )
        except IndexError:
            pass  # submit reached

        if cls.__submit_callback is None:
            raise TypeError("Submit callback should be set")

        form_object = cls.__create_object(data, state_data)
        data["state"] = state

        prepared_submit_callback = _prepare_function(
            cls.__submit_callback.callback, form_object, **data
        )

        try:
            await prepared_submit_callback()
        finally:
            if cls.__submit_callback.clear_state:
                await state.clear()

    @classmethod
    async def __current_field_filter(
        cls, message: types.Message, state: FSMContext, **data
    ):
        state_data: FormState.Data = await state.get_data()  # type: ignore

        if state_data["__form_name"] != cls.__name__:
            return False

        current_field = cls.fields[state_data["__current_field_index"]]

        async def send_error_message():
            if current_field.info.error_message_text:
                return await message.answer(
                    current_field.info.error_message_text,
                    reply_markup=current_field.info.reply_markup,
                )

        if current_field.filter.filter_type == filters._FormFilterType.magic:
            filter_result = current_field.filter.filter.resolve(
                message,
            )

            if filter_result is not None and filter_result is not False:
                return dict(value=filter_result)

            await send_error_message()
            return False

        if current_field.filter.filter_type == filters._FormFilterType.coro:
            prepared_field_filter = _prepare_function(
                current_field.filter.filter, message, **data
            )

            filter_result = await prepared_field_filter()

            if filter_result is not False:
                return dict(value=filter_result)

            await send_error_message()
            return False

        if current_field.filter.filter_type == filters._FormFilterType.func:
            prepared_field_filter = _prepare_function(
                current_field.filter.filter, message, **data
            )

            filter_result = prepared_field_filter()

            if filter_result is not False:
                return dict(value=filter_result)

            await send_error_message()
            return False

        raise TypeError(f"Invalid filter specified for field {current_field.name}")

    async def answer(
        self,
        text: str,
        reply_markup: Union[
            types.InlineKeyboardMarkup,
            types.ReplyKeyboardMarkup,
            types.ReplyKeyboardRemove,
            types.ForceReply,
            None,
        ] = None,
        reply_to_message_id: Optional[int] = None,
    ):
        return await self.bot.send_message(
            self.chat_id,
            text=text,
            reply_markup=reply_markup,
            reply_to_message_id=reply_to_message_id,
        )
