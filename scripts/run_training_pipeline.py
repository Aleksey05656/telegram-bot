# scripts/run_training_pipeline.py
"""Скрипт для запуска пайплайна обучения моделей."""
import asyncio
import pandas as pd
from typing import Dict, Any
from logger import logger
from config import get_settings

# === НОВЫЙ КОД ДЛЯ ЭТАПА 9.2 ===
# Импортируем функцию обучения
from scripts.train_model import train_league_market

async def run_training_pipeline(datasets: Dict[int, pd.DataFrame], min_matches_threshold: int = 1500) -> None:
    """
    Запуск пайплайна обучения для всех лиг.
    Args:
        datasets (Dict[int, pd.DataFrame]): Датасеты для каждой лиги
        min_matches_threshold (int): Минимальное количество матчей для отдельной лиги
    """
    try:
        logger.info("🚀 Запуск пайплайна обучения моделей")
        # Разделяем лиги на крупные и мелкие
        large_leagues = {}   # Лиги с достаточным количеством данных
        small_leagues = {}   # Лиги с недостаточным количеством данных
        for league_id, df in datasets.items():
            if len(df) >= min_matches_threshold:
                large_leagues[league_id] = df
                logger.info(f"Лига {league_id} классифицирована как крупная ({len(df)} матчей)")
            else:
                small_leagues[league_id] = df
                logger.info(f"Лига {league_id} классифицирована как мелкая ({len(df)} матчей)")
        # Создаем объединенный датасет для мелких лиг
        global_dataset = None
        if small_leagues:
            small_dfs = list(small_leagues.values())
            global_dataset = pd.concat(small_dfs, ignore_index=True)
            logger.info(f"Создан глобальный датасет для мелких лиг: {len(global_dataset)} матчей")
        # Обучаем модели для крупных лиг
        markets = ["1x2", "btts", "ou_2_5"]
        for league_id, df_league in large_leagues.items():
            logger.info(f"Начало обучения моделей для лиги {league_id}")
            for market in markets:
                try:
                    logger.info(f"Обучение модели для лиги {league_id}, рынок {market}")
                    # Запуск обучения
                    saved_paths = train_league_market(
                        league=str(league_id),
                        market=market,
                        df=df_league,
                        date_col="match_date"
                    )
                    logger.info(f"Модель для лиги {league_id}, рынок {market} обучена. "
                               f"Сохраненные артефакты: {list(saved_paths.keys())}")
                except Exception as e:
                    logger.error(f"Ошибка при обучении модели для лиги {league_id}, рынок {market}: {e}")
                    continue
        # Обучаем глобальную модель для мелких лиг
        if global_dataset is not None and not global_dataset.empty:
            logger.info("Начало обучения глобальной модели для мелких лиг")
            for market in markets:
                try:
                    logger.info(f"Обучение глобальной модели для рынка {market}")
                    # Запуск обучения с league="_global"
                    saved_paths = train_league_market(
                        league="_global",
                        market=market,
                        df=global_dataset,
                        date_col="match_date"
                    )
                    logger.info(f"Глобальная модель для рынка {market} обучена. "
                               f"Сохраненные артефакты: {list(saved_paths.keys())}")
                except Exception as e:
                    logger.error(f"Ошибка при обучении глобальной модели для рынка {market}: {e}")
                    continue
        logger.info("🏁 Пайплайн обучения моделей завершен")
    except Exception as e:
        logger.error(f"Критическая ошибка в пайплайне обучения: {e}", exc_info=True)
# === КОНЕЦ НОВОГО КОДА ДЛЯ ЭТАПА 9.2 ===

async def main():
    """Главная функция для запуска пайплайна обучения."""
    try:
        logger.info("🚀 Запуск пайплайна обучения моделей")
        # Загружаем датасеты (в реальной реализации из файлов или БД)
        # Пример загрузки из CSV файлов:
        datasets = {}
        # В реальной реализации здесь будет загрузка датасетов
        # Например:
        # import os
        # dataset_files = [f for f in os.listdir("data/datasets") if f.endswith("_dataset.csv")]
        # for file in dataset_files:
        #     league_id = int(file.split("_")[1])
        #     df = pd.read_csv(f"data/datasets/{file}")
        #     datasets[league_id] = df
        # Для демонстрации создаем пустой словарь
        # В реальной реализации здесь будут загруженные датасеты
        datasets = {}  # Загрузите реальные датасеты здесь
        if not datasets:
            logger.warning("Нет датасетов для обучения. Пожалуйста, сначала подготовьте датасеты.")
            return
        # Запускаем пайплайн обучения
        await run_training_pipeline(datasets, min_matches_threshold=1500)
        logger.info("🏁 Пайплайн обучения завершен")
    except Exception as e:
        logger.error(f"Критическая ошибка в основном процессе: {e}", exc_info=True)

if __name__ == "__main__":
    # Запуск асинхронной функции
    asyncio.run(main())
