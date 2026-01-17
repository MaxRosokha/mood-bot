import sqlite3
from datetime import datetime, timedelta
from typing import List, Tuple, Optional


class Database:
    def __init__(self, db_path: str = "mood.db"):
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        """Створює з'єднання з базою даних"""
        return sqlite3.connect(self.db_path)

    def init_db(self):
        """Ініціалізує базу даних, створює таблиці якщо їх немає"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Таблиця користувачів
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблиця записів настрою
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mood_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                mood TEXT NOT NULL,
                comment TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        conn.commit()
        conn.close()

    def add_user(self, user_id: int, username: Optional[str], first_name: Optional[str]):
        """Додає користувача в базу даних, якщо його ще немає"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR IGNORE INTO users (user_id, username, first_name)
            VALUES (?, ?, ?)
        """, (user_id, username, first_name))
        
        conn.commit()
        conn.close()

    def add_mood_entry(self, user_id: int, mood: str, comment: Optional[str] = None):
        """Додає запис настрою в базу даних"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO mood_entries (user_id, mood, comment)
            VALUES (?, ?, ?)
        """, (user_id, mood, comment))
        
        conn.commit()
        conn.close()

    def get_stats(self, user_id: int, days: int = 7) -> List[Tuple[str, int]]:
        """Отримує статистику настрою за останні N днів"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        since_date = datetime.now() - timedelta(days=days)
        
        cursor.execute("""
            SELECT mood, COUNT(*) as count
            FROM mood_entries
            WHERE user_id = ? AND timestamp >= ?
            GROUP BY mood
            ORDER BY count DESC
        """, (user_id, since_date.isoformat()))
        
        results = cursor.fetchall()
        conn.close()
        return results

    def get_recent_entries(self, user_id: int, limit: int = 5) -> List[Tuple[str, str, str]]:
        """Отримує останні N записів настрою з коментарями"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT mood, comment, timestamp
            FROM mood_entries
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (user_id, limit))
        
        results = cursor.fetchall()
        conn.close()
        return results

    def is_waiting_for_comment(self, user_id: int) -> bool:
        """Перевіряє, чи очікує бот коментар від користувача"""
        # Можна реалізувати через окрему таблицю або кеш
        # Для простоти, повертаємо False
        return False
