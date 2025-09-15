"""
Запуск обучающего пайплайна с управлением версией модели.
Добавлен аргумент --model-version. Если не задан — версия генерируется по формату
из config.MODEL_VERSION_FORMAT (fallback: %Y%m%d%H%M%S), далее сохраняется в .env
и в артефакты models/model_version.txt, чтобы цепочка переобучение → деплой была согласованной.
"""
import argparse
import asyncio
import os
from datetime import datetime
from pathlib import Path

import pandas as pd

from config import get_settings
from logger import logger
from scripts.train_model import train_league_market


def _generate_model_version(fmt: str | None) -> str:
    fmt = fmt or "%Y%m%d%H%M%S"
    try:
        return f"v{datetime.now().strftime(fmt)}"
    except Exception:
        return f"v{datetime.now().strftime('%Y%m%d%H%M%S')}"


def _update_env_file(env_path: Path, key: str, value: str) -> None:
    """Обновляет или добавляет переменную key=value в .env."""
    env_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    found = False
    for line in lines:
        if not line.strip() or line.strip().startswith("#"):
            out.append(line)
            continue
        if line.split("=", 1)[0].strip() == key:
            out.append(f"{key}={value}")
            found = True
        else:
            out.append(line)
    if not found:
        out.append(f"{key}={value}")
    env_path.write_text("\n".join(out) + "\n", encoding="utf-8")


def _persist_model_version_artifacts(version: str, models_dir: Path) -> None:
    """Сохраняет версию модели в артефакты (models/model_version.txt)."""
    models_dir.mkdir(parents=True, exist_ok=True)
    (models_dir / "model_version.txt").write_text(version + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    """Парсинг аргументов командной строки."""
    parser = argparse.ArgumentParser(
        description="Run training pipeline with explicit model versioning."
    )
    parser.add_argument(
        "--model-version",
        type=str,
        default=None,
        help="Явно задать версию модели (например, v20250823). Если не задано — сгенерируется автоматически.",
    )
    return parser.parse_args()


async def run_training_pipeline(
    datasets: dict[int, pd.DataFrame], min_matches_threshold: int = 1500
) -> None:
    """
    Запуск пайплайна обучения для всех лиг.
    Args:
        datasets (Dict[int, pd.DataFrame]): Датасеты для каждой лиги
        min_matches_threshold (int): Минимальное количество матчей для отдельной лиги
    """
    try:
        logger.info("🚀 Запуск пайплайна обучения моделей")
        # Разделяем лиги на крупные и мелкие
        large_leagues = {}  # Лиги с достаточным количеством данных
        small_leagues = {}  # Лиги с недостаточным количеством данных
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
                        date_col="match_date",
                    )
                    logger.info(
                        f"Модель для лиги {league_id}, рынок {market} обучена. "
                        f"Сохраненные артефакты: {list(saved_paths.keys())}"
                    )
                except Exception as e:
                    logger.error(
                        f"Ошибка при обучении модели для лиги {league_id}, рынок {market}: {e}"
                    )
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
                        date_col="match_date",
                    )
                    logger.info(
                        f"Глобальная модель для рынка {market} обучена. "
                        f"Сохраненные артефакты: {list(saved_paths.keys())}"
                    )
                except Exception as e:
                    logger.error(f"Ошибка при обучении глобальной модели для рынка {market}: {e}")
                    continue
        logger.info("🏁 Пайплайн обучения моделей завершен")
    except Exception as e:
        logger.error(f"Критическая ошибка в пайплайне обучения: {e}", exc_info=True)


# === КОНЕЦ НОВОГО КОДА ДЛЯ ЭТАПА 9.2 ===


async def async_main() -> None:
    """Главная функция для запуска пайплайна обучения."""
    try:
        logger.info("🚀 Запуск пайплайна обучения моделей")
        # Загружаем датасеты (в реальной реализации из файлов или БД)
        datasets: dict[int, pd.DataFrame] = {}  # Загрузите реальные датасеты здесь
        if not datasets:
            logger.warning("Нет датасетов для обучения. Пожалуйста, сначала подготовьте датасеты.")
            return
        # Запускаем пайплайн обучения
        await run_training_pipeline(datasets, min_matches_threshold=1500)
        logger.info("🏁 Пайплайн обучения завершен")
    except Exception as e:
        logger.error(f"Критическая ошибка в основном процессе: {e}", exc_info=True)


def main() -> None:
    args = parse_args()
    settings = get_settings()
    model_version = args.model_version or _generate_model_version(
        getattr(settings, "MODEL_VERSION_FORMAT", "%Y%m%d%H%M%S")
    )
    _update_env_file(Path(".env"), "MODEL_VERSION", model_version)
    models_dir = Path(getattr(settings, "MODELS_DIR", "models"))
    _persist_model_version_artifacts(model_version, models_dir)
    os.environ["MODEL_VERSION"] = model_version
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
