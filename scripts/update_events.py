#!/usr/bin/env python3
"""events.json-ийг ForexFactory-ийн долоо хоногийн хуанлиар шинэчилнэ.

GitHub Actions өдөр бүр ажиллуулна. Гараар бичсэн мэдээг (src != "ForexFactory")
хэзээ ч устгахгүй — зөвхөн шинэ мэдээ нэмж, ForexFactory-ийн мэдээг шинэчилнэ.
"""
import json
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

FEED = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
PATH = sys.argv[1] if len(sys.argv) > 1 else "events.json"
SRC = "ForexFactory"
KEEP_DAYS = 120  # үүнээс хуучин FF мэдээг цэвэрлэнэ

COUNTRY = {"USD": "АНУ", "GBP": "Их Британи", "JPY": "Япон"}
TAGS = {"USD": ["XAU", "XAG", "DXY"], "GBP": ["GBPJPY"], "JPY": ["GBPJPY", "XAU"]}
IMP = {"High": 3, "Medium": 2}
# Апп өөрөө үүсгэдэг тул алгасна (давхардахгүйн тулд)
SKIP = re.compile(r"unemployment claims|crude oil inventories", re.I)
# Гарчгаас богино код
CODES = [
    (r"speaks|testifies|press conference", "Speech"), (r"minutes", "Minutes"),
    (r"non-farm|nfp", "NFP"), (r"fomc|federal funds", "FOMC"), (r"core pce|pce price", "PCE"),
    (r"ppi", "PPI"), (r"cpi", "CPI"), (r"retail sales", "Retail"), (r"gdp", "GDP"),
    (r"ism", "ISM"), (r"jolts", "JOLTS"), (r"employment cost", "ECI"),
    (r"boe|mpc|official bank rate", "BoE"), (r"boj|monetary policy statement", "BoJ"),
    (r"claimant|average earnings|unemployment rate", "Jobs"), (r"pmi", "PMI"),
    (r"uom|consumer sentiment", "UoM"),
]


def code_of(title, cur):
    for pat, code in CODES:
        if re.search(pat, title, re.I):
            if cur == "GBP" and code in ("CPI", "GDP", "Jobs", "Retail", "PMI"):
                return "UK " + code
            if cur == "JPY" and code not in ("BoJ", "Speech"):
                return "JP " + code
            return code
    return re.sub(r"[^A-Za-z]", "", title.split()[0])[:8] or "News"


def to_utc(s):
    return datetime.fromisoformat(s).astimezone(timezone.utc)


def fmt(dt):
    return dt.strftime("%Y-%m-%dT%H:%MZ")


def main():
    req = urllib.request.Request(FEED, headers={"User-Agent": "Mozilla/5.0 trade-notes-bot"})
    with urllib.request.urlopen(req, timeout=30) as r:
        feed = json.load(r)

    with open(PATH, encoding="utf-8") as f:
        data = json.load(f)
    items = data.get("items", [])

    fresh = []
    for e in feed:
        cur, imp = e.get("country"), IMP.get(e.get("impact"))
        if cur not in COUNTRY or not imp or SKIP.search(e.get("title", "")):
            continue
        dt = to_utc(e["date"])
        title = e["title"].strip()
        code = code_of(title, cur)
        note = " · ".join(x for x in [
            ("Таамаг " + e["forecast"]) if e.get("forecast") else "",
            ("Өмнөх " + e["previous"]) if e.get("previous") else "",
        ] if x)
        tags = list(TAGS[cur]) + (["OIL"] if cur == "USD" and imp == 3 else [])
        fresh.append({
            "id": "ff-" + dt.strftime("%Y%m%d%H%M") + "-" + re.sub(r"[^A-Za-z0-9]", "", title)[:24],
            "t": fmt(dt), "code": code, "title": COUNTRY[cur] + " · " + title,
            "imp": imp, "tags": tags, "cur": cur, "note": note, "src": SRC,
            "allDay": False, "approx": False,
        })
    if not fresh:
        print("feed хоосон — өөрчлөлтгүй")
        return

    lo = min(to_utc(e["date"]) for e in feed) - timedelta(hours=12)
    hi = max(to_utc(e["date"]) for e in feed) + timedelta(hours=12)
    cutoff = datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)

    def t_of(x):
        return datetime.strptime(x["t"], "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)

    manual = [x for x in items if x.get("src") != SRC]
    old_ff = [x for x in items if x.get("src") == SRC and not (lo <= t_of(x) <= hi) and t_of(x) >= cutoff]

    # Гараар бичсэн мэдээтэй давхардвал (ижил валют, ижил код, ±90 мин) FF-ийнхийг алгасна
    def dup(x):
        tx = t_of(x)
        return any(m["cur"] == x["cur"] and m["code"] == x["code"]
                   and abs((t_of(m) - tx).total_seconds()) <= 90 * 60 for m in manual)

    new_items = manual + old_ff + [x for x in fresh if not dup(x)]
    new_items.sort(key=lambda x: (x["t"], x["id"]))

    if new_items == items:
        print("өөрчлөлтгүй")
        return
    data["items"] = new_items
    data["updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("шинэчлэгдлээ:", len(new_items), "мэдээ")


if __name__ == "__main__":
    main()
