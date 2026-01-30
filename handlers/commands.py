"""
Обработчики основных команд бота.
"""

from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from aiogram.fsm.context import FSMContext

from database.db import get_or_create_user
from utils.filters import AllowedUserFilter
from utils.states import ContentStates, SettingsStates
from utils.keyboards import get_main_menu_keyboard, get_cancel_keyboard

router = Router()
router.message.filter(AllowedUserFilter())


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    """Обработчик команды /start."""
    await state.clear()
    await get_or_create_user(message.from_user.id)
    
    text = """👋 <b>Привет!</b>

Я бот для автоматической публикации постов в Telegram-группы.

<b>Как использовать:</b>
1️⃣ Загрузи контент
2️⃣ Укажи группу
3️⃣ Настрой интервал и часы работы
4️⃣ Запусти публикацию

Используй кнопки меню ниже 👇"""
    
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())


@router.message(F.text == "❓ Помощь")
@router.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext) -> None:
    """Обработчик команды /help."""
    await state.clear()
    
    text = """📖 <b>Справка по командам:</b>

<b>Настройка контента:</b>
📸 Загрузить контент — добавить фото и текст
👁 Предпросмотр — посмотреть как будет выглядеть пост

<b>Настройка публикации:</b>
🎯 Указать группу — выбрать группу для постинга
⏱ Интервал — задать мин/макс минут между постами
🕐 Часы работы — когда публиковать

<b>Управление:</b>
▶️ Запустить — начать автопубликацию
⏹ Остановить — прекратить публикацию
📊 Статус — текущее состояние

<b>Информация:</b>
⚙️ Настройки — показать все параметры
❓ Помощь — эта справка"""
    
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())


@router.message(F.text == "📸 Загрузить контент")
@router.message(Command("setcontent"))
async def cmd_setcontent(message: Message, state: FSMContext) -> None:
    """Обработчик команды /setcontent."""
    await state.set_state(ContentStates.waiting_for_content)
    
    text = """📸 <b>Отправь фото для публикации</b>

Ты можешь:
• Отправить фото с подписью — текст будет сохранён как описание
• Отправить только фото — я попрошу ввести текст отдельно

⏳ Жду фото..."""
    
    await message.answer(text, parse_mode="HTML", reply_markup=get_cancel_keyboard())


@router.message(F.text == "🎯 Указать группу")
@router.message(Command("setgroup"))
async def cmd_setgroup(message: Message, state: FSMContext) -> None:
    """Обработчик команды /setgroup."""
    await state.set_state(SettingsStates.waiting_for_group)
    
    text = """🎯 <b>Укажи целевую группу</b>

Отправь:
• @username группы (например: @mygroup)
• Или числовой ID группы (например: -1001234567890)

⚠️ Бот должен быть добавлен в группу с правами на отправку сообщений!

⏳ Жду ввода..."""
    
    await message.answer(text, parse_mode="HTML", reply_markup=get_cancel_keyboard())


@router.message(F.text == "⏱ Интервал")
@router.message(Command("setinterval"))
async def cmd_setinterval(message: Message, state: FSMContext) -> None:
    """Обработчик команды /setinterval."""
    # Проверяем, есть ли аргументы в команде
    args = message.text.split()[1:] if message.text else []
    
    if len(args) == 2:
        # Обрабатываем аргументы сразу
        from handlers.settings import process_interval
        await process_interval(message, state, args)
        return
    
    await state.set_state(SettingsStates.waiting_for_interval)
    
    text = """⏱ <b>Укажи интервал между публикациями</b>

Отправь два числа через пробел:
• Первое — минимум минут
• Второе — максимум минут

Пример: <code>2 5</code> — случайный интервал от 2 до 5 минут

⏳ Жду ввода..."""
    
    await message.answer(text, parse_mode="HTML", reply_markup=get_cancel_keyboard())


@router.message(F.text == "🕐 Часы работы")
@router.message(Command("sethours"))
async def cmd_sethours(message: Message, state: FSMContext) -> None:
    """Обработчик команды /sethours."""
    # Проверяем, есть ли аргументы в команде
    args = message.text.split()[1:] if message.text else []
    
    if len(args) == 2:
        # Обрабатываем аргументы сразу
        from handlers.settings import process_hours
        await process_hours(message, state, args)
        return
    
    await state.set_state(SettingsStates.waiting_for_hours)
    
    text = """🕐 <b>Укажи активные часы работы</b>

Отправь два числа через пробел:
• Первое — час начала (0-23)
• Второе — час окончания (0-23)

Пример: <code>9 22</code> — работа с 9:00 до 22:00

⏳ Жду ввода..."""
    
    await message.answer(text, parse_mode="HTML", reply_markup=get_cancel_keyboard())


@router.message(F.text == "❌ Отмена")
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    """Обработчик кнопки отмены."""
    await state.clear()
    
    text = "✅ Действие отменено."
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())

