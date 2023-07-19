import datetime
from typing import Any, Awaitable, Callable, Union

from aiogram import F, types
from aiogram.utils.magic_filter import MagicFilter

FormFilter = Union[
    MagicFilter,
    Callable[..., Awaitable[Any]],
    Callable[[types.Message], Any],
]

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
