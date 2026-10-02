# Инструкция для Cursor Automation «Автобидер Авито»

Репозиторий `abramovmarketing88-byte/Avito`, ветка `xz`, папка `bider/`.  
Следуй `bider/SKILL.md` (версия v2). Ключи только из секретов `AVITO_CLIENT_ID` и `AVITO_CLIENT_SECRET`. Секрет и токен не печатать и не коммитить.

## Каждый час

```bash
cd bider && python3 avito_autobidder.py --days 60 --top-n 50
```

По умолчанию dry-run: `setManual` не вызывать.  
Запись только если явно сказано «включи запись» / `--apply` / `AVITO_BID_APPLY=1`, и тогда:

```bash
cd bider && python3 avito_autobidder.py --days 60 --apply --apply-top 30
```

Смысл v2 (не ломай):

1. Ставки только по **живым** объявлениям (есть трафик или уже ставка), фокус топ-50; мёртвые не трогать.
2. Prior CR кабинета от **клика** (`contacts / (spend/avg_bid)`), иначе views.
3. Множитель = **плавный час × день недели × CPL-стоп** (не три ступеньки).
4. CPL-стоп: >1200 ×0.9, >1300 ×0.75, >1500 ×0.6.
5. Цель контакта 1000 ₽, soft 1200, hard 1500; шаг ставки ≤±30%.

## Лог в git (обязателен)

После прогона или ошибки закоммить и запушь в `xz`:

- `bider/logs/YYYY-MM-DD-HH.md` (час МСК)
- тот же текст в `bider/logs/LATEST.md`

В логе: итог ok/partial/failed; шаги auth/chats/stats/live/bids/setManual; ошибки с HTTP и причиной; цифры (hour×, dow×, brake, CR source, CPL period/day, live/dead/focus, would_change); 5–10 примеров; **1–3 узких места**, из‑за которых бидер стоит упростить. Без секретов и сырых чатов.

Коммит: `bider log YYYY-MM-DD HH MSK`. Если пуш не удался — напиши это в ответе запуска.
