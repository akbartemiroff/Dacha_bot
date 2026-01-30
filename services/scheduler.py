"""
Сервис планировщика задач для автопостинга.
"""

import logging
import random
import asyncio
from datetime import datetime, timedelta
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter
import pytz

from database.db import (
    get_user, set_running_status, get_content_by_id, 
    set_content_running, update_content_last_post, increment_content_post_count,
    get_running_contents
)
from services.poster import send_post, notify_user_error, send_content_post
from config import TIMEZONE

logger = logging.getLogger(__name__)

# Глобальный планировщик
scheduler: Optional[AsyncIOScheduler] = None


def init_scheduler() -> AsyncIOScheduler:
    """
    Инициализация планировщика.
    
    Returns:
        Экземпляр планировщика
    """
    global scheduler
    
    tz = pytz.timezone(TIMEZONE)
    scheduler = AsyncIOScheduler(timezone=tz)
    scheduler.start()
    
    logger.info(f"Планировщик запущен с часовым поясом {TIMEZONE}")
    return scheduler


def get_scheduler() -> AsyncIOScheduler:
    """
    Получение экземпляра планировщика.
    
    Returns:
        Экземпляр планировщика
    """
    global scheduler
    if scheduler is None:
        scheduler = init_scheduler()
    return scheduler


async def posting_task(user_id: int, bot: Bot) -> None:
    """
    Задача публикации поста.
    
    Args:
        user_id: ID пользователя
        bot: Экземпляр бота
    """
    user = await get_user(user_id)
    
    if not user or not user.get("is_running"):
        logger.info(f"Автопостинг остановлен для пользователя {user_id}")
        return
    
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    
    hours_start = user.get("hours_start", 9)
    hours_end = user.get("hours_end", 22)
    
    # Проверяем, находимся ли в активных часах
    if not (hours_start <= now.hour < hours_end):
        # Вычисляем время до начала активных часов
        if now.hour >= hours_end:
            # Ждём до следующего дня
            next_start = now.replace(hour=hours_start, minute=0, second=0, microsecond=0) + timedelta(days=1)
        else:
            # Ждём до начала сегодня
            next_start = now.replace(hour=hours_start, minute=0, second=0, microsecond=0)
        
        logger.info(f"Вне активных часов для {user_id}. Следующий запуск: {next_start}")
        
        # Планируем следующую проверку на начало активных часов
        schedule_next_post(user_id, bot, next_start)
        return
    
    # Отправляем пост
    success, error_msg = await send_post(user_id, bot)
    
    if not success:
        if "Flood wait" in error_msg:
            # Извлекаем время ожидания и планируем повтор
            try:
                wait_time = int(error_msg.split()[-2])
                next_time = now + timedelta(seconds=wait_time + 5)
                schedule_next_post(user_id, bot, next_time)
                logger.info(f"Повтор после flood wait через {wait_time}s для {user_id}")
                return
            except Exception:
                pass
        
        # Критическая ошибка — останавливаем постинг и уведомляем пользователя
        await set_running_status(user_id, False)
        await notify_user_error(user_id, bot, error_msg)
        return
    
    # Вычисляем случайный интервал
    interval_min = user.get("interval_min", 2)
    interval_max = user.get("interval_max", 5)
    delay_minutes = random.randint(interval_min, interval_max)
    
    next_time = now + timedelta(minutes=delay_minutes)
    
    # Проверяем, не выходит ли следующий пост за активные часы
    if next_time.hour >= hours_end:
        # Переносим на следующий день
        next_time = next_time.replace(hour=hours_start, minute=0, second=0, microsecond=0) + timedelta(days=1)
    
    schedule_next_post(user_id, bot, next_time)
    logger.info(f"Следующий пост для {user_id} запланирован на {next_time}")


