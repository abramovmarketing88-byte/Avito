#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Автобидер Авито. Цифры кабинета не зашиты: цель лида, потолки и тип оплаты
приходят из --cabinet или флагов. Логика одна для всех ниш.

Ключи: AVITO_CLIENT_ID / AVITO_CLIENT_SECRET. Секреты не печатать.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

BASE = "https://api.avito.ru"
MSK = ZoneInfo("Europe/Moscow")
DOW = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]

TARGET_CPL = 1000.0
SOFT_CPL = 1200.0
HARD_CPL = 1500.0
CPL_BRAKE_SOFT = 1300.0  # суточный/периодный CPL → режем ставки
# actionTypeID: 5 = пакет кликов (CPA click)
ACTION_CLICK = 5
MIN_VIEWS_FOR_CR = 20
MIN_CONTACTS_FOR_CR = 1
LIVE_MIN_VIEWS = 5  # ниже — «мёртвое» объявление, ставку не крутим
ACCOUNT_PRIOR_VIEWS = 100
DEFAULT_TOP_N = 50  # сколько живых объявлений трогаем за проход
DEFAULT_APPLY_TOP = 30  # при --apply пишем только топ по контактам
# XL / цвет / плашка: неделя, не чаще 1–2 новых подключений в сутки
VAS_WEEK_DAYS = 7
VAS_MAX_PER_DAY = 1  # потолок задаётся --vas-max, не выше 2
VAS_HARD_CAP = 2
VAS_MIN_IMPRESSIONS = 200
VAS_CTR_GAP = 0.85  # брать только если CTR объявления < 85% среднего по живым
VAS_SLUGS = ("highlight", "xl", "stickerpack_x1")
# зоны для отчёта (множитель часа — плавный от heatmap, не ступеньки)
PEAK_RATIO = 1.35
QUIET_RATIO = 0.55
HOUR_MULT_MIN = 0.40
HOUR_MULT_MAX = 1.20
DOW_MULT_MIN = 0.70
DOW_MULT_MAX = 1.10
MAX_STEP_RATIO = 0.30  # не менять текущую ставку больше чем на 30% за проход


def load_cabinet(name: str) -> dict:
    if not name:
        return {}
    path = Path(__file__).resolve().parent / "cabinets" / f"{name}.json"
    if not path.exists():
        raise SystemExit(f"Нет файла кабинета: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"Кабинет {name} должен быть JSON-объектом")
    return data


def bind_cabinet(args: argparse.Namespace) -> dict:
    """Подставляет цену лида и лимиты кабинета. Флаги командной строки важнее файла."""
    global TARGET_CPL, SOFT_CPL, HARD_CPL, CPL_BRAKE_SOFT, ACTION_CLICK
    cfg = load_cabinet(getattr(args, "cabinet", "") or "")
    if args.target_cpl is None:
        args.target_cpl = float(cfg.get("target_cpl", TARGET_CPL))
    if args.soft_cpl is None:
        args.soft_cpl = float(cfg.get("soft_cpl", SOFT_CPL))
    if args.hard_cpl is None:
        args.hard_cpl = float(cfg.get("hard_cpl", HARD_CPL))
    if args.brake_cpl is None:
        args.brake_cpl = float(cfg.get("brake_cpl", CPL_BRAKE_SOFT))
    if args.action_type is None:
        args.action_type = int(cfg.get("action_type", ACTION_CLICK))
    if args.days is None:
        args.days = int(cfg.get("days", 60))
    if args.top_n is None:
        args.top_n = int(cfg.get("top_n", DEFAULT_TOP_N))
    if args.apply_top is None:
        args.apply_top = int(cfg.get("apply_top", DEFAULT_APPLY_TOP))
    if args.vas_max is None:
        args.vas_max = int(cfg.get("vas_max", VAS_MAX_PER_DAY))
    if not args.apply and cfg.get("write_bids"):
        args.apply = True
    if not args.apply_vas and cfg.get("buy_vas"):
        args.apply_vas = True
    TARGET_CPL = float(args.target_cpl)
    SOFT_CPL = float(args.soft_cpl)
    HARD_CPL = float(args.hard_cpl)
    CPL_BRAKE_SOFT = float(args.brake_cpl)
    ACTION_CLICK = int(args.action_type)
    cfg["target_cpl"] = TARGET_CPL
    cfg["soft_cpl"] = SOFT_CPL
    cfg["hard_cpl"] = HARD_CPL
    cfg["brake_cpl"] = CPL_BRAKE_SOFT
    cfg["action_type"] = ACTION_CLICK
    args.cabinet_label = str(cfg.get("name") or args.cabinet or "")
    args.niche = str(cfg.get("niche") or "")
    print(
        f"кабинет {cfg.get('name') or args.cabinet or 'по флагам'} "
        f"лид {TARGET_CPL:.0f}/{SOFT_CPL:.0f}/{HARD_CPL:.0f} "
        f"тормоз {CPL_BRAKE_SOFT:.0f} actionType={ACTION_CLICK}",
        flush=True,
    )
    return cfg


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def ensure_env() -> None:
    here = Path(__file__).resolve().parent
    for p in (here / ".env.local", Path.cwd() / ".env.local", here.parent / ".env.local"):
        load_env_file(p)
    if not os.environ.get("AVITO_CLIENT_ID") or not os.environ.get("AVITO_CLIENT_SECRET"):
        print("Нужны AVITO_CLIENT_ID и AVITO_CLIENT_SECRET (.env.local).", file=sys.stderr)
        sys.exit(1)


def get_token() -> str:
    if os.environ.get("AVITO_TOKEN", "").strip():
        return os.environ["AVITO_TOKEN"].strip()
    body = urllib.parse.urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": os.environ["AVITO_CLIENT_ID"].strip(),
            "client_secret": os.environ["AVITO_CLIENT_SECRET"].strip(),
        }
    ).encode()
    req = urllib.request.Request(
        f"{BASE}/token",
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())["access_token"]


