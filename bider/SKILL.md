---
name: avito-bider
description: >-
  Облачный автобидер Авито для кабинета «Фабрика Мебели»: анализ часов входящих
  чатов за 60 дней, расчёт CPA-ставок клика под целевой CPL 1000/1200/1500 ₽ и
  dry-run или запись через cpxpromo. Use when автобидер Авито, Avito bidder,
  бидер ставок Авито, Фабрика Мебели CPA, hourly Avito bids, automation
  abramovmarketing88-byte/Avito/xz. Not for фиды объявлений, фото, лендинги
  или статистику без ставок.
---

# Автобидер Авито — «Фабрика Мебели»

## Контекст кабинета

| Параметр | Значение |
|----------|----------|
| Кабинет | Фабрика Мебели |
| Account id (ориентир) | `181493224` — всегда перепроверяй через `GET /core/v1/accounts/self` |
| Репозиторий автоматизации | `abramovmarketing88-byte/Avito`, ветка `xz` |
| Папка в репо | `bider/` |
| Скрипт | `bider/avito_autobidder.py` |
| Таймзона | `Europe/Moscow` |
| Окно данных | 60 дней |
| Режим по умолчанию | **dry-run** (ставки в кабинет НЕ писать) |
| Боевая запись | только при явном `--apply` или секрете/флаге `AVITO_BID_APPLY=1` |

Ключи API только из секретов автоматизации / env:

- `AVITO_CLIENT_ID`
- `AVITO_CLIENT_SECRET`

**Никогда** не печатай `client_secret`, access token и содержимое `.env.local` в чат, Run History или отчёт.

## Цель бизнеса

Держать **стоимость контакта (CPL)** около:

- адекват: **1000 ₽**
- нормальный верх: **1200 ₽**
- жёсткий край: **1500 ₽**

Контакт в метриках Авито = **чат + телефон** (поле `contacts` / `uniqContacts`), не «только звонок».

Оплачиваемое действие в этом кабинете — **пакет кликов** (`actionTypeID = 5`).

## Формула ставки

```
CR = contacts / views   # по объявлению, если views ≥ 20; иначе CR кабинета
bid_rub ≈ 1000 × CR × time_mult × cpl_guard
```

Примеры (как договорились с владельцем):

- CR 10% → ставка ~100 ₽ при цели 1000
- CR 2% → ставка ~20 ₽

Ограничения:

1. Зажать в `minBidPenny` / `maxBidPenny` из `GET /cpxpromo/1/getBids/{itemId}` (суммы в **копейках**).
2. За один проход не менять текущую ставку больше чем на **±30%**.
3. Если CPL кабинета > 1500 — дополнительно резать ставку (`cpl_guard < 1`).
4. Мало статистики по объявлению → брать prior CR кабинета, не прыгать агрессивно.
5. Views ≥ 20 и 0 контактов → prior CR × 0.35 (режем).

В API **нет отдельного поля «клики»** для этой логики: для CR используем `uniqViews` / `views` как прокси трафика к контакту. Расход — из `/spendings` (`presence` / `cpa_click_package`, уже в рублях).

## Множитель по времени суток (МСК)

По чатам за 60 дней (`created` в `GET /messenger/v2/accounts/{user_id}/chats`):

| Зона | Правило | Множитель |
|------|---------|-----------|
| peak | сообщений ≥ 1.35 × среднего на час и ≥ 2 | **1.15** |
| quiet | ≤ 0.55 × среднего | **0.45** |
| normal | всё остальное | **0.85** |

Baseline с первого прогона (пересчитывать каждый час, не хардкодить навсегда):

- **Пик:** 10, 11, 12, 14, 19, 22
- **Тишина:** 1–7, 17

Идея: в часы, когда люди пишут, ставки выше; ночью и в «пустые» часы — ниже, чтобы CPL не разъезжался.

## Что агент делает каждый час

