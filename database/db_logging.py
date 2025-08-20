import logging
import os
import time
from psycopg2 import pool as pg_pool
from typing import Optional

# Настройка логирования
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)

# Проверка, чтобы не добавлять обработчик, если он уже существует
if not logger.handlers:
    logger.addHandler(ch)

class DBLogger:
    def __init__(self, db_url: str = None, db_user: str = None, db_password: str = None, db_name: str = None):
        # Использование переменных окружения вместо хранения в config
        self.db_url = db_url or os.getenv('DB_URL')
        self.db_user = db_user or os.getenv('DB_USER')
        self.db_password = db_password or os.getenv('DB_PASSWORD')
        self.db_name = db_name or os.getenv('DB_NAME')
        self.connection = None
        self.cursor = None
        self.pool = None

    def connect(self):
        """Подключение к базе данных через пул соединений."""
        try:
            if not self.pool:
                self.pool = pg_pool.SimpleConnectionPool(
                    1,
                    10,
                    dbname=self.db_name,
                    user=self.db_user,
                    password=self.db_password,
                    host=self.db_url,
                )
            self.connection = self.pool.getconn()
            self.cursor = self.connection.cursor()
            logger.info("Подключение к базе данных успешно установлено.")
        except Exception as e:
            logger.error("Ошибка при подключении к базе данных: %s", e)

    def execute_query(self, query: str, params: Optional[tuple] = None, retries: int = 3):
        """Выполнение SQL-запроса с возможностью повторной попытки."""
        attempt = 0
        while attempt < retries:
            try:
                self.cursor.execute(query, params)
                self.connection.commit()
                logger.info("Успешное выполнение запроса: %s", query)
                return
            except Exception as e:
                self.connection.rollback()
                attempt += 1
                logger.error(
                    "Ошибка при выполнении запроса %s: %s. Попытка %s/%s",
                    query,
                    e,
                    attempt,
                    retries,
                )
                if attempt >= retries:
                    logger.error("Превышено количество попыток для запроса %s", query)
                    break
                time.sleep(1)  # небольшая задержка перед повтором

    def fetch_one(self, query: str, params: Optional[tuple] = None):
        """Получение одного результата."""
        try:
            self.cursor.execute(query, params)
            result = self.cursor.fetchone()
            # Логируем только при успешном выполнении запроса
            logger.info("Запрос выполнен успешно: %s", query)
            return result
        except Exception as e:
            logger.error("Ошибка при выполнении запроса %s: %s", query, e)
            return None

    def fetch_all(self, query: str, params: Optional[tuple] = None):
        """Получение всех результатов."""
        try:
            self.cursor.execute(query, params)
            results = self.cursor.fetchall()
            # Логируем только при успешном выполнении запроса
            logger.info("Запрос выполнен успешно: %s", query)
            return results
        except Exception as e:
            logger.error("Ошибка при выполнении запроса %s: %s", query, e)
            return []

    def close(self):
        """Закрытие соединения с базой данных."""
        try:
            if self.cursor:
                self.cursor.close()
                self.cursor = None
            if self.connection:
                if self.pool:
                    self.pool.putconn(self.connection)
                else:
                    self.connection.close()
                self.connection = None
            if self.pool:
                self.pool.closeall()
                self.pool = None
            logger.info("Соединение с базой данных закрыто.")
        except Exception as e:
            logger.error("Ошибка при закрытии соединения: %s", e)

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
