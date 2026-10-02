# Инструкция для Cursor Automation «Автобидер Авито»

Репозиторий: `abramovmarketing88-byte/Avito`, ветка `xz`, папка `bider/`.

Следуй скиллу `bider/SKILL.md`. Ключи только из секретов `AVITO_CLIENT_ID` и `AVITO_CLIENT_SECRET`. Секрет и токен не печатать и не коммитить.

Каждый час:

```bash
cd bider && python3 avito_autobidder.py --days 60
```

По умолчанию dry-run: `setManual` не вызывать. Запись ставок только если явно сказано «включи запись», передан `--apply` или `AVITO_BID_APPLY=1`.

После прогона обязательно залогируй результат в git и запушь в ветку `xz`:

- новый файл `bider/logs/YYYY-MM-DD-HH.md` (час МСК);
- тот же текст в `bider/logs/LATEST.md`.

В логе: итог ok/partial/failed, таблица шагов (auth, chats, stats, spendings, bids, setManual), ошибки с HTTP-кодом и причиной, цифры (зона, CR, CPL, сколько ставок изменил бы), 5–10 примеров, 1–3 конкретных узких места этого прогона. Без секретов, без сырых чатов и имён клиентов.

Коммит: `bider log YYYY-MM-DD HH MSK`. Если пуш не удался — напиши это в ответе запуска.
