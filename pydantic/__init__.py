"""
/**
 * @file: pydantic/__init__.py
 * @description: Minimal stub of Pydantic interfaces required for offline testing.
 * @dependencies: typing, dataclasses, pathlib
 * @created: 2025-02-15
 */
"""

from __future__ import annotations

from dataclasses import is_dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple, TypeVar, get_args, get_origin

__all__ = [
    "BaseModel",
    "ValidationError",
    "Field",
    "computed_field",
    "field_validator",
]


_T = TypeVar("_T")


class ValidationError(Exception):
    """Exception raised when model validation fails."""


class _UnsetType:
    pass


_UNSET = _UnsetType()


class _FieldInfo:
    __slots__ = ("default", "default_factory", "alias")

    def __init__(
        self,
        *,
        default: Any = _UNSET,
        default_factory: Optional[Callable[[], Any]] = None,
        alias: Optional[str] = None,
    ) -> None:
        self.default = default
        self.default_factory = default_factory
        self.alias = alias


def Field(
    default: Any = _UNSET,
    *,
    default_factory: Optional[Callable[[], Any]] = None,
    alias: Optional[str] = None,
    **_: Any,
) -> _FieldInfo:
    """Return field metadata for stub models."""

    return _FieldInfo(default=default, default_factory=default_factory, alias=alias)


def computed_field(func: Optional[Callable[..., _T]] = None, **_: Any) -> Callable[[Callable[..., _T]], property]:
    """Decorator emulating pydantic.computed_field by returning property wrapper."""

    def decorator(inner: Callable[..., _T]) -> property:
        return property(inner)

    if func is not None:
        return decorator(func)
    return decorator


def field_validator(*fields: str, **_: Any) -> Callable[[Callable[..., _T]], Callable[..., _T]]:
    """Decorator placeholder that records validator targets for compatibility."""

    def decorator(func: Callable[..., _T]) -> Callable[..., _T]:
        func.__pydantic_validator_fields__ = fields  # type: ignore[attr-defined]
        return func

    return decorator


class BaseModel:
    """Very small subset of pydantic.BaseModel supporting defaults and naive coercion."""

    __pydantic_fields__: Dict[str, _FieldInfo]
    __pydantic_annotations__: Dict[str, Any]

    def __init_subclass__(cls, **kwargs: Any) -> None:  # pragma: no cover - class registration
        super().__init_subclass__(**kwargs)
        cls.__pydantic_fields__ = {}
        annotations: Dict[str, Any] = {}
        for base in reversed(cls.__mro__):
            annotations.update(getattr(base, "__annotations__", {}))
        cls.__pydantic_annotations__ = annotations
        for name in annotations:
            value = getattr(cls, name, _UNSET)
            if isinstance(value, _FieldInfo):
                cls.__pydantic_fields__[name] = value
            elif value is not _UNSET:
                cls.__pydantic_fields__[name] = _FieldInfo(default=value)
            else:
                cls.__pydantic_fields__[name] = _FieldInfo()

    def __init__(self, **data: Any) -> None:
        fields = self.__class__.__pydantic_fields__
        annotations = self.__class__.__pydantic_annotations__
        for name, info in fields.items():
            alias = info.alias
            if name in data:
                value = data.pop(name)
            elif alias and alias in data:
                value = data.pop(alias)
            elif info.default_factory is not None:
                value = info.default_factory()
            elif info.default is not _UNSET:
                value = info.default
            else:
                raise ValidationError(f"Missing field: {name}")
            value = self._coerce_value(value, annotations.get(name))
            setattr(self, name, value)
        for extra_key, extra_value in data.items():
            setattr(self, extra_key, extra_value)
        self._run_validators()

    @classmethod
    def _coerce_value(cls, value: Any, annotation: Any) -> Any:
        origin = get_origin(annotation)
        args = get_args(annotation)
        if annotation in (None, Any):
            return value
        if annotation in (str, int, float):
            try:
                return annotation(value)
            except Exception:
                return value
        if annotation is bool:
            if isinstance(value, str):
                return value.strip().lower() in {"1", "true", "yes", "on"}
            return bool(value)
        if origin is list:
            inner = args[0] if args else Any
            return [cls._coerce_value(item, inner) for item in cls._ensure_iterable(value)]
        if origin is tuple:
            inner = args[0] if args else Any
            return tuple(cls._coerce_value(item, inner) for item in cls._ensure_iterable(value))
        if origin is set:
            inner = args[0] if args else Any
            return {cls._coerce_value(item, inner) for item in cls._ensure_iterable(value)}
        if origin is dict:
            key_type = args[0] if args else Any
            val_type = args[1] if len(args) > 1 else Any
            return {
                cls._coerce_value(key, key_type): cls._coerce_value(val, val_type)
                for key, val in dict(value).items()
            }
        if origin is Optional:
            inner = args[0]
            return None if value is None else cls._coerce_value(value, inner)
        if isinstance(value, str) and annotation is Path:
            return Path(value)
        if isinstance(value, dict) and isinstance(annotation, type) and issubclass(annotation, BaseModel):
            return annotation(**value)
        if is_dataclass(annotation) and isinstance(value, dict):
            return annotation(**value)
        return value

    @staticmethod
    def _ensure_iterable(value: Any) -> Tuple[Any, ...]:
        if isinstance(value, (list, tuple, set)):
            return tuple(value)
        if isinstance(value, str):
            return tuple(item.strip() for item in value.split(",") if item.strip())
        return (value,)

    def _run_validators(self) -> None:
        for name in dir(self.__class__):
            attr = getattr(self.__class__, name)
            targets = getattr(attr, "__pydantic_validator_fields__", None)
            if not targets:
                continue
            for field in targets:
                current = getattr(self, field)
                if hasattr(attr, "__self__"):
                    result = attr(current)
                else:
                    result = attr(self.__class__, current)
                if result is not None:
                    setattr(self, field, result)

    def model_dump(self) -> Dict[str, Any]:
        return {
            field: getattr(self, field)
            for field in self.__class__.__pydantic_fields__.keys()
            if hasattr(self, field)
        }

    model_dump_json = model_dump

