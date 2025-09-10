<!--
@file: DEBT_CHECKLIST.md
@description: Checklist for upcoming technical debt fixes.
@dependencies: docs/changelog.md, docs/tasktracker.md
@created: 2025-09-10
-->
# Tech Debt Checklist
- [ ] Перенести реальную реализацию функций в `app/data_processor/*`.
- [ ] Реализовать обучение GLM (вместо DummyModel) и реестр моделей.
- [ ] Реализовать модификаторы вероятностей (инъекции контекста).
- [ ] CLI subcommand `retrain`.
- [ ] Повысить покрытие тестами до ≥80% для `data_processor`.
