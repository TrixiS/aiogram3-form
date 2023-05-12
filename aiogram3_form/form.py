import functools
import inspect
from abc import ABC, ABCMeta
from typing import Any, Callable, ClassVar, Optional, Set, Type, Union

from aiogram import Bot, types
from aiogram.dispatcher.router import Router
from aiogram.fsm.context import FSMContext
from aiogram.utils.magic_filter import MagicFilter

from . import filters
from .field import FormFieldData, FormFieldInfo
from .state import FormState

SubmitCallback = Callable[..., Any]
Markup = Union[types.ReplyKeyboardMarkup, types.InlineKeyboardMarkup]

REMOVE_MARKUP = types.ReplyKeyboardRemove(remove_keyboard=True)


class FormMeta(ABCMeta):
    bot: ClassVar[Bot]
    router: ClassVar[Router]
    clear_state_on_submit: ClassVar[bool] = True

    __form_cls_names: Set[str] = set()

    def __new__(
        cls,
        cls_name: str,
        parents: tuple,
        cls_dict: dict,
        *,
        router: Router,
        bot: Bot,
        clear_state_on_submit: bool = True,
    ):
        if cls_name in cls.__form_cls_names:
            raise NameError("Form with the same name does exist")

        cls.__form_cls_names.add(cls_name)

        cls_dict["clear_state_on_submit"] = clear_state_on_submit
        cls_dict["router"] = router
        cls_dict["bot"] = bot

        return super().__new__(cls, cls_name, parents, cls_dict)


class Form(ABC, metaclass=FormMeta, router=None, bot=None):  # type: ignore
    __registered_forms: Set[Type["Form"]] = set()
    __submit_callback: Optional[SubmitCallback] = None

    def __init__(self, state: FSMContext):
        self.state = state

    @classmethod
    def submit(cls):
        def decorator(submit_callback: SubmitCallback):
            cls.__submit_callback = submit_callback

        return decorator

    @classmethod
    async def __from_state(cls, state: FSMContext):
        state_data = await state.get_data()
        form_object = cls(state)
        form_object.__dict__.update(state_data["__form_values"])
        return form_object

    @classmethod
    def __get_filter_from_type(cls, field_type: Type):
        field_filter = filters.DEFAULT_FORM_FILTERS.get(field_type)

        if field_filter is None:
            raise TypeError(
                f"There is no default filter for type {field_type}. You should consider writing your own filter"
            )

        return field_filter

    @classmethod
    def __prepare_submit_callback(cls, *args, **kwargs):
        if cls.__submit_callback is None:
            raise TypeError("Submit callback should be set")

        return cls.__prepare_function(cls.__submit_callback, *args, **kwargs)

    @classmethod
    def __prepare_function(cls, func: Callable, *args, **kwargs):
        arg_spec = inspect.getfullargspec(func)
        prepared_kwargs = {
            k: v
            for k, v in kwargs.items()
            if k in arg_spec.args or k in arg_spec.kwonlyargs
        }

        partial_func = functools.partial(func, *args, **prepared_kwargs)
        return partial_func

    @classmethod
    def __get_field_data_by_name(cls, name: str):
        field_info: FormFieldInfo = getattr(cls, name)
        field_type = cls.__annotations__[name]
        field_data = FormFieldData(name, field_type, field_info)
        return field_data

    @classmethod
    def __get_next_field(
        cls, current_field_name: Optional[str]
    ) -> Optional[FormFieldData]:
        field_names = tuple(cls.__annotations__.keys())

        if current_field_name is None:
            return cls.__get_field_data_by_name(field_names[0])

        current_field_index = field_names.index(current_field_name)

        try:
            next_field_name = field_names[current_field_index + 1]
            return cls.__get_field_data_by_name(next_field_name)
        except IndexError:
            return None

    # TODO: method to send enter message
    @classmethod
    async def start(cls, state_ctx: FSMContext):
        first_field = cls.__get_next_field(None)

        if first_field is None:
            raise TypeError("First field couldn't be None")

        await state_ctx.set_state(FormState.waiting_field_value)

        await state_ctx.update_data(
            __current_field_name=first_field.name,  # type: ignore
            __form_values={},
            __form_name=cls.__name__,
        )

        if first_field.info.enter_callback:
            await first_field.info.enter_callback(
                state_ctx.key.chat_id, state_ctx.key.user_id, {}
            )
        else:
            await cls.bot.send_message(
                state_ctx.key.chat_id,
                first_field.info.enter_message_text,  # type: ignore
                reply_markup=first_field.info.reply_markup or REMOVE_MARKUP,  # type: ignore
            )

        if cls in Form.__registered_forms:
            return

        cls.router.message.register(
            cls.__resolve_callback,
            FormState.waiting_field_value,
            cls.__current_field_filter,
        )

        Form.__registered_forms.add(cls)

    @classmethod
    async def __resolve_callback(
        cls, message: types.Message, state: FSMContext, value: Any, **data
    ):
        state_data = await state.get_data()
        current_field_name: str = state_data["__current_field_name"]
        state_data["__form_values"][current_field_name] = value
        await state.set_data(state_data)

        next_field = cls.__get_next_field(current_field_name)

        if next_field:
            state_data["__current_field_name"] = next_field.name
            await state.set_data(state_data)

            if next_field.info.enter_callback:
                return await next_field.info.enter_callback(
                    state.key.chat_id, state.key.user_id, state_data
                )

            return await message.answer(
                next_field.info.enter_message_text,  # type: ignore
                reply_markup=next_field.info.reply_markup or REMOVE_MARKUP,
            )

        if not cls.__submit_callback:
            raise TypeError(
                f"{cls.__name__} submit callback is {cls.__submit_callback}"
            )

        form_object = await cls.__from_state(state)
        data["state"] = state

        prepared_submit_callback = cls.__prepare_submit_callback(form_object, **data)

        try:
            await prepared_submit_callback()
        finally:
            if cls.clear_state_on_submit:
                await state.clear()

    @classmethod
    async def __current_field_filter(
        cls, message: types.Message, state: FSMContext, **data
    ):
        state_data = await state.get_data()

        if state_data["__form_name"] != cls.__name__:
            return False

        current_field_name: str = state_data["__current_field_name"]
        current_field = cls.__get_field_data_by_name(current_field_name)

        field_filter = current_field.info.filter or cls.__get_filter_from_type(
            current_field.type
        )

        # TODO: allow using sync filters
        if inspect.iscoroutinefunction(field_filter):
            prepared_field_filter = cls.__prepare_function(
                field_filter, message, **data
            )

            filter_result = await prepared_field_filter()

            if filter_result is False:
                return False

            return dict(value=filter_result)

        if isinstance(field_filter, MagicFilter):
            filter_result = field_filter.resolve(message)

            if not filter_result:
                return False

            return dict(value=filter_result)

        if current_field.info.error_message_text:
            await message.answer(
                current_field.info.error_message_text,
                reply_markup=current_field.info.reply_markup or REMOVE_MARKUP,
            )

        return False

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
    ):
        await self.__class__.bot.send_message(
            self.state.key.chat_id, text=text, reply_markup=reply_markup
        )
