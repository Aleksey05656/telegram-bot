# telegram/utils/formatter.py
"""Утилиты для форматирования прогнозов."""
# Добавлен Union в импорт typing на случай использования в этом модуле или при импорте
from typing import Any

from logger import logger  # Импортируем logger для логирования ошибок форматирования


def _pct(value: float | int) -> str:
    """Преобразование числа в проценты.

    Args:
        value (Union[float, int]): Значение для преобразования (0-1 или 0-100)

    Returns:
        str: Отформатированное значение в процентах
    """
    try:
        # Если значение в диапазоне 0-1, умножаем на 100
        if isinstance(value, float | int) and 0 <= value <= 1:
            return f"{value * 100:.1f}%"
        # Если значение уже в диапазоне 0-100, просто форматируем
        elif isinstance(value, float | int):
            return f"{value:.1f}%"
        else:
            # Если это строка или другой тип, возвращаем как есть
            return str(value)
    except Exception as e:
        logger.error(f"Ошибка при форматировании процента для значения {value}: {e}")
        return "N/A"


def _format_top_scores(top_scores: dict[str, float]) -> str:
    """Форматирование топ прогнозов точного счета.

    Args:
        top_scores (Dict[str, float]): Словарь счетов и их вероятностей

    Returns:
        str: Отформатированная строка с топ счетами
    """
    try:
        if not top_scores:
            return "Данные недоступны"

        # Сортируем счета по вероятности (от высокой к низкой) и берем топ-3
        sorted_scores = sorted(top_scores.items(), key=lambda x: x[1], reverse=True)[:3]

        formatted_scores = []
        for score, prob in sorted_scores:
            formatted_prob = _pct(prob)
            formatted_scores.append(f"  {score}: {formatted_prob}")

        return "\n".join(formatted_scores) if formatted_scores else "Данные недоступны"
    except Exception as e:
        logger.error(f"Ошибка при форматировании топ счетов: {e}")
        return "Ошибка форматирования"


def format_prediction_result(prediction_result: dict[str, Any]) -> str:
    """Форматирование результата прогноза для отправки пользователю.

    Args:
        prediction_result (Dict[str, Any]): Результат прогноза

    Returns:
        str: Отформатированный текст прогноза
    """
    try:
        if prediction_result.get("error"):
            error_msg = prediction_result.get("message", "Неизвестная ошибка")
            logger.warning(
                f"Форматирование результата: получен прогноз с ошибкой: {error_msg}"
            )
            return f"❌ Ошибка: {error_msg}"

        # Основная информация о матче
        match_info = prediction_result.get("match", "Матч не определен")
        base_goals = prediction_result.get("base_expected_goals", {})
        mod_goals = prediction_result.get("modified_expected_goals", {})

        # Вероятности исходов
        probs = prediction_result.get("probabilities", {})
        p1 = probs.get("1", 0) * 100  # Преобразуем в проценты, если они в диапазоне 0-1
        x = probs.get("X", 0) * 100
        p2 = probs.get("2", 0) * 100

        # Тоталы
        over_2_5 = prediction_result.get("over_2_5", 0)
        # Преобразуем в проценты, если нужно
        if isinstance(over_2_5, float) and 0 <= over_2_5 <= 1:
            over_2_5 *= 100

        under_2_5 = prediction_result.get("under_2_5", 0)
        # Преобразуем в проценты, если нужно
        if isinstance(under_2_5, float) and 0 <= under_2_5 <= 1:
            under_2_5 *= 100

        # Обе забьют
        btts_yes = prediction_result.get("btts_yes", 0)
        btts_no = prediction_result.get("btts_no", 0)
        # Преобразуем в проценты, если нужно
        if isinstance(btts_yes, float) and 0 <= btts_yes <= 1:
            btts_yes *= 100
        if isinstance(btts_no, float) and 0 <= btts_no <= 1:
            btts_no *= 100

        # Рекомендация и уверенность
        recommendation = prediction_result.get("recommendation", "Ставки не определены")
        confidence = prediction_result.get("confidence", "Неизвестно")
        risk_level = prediction_result.get("risk_level", "высокий")

        # Топ счетов
        top_scores = prediction_result.get("top_scores", {})

        # Форматируем топ счета
        top_scores_text = _format_top_scores(top_scores)

        # Формируем текст для "Обе забьют"
        btts_text = f"Обе забьют: Да {_pct(btts_yes)} / Нет {_pct(btts_no)}"

        # Форматируем топ счета для отображения, учитывая, что вероятности могут быть в 0-1 или 0-100
        # top_scores_items = list(top_scores.items())[:3]
        # formatted_top_scores = []
        # for score, prob in top_scores_items:
        #     if isinstance(prob, float) and 0 <= prob <= 1:
        #         formatted_prob = f"{prob * 100:.1f}%"
        #     elif isinstance(prob, float):
        #         formatted_prob = f"{prob:.1f}%"
        #     else:
        #         formatted_prob = f"{prob}" # На случай, если это строка или другой тип
        #     formatted_top_scores.append(f"  {score}: {formatted_prob}")
        # top_scores_text = "\n".join(formatted_top_scores) if formatted_top_scores else "  Данные недоступны"

        formatted_text = (
            f"🔮 <b>Прогноз на матч:</b>\n"
            f"<b>{match_info}</b>\n\n"
            f"⚽ <b>Ожидаемые голы:</b>\n"
            f"  Базовые: {base_goals.get('home', 'N/A'):.2f} - {base_goals.get('away', 'N/A'):.2f}\n"
            f"  Скорректированные: {mod_goals.get('home', 'N/A'):.2f} - {mod_goals.get('away', 'N/A'):.2f}\n\n"
            f"📊 <b>Вероятности исходов:</b>\n"
            f"  Победа хозяев: {p1:.1f}%\n"
            f"  Ничья: {x:.1f}%\n"
            f"  Победа гостей: {p2:.1f}%\n\n"
            f"📈 <b>Тоталы:</b>\n"
            f"  Тотал больше 2.5: {_pct(over_2_5)}\n"
            f"  Тотал меньше 2.5: {_pct(under_2_5)}\n\n"
            f"👥 <b>{btts_text}</b>\n\n"
            f"🎯 <b>Рекомендация:</b>\n"
            f"  {recommendation}\n"
            f"  Уровень уверенности: {confidence} ({risk_level})\n\n"
            f"💯 <b>Топ точных счетов:</b>\n"
            f"{top_scores_text}"
        )

        logger.debug("Результат прогноза успешно отформатирован")
        return formatted_text

    except Exception as e:
        error_msg = f"❌ Ошибка при форматировании результата прогноза: {e}"
        logger.error(error_msg, exc_info=True)
        return error_msg
