---
name: avito-factory
description: >-
  Полный пайплайн массовых объявлений для Авито: бриф или экспорт переписки → анализ
  ЦА → заголовки и спецофферы → креативы → объявления → аудит → спинтекст → CSV
  (Title, Description, Address). Пресет Татарстан: 200 объявлений (50 Казань, 20
  Набережные Челны, 130 города РТ). Use when user says avito factory, /avito-factory,
  массовая генерация объявлений Авито, спинтекст, CSV для Авито, 200 объявлений
  Татарстан, export_c68bc70d, переписка Авито как бриф.
disable-model-invocation: true
---

# Avito Factory

Оркестратор полного цикла: от брифа до CSV для массовой загрузки на Авито.

**Финальный результат:** `output/avito-ads-{slug}-{date}.csv` — колонки Title, Description, Address.

## Быстрый старт

1. Прочитай бриф пользователя (текст, файл, @mention).
2. Создай `output/session-{slug}.md` из [templates/session-state.md](templates/session-state.md).
3. Пройди этапы 0→8 строго по порядку.
4. На чекпоинтах жди подтверждения пользователя.
5. Отдай CSV + краткий отчёт.

**Slug** — транслит названия услуги, lowercase, через дефис (например `buhgalteriya-ip`).

---

## Быстрый путь: Татарстан 200 (из экспорта переписки)

Создай файл 200 объявлений республика татарстан: 50 разные адреса Казани, 20 разные Набережных Челнов и 130 остальные города и посёлки Татарстана.

Если пользователь прикладывает `export_*.txt` (переписка за полгода) — это **основной бриф**: услуги, заголовки объявлений, типичные вопросы клиентов.

### Шаги

1. Скопируй экспорт в `data/avito-chat-export.txt` (если ещё не там).
2. Прочитай [10-chat-export-brief.md](references/10-chat-export-brief.md).
3. Запусти:

```bash
python scripts/generate_tatarstan_200.py \
  --export data/avito-chat-export.txt \
  --output output/avito-ads-tatarstan-200.csv
```

4. Проверь: **ровно 200 строк**, распределение **50 / 20 / 130**.
5. Отдай файл `output/avito-ads-tatarstan-200.csv`.

Гео-правила: [11-tatarstan-geo-preset.md](references/11-tatarstan-geo-preset.md).

Для полного пайплайна с ЦА, аудитом и спинтекстом — этапы 0→8 ниже.

---

## Этапы пайплайна

```
0 Intake → 1 ЦА → 2 Креативы → 3 Объявления → 4 Аудит → 5 Спинтекст → 6 Масштаб → 7 CSV → [8 Фото]
```

| Этап | Что делать | Reference |
|------|------------|-----------|
| 0 | Сбор брифа, вопросы | [01-brief-intake.md](references/01-brief-intake.md) |
| 1 | Анализ ЦА, выбор сегмента | [02-audience-analysis.md](references/02-audience-analysis.md) + [03-avito-strategy.md](references/03-avito-strategy.md) |
| 2 | Заголовки, спецофферы, креативы | [04-creatives-offers.md](references/04-creatives-offers.md) |
| 3 | 3–4 базовых объявления | [05-ad-writing.md](references/05-ad-writing.md) |
| 4 | Аудит 12 уровней + правки | [06-audit-fix.md](references/06-audit-fix.md) |
| 5 | Спинтекст каждого объявления | [07-spintax.md](references/07-spintax.md) |
| 6 | Масштаб до N × города | session state §6 |
| 7 | Экспорт CSV | [08-csv-export.md](references/08-csv-export.md) |
| 8 | Фото (опционально) | [09-image-reverse.md](references/09-image-reverse.md) |
| — | Экспорт переписки как бриф | [10-chat-export-brief.md](references/10-chat-export-brief.md) |
| — | Пресет Татарстан 200 | [11-tatarstan-geo-preset.md](references/11-tatarstan-geo-preset.md) |

---

## Этап 0: Intake

Прочитай [01-brief-intake.md](references/01-brief-intake.md).

- Извлеки данные из брифа.
- Задай **пакетом** всё недостающее (города, количество, ограничения, фото).
- Заполни секцию «0. Бриф» в session state.
- **Не начинай этап 1** без: услуга, города/регион, количество объявлений.

---

## Этап 1: Анализ ЦА

Прочитай [02-audience-analysis.md](references/02-audience-analysis.md) и [03-avito-strategy.md](references/03-avito-strategy.md).

Выход в session state §1:
- 3–5 сегментов (боль, мотивация, приоритет)
- 1 выбранная ЦА с обоснованием
- язык клиента, возражения

**Чекпоинт 1:** покажи пользователю выбранную ЦА → жди «ок».

---

## Этап 2: Заголовки, спецофферы, креативы

Прочитай [04-creatives-offers.md](references/04-creatives-offers.md).

Выход в session state §2:
- 8–12 заголовков (ВЧ/СЧ/НЧ)
- 3–5 спецофферов
- 3–4 креативных угла для базовых объявлений

