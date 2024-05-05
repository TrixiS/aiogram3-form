from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Type

from aiogram import types

from .filters import FormFilter, InputTransformer

Markup = (
    types.ReplyKeyboardMarkup | types.InlineKeyboardMarkup | types.ReplyKeyboardRemove
)

EnterCallback = Callable[[int, int, dict[str, Any]], Awaitable[types.Message]]


@dataclass(frozen=True)
class FormFieldInfo:
    enter_message_text: str | None
    error_message_text: str | None
    filter: FormFilter | None
    reply_markup: Markup | None
    enter_callback: EnterCallback | None


@dataclass(frozen=True)
class FormFieldData:
    name: str
    type: Type
    info: FormFieldInfo
    transformer: InputTransformer


def FormField(
    *,
    enter_message_text: str | None = None,
    filter: FormFilter | None = None,
    error_message_text: str | None = None,
    reply_markup: Markup | None = None,
    enter_callback: EnterCallback | None = None
) -> Any:
    if enter_message_text is None and enter_callback is None:
        raise ValueError("enter_message_text or enter_callback should be set")

    return FormFieldInfo(
        enter_message_text=enter_message_text,
        error_message_text=error_message_text,
        filter=filter,
        reply_markup=reply_markup,
        enter_callback=enter_callback,
    )
