from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional, Type, Union

from aiogram import types

from .filters import FormFilter, _FormFilter

Markup = Union[
    types.ReplyKeyboardMarkup, types.InlineKeyboardMarkup, types.ReplyKeyboardRemove
]

EnterCallback = Callable[[int, int, Dict[str, Any]], Awaitable[types.Message]]


@dataclass(frozen=True)
class FormFieldInfo:
    enter_message_text: Optional[str]
    error_message_text: Optional[str]
    filter: Optional[FormFilter]
    reply_markup: Optional[Markup]
    enter_callback: Optional[EnterCallback]


@dataclass(frozen=True)
class FormFieldData:
    name: str
    type: Type
    info: FormFieldInfo
    filter: _FormFilter


def FormField(
    *,
    enter_message_text: Optional[str] = None,
    filter: Optional[FormFilter] = None,
    error_message_text: Optional[str] = None,
    reply_markup: Optional[Markup] = None,
    enter_callback: Optional[EnterCallback] = None
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
