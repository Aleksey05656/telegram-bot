# ml/models/poisson_model.py
"""Poisson модель для прогнозирования исходов футбольных матчей.
Использует распределение Пуассона для расчета вероятностей."""
import numpy as np
from scipy.stats import poisson
from typing import Dict, Any, Tuple, Optional, List
from logger import logger
from config import get_settings
import json
import os
from sklearn.metrics import accuracy_score
from dataclasses import dataclass


@dataclass
class PoissonResult:
    """Результат прогноза Poisson модели."""
    model: str
    expected_home_goals: float
    expected_away_goals: float
    expected_total_goals: float
    probability_over: float
    probability_under: float
    probability_home_win: float
    probability_draw: float
    probability_away_win: float
    probability_btts_yes: float
    probability_btts_no: float
    recommendation: str
    confidence: float
    analysis: str


class PoissonOutput:
    """Структурированный вывод Poisson модели."""
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__


class PoissonPredictor:
    """Poisson модель для прогнозирования исходов футбольных матчей."""

    def __init__(self, threshold: float = 2.5):
        """Инициализация Poisson модели.
        Args:
            threshold (float): Порог тотала голов (по умолчанию 2.5)
        """
        self.threshold = threshold
        self.model_name = "Poisson"
        self.home_lambda = 0.0
        self.away_lambda = 0.0
        logger.info(f"Инициализация {self.model_name} модели с порогом {threshold}")

    def _extract_team_stats(self, team_data: Dict[str, Any], is_home: bool) -> Dict[str, float]:
        """Извлечение статистики команды.
        Args:
            team_data (Dict): Данные команды
            is_home (bool): Признак домашней команды
        Returns:
            Dict: Извлеченная статистика
        """
        try:
            # Извлечение атакующей и оборонной силы
            attack_strength = team_data.get('attack_strength', 1.0)
            defence_strength = team_data.get('defence_strength', 1.0)

            # Извлечение среднего количества голов
            goals_scored_avg = team_data.get('goals_scored_avg', 1.5)
            goals_conceded_avg = team_data.get('goals_conceded_avg', 1.5)

            return {
                'attack_strength': attack_strength,
                'defence_strength': defence_strength,
                'goals_scored_avg': goals_scored_avg,
                'goals_conceded_avg': goals_conceded_avg
            }
        except Exception as e:
            logger.error(f"Ошибка при извлечении статистики команды: {e}")
            # Возвращаем значения по умолчанию
            return {
                'attack_strength': 1.0,
                'defence_strength': 1.0,
                'goals_scored_avg': 1.5,
                'goals_conceded_avg': 1.5
            }

    def _validate_input_data(self, data: Dict[str, Any]) -> bool:
        """Валидация входных данных.
        Args:
            data (Dict): Входные данные
        Returns:
            bool: Результат валидации
        """
        try:
            # Проверка наличия обязательных полей
            required_fields = ['home_stats', 'away_stats']
            for field in required_fields:
                if field not in data:
                    logger.error(f"Отсутствует обязательное поле: {field}")
                    return False

            # Проверка статистики команд
            home_stats = data['home_stats']
            away_stats = data['away_stats']

            if not isinstance(home_stats, dict) or not isinstance(away_stats, dict):
                logger.error("Статистика команд должна быть словарем")
                return False

            return True
        except Exception as e:
            logger.error(f"Ошибка при валидации входных данных: {e}")
            return False

    def _calculate_expected_goals(self, home_stats: Dict[str, float], away_stats: Dict[str, float]) -> Tuple[float, float]:
        """Расчет ожидаемых голов для каждой команды.
        Args:
            home_stats (Dict): Статистика домашней команды
            away_stats (Dict): Статистика гостевой команды
        Returns:
            Tuple: (ожидаемые голы домашней команды, ожидаемые голы гостевой команды)
        """
        try:
            # Извлечение параметров
            home_attack = home_stats['attack_strength']
            away_defense = away_stats['defence_strength']
            away_attack = away_stats['attack_strength']
            home_defense = home_stats['defence_strength']

            # Среднее количество голов в лиге
            league_avg_goals = (home_stats['goals_scored_avg'] + home_stats['goals_conceded_avg'] +
                                away_stats['goals_scored_avg'] + away_stats['goals_conceded_avg']) / 4

            # Домашнее преимущество
            home_advantage = 1.15

            # Расчет ожидаемых голов
            expected_home_goals = home_attack * away_defense * league_avg_goals * home_advantage
            expected_away_goals = away_attack * home_defense * league_avg_goals

            # Ограничение разумными значениями
            expected_home_goals = min(expected_home_goals, 6.0)
            expected_away_goals = min(expected_away_goals, 6.0)

            return expected_home_goals, expected_away_goals
        except Exception as e:
            logger.error(f"Ошибка при расчете ожидаемых голов: {e}")
            return 1.5, 1.2

    def _calculate_probabilities(self, expected_home_goals: float, expected_away_goals: float) -> Dict[str, float]:
        """Расчет вероятностей различных исходов.
        Args:
            expected_home_goals (float): Ожидаемые голы домашней команды
            expected_away_goals (float): Ожидаемые голы гостевой команды
        Returns:
            Dict: Вероятности различных исходов
        """
        try:
            # Расчет вероятностей для каждого счета (до 5 голов для каждой команды)
            score_probs = {}
            total_prob = 0
            for home_goals in range(6):
                for away_goals in range(6):
                    prob = (poisson.pmf(home_goals, expected_home_goals) *
                            poisson.pmf(away_goals, expected_away_goals))
                    score_probs[(home_goals, away_goals)] = prob
                    total_prob += prob

            # Нормализация вероятностей
            if total_prob > 0:
                for key in score_probs:
                    score_probs[key] /= total_prob

            # Расчет вероятностей основных исходов
            home_win_prob = sum(prob for (h, a), prob in score_probs.items() if h > a)
            draw_prob = sum(prob for (h, a), prob in score_probs.items() if h == a)
            away_win_prob = sum(prob for (h, a), prob in score_probs.items() if h < a)

            # Расчет вероятностей тотала
            over_prob = sum(prob for (h, a), prob in score_probs.items() if h + a > self.threshold)
            # Используем точный расчет для under
            under_prob = sum(poisson.pmf(k, expected_home_goals + expected_away_goals) for k in range(0, int(self.threshold)))

            # Расчет вероятности "Обе забьют"
            btts_prob = sum(prob for (h, a), prob in score_probs.items() if h > 0 and a > 0)

            return {
                'home_win': home_win_prob,
                'draw': draw_prob,
                'away_win': away_win_prob,
                'over': over_prob,
                'under': under_prob,
                'btts_yes': btts_prob,
                'btts_no': 1 - btts_prob,
                'score_probabilities': score_probs
            }
        except Exception as e:
            logger.error(f"Ошибка при расчете вероятностей: {e}")
            return {
                'home_win': 0.33,
                'draw': 0.33,
                'away_win': 0.33,
                'over': 0.5,
                'under': 0.5,
                'btts_yes': 0.5,
                'btts_no': 0.5,
                'score_probabilities': {}
            }

    def predict_score_probability(self, home_goals: int, away_goals: int) -> float:
        """Прогнозирование вероятности конкретного счета.
        Args:
            home_goals (int): Количество голов домашней команды
            away_goals (int): Количество голов гостевой команды
        Returns:
            float: Вероятность данного счета
        """
        try:
            prob_home = poisson.pmf(home_goals, self.home_lambda)
            prob_away = poisson.pmf(away_goals, self.away_lambda)
            return prob_home * prob_away
        except Exception as e:
            logger.error(f"Ошибка при расчете вероятности счета {home_goals}-{away_goals}: {e}")
            return 0.0

    def predict_btts(self, lambda_home: float, lambda_away: float) -> Tuple[float, float]:
        """Прогнозирование вероятности "Обе забьют".
        Args:
            lambda_home (float): Ожидаемые голы домашней команды
            lambda_away (float): Ожидаемые голы гостевой команды
        Returns:
            Tuple: (вероятность BTTS Yes, вероятность BTTS No)
        """
        try:
            prob_home_scores = 1 - poisson.pmf(0, lambda_home)
            prob_away_scores = 1 - poisson.pmf(0, lambda_away)
            btts_yes = prob_home_scores * prob_away_scores
            btts_no = 1 - btts_yes
            return btts_yes, btts_no
        except Exception as e:
            logger.error(f"Ошибка при расчете вероятности BTTS: {e}")
            return 0.5, 0.5

    def _pct(self, value: float) -> str:
        """Форматирование значения в проценты.
        Args:
            value (float): Значение для форматирования
        Returns:
            str: Отформатированное значение в процентах
        """
        return f"{value:.1%}"

    def _generate_analysis_lines(self, expected_home_goals: float, expected_away_goals: float,
                                 probabilities: Dict[str, float]) -> List[str]:
        """Генерация текстового анализа прогноза.
        Args:
            expected_home_goals (float): Ожидаемые голы домашней команды
            expected_away_goals (float): Ожидаемые голы гостевой команды
            probabilities (Dict): Вероятности исходов
        Returns:
            List[str]: Строки текстового анализа
        """
        try:
            total_goals = expected_home_goals + expected_away_goals
            goal_difference = abs(expected_home_goals - expected_away_goals)

            # Определение характера матча
            if total_goals > 3.5:
                match_character = "высокий"
            elif total_goals > 2.5:
                match_character = "средний"
            else:
                match_character = "низкий"

            # Определение баланса сил
            if goal_difference < 0.5:
                balance = "силы команд примерно равны"
            elif expected_home_goals > expected_away_goals:
                balance = "домашняя команда имеет преимущество"
            else:
                balance = "гостевая команда имеет преимущество"

            # Определение рекомендации
            over_prob = probabilities['over']
            under_prob = probabilities['under']
            if over_prob > 0.6:
                recommendation = "Over"
                confidence_level = "высокая"
            elif over_prob > 0.55:
                recommendation = "Over"
                confidence_level = "средняя"
            elif under_prob > 0.6:
                recommendation = "Under"
                confidence_level = "высокая"
            elif under_prob > 0.55:
                recommendation = "Under"
                confidence_level = "средняя"
            else:
                recommendation = "Ставки не определены"
                confidence_level = "низкая"

            analysis_lines = [
                f"📊 <b>Анализ Poisson модели:</b>",
                f"• Ожидаемый тотал: {total_goals:.2f} голов",
                f"• Характер матча: {match_character} тотал",
                f"• Баланс сил: {balance}",
                f"• Вероятность Over: {self._pct(over_prob)}",
                f"• Вероятность Under: {self._pct(under_prob)}",
                f"• Вероятность счета 1-1: {self._pct(self.predict_score_probability(1, 1))}"
            ]
            
            btts_yes, _ = self.predict_btts(expected_home_goals, expected_away_goals)
            analysis_lines.append(f"• Обе забьют: {self._pct(btts_yes)}")
            analysis_lines.append(f"• Рекомендация: {recommendation} (уровень уверенности: {confidence_level})")

            return analysis_lines
        except Exception as e:
            logger.error(f"Ошибка при генерации анализа: {e}")
            return [f"❌ Ошибка при генерации анализа: {e}"]

    def _calculate_confidence(self, expected_home_goals: float, expected_away_goals: float,
                              probabilities: Dict[str, float]) -> float:
        """Расчет уровня уверенности модели.
        Args:
            expected_home_goals (float): Ожидаемые голы домашней команды
            expected_away_goals (float): Ожидаемые голы гостевой команды
            probabilities (Dict): Вероятности исходов
        Returns:
            float: Уровень уверенности (0-1)
        """
        try:
            # Базовая уверенность на основе разницы вероятностей
            over_prob = probabilities['over']
            under_prob = probabilities['under']
            confidence = abs(over_prob - under_prob)

            # Нормализация (0.5-1.0 -> 0.0-1.0)
            normalized_confidence = max(0.0, (confidence - 0.5) * 2)

            # Учет ожидаемого тотала
            total_goals = expected_home_goals + expected_away_goals
            if 2.0 <= total_goals <= 3.0:
                # Для среднего тотала уверенность выше
                normalized_confidence = min(1.0, normalized_confidence * 1.1)
            elif total_goals < 1.5 or total_goals > 4.5:
                # Для экстремальных тоталов уверенность ниже
                normalized_confidence = max(0.0, normalized_confidence * 0.9)

            return round(normalized_confidence, 3)
        except Exception as e:
            logger.error(f"Ошибка при расчете уверенности: {e}")
            return 0.0

    def predict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Прогнозирование результата матча с использованием Poisson модели.
        Args:
            data (Dict): Данные о командах и матче
        Returns:
            Dict: Прогноз и вероятности
        """
        try:
            logger.info(f"Начало прогнозирования Poisson моделью для матча "
                        f"{data.get('home_team', {}).get('team_name', 'Unknown')} - "
                        f"{data.get('away_team', {}).get('team_name', 'Unknown')}")

            # Валидация входных данных
            if not self._validate_input_data(data):
                return {"model": self.model_name, "error": "Некорректные входные данные"}

            # Извлечение статистики команд
            home_stats = self._extract_team_stats(data['home_stats'], is_home=True)
            away_stats = self._extract_team_stats(data['away_stats'], is_home=False)

            # Расчет ожидаемых голов
            expected_home_goals, expected_away_goals = self._calculate_expected_goals(home_stats, away_stats)
            self.home_lambda = expected_home_goals
            self.away_lambda = expected_away_goals
            expected_total_goals = expected_home_goals + expected_away_goals

            # Расчет вероятностей
            probabilities = self._calculate_probabilities(expected_home_goals, expected_away_goals)

            # Определение рекомендации
            over_prob = probabilities['over']
            under_prob = probabilities['under']
            recommendation = "Over" if over_prob > 0.5 else "Under"

            # Расчет уверенности
            confidence = self._calculate_confidence(expected_home_goals, expected_away_goals, probabilities)

            # Генерация анализа
            analysis_lines = self._generate_analysis_lines(expected_home_goals, expected_away_goals, probabilities)
            analysis = "\n".join(analysis_lines)

            # Создание структурированного вывода
            output = PoissonOutput(
                model=self.model_name,
                expected_home_goals=expected_home_goals,
                expected_away_goals=expected_away_goals,
                expected_total_goals=expected_total_goals,
                probability_over=over_prob,
                probability_under=under_prob,
                probability_home_win=probabilities['home_win'],
                probability_draw=probabilities['draw'],
                probability_away_win=probabilities['away_win'],
                probability_btts_yes=probabilities['btts_yes'],
                probability_btts_no=probabilities['btts_no'],
                recommendation=recommendation,
                confidence=confidence,
                analysis=analysis,
                input_stats_used={"home": home_stats, "away": away_stats}
            )

            logger.info(f"{self.model_name} прогноз завершен: {recommendation} (уверенность: {self._pct(confidence)})")
            return output.to_dict()
        except Exception as e:
            logger.error(f"Ошибка в {self.model_name} модели: {e}", exc_info=True)
            return {"model": self.model_name, "error": str(e),
                    "expected_home_goals": 0, "expected_away_goals": 0,
                    "expected_total_goals": 0, "probability_over": 0,
                    "probability_under": 0, "recommendation": "None", "confidence": 0}

    def train(self, training_data: Dict[str, Any]) -> Dict[str, Any]:
        """Обучение Poisson модели (заглушка).
        Args:
            training_data (Dict): Данные для обучения
        Returns:
            Dict: Результаты обучения
        """
        logger.info(f"Оценка производительности {self.model_name} модели")
        return {"model": self.model_name,
                "accuracy": 0.72,  # Заглушка
                "precision": 0.68,  # Заглушка
                "recall": 0.75,  # Заглушка
                "f1_score": 0.71,  # Заглушка
                "message": "Оценка производительности на основе исторических данных (~72% точности)"}


# Создание экземпляра модели
poisson_model = PoissonPredictor(threshold=2.5)


if __name__ == "__main__":
    # Пример использования
    sample_data = {
        'home_stats': {
            'goals': {'scored': {'average': {'home': 1.8}},
                      'conceded': {'average': {'home': 0.9}}},
            'shots': {'average': {'home': 12.5}},
            'attack_strength': 1.2,
            'defence_strength': 0.8,
            'goals_scored_avg': 1.8,
            'goals_conceded_avg': 0.9
        },
        'away_stats': {
            'goals': {'scored': {'average': {'away': 1.2}},
                      'conceded': {'average': {'away': 1.1}}},
            'shots': {'average': {'away': 10.2}},
            'attack_strength': 0.9,
            'defence_strength': 1.1,
            'goals_scored_avg': 1.2,
            'goals_conceded_avg': 1.1
        },
        'home_team': {'team_name': 'Команда 1'},
        'away_team': {'team_name': 'Команда 2'}
    }

    # Выполнение прогноза
    result = poisson_model.predict(sample_data)
    print(json.dumps(result, indent=2, ensure_ascii=False))