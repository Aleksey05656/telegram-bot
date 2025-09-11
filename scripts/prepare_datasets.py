# scripts/prepare_datasets.py
"""Скрипт для подготовки датасетов для обучения моделей."""
import asyncio
import os  # Добавленный импорт
from datetime import datetime, timedelta

import pandas as pd

from logger import logger
from services.data_processor import build_features, data_processor
from services.sportmonks_client import sportmonks_client


# === НОВЫЙ КОД ДЛЯ ЭТАПА 9.1 ===
async def fetch_league_data(league_id: int, seasons: list[int]) -> pd.DataFrame:
    """
    Получение и обработка данных для конкретной лиги за указанные сезоны.
    Args:
        league_id (int): ID лиги в SportMonks
        seasons (List[int]): Список ID сезонов
    Returns:
        pd.DataFrame: Обработанный датасет для лиги
    """
    try:
        logger.info(f"Начало сбора данных для лиги {league_id}, сезоны: {seasons}")
        all_matches = []
        # Собираем данные по каждому сезону
        for season_id in seasons:
            logger.info(f"Получение данных для лиги {league_id}, сезон {season_id}")
            # Получаем сырые данные о матчах
            # Для примера возьмем данные за последние 2 года
            two_years_ago = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")
            raw_matches = await sportmonks_client.get_fixtures(
                league_id=league_id,
                season_id=season_id,
                next_fixtures=False,
                date_from=two_years_ago,
            )
            if not raw_matches:
                logger.warning(f"Нет данных для лиги {league_id}, сезон {season_id}")
                continue
            logger.info(
                f"Получено {len(raw_matches)} матчей для лиги {league_id}, сезон {season_id}"
            )
            all_matches.extend(raw_matches)
        if not all_matches:
            logger.warning(
                f"Нет данных для лиги {league_id} после обработки всех сезонов"
            )
            return pd.DataFrame(
                columns=[
                    "match_id",
                    "match_date",
                    "league_id",
                    "home_goals",
                    "away_goals",
                    "home_xg",
                    "away_xg",
                    "home_form",
                    "away_form",
                ]
            )
        # Обрабатываем данные через DataProcessor
        logger.info(f"Обработка {len(all_matches)} матчей для лиги {league_id}")
        processed_results = await data_processor.process_matches_batch(all_matches)
        # Фильтруем успешные результаты
        successful_matches = [
            result["data"]
            for result in processed_results
            if result["success"] and result["data"]
        ]
        if not successful_matches:
            logger.warning(f"Нет успешно обработанных матчей для лиги {league_id}")
            return pd.DataFrame(
                columns=[
                    "match_id",
                    "match_date",
                    "league_id",
                    "home_goals",
                    "away_goals",
                    "home_xg",
                    "away_xg",
                    "home_form",
                    "away_form",
                ]
            )
        logger.info(
            f"Успешно обработано {len(successful_matches)} матчей для лиги {league_id}"
        )
        # Преобразуем в DataFrame
        df_records = []
        for match_data in successful_matches:
            try:
                context = match_data.get("context", {})
                home_stats = match_data.get("home_stats", {})
                away_stats = match_data.get("away_stats", {})
                # Базовые данные матча
                record = {
                    "match_id": context.get("fixture_id"),
                    "match_date": context.get("match_date"),
                    "league_id": context.get("league_id"),
                    "home_goals": home_stats.get("goals", 0),
                    "away_goals": away_stats.get("goals", 0),
                    "home_xg": home_stats.get("xg", 0),
                    "away_xg": away_stats.get("xg", 0),
                    "home_form": home_stats.get("form", 0),
                    "away_form": away_stats.get("form", 0),
                    # Другие признаки могут быть добавлены здесь
                }
                df_records.append(record)
            except Exception as e:
                logger.error(
                    f"Ошибка при обработке матча {match_data.get('fixture_id', 'unknown')}: {e}"
                )
                continue
        if not df_records:
            logger.warning(f"Нет записей для создания DataFrame для лиги {league_id}")
            return pd.DataFrame(
                columns=[
                    "match_id",
                    "match_date",
                    "league_id",
                    "home_goals",
                    "away_goals",
                    "home_xg",
                    "away_xg",
                    "home_form",
                    "away_form",
                ]
            )
        # Создаем DataFrame
        df = pd.DataFrame(df_records)
        # Преобразуем дату
        if "match_date" in df.columns:
            df["match_date"] = pd.to_datetime(df["match_date"])
        # Добавляем базовые фичи
        df = build_features(df)  # Исправленный вызов функции
        logger.info(f"Создан датасет для лиги {league_id} с {len(df)} записями")
        return df
    except Exception as e:
        logger.error(
            f"Ошибка при сборе данных для лиги {league_id}: {e}", exc_info=True
        )
        return pd.DataFrame(
            columns=[
                "match_id",
                "match_date",
                "league_id",
                "home_goals",
                "away_goals",
                "home_xg",
                "away_xg",
                "home_form",
                "away_form",
            ]
        )


