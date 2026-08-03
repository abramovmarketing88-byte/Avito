# Chat export as brief source

When the user attaches an Avito chat export (`export_*.txt`), use it as the primary brief.

## File format

```
=== Чат: ... | Объявление: «Title» | Категория: ... ===
[date] Клиент: ...
[date] Я: ...
```

## What to extract

1. **Ad titles** — regex: `Объявление: «([^»]+)»`
2. **Services** — from client messages: ИП, ООО, УСН, маркетплейсы, 3-НДФЛ, патент, НДС, открытие, восстановление
3. **Phone** — from agent replies: `+7 905 623 6202`
4. **Work mode** — online по всей России
5. **Client segments** — taxi drivers, construction, marketplaces, retail, NKO, self-employed

## Service lines (from typical export)

- Ведение бухгалтерии ИП / ООО / НКО под ключ
- УСН, патент, ОСНО, НДС 2026
- Маркетплейсы: Ozon, Wildberries
- 3-НДФЛ, декларации физлиц
- Открытие ИП и ООО
- Восстановление учёта, аудит после ухода бухгалтера
- Зарплата, кадры, 1С
- Консультации, оптимизация налогов

## Usage in pipeline

- Stage 0: parse export → fill session state §0 without re-asking known facts
- Stage 1–2: derive ЦА and headlines from real client questions in export
- Stage 3: use extracted ad titles as headline pool

Store export copy in `data/avito-chat-export.txt`.
