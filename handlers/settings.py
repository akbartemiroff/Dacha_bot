"""
Обработчики настроек пользователя.
"""

from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from database.db import update_user, get_or_create_user
from utils.filters import AllowedUserFilter
from utils.states import SettingsStates
from utils.keyboards import get_main_menu_keyboard

router = Router()
router.message.filter(AllowedUserFilter())


@router.message(SettingsStates.waiting_for_group, F.text)
async def process_group_input(message: Message, state: FSMContext) -> None:
    """Обработка ввода группы."""
    # Проверка на кнопку отмены
    if message.text == "❌ Отмена":
        await state.clear()
        text = "✅ Действие отменено."
        await message.answer(text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())
        return
    
    user_id = message.from_user.id
    group_input = message.text.strip()
    
    # Проверяем формат
    if not (group_input.startswith("@") or group_input.lstrip("-").isdigit()):
        text = """❌ <b>Неверный формат!</b>

Укажи:
• @username группы (например: @mygroup)
• Или числовой ID (например: -1001234567890)

⏳ Попробуй ещё раз..."""
        await message.answer(text, parse_mode="HTML")
        return
    
    # Проверяем доступ к группе
    bot = message.bot
    try:
        chat = await bot.get_chat(group_input)
        chat_title = chat.title or group_input
        
        # Проверяем права бота в группе
        bot_member = await bot.get_chat_member(chat.id, bot.id)
        if bot_member.status not in ["administrator", "member"]:
            text = """❌ <b>Бот не является участником группы!</b>

Добавь бота в группу и попробуй снова.

⏳ Жду ввода..."""
            await message.answer(text, parse_mode="HTML")
            return
            
    except Exception as e:
        error_str = str(e).lower()
        if "chat not found" in error_str:
            text = """❌ <b>Группа не найдена!</b>

Возможные причины:
• Бот не добавлен в группу
• Неверный username или ID группы
• Группа является приватной

<b>Как получить ID группы:</b>
1. Добавь бота @getmyid_bot в группу
2. Он напишет ID группы (начинается с -100)
3. Скопируй этот ID и отправь мне

⏳ Попробуй ещё раз..."""
        else:
            text = f"""❌ <b>Ошибка проверки группы:</b>

{str(e)}

⏳ Попробуй ещё раз..."""
        await message.answer(text, parse_mode="HTML")
        return
    
    # Сохраняем ID группы (не username, для надёжности)
    await update_user(user_id, target_group=str(chat.id))
    await state.clear()
    
    text = f"""✅ <b>Группа установлена!</b>

🎯 Группа: <b>{chat_title}</b>
🆔 ID: <code>{chat.id}</code>

Бот успешно подключён к группе и готов к публикации."""
    
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())


@router.message(SettingsStates.waiting_for_group)
async def process_wrong_group(message: Message) -> None:
    """Обработка неправильного ввода группы."""
    text = """❌ <b>Нужно отправить текст!</b>

Укажи @username или ID группы.

⏳ Жду ввода..."""
    
    await message.answer(text, parse_mode="HTML")


async def process_interval(message: Message, state: FSMContext, args: list[str]) -> None:
    """
    Обработка ввода интервала.
    
    Args:
        message: Сообщение пользователя
        state: Контекст FSM
        args: Аргументы (два числа)
    """
    user_id = message.from_user.id
    
    try:
        min_val = int(args[0])
        max_val = int(args[1])
    except ValueError:
        text = """❌ <b>Нужно ввести два числа!</b>

Пример: <code>2 5</code>

⏳ Попробуй ещё раз..."""
        await message.answer(text, parse_mode="HTML")
        return
    
    # Валидация
    if min_val < 1:
        text = """❌ <b>Минимальный интервал должен быть не менее 1 минуты!</b>

⏳ Попробуй ещё раз..."""
        await message.answer(text, parse_mode="HTML")
        return
    
    if max_val < min_val:
        text = """❌ <b>Максимум не может быть меньше минимума!</b>

⏳ Попробуй ещё раз..."""
        await message.answer(text, parse_mode="HTML")
        return
    
    await update_user(user_id, interval_min=min_val, interval_max=max_val)
    await state.clear()
    
    text = f"""✅ <b>Интервал установлен!</b>

⏱ Интервал: от {min_val} до {max_val} минут

Публикации будут происходить со случайной задержкой в этом диапазоне."""
    
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())


@router.message(SettingsStates.waiting_for_interval, F.text)
async def process_interval_input(message: Message, state: FSMContext) -> None:
    """Обработка ввода интервала из состояния."""
    # Проверка на кнопку отмены
    if message.text == "❌ Отмена":
        await state.clear()
        text = "✅ Действие отменено."
        await message.answer(text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())
        return
    
    args = message.text.split()
    
    if len(args) != 2:
        text = """❌ <b>Нужно ввести два числа через пробел!</b>

Пример: <code>2 5</code>

⏳ Попробуй ещё раз..."""
        await message.answer(text, parse_mode="HTML")
        return
    
    await process_interval(message, state, args)


