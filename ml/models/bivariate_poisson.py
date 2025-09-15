# ml/models/bivariate_poisson.py
"""Bivariate Poisson модель для прогнозирования коррелированных исходов."""
import math
from typing import Any

import numpy as np
from scipy.special import gammaln

from logger import logger


class BivariatePoisson:
    """Bivariate Poisson модель для учета корреляции между голами команд."""

    def __init__(self, lam1: float, lam2: float, rho: float):
        """
        Инициализация Bivariate Poisson модели.
        Args:
            lam1 (float): Ожидаемые голы первой команды
            lam2 (float): Ожидаемые голы второй команды
            rho (float): Параметр корреляции (0 <= rho <= min(lam1, lam2))
        """
        self.l1 = max(0.01, lam1)  # Избегаем нуля
        self.l2 = max(0.01, lam2)  # Избегаем нуля
        # Ограничиваем rho допустимым диапазоном
        self.rho = max(0.0, min(rho, min(self.l1, self.l2)))
        logger.debug(
            f"Bivariate Poisson инициализирован: λ1={self.l1:.3f}, λ2={self.l2:.3f}, ρ={self.rho:.3f}"
        )

    def _log_prob(self, x: int, y: int) -> float:
        """
        Вычисление логарифма вероятности P(X=x, Y=y) через сумму по k.
        Args:
            x (int): Голы первой команды
            y (int): Голы второй команды
        Returns:
            float: log(P(X=x, Y=y))
        """
        try:
            # Специальный случай: если rho=0, то это произведение двух независимых Пуассонов
            if self.rho == 0:
                log_p = (
                    x * np.log(self.l1)
                    - self.l1
                    - gammaln(x + 1)
                    + y * np.log(self.l2)
                    - self.l2
                    - gammaln(y + 1)
                )
                return log_p
            # Верхняя граница суммы по k
            max_k = min(x, y)
            if max_k == 0:
                # Специальный случай: k может быть только 0
                log_p = (
                    x * np.log(self.l1 - self.rho)
                    - (self.l1 - self.rho)
                    - gammaln(x + 1)
                    + y * np.log(self.l2 - self.rho)
                    - (self.l2 - self.rho)
                    - gammaln(y + 1)
                    + -self.rho
                )
                return log_p
            # Вычисляем логарифмы вероятностей для каждого k
            log_probs = []
            for k in range(max_k + 1):
                log_prob_k = (
                    k * np.log(self.rho)
                    - self.rho
                    - gammaln(k + 1)
                    + (x - k) * np.log(self.l1 - self.rho)
                    - (self.l1 - self.rho)
                    - gammaln(x - k + 1)
                    + (y - k) * np.log(self.l2 - self.rho)
                    - (self.l2 - self.rho)
                    - gammaln(y - k + 1)
                )
                log_probs.append(log_prob_k)
            # Численно стабильное суммирование логарифмов вероятностей
            if len(log_probs) == 1:
                return log_probs[0]
            # Используем logsumexp для численной стабильности
            max_log_prob = max(log_probs)
            sum_exp = sum(np.exp(lp - max_log_prob) for lp in log_probs)
            return max_log_prob + np.log(sum_exp)
        except Exception as e:
            logger.error(f"Ошибка при вычислении лог-вероятности для ({x},{y}): {e}")
            return float("-inf")

    def prob(self, x: int, y: int) -> float:
        """
        Вычисление вероятности P(X=x, Y=y).
        Args:
            x (int): Голы первой команды
            y (int): Голы второй команды
        Returns:
            float: P(X=x, Y=y)
        """
        try:
            log_p = self._log_prob(x, y)
            return np.exp(log_p) if log_p > -700 else 0.0  # Избегаем underflow
        except Exception as e:
            logger.error(f"Ошибка при вычислении вероятности для ({x},{y}): {e}")
            return 0.0

    def prob_matrix(self, max_goals: int = 6) -> np.ndarray:
        """
        Генерация матрицы вероятностей для всех комбинаций голов.
        Args:
            max_goals (int): Максимальное количество голов для рассмотрения
        Returns:
            np.ndarray: Матрица вероятностей размером (max_goals+1) x (max_goals+1)
        """
        try:
            prob_matrix = np.zeros((max_goals + 1, max_goals + 1))
            for i in range(max_goals + 1):
                for j in range(max_goals + 1):
                    prob_matrix[i, j] = self.prob(i, j)
            logger.debug(f"Сгенерирована матрица вероятностей. Сумма: {prob_matrix.sum():.6f}")
            return prob_matrix
        except Exception as e:
            logger.error(f"Ошибка при генерации матрицы вероятностей: {e}")
            return np.zeros((max_goals + 1, max_goals + 1))

    def score_matrix(self, max_goals: int = 10) -> np.ndarray:
        """
        Генерация матрицы счетов.
        Args:
            max_goals (int): Максимальное количество голов
        Returns:
            np.ndarray: Матрица вероятностей счетов
        """
        return self.prob_matrix(max_goals)

    def calculate_marginals(self, max_goals: int = 6) -> tuple[np.ndarray, np.ndarray]:
        """
        Вычисление маргинальных распределений.
        Args:
            max_goals (int): Максимальное количество голов
        Returns:
            Tuple[np.ndarray, np.ndarray]: (P(X=x), P(Y=y))
        """
        try:
            prob_matrix = self.prob_matrix(max_goals)
            marginal_x = np.sum(prob_matrix, axis=1)
            marginal_y = np.sum(prob_matrix, axis=0)
            return marginal_x, marginal_y
        except Exception as e:
            logger.error(f"Ошибка при вычислении маргинальных распределений: {e}")
            return np.zeros(max_goals + 1), np.zeros(max_goals + 1)

    def calculate_btts(self, max_goals: int = 6) -> tuple[float, float]:
        """
        Вычисление вероятности "Обе забьют" (BTTS).
        Args:
            max_goals (int): Максимальное количество голов
        Returns:
            Tuple[float, float]: (P(BTTS=True), P(BTTS=False))
        """
        try:
            prob_matrix = self.prob_matrix(max_goals)
            btts_yes = np.sum(prob_matrix[1:, 1:])  # Обе команды забили хотя бы 1 гол
            btts_no = 1.0 - btts_yes
            return btts_yes, btts_no
        except Exception as e:
            logger.error(f"Ошибка при вычислении BTTS: {e}")
            return 0.5, 0.5

    def calculate_totals(self, threshold: float = 2.5, max_goals: int = 6) -> tuple[float, float]:
        """
        Вычисление вероятностей тотала.
        Args:
            threshold (float): Порог тотала
            max_goals (int): Максимальное количество голов
        Returns:
            Tuple[float, float]: (P(Over), P(Under))
        """
        try:
            prob_matrix = self.prob_matrix(max_goals)
            over_prob = 0.0
            under_prob = 0.0
            for i in range(max_goals + 1):
                for j in range(max_goals + 1):
                    total = i + j
                    if total > threshold:
                        over_prob += prob_matrix[i, j]
                    elif total < threshold:
                        under_prob += prob_matrix[i, j]
                    # Равенство (total == threshold) обычно не учитывается
            return over_prob, under_prob
        except Exception as e:
            logger.error(f"Ошибка при вычислении тоталов: {e}")
            return 0.5, 0.5

    def outcome_probabilities(self, max_goals: int = 10) -> dict[str, float]:
        """
        Вычисление вероятностей исходов рынков.
        Args:
            max_goals (int): Максимальное количество голов
        Returns:
            Dict[str,float]: Словарь вероятностей рынков
        """
        M = self.score_matrix(max_goals)
        # Вероятности основных исходов
        p_home = float(np.triu(M, k=1).sum())  # Победа домашней команды
        p_away = float(np.tril(M, k=-1).sum())  # Победа гостевой команды
        p_draw = float(np.trace(M))  # Ничья
        # Вероятности BTTS
        p_btts_yes = float(M[1:, 1:].sum())  # Обе забьют
        p_btts_no = 1.0 - p_btts_yes  # Ни одна не забьет
        # Вероятности тотала 2.5
        total_goals = np.add.outer(np.arange(M.shape[0]), np.arange(M.shape[1]))
        p_over_2_5 = float(np.sum(M[total_goals > 2.5]))
        p_under_2_5 = 1.0 - p_over_2_5
        return {
            "home": p_home,
            "draw": p_draw,
            "away": p_away,
            "btts_yes": p_btts_yes,
            "btts_no": p_btts_no,
            "over_2_5": p_over_2_5,
            "under_2_5": p_under_2_5,
        }


