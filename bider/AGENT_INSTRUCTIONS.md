# Инструкция для Cursor Automation

Следуй `bider/SKILL.md`. Секреты кабинета не вставляй в текст.

Цифры ниши бери из блока в промпте и из `bider/cabinets/<id>.json`. Что именно меняется между кабинетами и готовый текст для вставки — в `bider/cabinets/PROMPT.md`.

Запуск кабинета из файла:

```bash
cd bider && python3 avito_autobidder.py --cabinet <id>
```

`write_bids: да` в блоке → добавь `--apply`. `buy_vas: да` → добавь `--apply-vas`. Иначе ставки и XL/цвет/плашки только считаются.

Лог после каждого часа: `bider/logs/YYYY-MM-DD-HH.md` и `bider/logs/LATEST.md`, пуш в ветку `xz`. Если купил VAS — закоммить `bider/state/vas_ledger.json`. Секреты и сырые чаты в лог не писать.
