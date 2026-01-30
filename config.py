"""
Модуль конфигурации бота.
Загружает переменные окружения и настройки.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Токен бота
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

# Список разрешённых пользователей (пустой = доступен всем)
ALLOWED_USERS_STR: str = os.getenv("ALLOWED_USERS", "")
ALLOWED_USERS: list[int] = [
    int(uid.strip()) 
    for uid in ALLOWED_USERS_STR.split(",") 
    if uid.strip().isdigit()
]

# Часовой пояс
TIMEZONE: str = os.getenv("TIMEZONE", "Asia/Tashkent")

# Webhook настройки для Render
WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "")  # https://your-app.onrender.com
WEBHOOK_PATH: str = os.getenv("WEBHOOK_PATH", "/webhook")

# Настройки веб-сервера
WEBAPP_HOST: str = os.getenv("WEBAPP_HOST", "0.0.0.0")
WEBAPP_PORT: int = int(os.getenv("PORT", "10000"))  # Render устанавливает PORT автоматически

# Проверка обязательных переменных
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не установлен в переменных окружения!")

if not WEBHOOK_URL:
    raise ValueError("WEBHOOK_URL не установлен в переменных окружения!")
