import datetime
from enum import IntEnum
from typing import Any, Callable, NamedTuple, Union

from aiogram import F, types
from aiogram.utils.magic_filter import MagicFilter

FormFilter = Union[MagicFilter, Callable[..., Any]]


class _FormFilterType(IntEnum):
    magic = 0
    func = 1
    coro = 2


class _FormFilter(NamedTuple):
    filter: FormFilter
    filter_type: _FormFilterType


DEFAULT_FORM_FILTERS = {
    str: F.text,
    int: F.text.func(int),
    float: F.text.func(float),
    datetime.date: F.text.func(
        lambda text: datetime.datetime.strptime(text, r"%d.%m.%Y").date()
    ),
    datetime.datetime: F.text.func(
        lambda text: datetime.datetime.strptime(text, r"%d.%m.%Y %H:%M")
    ),
    datetime.time: F.text.func(
        lambda text: datetime.datetime.strptime(text, r"%H:%M").time()
    ),
    types.PhotoSize: F.photo.func(lambda photo: photo[-1]),
    types.Document: F.document.func(lambda document: document),
    types.Message: F.func(lambda m: m),
}
