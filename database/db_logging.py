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

    def upsert_prediction(self, payload: dict[str, Any]) -> bool:
        """
        Сохранить прогноз с UPSERT по (fixture_id, model_version).
        Ожидает в payload как минимум:
        fixture_id, model_version, lambda_home, lambda_away,
        prob_home_win, prob_draw, prob_away_win, confidence.
        Остальные поля опциональны.
        """
        required = [
            "fixture_id",
            "model_version",
            "lambda_home",
            "lambda_away",
            "probability_home_win",
            "probability_draw",
            "probability_away_win",
            "confidence",
        ]

        # Поддержка альтернативных ключей
        if "prob_home_win" in payload:
            payload.setdefault("probability_home_win", payload["prob_home_win"])
        if "prob_away_win" in payload:
            payload.setdefault("probability_away_win", payload["prob_away_win"])
        if "prob_draw" in payload:
            payload.setdefault("probability_draw", payload["prob_draw"])

        missing = [k for k in required if k not in payload]
        if missing:
            logger.error("upsert_prediction: missing fields: %s", ", ".join(missing))
            return False

        sql = """
        INSERT INTO predictions (
            fixture_id, league_id, season_id, home_team_id, away_team_id,
            match_start, model_name, model_version, cache_version, calibration_method, model_flags,
            lambda_home, lambda_away, prob_home_win, prob_draw, prob_away_win,
            totals_probs, btts_probs, totals_corr_probs, btts_corr_probs,
            confidence, missing_ratio, data_freshness_min, penalties,
            recommendations, features_snapshot, meta
        ) VALUES (
            %(fixture_id)s, %(league_id)s, %(season_id)s, %(home_team_id)s, %(away_team_id)s,
            %(match_start)s, %(model_name)s, %(model_version)s, %(cache_version)s, %(calibration_method)s, %(model_flags)s,
            %(lambda_home)s, %(lambda_away)s, %(probability_home_win)s, %(probability_draw)s, %(probability_away_win)s,
            %(totals_probs)s, %(btts_probs)s, %(totals_corr_probs)s, %(btts_corr_probs)s,
            %(confidence)s, %(missing_ratio)s, %(data_freshness_min)s, %(penalties)s,
            %(recommendations)s, %(features_snapshot)s, %(meta)s
        )
        ON CONFLICT (fixture_id, model_version) DO UPDATE SET
            updated_at = NOW(),
            lambda_home = EXCLUDED.lambda_home,
            lambda_away = EXCLUDED.lambda_away,
            prob_home_win = EXCLUDED.prob_home_win,
            prob_draw = EXCLUDED.prob_draw,
            prob_away_win = EXCLUDED.prob_away_win,
            totals_probs = COALESCE(EXCLUDED.totals_probs, predictions.totals_probs),
            btts_probs = COALESCE(EXCLUDED.btts_probs, predictions.btts_probs),
            totals_corr_probs = COALESCE(EXCLUDED.totals_corr_probs, predictions.totals_corr_probs),
            btts_corr_probs = COALESCE(EXCLUDED.btts_corr_probs, predictions.btts_corr_probs),
            confidence = EXCLUDED.confidence,
            missing_ratio = COALESCE(EXCLUDED.missing_ratio, predictions.missing_ratio),
            data_freshness_min = COALESCE(EXCLUDED.data_freshness_min, predictions.data_freshness_min),
            penalties = COALESCE(EXCLUDED.penalties, predictions.penalties),
            recommendations = COALESCE(EXCLUDED.recommendations, predictions.recommendations),
            features_snapshot = COALESCE(EXCLUDED.features_snapshot, predictions.features_snapshot),
            meta = COALESCE(EXCLUDED.meta, predictions.meta)
        ;
        """
        conn = None
        try:
            conn = self._acquire()
            with conn.cursor() as cur:
                cur.execute(sql, payload)
            conn.commit()
            logger.info(
                "UPSERT predictions OK for fixture_id=%s, model_version=%s",
                payload.get("fixture_id"),
                payload.get("model_version"),
            )
            return True
        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            logger.error("UPSERT predictions error: %s", e)
            return False
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