@router.message(SettingsStates.waiting_for_interval)
async def process_wrong_interval(message: Message) -> None:
    """Обработка неправильного ввода интервала."""
    text = """❌ <b>Нужно отправить текст!</b>

Введи два числа через пробел (мин и макс минут).

⏳ Жду ввода..."""
    
    await message.answer(text, parse_mode="HTML")


async def process_hours(message: Message, state: FSMContext, args: list[str]) -> None:
    """
    Обработка ввода часов.
    
    Args:
        message: Сообщение пользователя
        state: Контекст FSM
        args: Аргументы (два числа)
    """
    user_id = message.from_user.id
    
    try:
        start_hour = int(args[0])
        end_hour = int(args[1])
    except ValueError:
        text = """❌ <b>Нужно ввести два числа!</b>

Пример: <code>9 22</code>

⏳ Попробуй ещё раз..."""
        await message.answer(text, parse_mode="HTML")
        return
    
    # Валидация
    if not (0 <= start_hour <= 23) or not (0 <= end_hour <= 23):
        text = """❌ <b>Часы должны быть от 0 до 23!</b>

⏳ Попробуй ещё раз..."""
        await message.answer(text, parse_mode="HTML")
        return
    
    if start_hour >= end_hour:
        text = """❌ <b>Час начала должен быть меньше часа окончания!</b>

⏳ Попробуй ещё раз..."""
        await message.answer(text, parse_mode="HTML")
        return
    
    await update_user(user_id, hours_start=start_hour, hours_end=end_hour)
    await state.clear()
    
    text = f"""✅ <b>Часы работы установлены!</b>

🕐 Активные часы: с {start_hour}:00 до {end_hour}:00

Публикации будут происходить только в это время."""
    
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())


@router.message(SettingsStates.waiting_for_hours, F.text)
async def process_hours_input(message: Message, state: FSMContext) -> None:
    """Обработка ввода часов из состояния."""
    # Проверка на кнопку отмены
    if message.text == "❌ Отмена":
        await state.clear()
        text = "✅ Действие отменено."
        await message.answer(text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())
        return
    
    args = message.text.split()
    
    if len(args) != 2:
        text = """❌ <b>Нужно ввести два числа через пробел!</b>

Пример: <code>9 22</code>

⏳ Попробуй ещё раз..."""
        await message.answer(text, parse_mode="HTML")
        return
    
    await process_hours(message, state, args)


@router.message(SettingsStates.waiting_for_hours)
async def process_wrong_hours(message: Message) -> None:
    """Обработка неправильного ввода часов."""
    text = """❌ <b>Нужно отправить текст!</b>

Введи два числа через пробел (час начала и окончания).

⏳ Жду ввода..."""
    
    await message.answer(text, parse_mode="HTML")


@router.message(F.text == "⚙️ Настройки")
@router.message(Command("settings"))
async def cmd_settings(message: Message, state: FSMContext) -> None:
    """Обработчик команды /settings."""
    await state.clear()
    user = await get_or_create_user(message.from_user.id)
    
    # Форматируем данные
    photo_status = "✅ Загружено" if user.get("photo_file_id") else "❌ Не загружено"
    caption_status = "✅ Установлен" if user.get("caption") else "❌ Не установлен"
    group_status = user.get("target_group") or "❌ Не указана"
    interval = f"{user.get('interval_min', 2)} - {user.get('interval_max', 5)} мин"
    hours = f"{user.get('hours_start', 9)}:00 - {user.get('hours_end', 22)}:00"
    running = "🟢 Работает" if user.get("is_running") else "🔴 Остановлен"
    
    text = f"""⚙️ <b>Текущие настройки:</b>

📸 Фото: {photo_status}
📝 Текст: {caption_status}
🎯 Группа: <code>{group_status}</code>
⏱ Интервал: {interval}
🕐 Часы: {hours}
📊 Статус: {running}"""
    
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())


@router.message(F.text == "👁 Предпросмотр")
@router.message(Command("preview"))
async def cmd_preview(message: Message, state: FSMContext) -> None:
    """Обработчик команды /preview."""
    await state.clear()
    user = await get_or_create_user(message.from_user.id)
    
    photo_file_id = user.get("photo_file_id")
    caption = user.get("caption")
    
    if not photo_file_id:
        text = "❌ Контент не загружен! Нажми «📸 Загрузить контент»"
        await message.answer(text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())
        return
    
    if not caption:
        text = "❌ Текст не установлен! Нажми «📸 Загрузить контент»"
        await message.answer(text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())
        return
    
    # Отправляем предпросмотр
    await message.answer("👁 <b>Предпросмотр поста:</b>", parse_mode="HTML")
    await message.answer_photo(photo=photo_file_id, caption=caption)