def estimate_rho(feature_vector: dict[str, Any], default_rho: float = 0.1) -> float:
    """
    Оценка параметра корреляции rho на основе признаков матча.
    Args:
        feature_vector (Dict[str, Any]): Вектор признаков матча
        default_rho (float): Значение rho по умолчанию
    Returns:
        float: Оцененное значение rho
    """
    try:
        # Извлекаем признаки для оценки rho
        style_mismatch = feature_vector.get("style_mismatch", 0.0)
        match_importance = feature_vector.get("match_importance", 0.5)
        fatigue_intensity = feature_vector.get("fatigue_intensity", 0.0)
        # Простая линейная модель для оценки rho
        # Чем больше несоответствие стилей, тем выше корреляция (обе команды могут забивать/не забивать)
        rho_estimate = (
            0.05
            + 0.08 * style_mismatch
            + 0.03 * (1 - match_importance)  # Влияние стилевого несоответствия
            + 0.04 * fatigue_intensity  # Влияние важности матча  # Влияние усталости
        )
        # Ограничиваем rho разумными значениями
        rho_estimate = max(0.0, min(rho_estimate, 0.3))
        logger.debug(f"Оценено rho: {rho_estimate:.3f} (style_mismatch={style_mismatch:.3f})")
        return rho_estimate
    except Exception as e:
        logger.error(f"Ошибка при оценке rho: {e}")
        return default_rho


