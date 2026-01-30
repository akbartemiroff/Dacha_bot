"""
Обработчики управления контентами.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from database.db import (
    get_contents, get_content_by_id, toggle_content_status, 
    delete_content, add_content, get_or_create_user, set_content_running,
    update_content
)
from utils.filters import AllowedUserFilter
from utils.keyboards import get_main_menu_keyboard
from utils.states import ContentStates, EditContentStates
from services.scheduler import start_content_posting_job, stop_content_posting_job

router = Router()
router.message.filter(AllowedUserFilter())




def get_content_actions_keyboard(content_id: int, is_running: bool) -> InlineKeyboardMarkup:
    """Клавиатура действий с контентом."""
    if is_running:
        run_btn = InlineKeyboardButton(text="⏹ Остановить", callback_data=f"content_stop_{content_id}")
    else:
        run_btn = InlineKeyboardButton(text="▶️ Запустить", callback_data=f"content_start_{content_id}")
    
    buttons = [
        [
            run_btn,
            InlineKeyboardButton(text="👁 Предпросмотр", callback_data=f"content_preview_{content_id}"),
        ],
        [
            InlineKeyboardButton(text="✏️ Изменить", callback_data=f"content_edit_{content_id}"),
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"content_delete_{content_id}"),
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def format_content_card(content: dict) -> str:
    """Форматирование карточки контента."""
    name = content.get("name") or f"Контент #{content['id']}"
    
    if content.get("is_running"):
        status = "▶️ Публикуется"
    elif content.get("is_active"):
        status = "💾 Сохранён"
    else:
        status = "🔴 Неактивен"
    
    caption = content["caption"]
    interval_min = content.get("interval_min", 2)
    interval_max = content.get("interval_max", 5)
    time_start = content.get("time_start", "09:00")
    time_end = content.get("time_end", "22:00")
    post_count = content.get("post_count", 0)
    
    return f"""📄 <b>{name}</b>
📊 Статус: {status}
📝 Текст: <i>{caption[:80]}{'...' if len(caption) > 80 else ''}</i>
⏱ Интервал: {interval_min}-{interval_max} мин
🕐 Время: {time_start} — {time_end}
📈 Опубликовано: {post_count} раз"""


@router.message(F.text == "📋 Мои контенты")
@router.message(Command("contents"))
async def cmd_contents(message: Message, state: FSMContext) -> None:
    """Показать список контентов."""
    await state.clear()
    user_id = message.from_user.id
    await get_or_create_user(user_id)
    
    contents = await get_contents(user_id)
    
    if not contents:
        text = """📋 <b>Мои контенты</b>

У тебя пока нет сохранённых контентов.

Нажми «➕ Добавить» чтобы создать первый контент."""
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить контент", callback_data="content_add")]
        ])
        await message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    else:
        # Отправляем каждый контент отдельным сообщением с кнопками
        await message.answer(f"📋 <b>Мои контенты</b> ({len(contents)} шт.)", parse_mode="HTML")
        
        for content in contents:
            text = format_content_card(content)
            keyboard = get_content_actions_keyboard(content["id"], content.get("is_running", False))
            await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data == "content_list")
async def callback_content_list(callback: CallbackQuery, state: FSMContext) -> None:
    """Вернуться к списку контентов."""
    await state.clear()
    user_id = callback.from_user.id
    contents = await get_contents(user_id)
    
    # Удаляем текущее сообщение
    try:
        await callback.message.delete()
    except Exception:
        pass
    
    if not contents:
        text = """📋 <b>Мои контенты</b>

У тебя пока нет сохранённых контентов.

