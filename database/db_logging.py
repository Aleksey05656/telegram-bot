import logging
import psycopg2
from psycopg2 import sql
from typing import Optional

# Настройка логирования
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

class DBLogger:
    def __init__(self, db_url: str, db_user: str, db_password: str, db_name: str):
        self.db_url = db_url
        self.db_user = db_user
        self.db_password = db_password
        self.db_name = db_name
        self.connection = None
        self.cursor = None

    def connect(self):
        """Подключение к базе данных."""
        try:
            self.connection = psycopg2.connect(
                dbname=self.db_name,
                user=self.db_user,
                password=self.db_password,
                host=self.db_url
            )
            self.cursor = self.connection.cursor()
            logger.info("Подключение к базе данных успешно установлено.")
        except Exception as e:
            logger.error(f"Ошибка при подключении к базе данных: {e}")

    def execute_query(self, query: str, params: Optional[tuple] = None):
        """Выполнение SQL-запроса."""
        try:
            self.cursor.execute(query, params)
            self.connection.commit()
            logger.info(f"Успешное выполнение запроса: {query}")
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Ошибка при выполнении запроса {query}: {e}")

    def fetch_one(self, query: str, params: Optional[tuple] = None):
        """Получение одного результата."""
        try:
            self.cursor.execute(query, params)
            result = self.cursor.fetchone()
            logger.info(f"Запрос выполнен успешно: {query}")
            return result
        except Exception as e:
            logger.error(f"Ошибка при выполнении запроса {query}: {e}")
            return None

    def fetch_all(self, query: str, params: Optional[tuple] = None):
        """Получение всех результатов."""
        try:
            self.cursor.execute(query, params)
            results = self.cursor.fetchall()
            logger.info(f"Запрос выполнен успешно: {query}")
            return results
        except Exception as e:
            logger.error(f"Ошибка при выполнении запроса {query}: {e}")
            return []

    def close(self):
        """Закрытие соединения с базой данных."""
        try:
            if self.cursor:
                self.cursor.close()
            if self.connection:
                self.connection.close()
            logger.info("Соединение с базой данных закрыто.")
        except Exception as e:
            logger.error(f"Ошибка при закрытии соединения: {e}")
