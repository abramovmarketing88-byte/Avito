# Автобидер Авито — «Фабрика Мебели»

Сухой прогон. Ставки в кабинет не отправляются.

## Запуск

```bash
python3 bider/avito_autobidder.py --days 60
```

Ключи только из окружения: `AVITO_CLIENT_ID` и `AVITO_CLIENT_SECRET`. Не печатать секрет и токен, не писать их в git и в память автоматизации.

## Шаги

1. `POST https://api.avito.ru/token` — `grant_type=client_credentials`.
2. `GET /core/v1/accounts/self` — id кабинета.
3. Чаты за N дней: `GET /messenger/v2/accounts/{user_id}/chats` (Europe/Moscow). По полю `created` — счётчики по часу и heatmap день недели × час.
4. Множитель часа (каждый запуск заново): пик ≥ 1.35× среднего часа → 1.15; тишина ≤ 0.55× → 0.45; иначе 0.85. Если чатов в окне нет — baseline: пик 10–12, 14, 19, 22; тишина 1–7 и 17.
5. Статистика окна: `POST /stats/v1/accounts/{id}/items` (`uniqViews`, `uniqContacts`) и `POST /stats/v2/accounts/{id}/spendings`. Суммы spendings в рублях. CPL = расход / контакты.
6. Активные объявления `GET /core/v1/items`, затем `POST /cpxpromo/1/getPromotionsByItemIds` и для клика (`actionTypeID` = 5) `GET /cpxpromo/1/getBids/{itemId}`.
7. Ставка, ₽ ≈ `1000 × CR × time_mult`. Если CPL > 1200, умножить на `1000/CPL`. Если CPL > 1500, этот множитель ещё ограничить 0.70. Шаг не больше ±30% от текущей ручной ставки. Уважать `minBidPenny` / `maxBidPenny`. CR объявления, если просмотров ≥ 20, иначе CR кабинета.
8. Не вызывать `setManual`, `setAuto`, `remove`.
9. Короткий отчёт: час МСК, зона, chats, CR, CPL, сколько объявлений изменил бы, 5–10 примеров. Без секретов.

При HTTP 429 ждать около 65 секунд и повторить.
