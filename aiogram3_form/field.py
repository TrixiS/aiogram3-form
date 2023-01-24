from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional, Type, Union

from aiogram import types
from aiogram.utils.magic_filter import MagicFilter

Markup = Union[types.ReplyKeyboardMarkup, types.InlineKeyboardMarkup]
FormFilter = Union[MagicFilter, Callable[..., Awaitable[Any]]]
EnterCallback = Callable[["FormFieldData"], Awaitable[Any]]


@dataclass(frozen=True)
class FormFieldInfo:
    enter_message_text: str
    error_message_text: Optional[str]
    filter: Optional[FormFilter]
    reply_markup: Optional[Markup]
    enter_callback: EnterCallback | None


@dataclass
class FormFieldData:
    name: str
    type: Type
    info: FormFieldInfo


def FormField(
    *,
    enter_message_text: str,
    filter: Optional[FormFilter] = None,
    error_message_text: Optional[str] = None,
    reply_markup: Optional[Markup] = None,
    enter_callback: EnterCallback | None = None
) -> Any:
    return FormFieldInfo(
        enter_message_text=enter_message_text,
        error_message_text=error_message_text,
        filter=filter,
        reply_markup=reply_markup,
        enter_callback=enter_callback,
    )
