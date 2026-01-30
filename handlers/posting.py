"""
Обработчики управления автопостингом.
"""

from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from database.db import get_or_create_user, set_running_status, get_active_contents, get_contents
from utils.filters import AllowedUserFilter
from utils.keyboards import get_main_menu_keyboard
from services.scheduler import start_posting_job, stop_posting_job, get_next_run_time, get_content_next_run_time
from config import TIMEZONE

import pytz

router = Router()
router.message.filter(AllowedUserFilter())


@router.message(F.text == "▶️ Запустить")
@router.message(Command("startpost"))
async def cmd_startpost(message: Message, state: FSMContext) -> None:
    """Обработчик команды /startpost."""
    await state.clear()
    user_id = message.from_user.id
    user = await get_or_create_user(user_id)
    
    # Проверяем, не запущен ли уже
    if user.get("is_running"):
        text = "⚠️ Автопостинг уже запущен! Нажми «⏹ Остановить» для остановки."
        await message.answer(text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())
        return
    
    # Проверяем наличие всех необходимых данных
    errors = []
    
    # Проверяем контенты (новый формат) или старый формат
    active_contents = await get_active_contents(user_id)
    has_old_content = user.get("photo_file_id") and user.get("caption")
    
    if not active_contents and not has_old_content:
        errors.append("📸 Нет активных контентов")
    
    if not user.get("target_group"):
        errors.append("🎯 Не указана группа")
    
    if errors:
        error_list = "\n".join(errors)
        text = f"""❌ <b>Невозможно запустить автопостинг!</b>

Не настроено:
{error_list}

Добавь контент через «📋 Мои контенты» и укажи группу."""
        await message.answer(text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())
        return
    
    # Запускаем автопостинг
    await set_running_status(user_id, True)
    
    # Получаем объект бота
    bot = message.bot
    
    # Запускаем планировщик
    await start_posting_job(user_id, bot)
    
    text = """✅ <b>Автопостинг запущен!</b>

🟢 Бот начал публикацию контента в указанную группу.

Используй кнопки:
• «📊 Статус» — проверить состояние
• «⏹ Остановить» — остановить публикацию"""
    
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())


@router.message(F.text == "⏹ Остановить")
@router.message(Command("stoppost"))
async def cmd_stoppost(message: Message, state: FSMContext) -> None:
    """Обработчик команды /stoppost."""
    await state.clear()
    user_id = message.from_user.id
    user = await get_or_create_user(user_id)
    
    if not user.get("is_running"):
        text = "⚠️ Автопостинг не запущен."
        await message.answer(text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())
        return
    
    # Останавливаем автопостинг
    await set_running_status(user_id, False)
    stop_posting_job(user_id)
    
    text = """🛑 <b>Автопостинг остановлен!</b>

🔴 Публикация контента прекращена.

Нажми «▶️ Запустить» чтобы возобновить."""
    
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())


@router.message(F.text == "📊 Статус")
@router.message(Command("status"))
async def cmd_status(message: Message, state: FSMContext) -> None:
    """Обработчик команды /status."""
    await state.clear()
    user_id = message.from_user.id
    user = await get_or_create_user(user_id)
    
    # Получаем все контенты
    contents = await get_contents(user_id)
    
    # Подсчёт статусов
    running_count = sum(1 for c in contents if c.get("is_running"))
    saved_count = sum(1 for c in contents if c.get("is_active") and not c.get("is_running"))
    stopped_count = sum(1 for c in contents if not c.get("is_active"))
    
    # Группа
    target_group = user.get("target_group")
    group_str = f"<code>{target_group}</code>" if target_group else "❌ Не указана"
    
    # Формируем заголовок
    text = f"""📊 <b>Статус автопостинга</b>

🎯 Группа: {group_str}
📋 Всего контентов: {len(contents)}

▶️ Запущено: {running_count}
💾 Сохранено: {saved_count}
🔴 Остановлено: {stopped_count}

"""
    
    if not contents:
        text += "📭 Нет контентов. Нажми «➕ Добавить» чтобы создать."
    else:
        text += "<b>Список контентов:</b>\n\n"
        
        for content in contents:
            name = content.get("name") or f"#{content['id']}"
            
            if content.get("is_running"):
                status_icon = "▶️"
                status_text = "публикуется"
                # Получаем время следующего поста
                next_run = get_content_next_run_time(content["id"])
                if next_run:
                    next_str = next_run.strftime("%H:%M:%S")
                    status_text = f"след. пост: {next_str}"
            elif content.get("is_active"):
                status_icon = "💾"
                status_text = "сохранён"
            else:
                status_icon = "🔴"
                status_text = "остановлен"
            
            time_range = f"{content.get('time_start', '09:00')}-{content.get('time_end', '22:00')}"
            
            text += f"{status_icon} <b>{name}</b> — {status_text}\n"
            text += f"    ⏱ {content.get('interval_min', 2)}-{content.get('interval_max', 5)} мин | 🕐 {time_range}\n\n"
    
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())

