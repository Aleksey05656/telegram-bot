# @file: test_env_contract.py
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_EXAMPLE = PROJECT_ROOT / ".env.example"

_ENV_PATTERN = re.compile(r"os\.environ\[['\"]([A-Z0-9_]+)['\"]\]")


def _env_keys_from_example() -> set[str]:
    keys: set[str] = set()
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        if key:
            keys.add(key)
    return keys


def _env_keys_from_code() -> set[str]:
    keys: set[str] = set()
    for path in PROJECT_ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in _ENV_PATTERN.finditer(text):
            after = text[match.end():].lstrip()
            if after.startswith("="):
                continue
            keys.add(match.group(1))
    return keys


def test_env_example_covers_os_environ_usage():
    example_keys = _env_keys_from_example()
    code_keys = _env_keys_from_code()
    missing = sorted(code_keys - example_keys)
    assert not missing, f"Отсутствуют ключи в .env.example: {missing}"