async def prepare_all_datasets(
    league_seasons: dict[int, list[int]]
) -> dict[int, pd.DataFrame]:
    """
    Подготовка датасетов для всех лиг.
    Args:
        league_seasons (Dict[int, List[int]]): Словарь {league_id: [season_ids]}
    Returns:
        Dict[int, pd.DataFrame]: Словарь датасетов для каждой лиги
    """
    try:
        logger.info("Начало подготовки датасетов для всех лиг")
        datasets = {}
        # Собираем данные для каждой лиги
        for league_id, seasons in league_seasons.items():
            logger.info(f"Обработка лиги {league_id}")
            df = await fetch_league_data(league_id, seasons)
            if not df.empty:
                datasets[league_id] = df
                logger.info(
                    f"Датасет для лиги {league_id} успешно создан ({len(df)} записей)"
                )
            else:
                logger.warning(f"Датасет для лиги {league_id} пуст")
        logger.info(f"Подготовка датасетов завершена. Обработано {len(datasets)} лиг")
        return datasets
    except Exception as e:
        logger.error(f"Ошибка при подготовке датасетов: {e}", exc_info=True)
        return {}


# === КОНЕЦ НОВОГО КОДА ДЛЯ ЭТАПА 9.1 ===
async def main():
    """Главная функция для подготовки датасетов."""
    try:
        logger.info("🚀 Запуск подготовки датасетов")
        # Создание директории для сохранения датасетов
        os.makedirs("data/datasets", exist_ok=True)  # Добавленное создание директории
        # Пример конфигурации лиг и сезонов
        # В реальной реализации это может быть загружено из конфига
        league_seasons = {
            # Premier League (примерные ID)
            39: [23855, 22855],  # 2023/24, 2022/23
            # La Liga
            140: [23859, 22859],  # 2023/24, 2022/23
            # Bundesliga
            78: [23863, 22863],  # 2023/24, 2022/23
            # Serie A
            135: [23861, 22861],  # 2023/24, 2022/23
            # Ligue 1
            61: [23857, 22857],  # 2023/24, 2022/23
        }
        # Подготавливаем датасеты
        datasets = await prepare_all_datasets(league_seasons)
        # Сохраняем датасеты в файлы (опционально)
        for league_id, df in datasets.items():
            if not df.empty:
                filename = f"data/datasets/league_{league_id}_dataset.csv"
                df.to_csv(filename, index=False)
                logger.info(f"Датасет для лиги {league_id} сохранен в {filename}")
        logger.info("🏁 Подготовка датасетов завершена")
    except Exception as e:
        logger.error(f"Критическая ошибка в основном процессе: {e}", exc_info=True)


if __name__ == "__main__":
    # Запуск асинхронной функции
    asyncio.run(main())
