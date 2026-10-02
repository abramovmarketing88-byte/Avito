# Инструкция для Cursor Automation «Автобидер Авито»

Репозиторий: `abramovmarketing88-byte/Avito`, ветка `xz`, папка `bider/`.

Следуй скиллу [`SKILL.md`](SKILL.md). Ключи только из секретов `AVITO_CLIENT_ID` / `AVITO_CLIENT_SECRET`. Секреты и токен не печатать.

Каждый час:

```bash
cd bider && python3 avito_autobidder.py --days 60
```

По умолчанию dry-run — `setManual` не вызывать. Запись ставок только если в запуске явно сказано «включи запись» / `--apply` / `AVITO_BID_APPLY=1`.

В конце короткий отчёт: час МСК, зона peak/normal/quiet, chats, CR, CPL, сколько объявлений изменил бы, 5–10 примеров. Без секретов.