def schedule_next_post(user_id: int, bot: Bot, run_time: datetime) -> None:
    """
    Планирование следующей публикации.
    
    Args:
        user_id: ID пользователя
        bot: Экземпляр бота
        run_time: Время следующего запуска
    """
    sched = get_scheduler()
    job_id = f"posting_{user_id}"
    
    # Удаляем старую задачу если есть
    existing_job = sched.get_job(job_id)
    if existing_job:
        sched.remove_job(job_id)
    
    # Добавляем новую задачу
    sched.add_job(
        posting_task,
        trigger=DateTrigger(run_date=run_time),
        args=[user_id, bot],
        id=job_id,
        replace_existing=True
    )


async def start_posting_job(user_id: int, bot: Bot) -> None:
    """
    Запуск цикла автопостинга для пользователя.
    
    Args:
        user_id: ID пользователя
        bot: Экземпляр бота
    """
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    
    user = await get_user(user_id)
    hours_start = user.get("hours_start", 9)
    hours_end = user.get("hours_end", 22)
    
    # Определяем время первого поста
    if hours_start <= now.hour < hours_end:
        # Мы в активных часах — публикуем через 5 секунд
        first_run = now + timedelta(seconds=5)
    elif now.hour >= hours_end:
        # После окончания активных часов — ждём до завтра
        first_run = now.replace(hour=hours_start, minute=0, second=0, microsecond=0) + timedelta(days=1)
    else:
        # До начала активных часов — ждём начала
        first_run = now.replace(hour=hours_start, minute=0, second=0, microsecond=0)
    
    schedule_next_post(user_id, bot, first_run)
    logger.info(f"Автопостинг запущен для {user_id}, первый пост: {first_run}")


def stop_posting_job(user_id: int) -> None:
    """
    Остановка автопостинга для пользователя.
    
    Args:
        user_id: ID пользователя
    """
    sched = get_scheduler()
    job_id = f"posting_{user_id}"
    
    existing_job = sched.get_job(job_id)
    if existing_job:
        sched.remove_job(job_id)
        logger.info(f"Автопостинг остановлен для {user_id}")


def get_next_run_time(user_id: int) -> Optional[datetime]:
    """
    Получение времени следующего запуска.
    
    Args:
        user_id: ID пользователя
        
    Returns:
        Время следующего запуска или None
    """
    sched = get_scheduler()
    job_id = f"posting_{user_id}"
    
    job = sched.get_job(job_id)
    if job:
        return job.next_run_time
    return None


# ============== Функции для работы с отдельными контентами ==============

def parse_time(time_str: str) -> tuple[int, int]:
    """Парсинг времени из строки ЧЧ:ММ."""
    parts = time_str.split(":")
    return int(parts[0]), int(parts[1])


def is_within_time_range(now: datetime, time_start: str, time_end: str) -> bool:
    """Проверка, находится ли текущее время в диапазоне."""
    start_h, start_m = parse_time(time_start)
    end_h, end_m = parse_time(time_end)
    
    current_minutes = now.hour * 60 + now.minute
    start_minutes = start_h * 60 + start_m
    end_minutes = end_h * 60 + end_m
    
    return start_minutes <= current_minutes < end_minutes


def get_next_start_time(now: datetime, time_start: str) -> datetime:
    """Получение времени следующего старта."""
    start_h, start_m = parse_time(time_start)
    
    next_start = now.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
    
    if next_start <= now:
        next_start += timedelta(days=1)
    
    return next_start


