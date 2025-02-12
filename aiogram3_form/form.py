import inspect
from abc import ABC, ABCMeta
from typing import Any, Callable, Coroutine, Generator, NamedTuple, TypedDict

from aiogram import Bot, types
from aiogram.dispatcher.router import Router
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.utils.magic_filter import MagicFilter

from . import filters, utils
from .field import FormFieldData, FormFieldInfo

SubmitCallback = Callable[..., Any]
Markup = types.ReplyKeyboardMarkup | types.InlineKeyboardMarkup


def _form_fields_data_generator(cls: "FormMeta") -> Generator[FormFieldData, Any, None]:
    annotations = inspect.get_annotations(cls)

    for field_name, field_type in annotations.items():
        field_info = getattr(cls, field_name, None)

        if not isinstance(field_info, FormFieldInfo):
            continue

        if field_info.filter is None:
            field_filter = filters.get_form_filter_for_type(field_type)
        else:
            field_filter = field_info.filter

        if isinstance(field_filter, MagicFilter):
            transformer = filters.MagicInputTransformer(field_filter)
        elif inspect.iscoroutinefunction(field_filter):
            transformer = filters.CoroInputTransformer(field_filter)
        elif inspect.isfunction(field_filter):
            transformer = filters.FuncInputTransformer(field_filter)
        else:
            raise TypeError(
                f"Invalid filter of type {field_filter.__class__.__name__} for field {field_name}"  # noqa: E501
            )

        yield FormFieldData(name=field_name, info=field_info, transformer=transformer)


class FormStateData(TypedDict):
    __current_field_index: int
    __form_values: dict[str, Any]


class FormMeta(ABCMeta):
    __form_cls_names: set[str] = set()

    def __new__(cls, cls_name: str, parents: tuple, cls_dict: dict):
        if cls_name in cls.__form_cls_names:
            raise NameError("Form with the same name does exist")

        cls.__form_cls_names.add(cls_name)

        subcls = super().__new__(cls, cls_name, parents, cls_dict)
        setattr(subcls, "fields", tuple(_form_fields_data_generator(subcls)))
        return subcls


class FormSubmitData(NamedTuple):
    callback: SubmitCallback
    clear_state: bool


class Form(ABC, metaclass=FormMeta):
    fields: tuple[FormFieldData, ...]

    __submit_data: FormSubmitData = None  # type: ignore
    # this should be set by the user via .submit()

    def __init__(self, bot: Bot, chat_id: int):
        self.bot = bot
        self.chat_id = chat_id

    @classmethod
    def submit(
        cls, *, router: Router, clear_state: bool = True
    ) -> Callable[..., SubmitCallback]:
        def _decorator(submit_callback: SubmitCallback) -> SubmitCallback:
            if cls.__submit_data is not None:
                raise ValueError(f"{cls.__name__} submit callback is already set")

            cls.__submit_data = FormSubmitData(submit_callback, clear_state)

            router.message.register(
                cls.__resolve_callback,
                StateFilter(cls.__name__),
                cls.__current_field_filter,
            )

            return submit_callback

        return _decorator

    @classmethod
    async def start(cls, bot: Bot, state_ctx: FSMContext, **data: Any) -> types.Message:
        first_field = cls.fields[0]

        await state_ctx.set_state(cls.__name__)

        state_data: FormStateData = {
            "__form_values": {},
            "__current_field_index": 0,
        }

        await state_ctx.update_data(
            state_data,  # type: ignore
        )

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
    def __create_object(cls, handler_data: dict[str, Any], state_data: FormStateData):
        form_object = cls(handler_data["bot"], handler_data["event_chat"].id)
        form_object.__dict__.update(state_data["__form_values"])
        return form_object

    @classmethod
    async def __resolve_callback(
        cls, message: types.Message, state: FSMContext, _form_value: Any, **data: Any
    ):
        state_data: FormStateData = await state.get_data()  # type: ignore

        current_field = cls.fields[state_data["__current_field_index"]]
        state_data["__form_values"][current_field.name] = _form_value

        next_field_index = state_data["__current_field_index"] + 1

        if next_field_index > len(cls.fields) - 1:
            if cls.__submit_data.clear_state:
                await state.set_state(None)

            form_object = cls.__create_object(data, state_data)
            data["state"] = state

            prepared_submit_callback = utils.prepare_function(
                cls.__submit_data.callback, form_object, **data
            )

            return await prepared_submit_callback()

        next_field = cls.fields[next_field_index]
        state_data["__current_field_index"] = next_field_index

        await state.set_data(
            state_data,  # type: ignore
        )

        if next_field.info.enter_callback:
            return await next_field.info.enter_callback(
                state.key.chat_id, state.key.user_id, data | state_data
            )

        return await message.answer(
            next_field.info.enter_message_text,  # type: ignore
            reply_markup=next_field.info.reply_markup,
        )

    @classmethod
    async def __current_field_filter(
        cls, message: types.Message, **data: Any
    ) -> dict[str, Any] | bool:
        state: FSMContext = data["state"]
        state_data: FormStateData = await state.get_data()  # type: ignore

        current_field = cls.fields[state_data["__current_field_index"]]

        (
            filter_result,
            success,
        ) = await current_field.transformer.transform_input_message(message, data)

        if success:
            return dict(_form_value=filter_result)

        if current_field.info.error_message_text:
            await message.answer(
                current_field.info.error_message_text,
                reply_markup=current_field.info.reply_markup,
            )

        return False

    def answer(
        self,
        text: str,
        reply_markup: (
            types.InlineKeyboardMarkup
            | types.ReplyKeyboardMarkup
            | types.ReplyKeyboardRemove
            | types.ForceReply
            | None
        ) = None,
        reply_to_message_id: int | None = None,
    ) -> Coroutine[Any, Any, types.Message]:
        return self.bot.send_message(
            self.chat_id,
            text=text,
            reply_markup=reply_markup,
            reply_to_message_id=reply_to_message_id,
        )
