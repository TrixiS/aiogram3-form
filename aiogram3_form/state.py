from typing import Any, Dict, TypedDict

from aiogram.fsm.state import State, StatesGroup


class FormState(StatesGroup):
    class Data(TypedDict):
        __form_name: str
        __current_field_index: int
        __form_values: Dict[str, Any]

    waiting_field_value = State()
