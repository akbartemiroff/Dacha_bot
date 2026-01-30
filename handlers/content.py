"""
Обработчики загрузки контента.
"""

import re
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from database.db import (
    update_user, get_or_create_user, add_content, get_contents,
    update_content, get_content_by_id, set_content_running
)
from utils.filters import AllowedUserFilter
from utils.states import ContentStates
from utils.keyboards import get_main_menu_keyboard, get_cancel_keyboard

router = Router()
router.message.filter(AllowedUserFilter())


def validate_time_format(time_str: str) -> bool:
    """Проверка формата времени ЧЧ:ММ."""
    pattern = r'^([0-1]?[0-9]|2[0-3]):([0-5][0-9])$'
    return bool(re.match(pattern, time_str))


def get_cancel_inline_keyboard() -> InlineKeyboardMarkup:
    """Inline кнопка отмены."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="content_cancel_add")]
    ])


@router.callback_query(F.data == "content_cancel_add")
async def callback_cancel_add(callback: CallbackQuery, state: FSMContext) -> None:
    """Отмена добавления контента."""
    await state.clear()
    await callback.message.edit_text("✅ Добавление отменено.", parse_mode="HTML")
    await callback.answer()


@router.message(ContentStates.waiting_for_content, F.photo)
async def process_photo(message: Message, state: FSMContext) -> None:
    """Обработка полученного фото."""
    user_id = message.from_user.id
    photo_file_id = message.photo[-1].file_id  # Берём фото в лучшем качестве
    data = await state.get_data()
    adding_to_list = data.get("adding_to_list", False)
    
    if message.caption:
        if adding_to_list:
            # Добавляем в список контентов
            contents = await get_contents(user_id)
            content_id = await add_content(
                user_id, 
                photo_file_id, 
                message.caption,
                name=f"Контент #{len(contents) + 1}"
            )
            
            # Переходим к настройке интервала
            await state.update_data(content_id=content_id)
            await state.set_state(ContentStates.waiting_for_interval)
            
            text = """✅ Фото и текст сохранены!

⏱ <b>Укажи интервал между публикациями</b>

Отправь два числа через пробел:
• Первое — минимум минут
• Второе — максимум минут

Пример: <code>2 5</code> — случайный интервал от 2 до 5 минут"""
            
            await message.answer(text, parse_mode="HTML", reply_markup=get_cancel_inline_keyboard())
        else:
            # Старое поведение
            await update_user(
                user_id,
                photo_file_id=photo_file_id,
                caption=message.caption
            )
            await state.clear()
            
            text = """✅ <b>Контент сохранён!</b>

📸 Фото: загружено
📝 Текст: сохранён"""
            
            await message.answer(text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())
    else:
        # Фото без подписи — сохраняем фото и ждём текст
        await state.update_data(photo_file_id=photo_file_id)
        await state.set_state(ContentStates.waiting_for_caption)
        
        text = """📸 Фото получено!

✏️ Теперь отправь текст для подписи к посту.

⏳ Жду текст..."""
        
        await message.answer(text, parse_mode="HTML", reply_markup=get_cancel_inline_keyboard())


@router.message(ContentStates.waiting_for_content)
async def process_wrong_content(message: Message) -> None:
    """Обработка неправильного типа контента."""
    text = """❌ <b>Нужно отправить фото!</b>

Отправь изображение (можно с подписью).

⏳ Жду фото..."""
    
    await message.answer(text, parse_mode="HTML")


@router.message(ContentStates.waiting_for_caption, F.text)
async def process_caption(message: Message, state: FSMContext) -> None:
    """Обработка текста подписи."""
    if message.text == "❌ Отмена":
        await state.clear()
        text = "✅ Действие отменено."
        await message.answer(text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())
        return
    
    user_id = message.from_user.id
    data = await state.get_data()
    photo_file_id = data.get("photo_file_id")
    adding_to_list = data.get("adding_to_list", False)
    
    if not photo_file_id:
        await state.clear()
        text = "❌ Произошла ошибка. Нажми «➕ Добавить» заново."
        await message.answer(text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())
        return
    
    if adding_to_list:
        # Добавляем в список контентов
        contents = await get_contents(user_id)
        content_id = await add_content(
            user_id, 
            photo_file_id, 
            message.text,
            name=f"Контент #{len(contents) + 1}"
        )
        
        # Переходим к настройке интервала
        await state.update_data(content_id=content_id)
        await state.set_state(ContentStates.waiting_for_interval)
        
        text = """✅ Фото и текст сохранены!

⏱ <b>Укажи интервал между публикациями</b>

Отправь два числа через пробел:
• Первое — минимум минут
• Второе — максимум минут

Пример: <code>2 5</code> — случайный интервал от 2 до 5 минут"""
        
        await message.answer(text, parse_mode="HTML", reply_markup=get_cancel_inline_keyboard())
    else:
        await update_user(
            user_id,
            photo_file_id=photo_file_id,
            caption=message.text
        )
        await state.clear()
        
        text = """✅ <b>Контент сохранён!</b>

📸 Фото: загружено
📝 Текст: сохранён"""
        
        await message.answer(text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())


@router.message(ContentStates.waiting_for_caption)
async def process_wrong_caption(message: Message) -> None:
    """Обработка неправильного типа подписи."""
    text = """❌ <b>Нужно отправить текст!</b>

Отправь текстовое сообщение для подписи к посту.

⏳ Жду текст..."""
    
    await message.answer(text, parse_mode="HTML")


@router.message(ContentStates.waiting_for_interval, F.text)
async def process_content_interval(message: Message, state: FSMContext) -> None:
    """Обработка ввода интервала для контента."""
    args = message.text.split()
    
    if len(args) != 2:
        text = """❌ <b>Нужно ввести два числа через пробел!</b>

