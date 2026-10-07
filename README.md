# Avito

Ветка `xz` — рабочий контур облачного автобидера.

## Папка [`bider/`](bider/)

| Файл | Назначение |
|------|------------|
| [`SKILL.md`](bider/SKILL.md) | Полный скилл: кабинет, формула, пики часов, API, антипаттерны |
| [`AGENT_INSTRUCTIONS.md`](bider/AGENT_INSTRUCTIONS.md) | Короткий промпт для Cursor Automation |
| [`logs/`](bider/logs/) | Лог каждого прогона: что прошло, что упало и почему |
| [`avito_autobidder.py`](bider/avito_autobidder.py) | Скрипт расчёта/записи ставок |
| [`run_hourly.sh`](bider/run_hourly.sh) | Обёртка для cron |
| [`.env.example`](bider/.env.example) | Шаблон ключей (без секретов) |

Ключи Авито в git не класть — только секреты автоматизации или локальный `.env.local`.