def api(token: str, method: str, path: str, body: dict | None = None, retries: int = 6):
    data = None if body is None else json.dumps(body).encode()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "avito-autobidder/1.0",
    }
    last_err: Exception | None = None
    for attempt in range(retries):
        req = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read().decode()
                return resp.status, json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            err_body = e.read().decode(errors="replace")
            if e.code == 429 and attempt < retries - 1:
                wait = 65 + attempt * 10
                print(f"  429 → sleep {wait}s", flush=True)
                time.sleep(wait)
                continue
            try:
                return e.code, json.loads(err_body)
            except Exception:
                return e.code, err_body[:2000]
        except Exception as e:
            last_err = e
            time.sleep(3 * (attempt + 1))
    return 0, {"error": str(last_err)}


def fetch_self(token: str) -> dict:
    code, data = api(token, "GET", "/core/v1/accounts/self")
    if code != 200 or not isinstance(data, dict) or "id" not in data:
        raise RuntimeError(f"accounts/self failed: {code} {data}")
    return data


def fetch_active_items(token: str, max_pages: int = 30) -> list[dict]:
    items: list[dict] = []
    page = 1
    while page <= max_pages:
        code, data = api(token, "GET", f"/core/v1/items?per_page=100&page={page}&status=active")
        if code != 200:
            raise RuntimeError(f"items page {page}: {code} {data}")
        batch = (data if isinstance(data, dict) else {}).get("resources") or []
        items.extend(batch)
        print(f"  items page {page}: {len(batch)}", flush=True)
        if len(batch) < 100:
            break
        page += 1
        time.sleep(0.15)
    return items


def fetch_chats(token: str, user_id: int, since_ts: int) -> list[dict]:
    chats: list[dict] = []
    offset = 0
    while offset <= 10000:
        code, data = api(
            token,
            "GET",
            f"/messenger/v2/accounts/{user_id}/chats?limit=100&offset={offset}",
        )
        if code != 200 or not isinstance(data, dict):
            raise RuntimeError(f"chats offset {offset}: {code} {data}")
        batch = data.get("chats") or []
        if not batch:
            break
        chats.extend(batch)
        oldest = min(int(c.get("created") or 0) for c in batch)
        print(f"  chats offset {offset}: {len(batch)}", flush=True)
        offset += len(batch)
        if oldest < since_ts or not (data.get("meta") or {}).get("has_more"):
            break
        time.sleep(0.15)
    return [c for c in chats if int(c.get("created") or 0) >= since_ts]


def clamp(n: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, n))


def analyze_messages(chats: list[dict]) -> dict:
    by_hour = Counter()
    by_dow = Counter()
    by_cell = Counter()
    for c in chats:
        dt = datetime.fromtimestamp(int(c["created"]), tz=MSK)
        by_hour[dt.hour] += 1
        by_dow[dt.weekday()] += 1
        by_cell[(dt.weekday(), dt.hour)] += 1
    total = sum(by_hour.values()) or 1
    avg = total / 24.0
    hours = []
    for h in range(24):
        n = by_hour.get(h, 0)
        ratio = n / avg if avg else 0
        if ratio >= PEAK_RATIO and n >= 2:
            band = "peak"
        elif ratio <= QUIET_RATIO:
            band = "quiet"
        else:
            band = "normal"
        hours.append({"hour": h, "messages": n, "ratio": round(ratio, 2), "band": band})
    peak_hours = [h["hour"] for h in hours if h["band"] == "peak"]
    quiet_hours = [h["hour"] for h in hours if h["band"] == "quiet"]
    dow_counts = [by_dow.get(d, 0) for d in range(7)]
    return {
        "total_chats": sum(by_hour.values()),
        "avg_per_hour": round(avg, 2),
        "hours": hours,
        "peak_hours": peak_hours,
        "quiet_hours": quiet_hours,
        "by_dow": {DOW[d]: dow_counts[d] for d in range(7)},
        "by_dow_counts": dow_counts,
        "cells": {f"{d}-{h}": by_cell.get((d, h), 0) for d in range(7) for h in range(24)},
    }