# === НОВЫЕ ФУНКЦИИ ДЛЯ ЭТАПА 3 ===
# 3.1. API вероятностей рынков через двумерный Пуассон
def score_matrix(
    lam_home: float,
    lam_away: float,
    rho: float,
    max_goals: int = 10,
    apply_dixon_coles: bool = True,
) -> np.ndarray:
    pm = np.zeros((max_goals + 1, max_goals + 1), dtype=float)
    pmf = globals().get("bivariate_poisson_pmf", None)
    for gh in range(max_goals + 1):
        for ga in range(max_goals + 1):
            if pmf:
                pm[gh, ga] = pmf(gh, ga, lam_home, lam_away, rho)
            else:
                # независимая аппроксимация
                def pois(k, lam):
                    return (lam**k) * np.exp(-lam) / float(math.factorial(k))

                pm[gh, ga] = pois(gh, lam_home) * pois(ga, lam_away)
    if pm.sum() > 0:
        pm /= pm.sum()
    return pm


def outcome_probabilities(
    lam_home: float,
    lam_away: float,
    rho: float,
    max_goals: int = 10,
    apply_dixon_coles: bool = True,
) -> dict[str, float]:
    M = score_matrix(
        lam_home,
        lam_away,
        rho,
        max_goals=max_goals,
        apply_dixon_coles=apply_dixon_coles,
    )
    p_home = float(np.triu(M, k=1).sum())
    p_away = float(np.tril(M, k=-1).sum())
    p_draw = float(np.trace(M))
    return {
        "home": p_home,
        "draw": p_draw,
        "away": p_away,
    }


# === КОНЕЦ НОВЫХ ФУНКЦИЙ ===
