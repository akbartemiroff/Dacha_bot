"""
Сервис отправки постов в группу.
"""

import logging
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest, TelegramRetryAfter

from database.db import (
    get_user, update_last_post_time, set_running_status,
    get_next_content_for_posting, get_active_contents, increment_content_post_count,
    get_content_by_id
)

logger = logging.getLogger(__name__)


async def send_post(user_id: int, bot: Bot) -> tuple[bool, str]:
    """
    Отправляет пост в целевую группу.
    Использует ротацию контентов из списка.
    
    Args:
        user_id: ID пользователя
        bot: Экземпляр бота
        
    Returns:
        Кортеж (успех, сообщение об ошибке или пустая строка)
    """
    user = await get_user(user_id)
    
    if not user:
        logger.error(f"Пользователь {user_id} не найден")
        return False, "Пользователь не найден"
    
    target_group = user.get("target_group")
    
    if not target_group:
        logger.error(f"Не указана группа: user_id={user_id}")
        return False, "Не указана целевая группа"
    
    # Пробуем получить контент из списка контентов
    content = await get_next_content_for_posting(user_id)
    
    if content:
        # Используем контент из списка
        photo_file_id = content["photo_file_id"]
        caption = content["caption"]
        content_id = content["id"]
        content_name = content.get("name") or f"#{content_id}"
    else:
        # Fallback на старый формат (контент в профиле пользователя)
        photo_file_id = user.get("photo_file_id")
        caption = user.get("caption")
        content_id = None
        content_name = "основной"
        
        if not all([photo_file_id, caption]):
            logger.error(f"Нет активных контентов: user_id={user_id}")
            return False, "Нет активных контентов для публикации"
    
    try:
        await bot.send_photo(
            chat_id=target_group,
            photo=photo_file_id,
            caption=caption
        )
        
        # Обновляем время последней публикации
        await update_last_post_time(user_id)
        
        # Увеличиваем счётчик публикаций контента
        if content_id:
            await increment_content_post_count(content_id)
        
        logger.info(f"Пост отправлен: user_id={user_id}, content={content_name}, group={target_group}")
        return True, ""
        
    except TelegramForbiddenError:
        error_msg = "Бот не имеет доступа к группе. Проверьте, добавлен ли бот в группу."
        logger.error(f"Ошибка доступа: user_id={user_id}, group={target_group}")
        return False, error_msg
        
    except TelegramBadRequest as e:
        error_msg = f"Ошибка запроса: {str(e)}"
        logger.error(f"Ошибка запроса: user_id={user_id}, error={str(e)}")
        return False, error_msg
        
    except TelegramRetryAfter as e:
        # Flood wait - нужно подождать
        error_msg = f"Flood wait: нужно подождать {e.retry_after} секунд"
        logger.warning(f"Flood wait: user_id={user_id}, wait={e.retry_after}s")
        return False, error_msg
        
    except Exception as e:
        error_msg = f"Неизвестная ошибка: {str(e)}"
        logger.error(f"Неизвестная ошибка: user_id={user_id}, error={str(e)}")
        return False, error_msg


async def notify_user_error(user_id: int, bot: Bot, error_msg: str) -> None:
    """
    Уведомляет пользователя об ошибке.
    
    Args:
        user_id: ID пользователя
        bot: Экземпляр бота
        error_msg: Сообщение об ошибке
    """
    try:
        text = f"""❌ <b>Ошибка автопостинга!</b>

{error_msg}

🛑 Автопостинг остановлен. Исправьте проблему и запустите снова."""
        
        await bot.send_message(user_id, text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Не удалось уведомить пользователя {user_id}: {str(e)}")


async def send_content_post(content_id: int, bot: Bot) -> tuple[bool, str]:
    """
    Отправляет пост конкретного контента в группу.
    
    Args:
        content_id: ID контента
        bot: Экземпляр бота
        
    Returns:
        Кортеж (успех, сообщение об ошибке или пустая строка)
    """
    content = await get_content_by_id(content_id)
    
    if not content:
        logger.error(f"Контент {content_id} не найден")
        return False, "Контент не найден"
    
    user_id = content["user_id"]
    user = await get_user(user_id)
    
    if not user:
        logger.error(f"Пользователь {user_id} не найден")
        return False, "Пользователь не найден"
    
    target_group = user.get("target_group")
    
    if not target_group:
        logger.error(f"Не указана группа для пользователя {user_id}")
        return False, "Не указана целевая группа"
    
    photo_file_id = content["photo_file_id"]
    caption = content["caption"]
    
    try:
        await bot.send_photo(
            chat_id=target_group,
            photo=photo_file_id,
            caption=caption
        )
        
        logger.info(f"Пост контента {content_id} отправлен в {target_group}")
        return True, ""
        
    except TelegramForbiddenError:
        error_msg = "Бот не имеет доступа к группе. Проверьте, добавлен ли бот в группу."
        logger.error(f"Ошибка доступа: content_id={content_id}, group={target_group}")
        return False, error_msg
        
    except TelegramBadRequest as e:
        error_msg = f"Ошибка запроса: {str(e)}"
        logger.error(f"Ошибка запроса: content_id={content_id}, error={str(e)}")
        return False, error_msg
        
    except TelegramRetryAfter as e:
        error_msg = f"Flood wait: нужно подождать {e.retry_after} секунд"
        logger.warning(f"Flood wait: content_id={content_id}, wait={e.retry_after}s")
        return False, error_msg
        
    except Exception as e:
        error_msg = f"Неизвестная ошибка: {str(e)}"
        logger.error(f"Неизвестная ошибка: content_id={content_id}, error={str(e)}")
        return False, error_msg