Нажми «➕ Добавить» чтобы создать первый контент."""
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить контент", callback_data="content_add")]
        ])
        await callback.message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await callback.message.answer(f"📋 <b>Мои контенты</b> ({len(contents)} шт.)", parse_mode="HTML")
        
        for content in contents:
            text = format_content_card(content)
            keyboard = get_content_actions_keyboard(content["id"], content.get("is_running", False))
            await callback.message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    
    await callback.answer()


@router.callback_query(F.data.startswith("content_view_"))
async def callback_content_view(callback: CallbackQuery) -> None:
    """Просмотр контента."""
    content_id = int(callback.data.split("_")[-1])
    content = await get_content_by_id(content_id)
    
    if not content:
        await callback.answer("❌ Контент не найден!", show_alert=True)
        return
    
    text = format_content_card(content)
    keyboard = get_content_actions_keyboard(content_id, content.get("is_running", False))
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("content_start_"))
async def callback_content_start(callback: CallbackQuery) -> None:
    """Запуск публикации контента."""
    content_id = int(callback.data.split("_")[-1])
    content = await get_content_by_id(content_id)
    
    if not content:
        await callback.answer("❌ Контент не найден!", show_alert=True)
        return
    
    # Проверяем группу
    from database.db import get_user
    user = await get_user(content["user_id"])
    
    if not user or not user.get("target_group"):
        await callback.answer("❌ Сначала укажи группу!", show_alert=True)
        return
    
    # Запускаем
    await set_content_running(content_id, True)
    await start_content_posting_job(content_id, callback.bot)
    
    await callback.answer("▶️ Запущено!", show_alert=False)
    
    # Обновляем отображение
    content = await get_content_by_id(content_id)
    await update_content_view(callback, content)


@router.callback_query(F.data.startswith("content_stop_"))
async def callback_content_stop(callback: CallbackQuery) -> None:
    """Остановка публикации контента."""
    content_id = int(callback.data.split("_")[-1])
    
    await set_content_running(content_id, False)
    stop_content_posting_job(content_id)
    
    await callback.answer("⏹ Остановлено!", show_alert=False)
    
    # Обновляем отображение
    content = await get_content_by_id(content_id)
    await update_content_view(callback, content)


async def update_content_view(callback: CallbackQuery, content: dict) -> None:
    """Обновление вида контента."""
    if not content:
        return
    
    text = format_content_card(content)
    keyboard = get_content_actions_keyboard(content["id"], content.get("is_running", False))
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data.startswith("content_preview_"))
async def callback_content_preview(callback: CallbackQuery) -> None:
    """Предпросмотр контента."""
    content_id = int(callback.data.split("_")[-1])
    content = await get_content_by_id(content_id)
    
    if not content:
        await callback.answer("❌ Контент не найден!", show_alert=True)
        return
    
    await callback.answer()
    await callback.message.answer_photo(
        photo=content["photo_file_id"],
        caption=content["caption"]
    )


@router.callback_query(F.data.startswith("content_edit_"))
async def callback_content_edit(callback: CallbackQuery) -> None:
    """Меню редактирования контента."""
    content_id = int(callback.data.split("_")[-1])
    content = await get_content_by_id(content_id)
    
    if not content:
        await callback.answer("❌ Контент не найден!", show_alert=True)
        return
    
    text = """✏️ <b>Что изменить?</b>

Выбери параметр для редактирования:"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📸 Фото", callback_data=f"edit_photo_{content_id}"),
            InlineKeyboardButton(text="📝 Текст", callback_data=f"edit_caption_{content_id}"),
        ],
        [
            InlineKeyboardButton(text="⏱ Интервал", callback_data=f"edit_interval_{content_id}"),
            InlineKeyboardButton(text="🕐 Время", callback_data=f"edit_time_{content_id}"),
        ],
        [
            InlineKeyboardButton(text="« Назад", callback_data=f"content_view_{content_id}"),
        ]
    ])
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("content_delete_"))
async def callback_content_delete(callback: CallbackQuery) -> None:
    """Подтверждение удаления контента."""
    content_id = int(callback.data.split("_")[-1])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"content_confirm_delete_{content_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data=f"content_view_{content_id}")
        ]
    ])
    
    await callback.message.edit_text(
        "🗑 <b>Удалить контент?</b>\n\nЭто действие нельзя отменить!",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data.startswith("content_confirm_delete_"))