1. Взять ключи из секретов / env. Получить token: `POST https://api.avito.ru/token` (`grant_type=client_credentials`).
2. `GET /core/v1/accounts/self` → `user_id`, имя.
3. Выгрузить чаты с пагинацией `limit=100`, пока `created` старше 60 дней или нет `has_more`. Построить heatmap по часу и дню недели (МСК). Определить текущий `time_mult`.
4. Кабинет за 60 дней: `POST /stats/v2/accounts/{user_id}/items` (`views`, `contacts`, `grouping=day`) и `POST .../spendings`. Посчитать CR и CPL.
5. Активные объявления: `GET /core/v1/items?status=active&per_page=100` (все страницы).
6. Stats по itemIds батчами ≤200: `POST /stats/v1/accounts/{user_id}/items` (`uniqViews`, `uniqContacts`, `periodGrouping=day`).
7. Текущие продвижения: `POST /cpxpromo/1/getPromotionsByItemIds` (`itemIDs`, ≤200).
8. Для объявлений с трафиком посчитать `new_bid_rub`. Чужой `actionTypeID` (не 5 и не пустой) — **не трогать**.
9. **Dry-run по умолчанию:** не вызывать `POST /cpxpromo/1/setManual`.
10. Отчёт (коротко): час МСК, зона, chats, CR, CPL, spend, сколько объявлений scored / would-change, 5–10 примеров `item_id current→new`. Без секретов.

### Запись ставок (только если явно разрешено)

`POST /cpxpromo/1/setManual`:

```json
{
  "itemID": 123,
  "actionTypeID": 5,
  "bidPenny": 1700
}
```

`bidPenny` в копейках. Лимит setManual ≈ 20 req/min — пауза ~3 с между записью. Перед записью уточнить min/max через `getBids`.

## Как запускать скрипт в репо

Из корня checkout ветки `xz`:

```bash
cd bider
# секреты уже в env автоматизации ИЛИ локально .env.local (не коммитить)
python3 avito_autobidder.py --days 60
python3 avito_autobidder.py --days 60 --apply          # боевая запись
python3 avito_autobidder.py --loop --interval-min 60   # непрерывный цикл
```

Выход в `bider/out/`:

- `message_heatmap.html`, `message_hours.csv`, `message_hours.json`
- `bids.csv`, `summary.json`, `runs.jsonl`

## Лимиты и ошибки API

| Ситуация | Действие |
|----------|----------|
| HTTP 429 | sleep ~65+ с, retry |
| spendings часто 1 req/min | не долбить подряд |
| getBids | ≤20/min |
| setManual | ≤20/min |
| stats v1 | ≤200 itemIds, окно ≤~90 дней |

Документация: https://developers.avito.ru/api-catalog  
Messenger: `/messenger/v2/.../chats`  
Ставки ЦД: `/cpxpromo/1/getBids/{itemId}`, `setManual`, `getPromotionsByItemIds`

## Cursor Automation (облако)

| Поле | Значение |
|------|----------|
| Name | Автобидер Авито |
| Repo / branch | `abramovmarketing88-byte/Avito` / `xz` |
| Trigger | Every hour (`0 * * * *`) |
| Secrets | `AVITO_CLIENT_ID`, `AVITO_CLIENT_SECRET` |
| Default | dry-run |
| Inactive → Active | после проверки Test |

Инструкция автоматизации может быть короткой: «Следуй `bider/SKILL.md`; запусти `python3 bider/avito_autobidder.py --days 60`; отчёт из summary».

Локальный cron на ПК **не заменяет** облако: если компьютер выключен, локальный прогон не случится. Облачная автоматизация работает без ПК.

## Антипаттерны

- Класть ключи в `SKILL.md`, README, промпт или git.
- Вызывать `setManual` без явного разрешения на запись.
- Менять ставки объявлений с другим типом ЦД (звонок=1, мессенджер=7).
- Считать CPL только по звонкам.
- Хардкодить пиковые часы без пересчёта чатов.
- Путать копейки (`*Penny`) и рубли в spendings.

## Первый эталонный прогон (факт)

Сухой прогон кабинета «Фабрика Мебели»:

- ~155 чатов / 60 дней
- ~3463 views, 164 contacts, CR ≈ 4.7%
- spend ≈ 169 тыс. ₽, CPL ≈ **1030 ₽** (в коридоре цели)
- 1233 active items; ставки не записывались (`applied: 0`)

Используй как sanity-check: резкий уход CPL сильно выше 1500 или CR ≈ 0 при большом spend — красный флаг в отчёте.
