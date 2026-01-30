"""
Фильтры для ограничения доступа к боту.
"""

from typing import Union
from aiogram.filters import Filter
from aiogram.types import Message

from config import ALLOWED_USERS


class AllowedUserFilter(Filter):
    """Фильтр для проверки разрешённых пользователей."""
    
    async def __call__(self, message: Message) -> bool:
        """
        Проверяет, имеет ли пользователь доступ к боту.
        
        Args:
            message: Сообщение пользователя
            
        Returns:
            True если доступ разрешён, False иначе
        """
        # Если список пустой — доступ разрешён всем
        if not ALLOWED_USERS:
            return True
        
        return message.from_user.id in ALLOWED_USERS