async def callback_content_confirm_delete(callback: CallbackQuery) -> None:
    """Удаление контента."""
    content_id = int(callback.data.split("_")[-1])
    deleted = await delete_content(content_id)
    
    if deleted:
        await callback.answer("✅ Контент удалён!", show_alert=False)
    else:
        await callback.answer("❌ Ошибка удаления!", show_alert=True)
    
    # Возвращаемся к списку
    user_id = callback.from_user.id
    contents = await get_contents(user_id)
    
    # Удаляем сообщение и показываем список заново
    try:
        await callback.message.delete()
    except Exception:
        pass
    
    if not contents:
        text = """📋 <b>Мои контенты</b>

У тебя пока нет сохранённых контентов.

Нажми «➕ Добавить» чтобы создать первый контент."""
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить контент", callback_data="content_add")]
        ])
        await callback.message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await callback.message.answer(f"📋 <b>Мои контенты</b> ({len(contents)} шт.)", parse_mode="HTML")
        
        for content in contents:
            text = format_content_card(content)
            keyboard = get_content_actions_keyboard(content["id"], content.get("is_running", False))
            await callback.message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data == "content_add")
async def callback_content_add(callback: CallbackQuery, state: FSMContext) -> None:
    """Начало добавления контента (из inline-кнопки)."""
    await state.set_state(ContentStates.waiting_for_content)
    await state.update_data(adding_to_list=True)
    
    text = """📸 <b>Добавление нового контента</b>

Отправь фото для публикации.

Ты можешь:
• Отправить фото с подписью
• Или сначала фото, потом текст отдельно

⏳ Жду фото..."""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="content_list")]
    ])
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


@router.message(F.text == "➕ Добавить")
async def cmd_add_content(message: Message, state: FSMContext) -> None:
    """Начало добавления контента (из меню)."""
    await state.set_state(ContentStates.waiting_for_content)
    await state.update_data(adding_to_list=True)
    
    text = """📸 <b>Добавление нового контента</b>

Отправь фото для публикации.

Ты можешь:
• Отправить фото с подписью
• Или сначала фото, потом текст отдельно

⏳ Жду фото..."""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="content_list")]
    ])
    
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


# ============== Обработчики редактирования ==============

import re

def validate_time_format(time_str: str) -> bool:
    """Проверка формата времени ЧЧ:ММ."""
    pattern = r'^([0-1]?[0-9]|2[0-3]):([0-5][0-9])$'
    return bool(re.match(pattern, time_str))


@router.callback_query(F.data.startswith("edit_photo_"))
async def callback_edit_photo(callback: CallbackQuery, state: FSMContext) -> None:
    """Редактирование фото."""
    content_id = int(callback.data.split("_")[-1])
    
    await state.set_state(EditContentStates.waiting_for_photo)
    await state.update_data(edit_content_id=content_id)
    
    text = """📸 <b>Отправь новое фото</b>

⏳ Жду фото..."""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"content_view_{content_id}")]
    ])
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


@router.message(EditContentStates.waiting_for_photo, F.photo)
async def process_edit_photo(message: Message, state: FSMContext) -> None:
    """Обработка нового фото."""
    data = await state.get_data()
    content_id = data.get("edit_content_id")
    
    if not content_id:
        await state.clear()
        await message.answer("❌ Ошибка. Попробуй заново.", reply_markup=get_main_menu_keyboard())
        return
    
    photo_file_id = message.photo[-1].file_id
    await update_content(content_id, photo_file_id=photo_file_id)
    await state.clear()
    
    await message.answer("✅ Фото обновлено!", reply_markup=get_main_menu_keyboard())


@router.callback_query(F.data.startswith("edit_caption_"))
async def callback_edit_caption(callback: CallbackQuery, state: FSMContext) -> None:
    """Редактирование текста."""
    content_id = int(callback.data.split("_")[-1])
    
    await state.set_state(EditContentStates.waiting_for_caption)
    await state.update_data(edit_content_id=content_id)
    
    text = """📝 <b>Отправь новый текст</b>

⏳ Жду текст..."""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"content_view_{content_id}")]
    ])
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