def time_multipliers(now: datetime, analysis: dict) -> dict:
    """Плавный час из heatmap + день недели. Два пика (утро/вечер) сами вылезают из ratio."""
    hours = analysis["hours"]
    ratios = {h["hour"]: float(h["ratio"]) for h in hours}
    bands = {h["hour"]: h["band"] for h in hours}
    max_r = max(ratios.values()) if ratios else 1.0
    max_r = max_r or 1.0
    r = ratios.get(now.hour, 0.0)
    hour_mult = clamp(
        HOUR_MULT_MIN + (HOUR_MULT_MAX - HOUR_MULT_MIN) * (r / max_r),
        HOUR_MULT_MIN,
        HOUR_MULT_MAX,
    )
    band = bands.get(now.hour, "normal")

    dow_counts = analysis.get("by_dow_counts") or [0] * 7
    avg_dow = (sum(dow_counts) / 7.0) or 1.0
    today = now.weekday()
    dr = dow_counts[today] / avg_dow
    max_dr = max((c / avg_dow for c in dow_counts), default=1.0) or 1.0
    dow_mult = clamp(
        DOW_MULT_MIN + (DOW_MULT_MAX - DOW_MULT_MIN) * (dr / max_dr),
        DOW_MULT_MIN,
        DOW_MULT_MAX,
    )
    combined = round(hour_mult * dow_mult, 3)
    return {
        "hour_mult": round(hour_mult, 3),
        "dow_mult": round(dow_mult, 3),
        "combined": combined,
        "band": band,
        "hour_ratio": round(r, 2),
        "dow_ratio": round(dr, 2),
        "dow": DOW[today],
    }


def cpl_brake_factor(period_cpl: float | None, day_cpl: float | None) -> tuple[float, str]:
    """Если CPL уже высокий — давим ставки до пересчёта CR."""
    ref = day_cpl if day_cpl is not None else period_cpl
    src = "day" if day_cpl is not None else "period"
    if ref is None:
        return 1.0, "none"
    if ref > HARD_CPL:
        return 0.60, f"{src}>{HARD_CPL:.0f}"
    if ref > CPL_BRAKE_SOFT:
        return 0.75, f"{src}>{CPL_BRAKE_SOFT:.0f}"
    if ref > SOFT_CPL:
        return 0.90, f"{src}>{SOFT_CPL:.0f}"
    return 1.0, f"{src}_ok"


def fetch_item_stats(token: str, user_id: int, item_ids: list[int], d0: str, d1: str) -> dict[int, dict]:
    """item_id -> {views, contacts} за период. views = прокси кликов (в API нет отдельного clicks)."""
    out: dict[int, dict] = {}
    for i in range(0, len(item_ids), 200):
        batch = item_ids[i : i + 200]
        body = {
            "dateFrom": d0,
            "dateTo": d1,
            "itemIds": batch,
            "fields": ["uniqViews", "uniqContacts", "views", "contacts"],
            "periodGrouping": "day",
        }
        code, data = api(token, "POST", f"/stats/v1/accounts/{user_id}/items", body)
        print(f"  stats v1 batch {i}: HTTP {code}", flush=True)
        if code != 200 or not isinstance(data, dict):
            time.sleep(0.4)
            continue
        result = data.get("result") or data
        for row in (result.get("items") or []) if isinstance(result, dict) else []:
            iid = int(row.get("itemId") or row.get("id") or 0)
            views = contacts = 0.0
            for s in row.get("stats") or []:
                views += float(s.get("uniqViews") or s.get("views") or 0)
                contacts += float(s.get("uniqContacts") or s.get("contacts") or 0)
            if iid:
                out[iid] = {"views": views, "contacts": contacts}
        time.sleep(0.3)
    return out


def fetch_account_totals(token: str, user_id: int, d0: str, d1: str) -> dict:
    body = {
        "dateFrom": d0,
        "dateTo": d1,
        "grouping": "day",
        "metrics": ["views", "contacts", "favorites"],
        "limit": 1000,
        "offset": 0,
    }
    code, data = api(token, "POST", f"/stats/v2/accounts/{user_id}/items", body)
    if code != 200 or not isinstance(data, dict):
        return {"views": 0.0, "contacts": 0.0, "error": f"{code}"}
    views = contacts = 0.0
    for g in (data.get("result") or {}).get("groupings") or []:
        m = {x["slug"]: float(x.get("value") or 0) for x in (g.get("metrics") or [])}
        views += m.get("views", 0)
        contacts += m.get("contacts", 0)
    return {"views": views, "contacts": contacts}


def fetch_spendings_rub(token: str, user_id: int, d0: str, d1: str) -> float:
    body = {
        "dateFrom": d0,
        "dateTo": d1,
        "grouping": "day",
        "spendingTypes": ["all", "promotion", "presence", "commission", "rest"],
    }
    code, data = api(token, "POST", f"/stats/v2/accounts/{user_id}/spendings", body)
    if code != 200 or not isinstance(data, dict):
        print(f"  spendings HTTP {code}", flush=True)
        return 0.0
    total = 0.0
    for g in (data.get("result") or {}).get("groupings") or []:
        for s in g.get("spendings") or []:
            slug = s.get("slug") or ""
            if slug in ("presence", "promotion"):
                total += float(s.get("value") or 0)
            for svc in s.get("services") or []:
                if (svc.get("slug") or "") in ("cpa_click_package", "presence"):
                    total += float(svc.get("value") or 0)
    return total


def fetch_item_funnel(token: str, user_id: int, d0: str, d1: str) -> dict[int, dict]:
    """item_id -> impressions, views, contacts. grouping=item, окно до 1000 строк."""
    out: dict[int, dict] = {}
    offset = 0
    while offset <= 2000:
        body = {
            "dateFrom": d0,
            "dateTo": d1,
            "grouping": "item",
            "metrics": ["impressions", "views", "contacts"],
            "limit": 1000,
            "offset": offset,
        }
        code, data = api(token, "POST", f"/stats/v2/accounts/{user_id}/items", body)
        print(f"  funnel offset {offset}: HTTP {code}", flush=True)
        if code != 200 or not isinstance(data, dict):
            break
        groups = (data.get("result") or {}).get("groupings") or []
        if not groups:
            break
        for g in groups:
            iid = int(g.get("id") or 0)
            m = {x["slug"]: float(x.get("value") or 0) for x in (g.get("metrics") or [])}
            if iid:
                out[iid] = {
                    "impressions": m.get("impressions", 0.0),
                    "views": m.get("views", 0.0),
                    "contacts": m.get("contacts", 0.0),
                }
        if len(groups) < 1000:
            break
        offset += 1000
        time.sleep(0.3)
    return out


