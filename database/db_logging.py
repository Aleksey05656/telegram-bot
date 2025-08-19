# database/db_logging.py
"""Модуль для логирования прогнозов и исходов матчей в PostgreSQL."""
import asyncio
import json
from typing import Dict, Any, Optional
from datetime import datetime
import asyncpg
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text, Column, Integer, String, Float, DateTime, CheckConstraint, BigInteger
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from logger import logger
from config import get_settings
# Получаем настройки
settings = get_settings()
# Создание асинхронного движка SQLAlchemy
engine = create_async_engine(
    settings.DATABASE_URL, 
    pool_pre_ping=True,
    echo=settings.DEBUG_MODE  # Включаем логирование SQL запросов в режиме отладки
)
SessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
# Базовая модель
Base = declarative_base()
class Prediction(Base):
    """Модель для таблицы predictions."""
    __tablename__ = 'predictions'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    match_id = Column(BigInteger, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    features_json = Column(JSONB, nullable=False)
    probs_json = Column(JSONB, nullable=False)
    lambda_home = Column(Float, nullable=False)
    lambda_away = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)
class Outcome(Base):
    """Модель для таблицы outcomes."""
    __tablename__ = 'outcomes'
    match_id = Column(BigInteger, primary_key=True)
    finished_at = Column(DateTime(timezone=True))
    goals_home = Column(Integer)
    goals_away = Column(Integer)
    result = Column(String(1), CheckConstraint("result IN ('H','D','A')"))
# Новая модель для таблицы predictions_log
class PredictionLog(Base):
    """Модель для таблицы predictions_log."""
    __tablename__ = 'predictions_log'
    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(BigInteger, nullable=False)
    league = Column(String, nullable=False)
    market = Column(String, nullable=False)
    model_version = Column(String, nullable=False)
    probs_json = Column(JSONB, nullable=False)
    confidence = Column(Float, nullable=False)
    features_json = Column(JSONB)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
async def init_db():
    """Инициализация базы данных - создание таблиц."""
    try:
        async with engine.begin() as conn:
            # Создаем таблицы (для моделей SQLAlchemy)
            await conn.run_sync(Base.metadata.create_all)
            
            # Создаем новую таблицу predictions_log и индексы вручную
            # (на случай, если модель не была добавлена своевременно или нужны специфичные индексы)
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS predictions_log (
                  id SERIAL PRIMARY KEY,
                  match_id BIGINT NOT NULL,
                  league TEXT NOT NULL,
                  market TEXT NOT NULL,
                  model_version TEXT NOT NULL,
                  probs_json JSONB NOT NULL,
                  confidence DOUBLE PRECISION NOT NULL,
                  features_json JSONB,
                  created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
                )
            """))
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_predictions_log_match 
                ON predictions_log(match_id)
            """))
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_predictions_log_league_market 
                ON predictions_log(league, market)
            """))
            
        logger.info("✅ Таблицы базы данных успешно созданы или уже существуют")
        logger.info("✅ Таблица predictions_log и индексы созданы или уже существуют")
    except Exception as e:
        logger.error(f"❌ Ошибка при инициализации базы данных: {e}")
        raise
# Новая функция логирования прогноза
from typing import Any, Dict, Optional
from datetime import datetime
import json, asyncpg

async def log_prediction_new(
    pool: asyncpg.Pool,
    *,
    match_id: int, league: str, market: str, model_version: str,
    probs: Dict[str, float], confidence: float,
    features: Dict[str, Any] | None = None,
    created_at: Optional[datetime] = None
) -> None:
    created_at = created_at or datetime.utcnow()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO predictions_log
            (match_id, league, market, model_version, probs_json, confidence, features_json, created_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
            """,
            match_id, league, market, model_version,
            json.dumps(probs, ensure_ascii=False),
            confidence,
            json.dumps(features or {}, ensure_ascii=False),
            created_at
        )
async def log_prediction(match_id: int, features: Dict[str, Any], probs: Dict[str, Any], 
                        lam_home: float, lam_away: float, confidence: float) -> bool:
    """
    Логирование прогноза в базу данных.
    Args:
        match_id (int): ID матча
        features (Dict[str, Any]): Признаки матча
        probs (Dict[str, Any]): Вероятности исходов
        lam_home (float): Ожидаемые голы домашней команды
        lam_away (float): Ожидаемые голы гостевой команды
        confidence (float): Уверенность прогноза
    Returns:
        bool: Успешность операции
    """
    try:
        async with SessionLocal() as session:
            # Создаем запись прогноза
            prediction_record = Prediction(
                match_id=match_id,
                features_json=json.dumps(features, ensure_ascii=False),
                probs_json=json.dumps(probs, ensure_ascii=False),
                lambda_home=float(lam_home),
                lambda_away=float(lam_away),
                confidence=float(confidence)
            )
            session.add(prediction_record)
            await session.commit()
            await session.refresh(prediction_record)
            logger.debug(f"✅ Прогноз для матча {match_id} успешно записан в БД (ID: {prediction_record.id})")
            return True
    except Exception as e:
        logger.error(f"❌ Ошибка при записи прогноза для матча {match_id} в БД: {e}")
        return False
