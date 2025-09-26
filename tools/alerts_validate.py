"""
@file: tools/alerts_validate.py
@description: Validate Prometheus alert YAML syntax with optional PyYAML fallback.
@created: 2025-10-30
"""
from __future__ import annotations

from pathlib import Path


def _basic_yaml_checks(text: str) -> None:
    indent_stack = [0]
    block_indent: int | None = None
    for idx, raw in enumerate(text.splitlines(), 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or stripped == "---":
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if block_indent is not None and indent > block_indent:
            continue
        if block_indent is not None and indent <= block_indent:
            block_indent = None
        if indent % 2 != 0:
            raise SystemExit(f"Invalid indentation on line {idx}: expected multiples of two spaces")
        while indent_stack and indent < indent_stack[-1]:
            indent_stack.pop()
        current = indent_stack[-1] if indent_stack else 0
        if indent > current and indent - current != 2:
            raise SystemExit(f"Unexpected indentation step on line {idx}: got {indent}, expected {current + 2}")
        if indent > current:
            indent_stack.append(indent)
        if stripped.startswith("-"):
            if ":" in stripped.split("-", 1)[-1]:
                if stripped.endswith("|") or stripped.endswith(">"):
                    block_indent = indent
                continue
            if stripped == "-":
                continue
            continue
        if ":" not in stripped:
            raise SystemExit(f"Missing ':' separator on line {idx}")
        if stripped.endswith("|") or stripped.endswith(">"):
            block_indent = indent


def main() -> None:
    path = Path("monitoring/alerts.yaml")
    if not path.exists():
        raise SystemExit("monitoring/alerts.yaml not found")
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
    except ModuleNotFoundError:
        _basic_yaml_checks(text)
        print(f"{path} basic structure OK (PyYAML not installed)")
        return
    yaml.safe_load(text)
    print(f"{path} OK")


if __name__ == "__main__":
    main()
