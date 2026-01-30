"""
Модуль для работы с базой данных SQLite.
Содержит функции создания таблиц и CRUD операции для пользователей.
"""

import aiosqlite
from datetime import datetime
from pathlib import Path
from typing import Optional

DATABASE_PATH = Path(__file__).parent.parent / "data" / "bot.db"


async def init_db() -> None:
    """Инициализация базы данных и создание таблиц."""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                photo_file_id TEXT,
                caption TEXT,
                target_group TEXT,
                interval_min INTEGER DEFAULT 2,
                interval_max INTEGER DEFAULT 5,
                hours_start INTEGER DEFAULT 9,
                hours_end INTEGER DEFAULT 22,
                is_running INTEGER DEFAULT 0,
                last_post_time TEXT,
                current_content_index INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        
        # Таблица контентов
        await db.execute("""
            CREATE TABLE IF NOT EXISTS contents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT,
                photo_file_id TEXT NOT NULL,
                caption TEXT NOT NULL,
                is_active INTEGER DEFAULT 0,
                is_running INTEGER DEFAULT 0,
                interval_min INTEGER DEFAULT 2,
                interval_max INTEGER DEFAULT 5,
                time_start TEXT DEFAULT '09:00',
                time_end TEXT DEFAULT '22:00',
                post_count INTEGER DEFAULT 0,
                last_post_time TEXT,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        await db.commit()


async def get_user(user_id: int) -> Optional[dict]:
    """
    Получение данных пользователя по ID.
    
    Args:
        user_id: Telegram ID пользователя
        
    Returns:
        Словарь с данными пользователя или None
    """
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None


async def create_user(user_id: int) -> None:
    """
    Создание нового пользователя.
    
    Args:
        user_id: Telegram ID пользователя
    """
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT OR IGNORE INTO users (user_id, created_at, updated_at)
            VALUES (?, ?, ?)
            """,
            (user_id, now, now)
        )
        await db.commit()


async def update_user(user_id: int, **kwargs) -> None:
    """
    Обновление данных пользователя.
    
    Args:
        user_id: Telegram ID пользователя
        **kwargs: Поля для обновления
    """
    if not kwargs:
        return
    
    kwargs["updated_at"] = datetime.now().isoformat()
    
    fields = ", ".join(f"{key} = ?" for key in kwargs.keys())
    values = list(kwargs.values())
    values.append(user_id)
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            f"UPDATE users SET {fields} WHERE user_id = ?",
            values
        )
        await db.commit()


async def get_or_create_user(user_id: int) -> dict:
    """
    Получение пользователя или создание нового.
    
    Args:
        user_id: Telegram ID пользователя
        
    Returns:
        Словарь с данными пользователя
    """
    user = await get_user(user_id)
    if not user:
        await create_user(user_id)
        user = await get_user(user_id)
    return user


async def get_running_users() -> list[dict]:
    """
    Получение списка пользователей с активным автопостингом.
    
    Returns:
        Список словарей с данными пользователей
    """
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE is_running = 1"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def set_running_status(user_id: int, is_running: bool) -> None:
    """
    Установка статуса автопостинга.
    
    Args:
        user_id: Telegram ID пользователя
        is_running: Статус (True - запущен, False - остановлен)
    """
    await update_user(user_id, is_running=1 if is_running else 0)


async def update_last_post_time(user_id: int) -> None:
    """
    Обновление времени последней публикации.
    
    Args:
        user_id: Telegram ID пользователя
    """
    await update_user(user_id, last_post_time=datetime.now().isoformat())


# ============== Функции для работы с контентами ==============

