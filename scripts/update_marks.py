#!/usr/bin/env python3
"""Забирает планки отметок с blitzhata.ru/marks и пишет data.js.

Берёт уровни X, IX и VIII. Если страница не скачалась или разобралась
подозрительно (мало танков), старый data.js не трогается и скрипт
завершается с ошибкой, чтобы GitHub прислал уведомление.
"""
import datetime
import json
import re
import sys
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

URL = "https://blitzhata.ru/marks"
OUT = Path(__file__).resolve().parent.parent / "data.js"
TIERS = {"X": "10", "IX": "9", "VIII": "8"}
MIN_TANKS = {"10": 40, "9": 20, "8": 40}


class MarksParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tier = None          # "10" / "9" / "8" или None
        self.in_h = False
        self.h_text = ""
        self.in_cell = False
        self.cell = ""
        self.row = None
        self.data = {t: [] for t in TIERS.values()}

    def handle_starttag(self, tag, attrs):
        if tag in ("h1", "h2", "h3"):
            self.in_h, self.h_text = True, ""
        elif tag == "tr":
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.in_cell, self.cell = True, ""

    def handle_endtag(self, tag):
        if tag in ("h1", "h2", "h3") and self.in_h:
            self.in_h = False
            m = re.search(r"\b(VIII|IX|X|VII|VI|V|IV|III|II|I)\s+уров", self.h_text)
            if m:
                self.tier = TIERS.get(m.group(1))
        elif tag in ("td", "th") and self.in_cell:
            self.in_cell = False
            self.row.append(" ".join(self.cell.split()))
        elif tag == "tr" and self.row is not None:
            self.add_row(self.row)
            self.row = None

    def handle_data(self, d):
        if self.in_h:
            self.h_text += d
        if self.in_cell:
            self.cell += d

    def add_row(self, cells):
        if not self.tier or len(cells) < 4:
            return
        name = cells[0].strip()
        if not name or name.lower() == "танк":
            return
        marks = []
        for c in cells[1:4]:
            digits = re.sub(r"\D", "", c)
            marks.append(int(digits) if digits else None)
        if all(v is None for v in marks):
            return
        self.data[self.tier].append([name] + marks)


def main():
    req = urllib.request.Request(URL, headers={
        "User-Agent": "Mozilla/5.0 (compatible; marks-calculator; weekly update)",
        "Accept-Language": "ru,en;q=0.8",
    })
    with urllib.request.urlopen(req, timeout=60) as r:
        html = r.read().decode("utf-8", errors="replace")

    p = MarksParser()
    p.feed(html)

    for tier, need in MIN_TANKS.items():
        got = len(p.data[tier])
        print(f"Уровень {tier}: {got} танков")
        if got < need:
            sys.exit(f"Слишком мало танков на уровне {tier} ({got} < {need}) — "
                     "похоже, сайт поменял вёрстку. data.js не изменён.")

    payload = {
        "updated": datetime.date.today().isoformat(),
        "source": URL,
        "tiers": p.data,
    }
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    new = f"window.MARKS={body};\n"

    # Не коммитим, если поменялась только дата
    if OUT.exists():
        old = OUT.read_text(encoding="utf-8")
        m = re.search(r'"tiers":(\{.*\})\}', old)
        if m and json.loads(m.group(1)) == p.data:
            print("Планки не изменились.")
            return
    OUT.write_text(new, encoding="utf-8")
    print("data.js обновлён.")


if __name__ == "__main__":
    main()
