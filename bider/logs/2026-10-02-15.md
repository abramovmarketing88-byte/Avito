# Прогон 2026-10-02 15:00 МСК

- Итог: failed
- Режим: dry-run
- Кабинет / id: Фабрика Мебели / fabrika-mebeli
- Ниша: мебель на заказ, лид чат + телефон, action_type 5
- Цена лида: target 1000 / soft 1200 / brake 1300 / hard 1500
- Объём: days 60, top_n 50, apply_top 30, write_bids нет, vas_max 1, buy_vas нет

Команда: `python3 avito_autobidder.py --cabinet fabrika-mebeli`. Ключи и токен в лог не писались. Прогон около 15:40 МСК, код выхода 1.

## Шаги

| Шаг | Статус | Деталь |
| --- | --- | --- |
| auth | fail | `AVITO_CLIENT_ID` и `AVITO_CLIENT_SECRET` не заданы |
| chats heatmap | skipped | до HTTP не дошли |
| account stats + spend | skipped | до HTTP не дошли |
| live filter | skipped | до HTTP не дошли |
| bids | skipped | would_change — / applied 0 |
| setManual | skipped | write_bids нет, запрос не отправлялся |
| VAS | skipped | buy_vas нет, покупок 0 |

Скрипт напечатал пороги кабинета (лид 1000/1200/1500, тормоз 1300, actionType 5) и остановился: нужны `AVITO_CLIENT_ID` и `AVITO_CLIENT_SECRET`.

## Ошибки

Шаг auth. HTTP не было. В окружении автоматизации нет пары `AVITO_CLIENT_ID` / `AVITO_CLIENT_SECRET`. В следующий раз положить ключи этого кабинета в секреты автоматизации, не в текст промпта и не в git.

## Цифры

mult —, brake —, prior_cr —, account_cpl —, day_cpl —, items_live —, would_change —. Примеров current→new нет: ставки не считались.

## Что мешает бидеру

1. Секреты кабинета не попали в окружение, прогон обрывается до Авито.
2. В тексте промпта есть вторая пара ключей. Скрипт читает только одну пару из env, вторая не использовалась.
