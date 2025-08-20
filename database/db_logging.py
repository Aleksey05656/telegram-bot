import logging
from typing import Optional

from psycopg2 import pool as pg_pool
from urllib.parse import urlparse

# Настройка логирования
logger = logging.getLogger(__name__)
# Проверка, чтобы не добавлять обработчик, если он уже существует
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

class DBLogger:
    def __init__(self, db_url: str, db_user: str = None, db_password: str = None, db_name: str = None):
        # Разбираем DB_URL, если он передан как полный URL
        parsed_url = urlparse(db_url)
        self.db_url = parsed_url.hostname
        self.db_port = parsed_url.port
        self.db_user = db_user or parsed_url.username
        self.db_password = db_password or parsed_url.password
        self.db_name = db_name or parsed_url.path[1:]
        # Пул соединений создается при первом подключении
        self.pool = None

    def connect(self):
        """Подключение к базе данных через пул соединений."""
        if self.pool is None:
            self.pool = pg_pool.SimpleConnectionPool(
                1,
                10,
                dbname=self.db_name,
                user=self.db_user,
                password=self.db_password,
                host=self.db_url,
                port=self.db_port,
            )
        try:
            self.connection = self.pool.getconn()
            self.cursor = self.connection.cursor()  # Создание нового курсора
            logger.info("Подключение к базе данных успешно установлено.")
        except Exception as e:
            logger.error(f"Ошибка при подключении к базе данных: {e}")

    def execute_query(self, query: str, params: Optional[tuple] = None):
        """Выполнение SQL-запроса с проверкой наличия соединения перед rollback."""
        try:
            with self.connection.cursor() as cursor:  # Новый курсор для каждого запроса
                cursor.execute(query, params)
                self.connection.commit()
                logger.info(f"Успешное выполнение запроса: {query}")
        except Exception as e:
            if getattr(self, "connection", None):
                self.connection.rollback()
            logger.error(f"Ошибка при выполнении запроса {query}: {e}")

    def fetch_one(self, query: str, params: Optional[tuple] = None):
        """Получение одного результата."""
        try:
            self.cursor.execute(query, params)
            result = self.cursor.fetchone()
            logger.info("Запрос выполнен успешно: %s", query)
            return result
        except Exception as e:
            logger.error(
                "Ошибка при выполнении запроса %s: %s",
                query,
                e,
            )
            return None

    def fetch_all(self, query: str, params: Optional[tuple] = None):
        """Получение всех результатов."""
        try:
            self.cursor.execute(query, params)
            results = self.cursor.fetchall()
            logger.info("Запрос выполнен успешно: %s", query)
            return results
        except Exception as e:
            logger.error(
                "Ошибка при выполнении запроса %s: %s",
                query,
                e,
            )
            return []

    def close(self):
        """Закрытие соединения с базой данных и возвращение соединения в пул."""
        try:
            cursor = getattr(self, "cursor", None)
            if cursor:
                cursor.close()
                self.cursor = None
            connection = getattr(self, "connection", None)
            if connection:
                if self.pool:
                    self.pool.putconn(connection)
                else:
                    connection.close()
                self.connection = None
            # Пул соединений сохраняется для повторного использования
            logger.info("Соединение с базой данных закрыто.")
        except Exception as e:
            logger.error(f"Ошибка при закрытии соединения: {e}")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        # Не закрываем пул соединений, только соединение
