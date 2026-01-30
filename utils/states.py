"""
Определение состояний FSM для бота.
"""

from aiogram.fsm.state import State, StatesGroup


class ContentStates(StatesGroup):
    """Состояния для загрузки контента."""
    waiting_for_content = State()
    waiting_for_caption = State()
    waiting_for_interval = State()  # Интервал для контента
    waiting_for_time = State()  # Время начала и окончания (ЧЧ:ММ ЧЧ:ММ)


class EditContentStates(StatesGroup):
    """Состояния для редактирования контента."""
    waiting_for_photo = State()
    waiting_for_caption = State()
    waiting_for_interval = State()
    waiting_for_time = State()


class SettingsStates(StatesGroup):
    """Состояния для настроек."""
    waiting_for_group = State()
    waiting_for_interval = State()
    waiting_for_hours = State()

