import datetime
from dataclasses import dataclass
from typing import Any, Callable, Coroutine, Protocol, Type

from aiogram import F, types
from aiogram.utils.magic_filter import MagicFilter

from . import utils

FormFilter = MagicFilter | Callable[..., Any]
InputTransformResult = tuple[Any, bool]

DEFAULT_FORM_FILTERS: dict[Type, FormFilter] = {
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


class InputTransformer(Protocol):
    async def transform_input_message(
        self, message: types.Message, data: dict[str, Any]
    ) -> InputTransformResult: ...


@dataclass(frozen=True)
class MagicInputTransformer(InputTransformer):
    filter: MagicFilter

    async def transform_input_message(
        self, message: types.Message, data: dict[str, Any]
    ) -> InputTransformResult:
        filter_result = self.filter.resolve(message)

        if filter_result is None or filter_result is False:
            return filter_result, False

        return filter_result, True


@dataclass(frozen=True)
class SyncInputTransformer(InputTransformer):
    filter: Callable[..., Any]

    async def transform_input_message(
        self, message: types.Message, data: dict[str, Any]
    ) -> InputTransformResult:
        prepared_field_filter = utils.prepare_function(self.filter, message, **data)
        filter_result = prepared_field_filter()

        if filter_result is False:
            return filter_result, False

        return filter_result, True


@dataclass(frozen=True)
class AsyncInputTransformer(InputTransformer):
    filter: Callable[..., Coroutine[Any, Any, Any]]

    async def transform_input_message(
        self, message: types.Message, data: dict[str, Any]
    ) -> InputTransformResult:
        prepared_field_filter = utils.prepare_function(self.filter, message, **data)
        filter_result = await prepared_field_filter()

        if filter_result is False:
            return filter_result, False

        return filter_result, True


def get_form_filter_for_type(field_type: Type) -> FormFilter:
    field_filter = DEFAULT_FORM_FILTERS.get(field_type)

    if field_filter is None:
        raise TypeError(
            f"There is no default filter for type {field_type}. You should consider writing your own filter"  # noqa: E501
        )

    return field_filter
