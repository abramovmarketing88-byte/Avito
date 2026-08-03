# Tatarstan geo preset (200 ads)

Создай файл 200 объявлений республика татарстан: 50 разные адреса Казани, 20 разные Набережных Челнов и 130 остальные города и посёлки Татарстана.

## Distribution (strict)

| Bucket | Count | Address format |
|--------|-------|----------------|
| Kazan | 50 | `Республика Татарстан (Татарстан), Казань, {район/локация}` |
| Naberezhnye Chelny | 20 | `Республика Татарстан (Татарстан), Набережные Челны, {район/локация}` |
| Other RT | 130 | `Республика Татарстан (Татарстан), {город/посёлок}` |

**Total must be exactly 200.**

## Brief from chat export

If user attaches `export_*.txt` — use as primary brief. See [10-chat-export-brief.md](10-chat-export-brief.md).

Copy to: `data/avito-chat-export.txt`

## Generate

```bash
python scripts/generate_tatarstan_200.py \
  --export data/avito-chat-export.txt \
  --output output/avito-ads-tatarstan-200.csv
```

## Verify

- [ ] 200 data rows (+ 4 header rows)
- [ ] 50 addresses contain `Казань,`
- [ ] 20 addresses contain `Набережные Челны,`
- [ ] 130 other Tatarstan cities
- [ ] Titles from export (48 unique ad names)
- [ ] HTML Description with services from real chats

Canonical address lists are embedded in `scripts/generate_tatarstan_200.py`.