def load_vas_ledger(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return list(data.get("applies") or [])


def save_vas_ledger(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"applies": rows[-400:]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def vas_fresh(rows: list[dict], item_id: int, slug: str, now: datetime) -> bool:
    for row in rows:
        if int(row.get("item_id") or 0) != item_id or row.get("slug") != slug:
            continue
        try:
            ts = datetime.fromisoformat(str(row["applied_at"]))
        except Exception:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=MSK)
        if now - ts < timedelta(days=VAS_WEEK_DAYS):
            return True
    return False


def vas_today_count(rows: list[dict], now: datetime) -> int:
    day = now.date().isoformat()
    return sum(1 for row in rows if str(row.get("applied_at") or "").startswith(day))


def fetch_vas_prices(token: str, user_id: int, item_ids: list[int]) -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = {}
    for i in range(0, len(item_ids), 50):
        batch = item_ids[i : i + 50]
        code, data = api(
            token,
            "POST",
            f"/core/v1/accounts/{user_id}/vas/prices",
            {"itemIds": batch},
        )
        print(f"  vas prices {i}: HTTP {code}", flush=True)
        rows = data if isinstance(data, list) else (data.get("result") or data.get("items") or []) if isinstance(data, dict) else []
        for row in rows or []:
            iid = int(row.get("itemId") or row.get("item_id") or 0)
            if iid:
                out[iid] = list(row.get("vas") or row.get("services") or [])
        time.sleep(0.25)
    return out


def service_row(services: list[dict], slug: str) -> dict | None:
    for s in services:
        if (s.get("slug") or "") == slug:
            return s
    return None


def service_applied(row: dict | None) -> bool:
    if not row:
        return False
    return bool(row.get("isApplied") or row.get("applied") or str(row.get("status") or "") in ("active", "applied"))


def pick_vas_slug(services: list[dict], ledger: list[dict], item_id: int, now: datetime) -> tuple[str, float] | None:
    """Цвет, потом XL. Плашка только если XL уже на неделе. Уже висящее не покупаем."""
    for slug in ("highlight", "xl"):
        if vas_fresh(ledger, item_id, slug, now):
            continue
        row = service_row(services, slug)
        if service_applied(row):
            continue
        if row and row.get("price") is not None:
            return slug, float(row["price"])
    xl_on = vas_fresh(ledger, item_id, "xl", now) or service_applied(service_row(services, "xl"))
    if xl_on and not vas_fresh(ledger, item_id, "stickerpack_x1", now):
        row = service_row(services, "stickerpack_x1")
        if row and not service_applied(row) and row.get("price") is not None:
            return "stickerpack_x1", float(row["price"])
    return None


def apply_vas(token: str, item_id: int, slug: str) -> tuple[int, object]:
    return api(token, "PUT", f"/core/v2/items/{item_id}/vas/", {"slugs": [slug]})


def plan_vas(
    *,
    token: str,
    user_id: int,
    now: datetime,
    focus_ids: list[int],
    funnel: dict[int, dict],
    ledger_path: Path,
    do_apply: bool,
    vas_max: int,
) -> tuple[list[dict], list[dict]]:
    ledger = load_vas_ledger(ledger_path)
    cap = max(0, min(VAS_HARD_CAP, vas_max))
    left = max(0, cap - vas_today_count(ledger, now))
    if left <= 0:
        print(f"  VAS: лимит {cap}/день уже выбран, новые не считаем", flush=True)
        return [], ledger
    imps = []
    views = []
    for iid in focus_ids:
        f = funnel.get(iid) or {}
        imps.append(float(f.get("impressions") or 0))
        views.append(float(f.get("views") or 0))
    acc_ctr = (sum(views) / sum(imps)) if sum(imps) else 0.0
    ranked = []
    for iid in focus_ids:
        f = funnel.get(iid) or {}
        imp = float(f.get("impressions") or 0)
        v = float(f.get("views") or 0)
        if imp < VAS_MIN_IMPRESSIONS:
            continue
        ctr = v / imp
        if acc_ctr and ctr >= acc_ctr * VAS_CTR_GAP:
            continue
        ranked.append((ctr, -imp, iid, imp, v))
    ranked.sort()
    shortlist = [row[2] for row in ranked[:12]]
    prices = fetch_vas_prices(token, user_id, shortlist) if shortlist else {}
    plan = []
    for ctr, _neg, iid, imp, v in ranked:
        if len([p for p in plan if p["action"] in ("dry-run", "set")]) >= left and left >= 0:
            # всё ещё пишем skip-строки? нет, хватит отобранных слотов + причины пропуска уже покрытых
            pass
        chosen = pick_vas_slug(prices.get(iid) or [], ledger, iid, now)
        if not chosen:
            plan.append({
                "item_id": iid,
                "impressions": int(imp),
                "views": int(v),
                "ctr": round(ctr, 4),
                "slug": "",
                "price_rub": "",
                "action": "skip_already_or_no_offer",
                "status": "",
            })
            continue
        slug, price = chosen
        slots_used = sum(1 for p in plan if p["action"] in ("dry-run", "set"))
        if slots_used >= left:
            plan.append({
                "item_id": iid,
                "impressions": int(imp),
                "views": int(v),
                "ctr": round(ctr, 4),
                "slug": slug,
                "price_rub": price,
                "action": "skip_daily_cap",
                "status": f"cap {cap}/day",
            })
            continue
        action = "set" if do_apply else "dry-run"
        status = ""
        if action == "set":
            code, resp = apply_vas(token, iid, slug)
            status = f"HTTP {code}"
            if code == 200:
                ledger.append({
                    "item_id": iid,
                    "slug": slug,
                    "price_rub": price,
                    "applied_at": now.isoformat(timespec="minutes"),
                })
            else:
                status = f"HTTP {code} {str(resp)[:160]}"
                action = "fail"
            time.sleep(0.4)
        plan.append({
            "item_id": iid,
            "impressions": int(imp),
            "views": int(v),
            "ctr": round(ctr, 4),
            "slug": slug,
            "price_rub": price,
            "action": action,
            "status": status,
        })
        if sum(1 for p in plan if p["action"] in ("dry-run", "set")) >= max(left, 0) and not do_apply:
            break
        if do_apply and sum(1 for p in plan if p["action"] == "set") >= left:
            break
    if do_apply:
        save_vas_ledger(ledger_path, ledger)
    return plan, ledger


def get_promotions(token: str, item_ids: list[int]) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for i in range(0, len(item_ids), 200):
        batch = item_ids[i : i + 200]
        code, data = api(token, "POST", "/cpxpromo/1/getPromotionsByItemIds", {"itemIDs": batch})
        print(f"  promotions batch {i}: HTTP {code}", flush=True)
        if code != 200 or not isinstance(data, dict):
            time.sleep(0.3)
            continue
        for row in data.get("items") or []:
            iid = int(row.get("itemID") or 0)
            if iid:
                out[iid] = row
        time.sleep(0.2)
    return out


def get_bids_detail(token: str, item_id: int) -> dict | None:
    code, data = api(token, "GET", f"/cpxpromo/1/getBids/{item_id}")
    if code != 200 or not isinstance(data, dict):
        return None
    return data


def set_manual_bid(token: str, item_id: int, bid_penny: int, limit_penny: int | None) -> tuple[int, object]:
    body: dict = {
        "itemID": item_id,
        "actionTypeID": ACTION_CLICK,
        "bidPenny": bid_penny,
    }
    if limit_penny is not None:
        body["limitPenny"] = limit_penny
    return api(token, "POST", "/cpxpromo/1/setManual", body)


def compute_bid_rub(
    *,
    views: float,
    contacts: float,
    prior_cr: float,
    mult: float,
    min_rub: float,
    max_rub: float,
    current_rub: float | None,
    account_cpl: float | None,
) -> tuple[float, float, str]:
    """Возвращает (ставка_руб, cr, reason)."""
    if views >= MIN_VIEWS_FOR_CR and contacts >= MIN_CONTACTS_FOR_CR:
        cr = contacts / views
        src = "item"
    elif views >= MIN_VIEWS_FOR_CR and contacts == 0:
        # нет контактов при трафике — режем к тихому полу
        cr = prior_cr * 0.35
        src = "item_zero_contacts"
    else:
        cr = prior_cr
        src = "account_prior"

    # если фактический CPL кабинета выше края — дополнительно давим ставку
    cpl_factor = 1.0
    if account_cpl and account_cpl > HARD_CPL:
        cpl_factor = HARD_CPL / account_cpl
    elif account_cpl and account_cpl < TARGET_CPL * 0.7 and views >= ACCOUNT_PRIOR_VIEWS:
        cpl_factor = 1.08

    raw = TARGET_CPL * cr * mult * cpl_factor
    # мягкий потолок по цели SOFT × CR (без старых ступенек PEAK_MULT)
    soft_cap = SOFT_CPL * cr * max(1.0, min(mult, HOUR_MULT_MAX))
    raw = min(raw, soft_cap if soft_cap > 0 else raw)
    bid = clamp(raw, min_rub, max_rub)
    if current_rub and current_rub > 0:
        lo = current_rub * (1 - MAX_STEP_RATIO)
        hi = current_rub * (1 + MAX_STEP_RATIO)
        stepped = clamp(bid, lo, hi)
        stepped = clamp(stepped, min_rub, max_rub)
        if abs(stepped - bid) > 0.5:
            src += "+step"
            bid = stepped
    reason = f"{src} cr={cr:.4f} mult={mult:.2f}"
    if account_cpl:
        reason += f" acc_cpl={account_cpl:.0f}"
    return round(bid, 2), cr, reason


def write_heatmap_html(path: Path, analysis: dict, account: dict) -> None:
    cells = analysis["cells"]
    max_c = max((int(v) for v in cells.values()), default=1) or 1
    rows = []
    for d in range(7):
        tds = []
        for h in range(24):
            n = int(cells.get(f"{d}-{h}", 0))
            alpha = 0.08 + 0.92 * (n / max_c)
            tds.append(
                f'<td title="{DOW[d]} {h:02d}:00 — {n}" '
                f'style="background:rgba(180,70,30,{alpha:.2f})">{n or ""}</td>'
            )
        rows.append(f"<tr><th>{DOW[d]}</th>{''.join(tds)}</tr>")
    hours_rows = "".join(
        f"<tr><td>{h['hour']:02d}:00</td><td>{h['messages']}</td>"
        f"<td>{h['ratio']}</td><td>{h['band']}</td></tr>"
        for h in analysis["hours"]
    )
    peak = ", ".join(f"{h:02d}:00" for h in analysis["peak_hours"]) or "—"
    quiet = ", ".join(f"{h:02d}:00" for h in analysis["quiet_hours"]) or "—"
    doc = f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"/>
<title>Авито — когда пишут</title>
<style>
body {{ font: 14px/1.4 Georgia, serif; margin: 24px; color: #1c140f; background: #f6f1ea; }}
h1 {{ font-weight: 500; }}
table {{ border-collapse: collapse; }}
td, th {{ border: 1px solid #ddd2c6; padding: 4px 6px; text-align: center; min-width: 22px; }}
th {{ background: #efe6db; }}
.note {{ max-width: 720px; }}
</style></head><body>
<h1>{html.escape(str(account.get('name') or 'Кабинет'))}</h1>
<p class="note">Чаты за период: <b>{analysis['total_chats']}</b>.
Пик heatmap: <b>{peak}</b>.
Тишина: <b>{quiet}</b>.
Множитель часа плавный {HOUR_MULT_MIN}…{HOUR_MULT_MAX} от доли сообщений; день недели {DOW_MULT_MIN}…{DOW_MULT_MAX}.
Среднее на час: {analysis['avg_per_hour']}.</p>
<table>
<tr><th></th>{''.join(f'<th>{h}</th>' for h in range(24))}</tr>
{''.join(rows)}
</table>
<h2>По часам (МСК)</h2>
<table><tr><th>час</th><th>чаты</th><th>к среднему</th><th>зона</th></tr>
{hours_rows}
</table>
<p>Дни недели: {html.escape(json.dumps(analysis['by_dow'], ensure_ascii=False))}</p>
</body></html>
"""
    path.write_text(doc, encoding="utf-8")


def run_once(args: argparse.Namespace) -> int:
    ensure_env()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    now = datetime.now(tz=MSK)
    since = now - timedelta(days=args.days)
    d1 = date.today()
    d0 = d1 - timedelta(days=args.days)
    d0s, d1s = d0.isoformat(), d1.isoformat()

    print("auth…", flush=True)
    token = get_token()
    self_data = fetch_self(token)
    user_id = int(self_data["id"])
    print(f"account {user_id} {self_data.get('name')}", flush=True)
    (out / "account_self.json").write_text(
        json.dumps({k: self_data.get(k) for k in ("id", "name", "profile_url", "email") if k in self_data or True}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    # keep only safe fields
    safe = {k: self_data[k] for k in self_data if k in ("id", "name", "email", "phone", "profile_url")}
    (out / "account_self.json").write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")

    print("чаты…", flush=True)
    chats = fetch_chats(token, user_id, int(since.timestamp()))
    analysis = analyze_messages(chats)
    (out / "message_hours.json").write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
    write_heatmap_html(out / "message_heatmap.html", analysis, safe)
    with (out / "message_hours.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["hour", "messages", "ratio", "band"])
        w.writeheader()
        w.writerows(analysis["hours"])
    print(
        f"чатов {analysis['total_chats']}; пик {analysis['peak_hours']}; тишина {analysis['quiet_hours']}",
        flush=True,
    )

    print("объявления…", flush=True)
    items = fetch_active_items(token)
    titles = {int(it["id"]): (it.get("title") or "")[:120] for it in items if it.get("id")}
    ids = list(titles)

    print("статистика кабинета…", flush=True)
    acc = fetch_account_totals(token, user_id, d0s, d1s)
    print("расходы периода…", flush=True)
    spend = fetch_spendings_rub(token, user_id, d0s, d1s)
    account_cpl = (spend / acc["contacts"]) if acc["contacts"] else None

    print("расходы / контакты за сегодня (пауза из‑за лимита spendings)…", flush=True)
    time.sleep(65)
    spend_today = fetch_spendings_rub(token, user_id, d1s, d1s)
    acc_day = fetch_account_totals(token, user_id, d1s, d1s)
    day_contacts = float(acc_day.get("contacts") or 0)
    day_cpl = (spend_today / day_contacts) if spend_today and day_contacts else None

    print("текущие продвижения…", flush=True)
    promos = get_promotions(token, ids)
    bid_samples = []
    for row in promos.values():
        man = row.get("manualPromotion") or {}
        if man.get("bidPenny"):
            bid_samples.append(float(man["bidPenny"]) / 100.0)
    avg_bid = (sum(bid_samples) / len(bid_samples)) if bid_samples else None
    # CR от клика: contacts / (spend/avg_bid). Иначе fallback на views.
    prior_src = "views"
    if spend > 0 and avg_bid and avg_bid > 0 and acc["contacts"]:
        clicks_est = spend / avg_bid
        if clicks_est >= acc["contacts"]:
            prior_cr = acc["contacts"] / clicks_est
            prior_src = "click_est"
        else:
            prior_cr = (acc["contacts"] / acc["views"]) if acc["views"] else 0.02
    else:
        prior_cr = (acc["contacts"] / acc["views"]) if acc["views"] else 0.02

    tm = time_multipliers(now, analysis)
    brake, brake_why = cpl_brake_factor(account_cpl, day_cpl)
    mult = round(tm["combined"] * brake, 3)
    band = tm["band"]
    print(
        f"кабинет views={acc['views']:.0f} contacts={acc['contacts']:.0f} "
        f"prior_cr={prior_cr:.4f}({prior_src}) spend≈{spend:.0f} cpl={account_cpl} "
        f"today_cpl={day_cpl} avg_bid={avg_bid}",
        flush=True,
    )
    print(
        f"сейчас {now:%Y-%m-%d %H:%M} МСК {tm['dow']} час={now.hour} зона={band} "
        f"hour×{tm['hour_mult']} dow×{tm['dow_mult']} brake×{brake}({brake_why}) → mult={mult}",
        flush=True,
    )

    print("статистика объявлений…", flush=True)
    stats = fetch_item_stats(token, user_id, ids, d0s, d1s)

    sample_bounds = None
    for iid in ids[:5]:
        detail = get_bids_detail(token, iid)
        time.sleep(0.2)
        if detail and detail.get("manual"):
            sample_bounds = detail["manual"]
            break
    default_min = (sample_bounds or {}).get("minBidPenny") or 100
    default_max = (sample_bounds or {}).get("maxBidPenny") or 50000

    # Живые объявления: есть трафик или уже стоит ставка. Мёртвые не крутим.
    live_rows: list[tuple[float, float, int]] = []
    dead = 0
    for iid in ids:
        st = stats.get(iid) or {"views": 0.0, "contacts": 0.0}
        promo = promos.get(iid) or {}
        man = promo.get("manualPromotion") or {}
        has_bid = bool(man.get("bidPenny"))
        if st["views"] >= LIVE_MIN_VIEWS or st["contacts"] >= MIN_CONTACTS_FOR_CR or has_bid:
            live_rows.append((st["contacts"], st["views"], iid))
        else:
            dead += 1
    live_rows.sort(key=lambda x: (-x[0], -x[1]))
    top_n = max(1, int(args.top_n))
    apply_top = max(1, int(args.apply_top))
    focus_ids = [iid for _, _, iid in live_rows[:top_n]]
    apply_ids = set(iid for _, _, iid in live_rows[:apply_top])
    print(
        f"живых {len(live_rows)} / мёртвых {dead}; фокус топ-{top_n}={len(focus_ids)}; "
        f"apply-top={apply_top}",
        flush=True,
    )

    decisions = []
    applied = 0
    for n, iid in enumerate(focus_ids):
        st = stats.get(iid) or {"views": 0.0, "contacts": 0.0}
        promo = promos.get(iid) or {}
        manual = promo.get("manualPromotion") or {}
        cur_penny = manual.get("bidPenny")
        current_rub = (cur_penny / 100.0) if cur_penny else None
        min_penny = int(default_min)
        max_penny = int(default_max)
        bid_rub, cr, reason = compute_bid_rub(
            views=st["views"],
            contacts=st["contacts"],
            prior_cr=prior_cr,
            mult=mult,
            min_rub=min_penny / 100.0,
            max_rub=max_penny / 100.0,
            current_rub=current_rub,
            account_cpl=day_cpl or account_cpl,
        )
        reason = f"{reason} {prior_src} brake={brake}"
        bid_penny = int(round(bid_rub * 100))
        bid_penny = max(min_penny, min(max_penny, bid_penny))
        action = "hold"
        status = ""
        action_type = int(promo.get("actionTypeID") or 0)
        if promo and action_type not in (0, ACTION_CLICK):
            action = "skip_other_action"
        change = current_rub is None or abs(bid_penny - int(cur_penny or 0)) >= 50
        if action == "hold" and change:
            if args.apply and iid in apply_ids:
                action = "set"
            else:
                action = "dry-run"
        row = {
            "item_id": iid,
            "title": titles.get(iid, ""),
            "views": int(st["views"]),
            "contacts": int(st["contacts"]),
            "cr": round(cr, 4),
            "current_bid_rub": current_rub,
            "new_bid_rub": round(bid_penny / 100.0, 2),
            "band": band,
            "mult": mult,
            "action": action,
            "reason": reason,
            "status": status,
        }
        if action == "set":
            detail = get_bids_detail(token, iid)
            time.sleep(3.1)
            if detail and detail.get("manual"):
                man = detail["manual"]
                min_penny = int(man.get("minBidPenny") or min_penny)
                max_penny = int(man.get("maxBidPenny") or max_penny)
                bid_penny = max(min_penny, min(max_penny, bid_penny))
                row["new_bid_rub"] = round(bid_penny / 100.0, 2)
            code, resp = set_manual_bid(token, iid, bid_penny, None)
            row["status"] = f"HTTP {code}"
            if code == 200:
                applied += 1
            else:
                row["status"] = f"HTTP {code} {str(resp)[:180]}"
            time.sleep(3.1)
            print(f"  set {iid} {row['new_bid_rub']}₽ → {row['status']}", flush=True)
        decisions.append(row)
        if (n + 1) % 25 == 0:
            print(f"  scored {n+1}/{len(focus_ids)}", flush=True)

    fields = [
        "item_id", "title", "views", "contacts", "cr",
        "current_bid_rub", "new_bid_rub", "band", "mult", "action", "reason", "status",
    ]
    with (out / "bids.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(decisions)

    would_change = sum(1 for r in decisions if r["action"] in ("dry-run", "set"))

    print("воронка показ→просмотр и план VAS…", flush=True)
    funnel = fetch_item_funnel(token, user_id, d0s, d1s)
    ledger_path = Path(__file__).resolve().parent / "state" / "vas_ledger.json"
    vas_max = max(0, min(VAS_HARD_CAP, int(args.vas_max)))
    vas_plan, _ledger = plan_vas(
        token=token,
        user_id=user_id,
        now=now,
        focus_ids=focus_ids,
        funnel=funnel,
        ledger_path=ledger_path,
        do_apply=bool(args.apply_vas),
        vas_max=vas_max,
    )
    vas_set = [p for p in vas_plan if p["action"] in ("dry-run", "set")]
    with (out / "vas_plan.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["item_id", "impressions", "views", "ctr", "slug", "price_rub", "action", "status"],
        )
        w.writeheader()
        w.writerows(vas_plan)
    print(f"  VAS слотов сегодня ≤{vas_max}; к подключению {len(vas_set)} (apply={bool(args.apply_vas)})", flush=True)

    summary = {
        "ran_at_msk": now.isoformat(timespec="minutes"),
        "account_id": user_id,
        "account_name": safe.get("name"),
        "cabinet_label": getattr(args, "cabinet_label", "") or args.cabinet,
        "niche": getattr(args, "niche", ""),
        "action_type": ACTION_CLICK,
        "days": args.days,
        "chats": analysis["total_chats"],
        "peak_hours": analysis["peak_hours"],
        "quiet_hours": analysis["quiet_hours"],
        "now_hour": now.hour,
        "dow": tm["dow"],
        "band": band,
        "hour_mult": tm["hour_mult"],
        "dow_mult": tm["dow_mult"],
        "cpl_brake": brake,
        "cpl_brake_why": brake_why,
        "multiplier": mult,
        "account_views": acc["views"],
        "account_contacts": acc["contacts"],
        "prior_cr": prior_cr,
        "prior_cr_source": prior_src,
        "avg_bid_rub": avg_bid,
        "spend_rub": spend,
        "spend_today_rub": spend_today,
        "account_cpl": account_cpl,
        "day_cpl": day_cpl,
        "day_contacts": day_contacts,
        "target_cpl": TARGET_CPL,
        "soft_cpl": SOFT_CPL,
        "hard_cpl": HARD_CPL,
        "items_active": len(ids),
        "items_live": len(live_rows),
        "items_dead": dead,
        "items_focus": len(focus_ids),
        "would_change": would_change,
        "apply": bool(args.apply),
        "apply_top": apply_top,
        "applied": applied,
        "vas_max_per_day": vas_max,
        "vas_candidates": len(vas_set),
        "vas_applied": sum(1 for p in vas_plan if p["action"] == "set"),
        "formula": (
            "bid = clamp(1000 * CR * hour_mult * dow_mult * cpl_brake, min, max); "
            "CR=item contacts/views or account click_est; only live top-N; ±30% step; "
            "VAS highlight/xl/sticker ≤1-2/day, skip if applied within 7 days"
        ),
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    with (out / "runs.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(summary, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            {
                k: summary[k]
                for k in (
                    "chats", "dow", "band", "multiplier", "prior_cr", "prior_cr_source",
                    "account_cpl", "day_cpl", "items_live", "items_focus", "would_change", "applied",
                    "vas_candidates", "vas_applied",
                )
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Универсальный автобидер Авито")
    p.add_argument("--cabinet", default="", help="имя файла в bider/cabinets без .json")
    p.add_argument("--days", type=int, default=None, help="окно сообщений и статистики")
    p.add_argument("--out", default="", help="папка результата")
    p.add_argument("--apply", action="store_true", help="записать ставки (иначе dry-run)")
    p.add_argument("--top-n", type=int, default=None, help="сколько живых объявлений считать")
    p.add_argument("--apply-top", type=int, default=None, help="при --apply писать ставки только топ-N")
    p.add_argument("--target-cpl", type=float, default=None, help="адекватная цена лида, ₽")
    p.add_argument("--soft-cpl", type=float, default=None, help="мягкий верх цены лида, ₽")
    p.add_argument("--brake-cpl", type=float, default=None, help="с этой цены лида начинать сильнее резать ставки")
    p.add_argument("--hard-cpl", type=float, default=None, help="жёсткий край цены лида, ₽")
    p.add_argument("--action-type", type=int, default=None, help="5 клики, 1 звонок, 7 мессенджер")
    p.add_argument("--loop", action="store_true", help="крутить непрерывно")
    p.add_argument("--interval-min", type=int, default=60, help="пауза между проходами в --loop")
    p.add_argument("--vas-max", type=int, default=None, help="новых XL/цвета/плашек в сутки, 0..2")
    p.add_argument("--apply-vas", action="store_true", help="купить VAS (иначе только план)")
    args = p.parse_args()
    bind_cabinet(args)
    if not args.out:
        args.out = str(Path(__file__).resolve().parent / "out")
    if not args.loop:
        return run_once(args)
    while True:
        try:
            run_once(args)
        except Exception as e:
            print(f"loop error: {e}", flush=True)
        print(f"sleep {args.interval_min} min", flush=True)
        time.sleep(max(5, args.interval_min) * 60)


if __name__ == "__main__":
    raise SystemExit(main())
