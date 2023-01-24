from aiogram.fsm.state import State, StatesGroup


class FormState(StatesGroup):
    waiting_field_value = State()