**Чекпоинт 2:** покажи заголовки, офферы, углы → жди выбор углов.

---

## Этап 3: Базовые объявления

Прочитай [05-ad-writing.md](references/05-ad-writing.md).

Создай **3–4** полных объявления (Title + HTML Description) — по одному на утверждённый угол.

Сохрани в session state §3.

---

## Этап 4: Аудит и правки

Прочитай [06-audit-fix.md](references/06-audit-fix.md).

Для каждого объявления:
1. Оцени по 12 уровням аудита
2. Перечисли правки
3. Выдай исправленную версию (Ad-X-fixed)

**Опционально — субагент-reviewer:** запусти `generalPurpose` subagent с текстом объявления + чеклистом из 06-audit-fix.md (без истории создания). Используй его замечания.

Сохрани в session state §4.

**Чекпоинт 3:** покажи исправленные объявления → жди «ок».

---

## Этап 5: Спинтекст

Прочитай [07-spintax.md](references/07-spintax.md).

Для **каждого** исправленного объявления создай спинтекст-шаблон:
- уровень 4+ (абзацы и предложения, не только слова)
- факты не менять
- HTML остаётся валидным
- формат: `{вариант1|вариант2|вариант3}`

Сохрани:
- session state §5
- `output/spintax-ad-a.txt`, `output/spintax-ad-b.txt`, …

---

## Этап 6: Масштабирование

Заполни session state §6:

```
Итого ≈ базы × варианты_заголовков × варианты_текста × города
```

Убедись, что итого ≥ запрошенного количества.

**Для 50+ строк:** запусти параллельные subagents (по одному на базовое объявление) для генерации дополнительных спинтекст-вариантов заголовков и тел.

---

## Этап 7: CSV

Прочитай [08-csv-export.md](references/08-csv-export.md).

### Малый объём (< 30 строк)

Собери CSV вручную: скопируй header из [templates/csv-header.csv](templates/csv-header.csv), добавь строки.

### Большой объём (30+ строк)

1. Подготовь файлы:
   - `output/titles-spintax.txt` — шаблоны заголовков (по строке или через `---`)
   - `output/bodies-spintax.txt` — шаблоны Description
   - `output/cities.txt` — города (по строке)

2. Запусти скрипт:

```bash
python scripts/expand_to_csv.py \
  --titles output/titles-spintax.txt \
  --bodies output/bodies-spintax.txt \
  --cities-file output/cities.txt \
  --count 200 \
  --output output/avito-ads-{slug}-{date}.csv \
  --seed 42
```

3. Проверь по чеклисту из 08-csv-export.md.

**Отдай пользователю:** путь к CSV + количество строк + краткая сводка (ЦА, углы, города).

---

## Этап 8: Фото (опционально)

Спроси на этапе 0 или после CSV: «Нужны фото / реверс-инжиниринг?»

Если да — прочитай [09-image-reverse.md](references/09-image-reverse.md):
- реверс референсов → промпты → генерация
- или промпты из офферов этапа 2

Сохрани в `output/images/`, зафиксируй в session state §8.

---

## Session State

**Обязательно** веди файл состояния:

- Шаблон: [templates/session-state.md](templates/session-state.md)
- Путь: `output/session-{slug}.md`
- Обновляй после **каждого** этапа
- Перед следующим этапом — перечитай session state

Это предотвращает потерю смысла между этапами.

---

## Субагенты — когда использовать

| Задача | Subagent | Тип |
|--------|----------|-----|
| Независимый аудит (этап 4) | reviewer | `generalPurpose` |
| Параллельный спинтекст (этап 6) | spintax-batch-A/B/C | `generalPurpose` |
| Реверс фото (этап 8) | image-analyst | `generalPurpose` |

**Не делегируй субагентам:** этапы 0–2 (нужен диалог), финальную сборку CSV.

При запуске subagent передай: session state (релевантные секции) + reference файл этапа + конкретное задание.

---

## Чеклист перед выдачей

```
Task Progress:
- [ ] Session state заполнен
- [ ] ЦА утверждена
- [ ] 3–4 базовых объявления прошли аудит
- [ ] Спинтекст создан для каждого
- [ ] CSV: header 4 строки + N данных
- [ ] Title / Description / Address заполнены
- [ ] Города из брифа
- [ ] Количество строк ≈ запрошенному
- [ ] Факты не искажены
```

---

## Пример запуска пользователем

> Запусти Avito Factory. Бриф: [текст]. Нужно 200 объявлений. Города: Казань, СПб, Москва.

Твои действия:
1. Создать session state
2. Дозадать вопросы (если нужно)
3. Пройти этапы с чекпоинтами
4. Отдать `output/avito-ads-buhgalteriya-2026-07-29.csv`

---

## Дополнительные ресурсы

- Эталон CSV: [templates/avito-bulk-upload-example.csv](templates/avito-bulk-upload-example.csv)
- Header шаблон: [templates/csv-header.csv](templates/csv-header.csv)
- Правило: `.cursor/rules/avito-factory.mdc`