async def log_outcome(match_id: int, finished_at: datetime, goals_home: int, 
                     goals_away: int, result: str) -> bool:
    """
    Логирование исхода матча в базу данных.
    Args:
        match_id (int): ID матча
        finished_at (datetime): Время завершения матча
        goals_home (int): Голы домашней команды
        goals_away (int): Голы гостевой команды
        result (str): Результат матча ('H' - победа дома, 'D' - ничья, 'A' - победа гостей)
    Returns:
        bool: Успешность операции
    """
    try:
        async with SessionLocal() as session:
            # Проверяем, существует ли уже запись об исходе
            existing_outcome = await session.execute(
                text("SELECT match_id FROM outcomes WHERE match_id = :match_id"),
                {"match_id": match_id}
            )
            if existing_outcome.fetchone():
                # Обновляем существующую запись
                await session.execute(
                    text("""
                        UPDATE outcomes 
                        SET finished_at = :finished_at, 
                            goals_home = :goals_home, 
                            goals_away = :goals_away, 
                            result = :result
                        WHERE match_id = :match_id
                    """),
                    {
                        "match_id": match_id,
                        "finished_at": finished_at,
                        "goals_home": goals_home,
                        "goals_away": goals_away,
                        "result": result
                    }
                )
                logger.debug(f"🔄 Исход матча {match_id} обновлен в БД")
            else:
                # Создаем новую запись
                await session.execute(
                    text("""
                        INSERT INTO outcomes (match_id, finished_at, goals_home, goals_away, result)
                        VALUES (:match_id, :finished_at, :goals_home, :goals_away, :result)
                    """),
                    {
                        "match_id": match_id,
                        "finished_at": finished_at,
                        "goals_home": goals_home,
                        "goals_away": goals_away,
                        "result": result
                    }
                )
                logger.debug(f"✅ Исход матча {match_id} успешно записан в БД")
            await session.commit()
            return True
    except Exception as e:
        logger.error(f"❌ Ошибка при записи исхода матча {match_id} в БД: {e}")
        return False
async def get_prediction_by_match_id(match_id: int) -> Optional[Dict[str, Any]]:
    """
    Получение последнего прогноза для матча.
    Args:
        match_id (int): ID матча
    Returns:
        Optional[Dict[str, Any]]: Данные прогноза или None
    """
    try:
        async with SessionLocal() as session:
            result = await session.execute(
                text("""
                    SELECT id, match_id, created_at, features_json, probs_json, 
                           lambda_home, lambda_away, confidence
                    FROM predictions 
                    WHERE match_id = :match_id 
                    ORDER BY created_at DESC 
                    LIMIT 1
                """),
                {"match_id": match_id}
            )
            row = result.fetchone()
            if row:
                return {
                    "id": row[0],
                    "match_id": row[1],
                    "created_at": row[2],
                    "features_json": row[3],
                    "probs_json": row[4],
                    "lambda_home": row[5],
                    "lambda_away": row[6],
                    "confidence": row[7]
                }
            return None
    except Exception as e:
        logger.error(f"❌ Ошибка при получении прогноза для матча {match_id} из БД: {e}")
        return None
async def get_outcome_by_match_id(match_id: int) -> Optional[Dict[str, Any]]:
    """
    Получение исхода матча.
    Args:
        match_id (int): ID матча
    Returns:
        Optional[Dict[str, Any]]: Данные исхода или None
    """
    try:
        async with SessionLocal() as session:
            result = await session.execute(
                text("""
                    SELECT match_id, finished_at, goals_home, goals_away, result
                    FROM outcomes 
                    WHERE match_id = :match_id
                """),
                {"match_id": match_id}
            )
            row = result.fetchone()
            if row:
                return {
                    "match_id": row[0],
                    "finished_at": row[1],
                    "goals_home": row[2],
                    "goals_away": row[3],
                    "result": row[4]
                }
            return None
    except Exception as e:
        logger.error(f"❌ Ошибка при получении исхода матча {match_id} из БД: {e}")
        return None
# Функции для CLI использования
async def main():
    """Основная функция для CLI."""
    import sys
    import argparse
    parser = argparse.ArgumentParser(description='Database Logging CLI')
    parser.add_argument('action', choices=['init', 'test'], help='Действие для выполнения')
    args = parser.parse_args()
    if args.action == 'init':
        # Инициализация базы данных
        await init_db()
        print("База данных инициализирована")
    elif args.action == 'test':
        # Тестовая запись
        test_features = {"test": "feature"}
        test_probs = {"home_win": 0.4, "draw": 0.3, "away_win": 0.3}
        success = await log_prediction(
            match_id=12345,
            features=test_features,
            probs=test_probs,
            lam_home=1.5,
            lam_away=1.2,
            confidence=0.75
        )
        if success:
            print("Тестовая запись успешна")
        else:
            print("Ошибка при тестовой записи")
        # Тестовая запись исхода
        outcome_success = await log_outcome(
            match_id=12345,
            finished_at=datetime.now(),
            goals_home=2,
            goals_away=1,
            result='H'
        )
        if outcome_success:
            print("Тестовая запись исхода успешна")
        else:
            print("Ошибка при тестовой записи исхода")
if __name__ == "__main__":
    # Запуск основной функции
    asyncio.run(main())
