/**
 * @file: __init__.py
 * @description: Facade for the data_processor package with backward compatibility.
 * @dependencies: data_processor legacy module
 * @created: 2025-09-10
 */
# Фасад: импортируем из старого модуля для обратной совместимости
import data_processor as legacy
from .validators import validate_required_columns
from .feature_engineering import build_features
from .transformers import make_transformers
from .io import load_data, save_data
