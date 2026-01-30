"""
Главный файл запуска Telegram-бота для автопостинга.
Webhook версия для деплоя на Render.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from config import BOT_TOKEN, WEBHOOK_URL, WEBHOOK_PATH, WEBAPP_HOST, WEBAPP_PORT
from database.db import init_db
from services.scheduler import init_scheduler, start_posting_job, get_scheduler, restore_running_contents
from handlers import commands, content, settings, posting, content_manager

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot) -> None:
    """
    Действия при запуске бота.
    
    Args:
        bot: Экземпляр бота
    """
    # Инициализируем базу данных
    await init_db()
    logger.info("База данных инициализирована")
    
    # Инициализируем планировщик
    init_scheduler()
    logger.info("Планировщик инициализирован")
    
    # Восстанавливаем запущенные задачи автопостинга (старый формат)
    from database.db import get_running_users
    running_users = await get_running_users()
    
    for user in running_users:
        user_id = user["user_id"]
        await start_posting_job(user_id, bot)
        logger.info(f"Восстановлен автопостинг для пользователя {user_id}")
    
    # Восстанавливаем запущенные контенты (новый формат)
    await restore_running_contents(bot)
    
    # Устанавливаем webhook
    webhook_url = f"{WEBHOOK_URL}{WEBHOOK_PATH}"
    await bot.set_webhook(webhook_url)
    logger.info(f"Webhook установлен: {webhook_url}")
    
    logger.info("Бот запущен и готов к работе!")


async def on_shutdown(bot: Bot) -> None:
    """
    Действия при остановке бота.
    
    Args:
        bot: Экземпляр бота
    """
    # Удаляем webhook
    await bot.delete_webhook()
    
    # Останавливаем планировщик
    scheduler = get_scheduler()
    if scheduler:
        scheduler.shutdown(wait=False)
    
    logger.info("Бот остановлен")


async def health_handler(request: web.Request) -> web.Response:
    """
    Health check endpoint для UptimeRobot и Render.
    """
    return web.Response(text="OK", status=200)


async def root_handler(request: web.Request) -> web.Response:
    """
    Корневой endpoint.
    """
    return web.Response(text="Telegram Bot is running!", status=200)


def main() -> None:
    """Главная функция запуска бота."""
    
    # Создаём бота
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Создаём диспетчер
    dp = Dispatcher(storage=MemoryStorage())
    
    # Регистрируем роутеры
    dp.include_router(commands.router)
    dp.include_router(content_manager.router)
    dp.include_router(content.router)
    dp.include_router(settings.router)
    dp.include_router(posting.router)
    
    # Регистрируем события
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    # Создаём aiohttp приложение
    app = web.Application()
    
    # Добавляем health check endpoints
    app.router.add_get("/", root_handler)
    app.router.add_get("/health", health_handler)
    app.router.add_get("/ping", health_handler)
    
    # Настраиваем webhook handler
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot
    )
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    
    # Настраиваем startup/shutdown для aiogram
    setup_application(app, dp, bot=bot)
    
    # Запускаем сервер
    logger.info(f"Запуск сервера на {WEBAPP_HOST}:{WEBAPP_PORT}")
    web.run_app(app, host=WEBAPP_HOST, port=WEBAPP_PORT)


if __name__ == "__main__":
    main()