async def content_posting_task(content_id: int, bot: Bot) -> None:
    """
    Задача публикации контента.
    
    Args:
        content_id: ID контента
        bot: Экземпляр бота
    """
    content = await get_content_by_id(content_id)
    
    if not content or not content.get("is_running"):
        logger.info(f"Публикация контента {content_id} остановлена")
        return
    
    user_id = content["user_id"]
    user = await get_user(user_id)
    
    if not user:
        logger.error(f"Пользователь {user_id} не найден для контента {content_id}")
        return
    
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    
    time_start = content.get("time_start", "09:00")
    time_end = content.get("time_end", "22:00")
    
    # Проверяем, находимся ли в активном времени
    if not is_within_time_range(now, time_start, time_end):
        next_start = get_next_start_time(now, time_start)
        logger.info(f"Контент {content_id} вне активного времени. Следующий запуск: {next_start}")
        schedule_content_post(content_id, bot, next_start)
        return
    
    # Отправляем пост
    success, error_msg = await send_content_post(content_id, bot)
    
    if not success:
        if "Flood wait" in error_msg:
            try:
                wait_time = int(error_msg.split()[-2])
                next_time = now + timedelta(seconds=wait_time + 5)
                schedule_content_post(content_id, bot, next_time)
                logger.info(f"Повтор контента {content_id} после flood wait через {wait_time}s")
                return
            except Exception:
                pass
        
        # Критическая ошибка
        await set_content_running(content_id, False)
        await notify_user_error(user_id, bot, error_msg)
        return
    
    # Обновляем статистику
    await increment_content_post_count(content_id)
    await update_content_last_post(content_id)
    
    # Вычисляем следующий интервал
    interval_min = content.get("interval_min", 2)
    interval_max = content.get("interval_max", 5)
    delay_minutes = random.randint(interval_min, interval_max)
    
    next_time = now + timedelta(minutes=delay_minutes)
    
    # Проверяем, не выходит ли за пределы времени
    end_h, end_m = parse_time(time_end)
    end_minutes = end_h * 60 + end_m
    next_minutes = next_time.hour * 60 + next_time.minute
    
    if next_minutes >= end_minutes:
        next_time = get_next_start_time(now, time_start)
    
    schedule_content_post(content_id, bot, next_time)
    logger.info(f"Следующий пост контента {content_id} запланирован на {next_time}")


def schedule_content_post(content_id: int, bot: Bot, run_time: datetime) -> None:
    """
    Планирование следующей публикации контента.
    
    Args:
        content_id: ID контента
        bot: Экземпляр бота
        run_time: Время следующего запуска
    """
    sched = get_scheduler()
    job_id = f"content_{content_id}"
    
    existing_job = sched.get_job(job_id)
    if existing_job:
        sched.remove_job(job_id)
    
    sched.add_job(
        content_posting_task,
        trigger=DateTrigger(run_date=run_time),
        args=[content_id, bot],
        id=job_id,
        replace_existing=True
    )


async def start_content_posting_job(content_id: int, bot: Bot) -> None:
    """
    Запуск публикации контента.
    
    Args:
        content_id: ID контента
        bot: Экземпляр бота
    """
    content = await get_content_by_id(content_id)
    if not content:
        return
    
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    
    time_start = content.get("time_start", "09:00")
    time_end = content.get("time_end", "22:00")
    
    if is_within_time_range(now, time_start, time_end):
        first_run = now + timedelta(seconds=5)
    else:
        first_run = get_next_start_time(now, time_start)
    
    schedule_content_post(content_id, bot, first_run)
    logger.info(f"Публикация контента {content_id} запущена, первый пост: {first_run}")


def stop_content_posting_job(content_id: int) -> None:
    """
    Остановка публикации контента.
    
    Args:
        content_id: ID контента
    """
    sched = get_scheduler()
    job_id = f"content_{content_id}"
    
    existing_job = sched.get_job(job_id)
    if existing_job:
        sched.remove_job(job_id)
        logger.info(f"Публикация контента {content_id} остановлена")


def get_content_next_run_time(content_id: int) -> Optional[datetime]:
    """
    Получение времени следующего запуска контента.
    
    Args:
        content_id: ID контента
        
    Returns:
        Время следующего запуска или None
    """
    sched = get_scheduler()
    job_id = f"content_{content_id}"
    
    job = sched.get_job(job_id)
    if job:
        return job.next_run_time
    return None


async def restore_running_contents(bot: Bot) -> None:
    """
    Восстановление запущенных контентов при старте бота.
    
    Args:
        bot: Экземпляр бота
    """
    running_contents = await get_running_contents()
    
    for content in running_contents:
        content_id = content["id"]
        await start_content_posting_job(content_id, bot)
        logger.info(f"Восстановлена публикация контента {content_id}")