@router.message(EditContentStates.waiting_for_caption, F.text)
async def process_edit_caption(message: Message, state: FSMContext) -> None:
    """Обработка нового текста."""
    data = await state.get_data()
    content_id = data.get("edit_content_id")
    
    if not content_id:
        await state.clear()
        await message.answer("❌ Ошибка. Попробуй заново.", reply_markup=get_main_menu_keyboard())
        return
    
    await update_content(content_id, caption=message.text)
    await state.clear()
    
    await message.answer("✅ Текст обновлён!", reply_markup=get_main_menu_keyboard())


@router.callback_query(F.data.startswith("edit_interval_"))
async def callback_edit_interval(callback: CallbackQuery, state: FSMContext) -> None:
    """Редактирование интервала."""
    content_id = int(callback.data.split("_")[-1])
    
    await state.set_state(EditContentStates.waiting_for_interval)
    await state.update_data(edit_content_id=content_id)
    
    text = """⏱ <b>Укажи новый интервал</b>

Формат: <code>мин макс</code>

Пример: <code>2 5</code> — от 2 до 5 минут"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"content_view_{content_id}")]
    ])
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


@router.message(EditContentStates.waiting_for_interval, F.text)
async def process_edit_interval(message: Message, state: FSMContext) -> None:
    """Обработка нового интервала."""
    data = await state.get_data()
    content_id = data.get("edit_content_id")
    
    if not content_id:
        await state.clear()
        await message.answer("❌ Ошибка. Попробуй заново.", reply_markup=get_main_menu_keyboard())
        return
    
    args = message.text.split()
    
    if len(args) != 2:
        await message.answer("❌ Нужно два числа через пробел. Пример: <code>2 5</code>", parse_mode="HTML")
        return
    
    try:
        min_val = int(args[0])
        max_val = int(args[1])
    except ValueError:
        await message.answer("❌ Нужно ввести числа!", parse_mode="HTML")
        return
    
    if min_val < 1 or max_val < min_val:
        await message.answer("❌ Минимум от 1, максимум >= минимума!", parse_mode="HTML")
        return
    
    await update_content(content_id, interval_min=min_val, interval_max=max_val)
    await state.clear()
    
    await message.answer(f"✅ Интервал обновлён: {min_val}-{max_val} мин", reply_markup=get_main_menu_keyboard())


@router.callback_query(F.data.startswith("edit_time_"))
async def callback_edit_time(callback: CallbackQuery, state: FSMContext) -> None:
    """Редактирование времени."""
    content_id = int(callback.data.split("_")[-1])
    
    await state.set_state(EditContentStates.waiting_for_time)
    await state.update_data(edit_content_id=content_id)
    
    text = """🕐 <b>Укажи новое время работы</b>

Формат: <code>ЧЧ:ММ ЧЧ:ММ</code>

Пример: <code>12:30 17:00</code>
(начало 12:30, окончание 17:00)"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"content_view_{content_id}")]
    ])
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


@router.message(EditContentStates.waiting_for_time, F.text)
async def process_edit_time(message: Message, state: FSMContext) -> None:
    """Обработка нового времени."""
    data = await state.get_data()
    content_id = data.get("edit_content_id")
    
    if not content_id:
        await state.clear()
        await message.answer("❌ Ошибка. Попробуй заново.", reply_markup=get_main_menu_keyboard())
        return
    
    parts = message.text.strip().split()
    
    if len(parts) != 2:
        await message.answer("❌ Нужно два времени через пробел. Пример: <code>12:30 17:00</code>", parse_mode="HTML")
        return
    
    time_start = parts[0]
    time_end = parts[1]
    
    if not validate_time_format(time_start) or not validate_time_format(time_end):
        await message.answer("❌ Неверный формат. Пример: <code>12:30 17:00</code>", parse_mode="HTML")
        return
    
    await update_content(content_id, time_start=time_start, time_end=time_end)
    await state.clear()
    
    await message.answer(f"✅ Время обновлено: {time_start} — {time_end}", reply_markup=get_main_menu_keyboard())
