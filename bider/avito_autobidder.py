#!/usr/bin/env python3
"""Dry-run Avito click-bid planner for «Фабрика Мебели».

Reads AVITO_CLIENT_ID and AVITO_CLIENT_SECRET from the environment.
Never calls setManual, setAuto, or remove. Never prints the secret or token.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

MSK = ZoneInfo("Europe/Moscow")
BASE = "https://api.avito.ru"
TARGET_CPL = 1000.0
SOFT_CPL = 1200.0
HARD_CPL = 1500.0
BASELINE_PEAK = {10, 11, 12, 14, 19, 22}
BASELINE_SILENCE = {1, 2, 3, 4, 5, 6, 7, 17}
WRITE_MARKERS = ("setmanual", "setauto", "/remove")
WEEKDAYS = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]


def log(msg: str) -> None:
    line = f"{datetime.now(MSK).strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)


def creds() -> tuple[str, str]:
    cid = os.environ.get("AVITO_CLIENT_ID", "").strip()
    sec = os.environ.get("AVITO_CLIENT_SECRET", "").strip()
    if not cid or not sec:
        raise SystemExit("AVITO_CLIENT_ID / AVITO_CLIENT_SECRET are not set")
    return cid, sec


class Avito:
    def __init__(self, token: str) -> None:
        self.token = token
        self._next_bids = 0.0

    def call(
        self,
        method: str,
        path: str,
        query: dict | None = None,
        body: dict | None = None,
        form: dict | None = None,
        auth: bool = True,
        bids_slot: bool = False,
    ) -> tuple[int, dict | list | str]:
        low = path.lower()
        if any(marker in low for marker in WRITE_MARKERS):
            raise RuntimeError(f"blocked write endpoint {path}")
        url = BASE + path
        if query:
            url += "?" + urllib.parse.urlencode(query, doseq=True)
        data = None
        headers = {"Accept": "application/json"}
        if auth:
            headers["Authorization"] = f"Bearer {self.token}"
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        elif form is not None:
            data = urllib.parse.urlencode(form).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        if bids_slot:
            wait = self._next_bids - time.time()
            if wait > 0:
                time.sleep(wait)
            self._next_bids = time.time() + 3.2
        attempt = 0
        while True:
            attempt += 1
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=90) as resp:
                    raw = resp.read().decode("utf-8", errors="replace")
                    status = resp.status
            except urllib.error.HTTPError as exc:
                raw = exc.read().decode("utf-8", errors="replace")
                status = exc.code
            except urllib.error.URLError as exc:
                reason = getattr(exc, "reason", exc)
                log(f"network {method} {path} {reason}")
                if attempt >= 4:
                    raise
                time.sleep(5)
                continue
            if status == 429:
                log(f"429 {method} {path} attempt {attempt}, sleep 65s")
                if attempt >= 6:
                    return status, "rate limited"
                time.sleep(65)
                if bids_slot:
                    self._next_bids = time.time() + 3.2
                continue
            if status >= 500 and attempt < 4:
                log(f"{status} {method} {path} retry")
                time.sleep(5 * attempt)
                continue
            if raw:
                try:
                    parsed: dict | list | str = json.loads(raw)
                except json.JSONDecodeError:
                    parsed = "non-json body"
            else:
                parsed = {}
            if status >= 400:
                err = parsed if isinstance(parsed, str) else _public_error(parsed)
                # Token errors can echo client identifiers; keep that path terse.
                if path == "/token":
                    log(f"HTTP {status} POST /token")
                else:
                    log(f"HTTP {status} {method} {path} {err}")
            return status, parsed


def _public_error(payload: dict | list) -> str:
    if not isinstance(payload, dict):
        return "non-object error"
    err = payload.get("error")
    if isinstance(err, dict):
        return f"code={err.get('code')} message={err.get('message')}"
    if isinstance(err, str):
        return err[:180]
    msg = payload.get("message") or payload.get("error_description")
    if msg:
        return str(msg)[:180]
    return "error"


def fetch_token() -> str:
    cid, sec = creds()
    client = Avito("")
    status, payload = client.call(
        "POST",
        "/token",
        form={
            "grant_type": "client_credentials",
            "client_id": cid,
            "client_secret": sec,
        },
        auth=False,
    )
    if status != 200 or not isinstance(payload, dict) or "access_token" not in payload:
        raise SystemExit(f"token failed status={status}")
    log("token ok")
    return str(payload["access_token"])


def account_id(api: Avito) -> int:
    status, payload = api.call("GET", "/core/v1/accounts/self")
    if status != 200 or not isinstance(payload, dict):
        raise SystemExit(f"accounts/self failed status={status}")
    raw = payload.get("id") or payload.get("user_id") or payload.get("userId")
    if raw is None and isinstance(payload.get("result"), dict):
        raw = payload["result"].get("id")
    if raw is None:
        raise SystemExit("accounts/self has no id")
    log(f"account id={raw}")
    return int(raw)


def fetch_chats(api: Avito, user_id: int, cutoff_ts: int) -> tuple[list[dict], bool, int]:
    chats: list[dict] = []
    offset = 0
    truncated = False
    while offset <= 1000:
        status, payload = api.call(
            "GET",
            f"/messenger/v2/accounts/{user_id}/chats",
            query={
                "limit": 100,
                "offset": offset,
                "chat_types": ["u2i", "u2u"],
                "unread_only": "false",
            },
        )
        if status != 200 or not isinstance(payload, dict):
            log(f"chats stop offset={offset} status={status}")
            break
        batch = payload.get("chats") or []
        if not isinstance(batch, list) or not batch:
            break
        chats.extend(batch)
        log(f"chats page offset={offset} got={len(batch)} total={len(chats)}")
        if len(batch) < 100:
            break
        if offset == 1000:
            truncated = True
            break
        offset += 100
    fresh = []
    for chat in chats:
        created = chat.get("created")
        if isinstance(created, (int, float)) and created >= cutoff_ts:
            fresh.append(chat)
    log(f"chats fetched={len(chats)} within_window={len(fresh)} truncated={truncated}")
    return fresh, truncated, len(chats)


def classify_hours(chats: list[dict], now: datetime) -> dict:
    hour_counts = [0] * 24
    heat = [[0] * 24 for _ in range(7)]
    for chat in chats:
        created = chat.get("created")
        if not isinstance(created, (int, float)):
            continue
        dt = datetime.fromtimestamp(int(created), MSK)
        hour_counts[dt.hour] += 1
        heat[dt.weekday()][dt.hour] += 1
    total = sum(hour_counts)
    mean = total / 24.0
    zones = {}
    for hour in range(24):
        count = hour_counts[hour]
        if total == 0:
            if hour in BASELINE_PEAK:
                zone, mult = "пик", 1.15
            elif hour in BASELINE_SILENCE:
                zone, mult = "тишина", 0.45
            else:
                zone, mult = "обычная", 0.85
            source = "baseline"
            ratio = None
        elif count >= 1.35 * mean:
            zone, mult, source = "пик", 1.15, "chats"
            ratio = count / mean
        elif count <= 0.55 * mean:
            zone, mult, source = "тишина", 0.45, "chats"
            ratio = count / mean
        else:
            zone, mult, source = "обычная", 0.85, "chats"
            ratio = count / mean
        zones[hour] = {
            "count": count,
            "zone": zone,
            "mult": mult,
            "ratio": ratio,
            "source": source,
        }
    current = zones[now.hour]
    return {
        "hour_counts": hour_counts,
        "heatmap": heat,
        "mean": mean,
        "total": total,
        "zones": zones,
        "current": current,
        "peak_hours": [h for h, z in zones.items() if z["zone"] == "пик"],
        "silence_hours": [h for h, z in zones.items() if z["zone"] == "тишина"],
    }


def list_active_items(api: Avito) -> list[dict]:
    items: list[dict] = []
    page = 1
    while page <= 80:
        status, payload = api.call(
            "GET",
            "/core/v1/items",
            query={"per_page": 99, "page": page, "status": "active"},
        )
        if status != 200 or not isinstance(payload, dict):
            log(f"items stop page={page} status={status}")
            break
        batch = payload.get("resources") or []
        if not isinstance(batch, list) or not batch:
            break
        for item in batch:
            if item.get("status") in (None, "active"):
                items.append(
                    {
                        "id": int(item["id"]),
                        "title": str(item.get("title") or ""),
                        "price": item.get("price"),
                    }
                )
        log(f"items page={page} got={len(batch)} total={len(items)}")
        if len(batch) < 99:
            break
        page += 1
        time.sleep(2.5)
    return items


def chunked(seq: list, size: int):
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def item_stats(
    api: Avito, user_id: int, item_ids: list[int], date_from: str, date_to: str
) -> dict[int, dict]:
    totals: dict[int, dict] = {}
    for batch in chunked(item_ids, 200):
        status, payload = api.call(
            "POST",
            f"/stats/v1/accounts/{user_id}/items",
            body={
                "dateFrom": date_from,
                "dateTo": date_to,
                "itemIds": batch,
                "fields": ["uniqViews", "uniqContacts"],
                "periodGrouping": "day",
            },
        )
        if status != 200 or not isinstance(payload, dict):
            log(f"stats v1 batch failed status={status} size={len(batch)}")
            continue
        result = payload.get("result") or {}
        for row in result.get("items") or []:
            iid = int(row.get("itemId") or row.get("item_id") or 0)
            views = contacts = 0
            for day in row.get("stats") or []:
                views += int(day.get("uniqViews") or 0)
                contacts += int(day.get("uniqContacts") or 0)
            totals[iid] = {"views": views, "contacts": contacts}
        log(f"stats v1 batch size={len(batch)} rows={len(result.get('items') or [])}")
        time.sleep(0.4)
    return totals


def spendings(api: Avito, user_id: int, date_from: str, date_to: str) -> dict:
    status, payload = api.call(
        "POST",
        f"/stats/v2/accounts/{user_id}/spendings",
        body={
            "dateFrom": date_from,
            "dateTo": date_to,
            "grouping": "month",
            "spendingTypes": ["all"],
        },
    )
    if status != 200 or not isinstance(payload, dict):
        return {"ok": False, "status": status, "rub": None, "by_slug": {}}
    groupings = ((payload.get("result") or {}).get("groupings")) or []
    by_slug: dict[str, float] = {}
    for group in groupings:
        for spend in group.get("spendings") or []:
            slug = str(spend.get("slug") or "unknown")
            by_slug[slug] = by_slug.get(slug, 0.0) + float(spend.get("value") or 0)
    rub = by_slug["all"] if "all" in by_slug else sum(by_slug.values())
    log(f"spendings rub={rub:.2f}")
    return {"ok": True, "status": status, "rub": rub, "by_slug": by_slug}


def promotions(api: Avito, item_ids: list[int]) -> dict[int, dict]:
    found: dict[int, dict] = {}
    for batch in chunked(item_ids, 200):
        status, payload = api.call(
            "POST",
            "/cpxpromo/1/getPromotionsByItemIds",
            body={"itemIDs": batch},
        )
        if status != 200 or not isinstance(payload, dict):
            log(f"promotions batch failed status={status}")
            continue
        rows = payload.get("items") or []
        for row in rows:
            found[int(row["itemID"])] = row
        log(f"promotions batch size={len(batch)} rows={len(rows)}")
        time.sleep(0.4)
    return found


def get_bids(api: Avito, item_id: int) -> dict | None:
    status, payload = api.call("GET", f"/cpxpromo/1/getBids/{item_id}", bids_slot=True)
    if status != 200 or not isinstance(payload, dict):
        return None
    return payload


def cpl_factor(cpl: float | None) -> float:
    """Target CPL 1000. Soft ceiling 1200. Hard edge 1500 caps the factor at 0.70."""
    if cpl is None or cpl <= 0:
        return 1.0
    if cpl > HARD_CPL:
        return min(0.70, TARGET_CPL / cpl)
    if cpl > SOFT_CPL:
        return TARGET_CPL / cpl
    return 1.0


def plan_bid(
    current_penny: int | None,
    anchor_penny: int | None,
    desired_rub: float,
    min_penny: int,
    max_penny: int,
) -> int:
    desired_penny = int(round(desired_rub * 100))
    anchor = current_penny if current_penny and current_penny > 0 else anchor_penny
    if anchor and anchor > 0:
        lo = int(round(anchor * 0.70))
        hi = int(round(anchor * 1.30))
        desired_penny = max(lo, min(hi, desired_penny))
    desired_penny = max(min_penny, min(max_penny, desired_penny))
    desired_penny = int(round(desired_penny / 100.0) * 100)
    desired_penny = max(min_penny, min(max_penny, desired_penny))
    return desired_penny


def self_check() -> None:
    assert abs(cpl_factor(1409.9) - (1000 / 1409.9)) < 1e-9
    assert cpl_factor(900) == 1.0
    assert cpl_factor(1200) == 1.0
    assert abs(cpl_factor(1200.01) - (1000 / 1200.01)) < 1e-9
    assert cpl_factor(2000) == min(0.70, 1000 / 2000)
    # ±30% around 13 RUB, desired far above, then whole rubles.
    got = plan_bid(1300, None, 39.64, 100, 50000)
    assert got == 1700, got
    # Decrease: current 22, desired ~17.48 → 70% floor is 15.4, so 17 RUB.
    got = plan_bid(2200, None, 17.48, 100, 50000)
    assert got == 1700, got
    zones = classify_hours([], datetime(2026, 10, 2, 11, tzinfo=MSK))
    assert zones["current"]["zone"] == "пик"
    assert zones["current"]["source"] == "baseline"
    silence = classify_hours([], datetime(2026, 10, 2, 3, tzinfo=MSK))
    assert silence["current"]["zone"] == "тишина"
    print("self-check ok")


def penny_rub(value: int | None) -> float | None:
    if value is None:
        return None
    return round(value / 100.0, 2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Avito dry-run click bid planner")
    parser.add_argument("--days", type=int, default=60)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument(
        "--report",
        default=os.environ.get("AVITO_REPORT_PATH", "/tmp/avito_report.json"),
    )
    args = parser.parse_args()
    if args.days < 1 or args.days > 365:
        raise SystemExit("--days must be 1..365")
    if args.self_check:
        self_check()
        return

    now = datetime.now(MSK)
    cutoff = now - timedelta(days=args.days)
    date_from = cutoff.date().isoformat()
    date_to = now.date().isoformat()
    log(f"start msk={now.isoformat()} window={date_from}..{date_to} dry_run=1")

    api = Avito(fetch_token())
    user_id = account_id(api)
    chats, truncated, scanned = fetch_chats(api, user_id, int(cutoff.timestamp()))
    timing = classify_hours(chats, now)
    current = timing["current"]
    time_mult = float(current["mult"])
    log(
        f"hour={now.hour} zone={current['zone']} mult={time_mult} "
        f"chats={timing['total']} mean={timing['mean']:.2f} source={current['source']}"
    )

    items = list_active_items(api)
    ids = [item["id"] for item in items]
    titles = {item["id"]: item["title"] for item in items}
    stats = item_stats(api, user_id, ids, date_from, date_to) if ids else {}
    spend = spendings(api, user_id, date_from, date_to)

    views = sum(row["views"] for row in stats.values())
    contacts = sum(row["contacts"] for row in stats.values())
    cr = (contacts / views) if views else None
    cpl = (spend["rub"] / contacts) if spend.get("rub") is not None and contacts else None
    factor = cpl_factor(cpl)
    log(f"views={views} contacts={contacts} cr={cr} cpl={cpl} factor={factor}")

    promos = promotions(api, ids) if ids else {}
    click_ids = [iid for iid, row in promos.items() if int(row.get("actionTypeID") or 0) == 5]
    log(f"active={len(items)} promotions={len(promos)} click_items={len(click_ids)}")

    proposals = []
    skipped = {"not_click": 0, "no_bounds": 0, "no_cr": 0, "bids_error": 0, "unchanged": 0}
    for iid in click_ids:
        promo = promos[iid]
        log(f"getBids {iid}")
        bids = get_bids(api, iid)
        if not bids:
            skipped["bids_error"] += 1
            continue
        if int(bids.get("actionTypeID") or 0) != 5:
            skipped["not_click"] += 1
            continue
        manual = bids.get("manual") or {}
        if manual.get("minBidPenny") is None or manual.get("maxBidPenny") is None:
            skipped["no_bounds"] += 1
            continue
        st = stats.get(iid) or {"views": 0, "contacts": 0}
        item_cr = (st["contacts"] / st["views"]) if st["views"] else None
        if st["views"] >= 20 and item_cr is not None:
            used_cr = item_cr
            cr_source = "item"
        else:
            used_cr = cr
            cr_source = "account"
        if not used_cr or used_cr <= 0:
            skipped["no_cr"] += 1
            continue
        manual_promo = promo.get("manualPromotion") or {}
        current_penny = manual.get("bidPenny")
        if current_penny is None:
            current_penny = manual_promo.get("bidPenny")
        current_penny = int(current_penny) if current_penny else None
        rec = manual.get("recBidPenny")
        anchor = int(rec) if rec else None
        desired_rub = TARGET_CPL * used_cr * time_mult * factor
        new_penny = plan_bid(
            current_penny,
            anchor,
            desired_rub,
            int(manual["minBidPenny"]),
            int(manual["maxBidPenny"]),
        )
        changed = new_penny != (current_penny or 0)
        if not changed:
            skipped["unchanged"] += 1
        title = titles.get(iid, "")
        proposals.append(
            {
                "item_id": iid,
                "title": title[:80],
                "views": st["views"],
                "contacts": st["contacts"],
                "cr": round(used_cr, 6),
                "cr_source": cr_source,
                "current_rub": penny_rub(current_penny),
                "desired_rub": round(desired_rub, 2),
                "new_rub": penny_rub(new_penny),
                "min_rub": penny_rub(int(manual["minBidPenny"])),
                "max_rub": penny_rub(int(manual["maxBidPenny"])),
                "changed": changed,
            }
        )

    would_change = [row for row in proposals if row["changed"]]
    examples = would_change[:10] if would_change else proposals[:10]
    report = {
        "dry_run": True,
        "set_manual_called": False,
        "account_id": user_id,
        "msk": now.isoformat(),
        "weekday": WEEKDAYS[now.weekday()],
        "hour_msk": now.hour,
        "zone": current["zone"],
        "time_mult": time_mult,
        "zone_source": current["source"],
        "hour_ratio": current["ratio"],
        "chats_window": timing["total"],
        "chats_scanned": scanned,
        "chats_truncated": truncated,
        "peak_hours": timing["peak_hours"],
        "silence_hours": timing["silence_hours"],
        "hour_counts": timing["hour_counts"],
        "window": {"from": date_from, "to": date_to, "days": args.days},
        "views": views,
        "contacts": contacts,
        "cr": cr,
        "spend_rub": spend.get("rub"),
        "spend_by_slug": spend.get("by_slug"),
        "cpl": cpl,
        "cpl_factor": factor,
        "active_items": len(items),
        "click_items": len(click_ids),
        "priced_items": len(proposals),
        "would_change": len(would_change),
        "skipped": skipped,
        "examples": examples,
        "proposals": proposals,
    }
    with open(args.report, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    log(f"report {args.report}")
    cr_pct = f"{cr * 100:.2f}%" if cr is not None else "n/a"
    cpl_txt = f"{cpl:.0f} ₽" if cpl is not None else "n/a"
    print("")
    print(
        f"МСК {now.strftime('%Y-%m-%d %H:%M')} ({WEEKDAYS[now.weekday()]}), "
        f"час {now.hour}, зона {current['zone']} ×{time_mult} ({current['source']})"
    )
    print(
        f"чаты {timing['total']} за {args.days}д"
        f"{' (выдача обрезана)' if truncated else ''}, "
        f"CR {cr_pct}, CPL {cpl_txt}, "
        f"изменил бы {len(would_change)} из {len(proposals)} кликовых"
    )
    print("setManual не вызывался")
    for row in examples:
        print(
            f"- {row['item_id']} {row['current_rub']} → {row['new_rub']} ₽ "
            f"(цель {row['desired_rub']}, CR {row['cr_source']} {row['cr']:.4f}) "
            f"{row['title']}"
        )


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(0)
