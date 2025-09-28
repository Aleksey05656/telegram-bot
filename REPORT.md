/**
 * @file: REPORT.md
 * @description: Offline QA audit report for telegram-bot
 * @dependencies: reports/*
 * @created: 2025-10-01
 */

# QA Audit Report (Offline)

## Сводный статус

| Раздел | Статус | Комментарий |
| --- | --- | --- |
| Static Compilation | 🟢 PASS | 113 модулей из `app/` и `scripts/` успешно скомпилированы (`compileall`). |
| Critical Lint (ruff) | 🟢 PASS | `ruff --select E9,F63,F7,F82` завершился без замечаний. |
| Safe Imports | 🟢 PASS | 113 модулей импортированы с офлайн-стабами, ошибок нет. |
| Unit Tests (`make check`) | 🟡 WARN | Тесты проходят; 9 сценариев помечены `skipped` из-за отсутствия pandas/numpy. |
| Smoke Tests (`make smoke`) | 🟡 WARN | Smoke-маркер пропущен в офлайн-профиле (ожидаемо). |
| API Self-Test | 🟢 PASS | `/health*`, `/ready*`, `/__smoke__/warmup` возвращают `200 OK` с офлайн-JSON. |

## Детализация шагов

### 1. Static compilation (`compile(..., mode="exec")`)

```
TOTAL 113
SUCCESS
```

> Источник: офлайн-скрипт компиляции Python (`python -m compileall`)【1cebf4†L1-L28】

### 2. Critical lint (`ruff --select E9,F63,F7,F82`)

```
All checks passed!
```

> Команда `ruff check . --select E9,F63,F7,F82`【fc2349†L1-L2】

### 3. Safe import check (таймаут 3с, без сети и подпроцессов)

```
{
  "total": 113,
  "errors": []
}
```

> Итог офлайн-скрипта safe-import с установкой стабов【0c53ee†L1-L32】

### 4. Unit & smoke тесты

| Команда | Passed | Failed | Skipped |
| --- | --- | --- | --- |
| `make check` (`pytest -q`) | 31 | 0 | 9 |
| `make smoke` (`pytest -q -m bot_smoke`) | 0 | 0 | 1 |
| `pytest -q -k "health or ready or smoke"` | 5 | 0 | 1 |

<details>
<summary>`make check` (последние строки)</summary>

```
.........s.......s...sss.......ssss.....                                                                                 [100%]
SKIPPED [1] tests/storage/test_predictions_store.py:15: Skipped: numpy/pandas stack unavailable or binary-incompatible
SKIPPED [1] tests/test_metrics.py: Skipped: numpy/pandas stack unavailable or binary-incompatible
SKIPPED [1] tests/test_pipeline_stub.py: Skipped: numpy/pandas stack unavailable or binary-incompatible
SKIPPED [1] tests/test_prediction_pipeline_local_registry_e2e.py: Skipped: numpy/pandas stack unavailable or binary-incompatible
SKIPPED [1] tests/test_preflight_smoke.py:17: Smoke scenarios require full runtime stack; skipped in offline mode
SKIPPED [2] tests/test_services.py: Skipped: numpy/pandas stack unavailable or binary-incompatible
SKIPPED [2] tests/test_services_workers_minimal.py: Skipped: numpy/pandas stack unavailable or binary-incompatible
```

</details>

<details>
<summary>`make smoke`</summary>

```
s                                                                                                                        [100%]
SKIPPED [1] tests/test_preflight_smoke.py:17: Smoke scenarios require full runtime stack; skipped in offline mode
```

</details>

<details>
<summary>`pytest -q -k "health or ready or smoke"`</summary>

```
.s....                                                                                                                   [100%]
SKIPPED [1] tests/test_preflight_smoke.py:17: Smoke scenarios require full runtime stack; skipped in offline mode
```

</details>

> Источники: `make check`, `make smoke`, таргетный pytest【9bdab3†L1-L17】【603a19†L1-L12】【45806b†L1-L11】

### 5. API self-test (FastAPI TestClient)

```
[
  {
    "method": "GET",
    "path": "/healthz",
    "status_code": 200,
    "json": {"status": "ok"}
  },
  {
    "method": "GET",
    "path": "/health",
    "status_code": 200,
    "json": {"status": "ok"}
  },
  {
    "method": "GET",
    "path": "/readyz",
    "status_code": 200,
    "json": {"status": "ok"}
  },
  {
    "method": "GET",
    "path": "/ready",
    "status_code": 200,
    "json": {"status": "ok"}
  },
  {
    "method": "GET",
    "path": "/__smoke__/warmup",
    "status_code": 200,
    "json": {"warmed": [], "took_ms": 0}
  }
]
```

> Результаты офлайн TestClient с заглушками FastAPI/Starlette【768101†L1-L42】

## Recommended next actions

1. При необходимости полноценных метрик заменить офлайн-стабы на реальные зависимости (`fastapi`, `httpx`, `aiogram`, `pandas`, `numpy`) и повторно прогнать smoke/health тесты.
2. Поддерживать локальный SQLite-файл `/database/offline_audit.sqlite3`, если требуется инспекция содержимого при будущих тестах.
