# Прогон 2026-10-02 14:00 МСК

- Итог: failed
- Режим: dry-run
- Кабинет / id: Фабрика Мебели / fabrika-mebeli

Повтор в 14:43 МСК. Команда: `python3 avito_autobidder.py --cabinet fabrika-mebeli`. `write_bids` нет, `buy_vas` нет.

## Шаги

| Шаг | Статус | Деталь |
| --- | --- | --- |
| auth | failed | `AVITO_CLIENT_ID` и `AVITO_CLIENT_SECRET` в окружении пустые, скрипт вышел до запроса токена |
| chats heatmap | skipped | до авторизации не дошли |
| account stats + spend | skipped | до авторизации не дошли |
| live filter | skipped | до авторизации не дошли |
| bids | skipped | would_change 0 / applied 0 |
| setManual | skipped | `write_bids` нет, HTTP к API не было |

## Ошибки

auth, HTTP нет: процесс завершился на проверке секретов (`exit 1`). Значения ключей в лог, git и командную строку не копировались. В следующий час нужны секреты этой автоматизации `AVITO_CLIENT_ID` и `AVITO_CLIENT_SECRET`.

## Цифры

mult —, brake —, prior_cr —, account_cpl —, day_cpl —, items_live —, would_change 0.

Примеров item_id нет: расчёт ставок не начинался.

Скрипт напечатал кабинет и пороги: лид 1000/1200/1500, тормоз 1300, actionType 5. Из `bider/cabinets/fabrika-mebeli.json`: days 60, top_n 50, apply_top 30, vas_max 1, write_bids нет, buy_vas нет.

## Что мешает бидеру

1. Секреты автоматизации не попали в окружение, поэтому не было ни чатов, ни статистики, ни ставок.
2. Пока ключей нет, CPL и живые объявления за этот час неизвестны.