async def add_content(user_id: int, photo_file_id: str, caption: str, name: str = None) -> int:
    """
    Добавление нового контента.
    
    Args:
        user_id: Telegram ID пользователя
        photo_file_id: ID файла фото в Telegram
        caption: Подпись к фото
        name: Название контента (опционально)
        
    Returns:
        ID созданного контента
    """
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO contents (user_id, name, photo_file_id, caption, is_active, is_running, created_at, updated_at)
            VALUES (?, ?, ?, ?, 0, 0, ?, ?)
            """,
            (user_id, name, photo_file_id, caption, now, now)
        )
        await db.commit()
        return cursor.lastrowid


async def update_content(content_id: int, **kwargs) -> None:
    """
    Обновление данных контента.
    
    Args:
        content_id: ID контента
        **kwargs: Поля для обновления
    """
    if not kwargs:
        return
    
    kwargs["updated_at"] = datetime.now().isoformat()
    
    fields = ", ".join(f"{key} = ?" for key in kwargs.keys())
    values = list(kwargs.values())
    values.append(content_id)
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            f"UPDATE contents SET {fields} WHERE id = ?",
            values
        )
        await db.commit()


async def set_content_running(content_id: int, is_running: bool) -> None:
    """
    Установка статуса запуска контента.
    
    Args:
        content_id: ID контента
        is_running: Статус (True - запущен, False - остановлен)
    """
    await update_content(content_id, is_running=1 if is_running else 0, is_active=1 if is_running else 0)


async def get_running_contents() -> list[dict]:
    """
    Получение всех запущенных контентов.
    
    Returns:
        Список запущенных контентов
    """
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM contents WHERE is_running = 1"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def update_content_last_post(content_id: int) -> None:
    """
    Обновление времени последней публикации контента.
    
    Args:
        content_id: ID контента
    """
    await update_content(content_id, last_post_time=datetime.now().isoformat())


async def get_contents(user_id: int) -> list[dict]:
    """
    Получение всех контентов пользователя.
    
    Args:
        user_id: Telegram ID пользователя
        
    Returns:
        Список контентов
    """
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM contents WHERE user_id = ? ORDER BY id",
            (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_active_contents(user_id: int) -> list[dict]:
    """
    Получение только активных контентов пользователя.
    
    Args:
        user_id: Telegram ID пользователя
        
    Returns:
        Список активных контентов
    """
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM contents WHERE user_id = ? AND is_active = 1 ORDER BY id",
            (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_content_by_id(content_id: int) -> Optional[dict]:
    """
    Получение контента по ID.
    
    Args:
        content_id: ID контента
        
    Returns:
        Словарь с данными контента или None
    """
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM contents WHERE id = ?",
            (content_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None


async def toggle_content_status(content_id: int) -> bool:
    """
    Переключение статуса контента (активен/неактивен).
    
    Args:
        content_id: ID контента
        
    Returns:
        Новый статус (True = активен)
    """
    content = await get_content_by_id(content_id)
    if not content:
        return False
    
    new_status = 0 if content["is_active"] else 1
    now = datetime.now().isoformat()
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE contents SET is_active = ?, updated_at = ? WHERE id = ?",
            (new_status, now, content_id)
        )
        await db.commit()
    
    return bool(new_status)


async def delete_content(content_id: int) -> bool:
    """
    Удаление контента.
    
    Args:
        content_id: ID контента
        
    Returns:
        True если удалён успешно
    """
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM contents WHERE id = ?",
            (content_id,)
        )
        await db.commit()
        return cursor.rowcount > 0


async def increment_content_post_count(content_id: int) -> None:
    """
    Увеличение счётчика публикаций контента.
    
    Args:
        content_id: ID контента
    """
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE contents SET post_count = post_count + 1, updated_at = ? WHERE id = ?",
            (now, content_id)
        )
        await db.commit()


async def get_next_content_for_posting(user_id: int) -> Optional[dict]:
    """
    Получение следующего контента для публикации (ротация).
    
    Args:
        user_id: Telegram ID пользователя
        
    Returns:
        Контент для публикации или None
    """
    active_contents = await get_active_contents(user_id)
    if not active_contents:
        return None
    
    user = await get_user(user_id)
    current_index = user.get("current_content_index", 0) or 0
    
    # Если индекс выходит за границы, сбрасываем
    if current_index >= len(active_contents):
        current_index = 0
    
    content = active_contents[current_index]
    
    # Обновляем индекс для следующего раза
    next_index = (current_index + 1) % len(active_contents)
    await update_user(user_id, current_content_index=next_index)
    
    return content

