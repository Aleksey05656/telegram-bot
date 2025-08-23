import logging
import os
import time
from typing import Optional, Any, Tuple, List

import psycopg2
from psycopg2 import pool as pg_pool

# --- Логирование: не переопределяем глобальный уровень, не плодим хендлеры ---
logger = logging.getLogger(__name__)
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(_h)


class DBLogger:
    """
    Безопасная обёртка для PostgreSQL:
    - Пул соединений создаётся лениво (при первом обращении)
    - На каждый вызов берём новое соединение и курсор; никаких self.cursor / self.connection
    - Обязательный возврат соединения в пул в finally
    - Надёжные rollback/commit с проверками
    """

    def __init__(
        self,
        dsn: Optional[str] = None,
        *,
        host: Optional[str] = None,
        port: Optional[int] = None,
        dbname: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        minconn: int = 1,
        maxconn: int = 10,
    ) -> None:
        # Можно передать готовый DSN или компоненты; компоненты берём из ENV по умолчанию
        self._dsn: Optional[str] = dsn or os.getenv("DATABASE_URL")
        self._host = host or os.getenv("DB_HOST")
        self._port = port or (int(os.getenv("DB_PORT")) if os.getenv("DB_PORT") else None)
        self._dbname = dbname or os.getenv("DB_NAME")
        self._user = user or os.getenv("DB_USER")
        self._password = password or os.getenv("DB_PASSWORD")
        self._minconn = int(minconn)
        self._maxconn = int(maxconn)
        self._pool: Optional[pg_pool.SimpleConnectionPool] = None

    # ---------- Внутренняя инфраструктура ----------
    def _ensure_pool(self) -> None:
        """Создать пул, если он ещё не создан."""
        if self._pool is not None:
            return
        try:
            if self._dsn:
                self._pool = pg_pool.SimpleConnectionPool(self._minconn, self._maxconn, dsn=self._dsn)
            else:
                # Требуем хотя бы host/dbname/user; port и password опциональны
                kwargs: dict[str, Any] = {}
                if self._host:
                    kwargs["host"] = self._host
                if self._port:
                    kwargs["port"] = self._port
                if self._dbname:
                    kwargs["dbname"] = self._dbname
                if self._user:
                    kwargs["user"] = self._user
                if self._password:
                    kwargs["password"] = self._password
                self._pool = pg_pool.SimpleConnectionPool(self._minconn, self._maxconn, **kwargs)  # type: ignore[arg-type]
            logger.info("DB connection pool initialized (min=%d, max=%d)", self._minconn, self._maxconn)
        except Exception as e:
            logger.error("Failed to initialize DB pool: %s", e)
            raise

    def _acquire(self):
        """Взять соединение из пула (с ленивой инициализацией пула)."""
        self._ensure_pool()
        assert self._pool is not None
        return self._pool.getconn()

    def _release(self, conn) -> None:
        """Вернуть соединение в пул (тихо игнорируем, если пула уже нет)."""
        try:
            if self._pool is not None and conn is not None:
                self._pool.putconn(conn)
        except Exception as e:
            logger.error("Failed to release connection back to pool: %s", e)

    # ---------- Публичные методы ----------
    def execute_query(self, query: str, params: Optional[Tuple[Any, ...]] = None, retries: int = 2) -> bool:
        """
        Выполнить запрос без выборки. Возвращает True при успехе.
        Всегда: своё соединение, свой курсор; никаких self.cursor.
        """
        attempt = 0
        while attempt <= retries:
            conn = None
            try:
                conn = self._acquire()
                with conn.cursor() as cur:
                    cur.execute(query, params)
                conn.commit()
                logger.info("SQL OK: %s", query)
                return True
            except Exception as e:
                if conn:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                attempt += 1
                logger.error("SQL error (attempt %d/%d) for %s: %s", attempt, retries, query, e)
                if attempt > retries:
                    return False
                time.sleep(min(0.25 * (2 ** (attempt - 1)), 2.0))
            finally:
                if conn:
                    self._release(conn)

    def fetch_one(self, query: str, params: Optional[Tuple[Any, ...]] = None) -> Optional[Tuple[Any, ...]]:
        """Выполнить SELECT и вернуть одну строку (или None)."""
        conn = None
        try:
            conn = self._acquire()
            with conn.cursor() as cur:
                cur.execute(query, params)
                row = cur.fetchone()
            logger.info("SQL fetch_one OK: %s", query)
            return row
        except Exception as e:
            logger.error("SQL fetch_one error for %s: %s", query, e)
            return None
        finally:
            if conn:
                self._release(conn)

    def fetch_all(self, query: str, params: Optional[Tuple[Any, ...]] = None) -> List[Tuple[Any, ...]]:
        """Выполнить SELECT и вернуть все строки (или пустой список)."""
        conn = None
        try:
            conn = self._acquire()
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
            logger.info("SQL fetch_all OK: %s", query)
            return rows
        except Exception as e:
            logger.error("SQL fetch_all error for %s: %s", query, e)
            return []
        finally:
            if conn:
                self._release(conn)

    # ---------- Контекст-менеджер ----------
    def __enter__(self) -> "DBLogger":
        # Ничего не берём заранее, только гарантируем наличие пула к моменту использования
        self._ensure_pool()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        # Пул намеренно не закрываем, чтобы переиспользовать между контекстами
        # Закрытие пула — отдельным вызовом close_pool()
        return None

    def close_pool(self) -> None:
        """Явно закрыть пул (например, при остановке приложения)."""
        if self._pool is not None:
            try:
                self._pool.closeall()
                logger.info("DB connection pool closed.")
            finally:
                self._pool = None

