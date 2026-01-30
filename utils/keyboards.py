"""
Клавиатуры для бота.
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton


def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """
    Главное меню с командами.
    
    Returns:
        ReplyKeyboardMarkup с кнопками команд
    """
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="➕ Добавить"),
                KeyboardButton(text="📋 Мои контенты")
            ],
            [
                KeyboardButton(text="🎯 Указать группу"),
                KeyboardButton(text="📊 Статус")
            ],
            [
                KeyboardButton(text="❓ Помощь")
            ]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие..."
    )
    return keyboard


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """
    Клавиатура с кнопкой отмены.
    
    Returns:
        ReplyKeyboardMarkup с кнопкой отмены
    """
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )
    return keyboard