Пример: <code>2 5</code>

⏳ Попробуй ещё раз..."""
        await message.answer(text, parse_mode="HTML")
        return
    
    try:
        min_val = int(args[0])
        max_val = int(args[1])
    except ValueError:
        text = """❌ <b>Нужно ввести числа!</b>

Пример: <code>2 5</code>

⏳ Попробуй ещё раз..."""
        await message.answer(text, parse_mode="HTML")
        return
    
    if min_val < 1:
        text = """❌ <b>Минимальный интервал — 1 минута!</b>

⏳ Попробуй ещё раз..."""
        await message.answer(text, parse_mode="HTML")
        return
    
    if max_val < min_val:
        text = """❌ <b>Максимум не может быть меньше минимума!</b>

⏳ Попробуй ещё раз..."""
        await message.answer(text, parse_mode="HTML")
        return
    
    data = await state.get_data()
    content_id = data.get("content_id")
    
    if content_id:
        await update_content(content_id, interval_min=min_val, interval_max=max_val)
    
    await state.update_data(interval_min=min_val, interval_max=max_val)
    await state.set_state(ContentStates.waiting_for_time)
    
    text = f"""✅ Интервал установлен: {min_val}-{max_val} минут

🕐 <b>Укажи время работы</b>

Формат: <code>ЧЧ:ММ ЧЧ:ММ</code> (начало и конец через пробел)

Пример: <code>12:30 17:00</code>
(публикация с 12:30 до 17:00)"""
    
    await message.answer(text, parse_mode="HTML", reply_markup=get_cancel_inline_keyboard())


@router.message(ContentStates.waiting_for_time, F.text)
async def process_time(message: Message, state: FSMContext) -> None:
    """Обработка времени начала и окончания."""
    parts = message.text.strip().split()
    
    if len(parts) != 2:
        text = """❌ <b>Нужно ввести два времени через пробел!</b>

Формат: <code>ЧЧ:ММ ЧЧ:ММ</code>
Пример: <code>12:30 17:00</code>

⏳ Попробуй ещё раз..."""
        await message.answer(text, parse_mode="HTML")
        return
    
    time_start = parts[0]
    time_end = parts[1]
    
    if not validate_time_format(time_start) or not validate_time_format(time_end):
        text = """❌ <b>Неверный формат времени!</b>

Формат: <code>ЧЧ:ММ ЧЧ:ММ</code>
Пример: <code>12:30 17:00</code>

⏳ Попробуй ещё раз..."""
        await message.answer(text, parse_mode="HTML")
        return
    
    data = await state.get_data()
    content_id = data.get("content_id")
    interval_min = data.get("interval_min", 2)
    interval_max = data.get("interval_max", 5)
    
    if content_id:
        await update_content(content_id, time_start=time_start, time_end=time_end)
        content = await get_content_by_id(content_id)
        caption_preview = content["caption"][:50] + "..." if len(content["caption"]) > 50 else content["caption"]
    else:
        caption_preview = "—"
    
    await state.clear()
    
    text = f"""✅ <b>Настройка завершена!</b>

📋 <b>Сводка:</b>
📝 Текст: <i>{caption_preview}</i>
⏱ Интервал: {interval_min}-{interval_max} мин
🕐 Время: {time_start} — {time_end}

Выбери действие:"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💾 Сохранить", callback_data=f"content_save_{content_id}"),
            InlineKeyboardButton(text="▶️ Запустить", callback_data=f"content_run_{content_id}")
        ],
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data="content_cancel_add")
        ]
    ])
    
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    await state.clear()


@router.callback_query(F.data.startswith("content_save_"))
async def callback_content_save(callback: CallbackQuery) -> None:
    """Сохранение контента без запуска."""
    content_id = int(callback.data.split("_")[-1])
    
    # Просто сохраняем (is_active = 1, is_running = 0)
    await update_content(content_id, is_active=1, is_running=0)
    
    text = """💾 <b>Контент сохранён!</b>

Контент добавлен в список «📋 Мои контенты».
Ты можешь запустить его позже."""
    
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer("✅ Сохранено!")


@router.callback_query(F.data.startswith("content_run_"))
async def callback_content_run(callback: CallbackQuery) -> None:
    """Запуск контента на публикацию."""
    content_id = int(callback.data.split("_")[-1])
    content = await get_content_by_id(content_id)
    
    if not content:
        await callback.answer("❌ Контент не найден!", show_alert=True)
        return
    
    # Проверяем, указана ли группа
    from database.db import get_user
    user = await get_user(content["user_id"])
    
    if not user or not user.get("target_group"):
        text = """❌ <b>Не указана группа!</b>

Сначала укажи группу через «🎯 Указать группу», затем запусти контент."""
        await callback.message.edit_text(text, parse_mode="HTML")
        await callback.answer("❌ Укажи группу!", show_alert=True)
        return
    
    # Запускаем контент
    await set_content_running(content_id, True)
    
    # Запускаем планировщик для этого контента
    from services.scheduler import start_content_posting_job
    await start_content_posting_job(content_id, callback.bot)
    
    text = f"""▶️ <b>Контент запущен!</b>

🟢 Публикация начата.
⏱ Интервал: {content.get('interval_min', 2)}-{content.get('interval_max', 5)} мин
🕐 Время: {content.get('time_start', '09:00')} — {content.get('time_end', '22:00')}

Управляй через «📋 Мои контенты»."""
    
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer("✅ Запущено!")
