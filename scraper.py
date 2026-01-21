import argparse
import base64
import datetime as dt
import json
import random
import re
import sys
import time
from typing import List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:
    ZoneInfo = None


BASE_URL = "https://www.platinsport.com"
LINK_HOME = f"{BASE_URL}/link/"
SOURCE_LIST_PATH = "/link/source-list.php?key="
MADRID_TZ = "Europe/Madrid"


# -----------------------------
# Fecha / key
# -----------------------------
def madrid_today_and_yesterday() -> Tuple[str, str]:
    if ZoneInfo is None:
        now = dt.datetime.utcnow()
    else:
        now = dt.datetime.now(ZoneInfo(MADRID_TZ))
    today = now.date()
    yesterday = today - dt.timedelta(days=1)
    return today.strftime("%Y-%m-%d"), yesterday.strftime("%Y-%m-%d")


def encode_key(date_str: str) -> str:
    raw = f"{date_str}PLATINSPORT"
    return base64.b64encode(raw.encode("utf-8")).decode("utf-8")


def make_source_list_url(date_str: str) -> str:
    return f"{BASE_URL}{SOURCE_LIST_PATH}{encode_key(date_str)}"


# -----------------------------
# Detección bloqueo / éxito
# -----------------------------
def looks_blocked(html: str) -> bool:
    h = (html or "").lower()
    needles = ["403 forbidden", "access denied", "captcha", "cloudflare", "attention required"]
    return any(n in h for n in needles)


def has_schedule_container(html: str) -> bool:
    h = (html or "").lower()
    return 'class="mydiv1"' in h or "class='mydiv1'" in h


# -----------------------------
# Fecha desde /link/
# -----------------------------
_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12
}


def parse_page_date_to_yyyy_mm_dd(page_html: str) -> Optional[str]:
    soup = BeautifulSoup(page_html, "html.parser")
    candidates = soup.find_all("div", class_="myDiv")
    pattern = re.compile(r"\b(\d{1,2})(st|nd|rd|th)?\s+([A-Za-z]+)\s+(\d{4})\b")

    for div in candidates:
        text = div.get_text(" ", strip=True)
        if not text:
            continue
        m = pattern.search(text)
        if not m:
            continue

        day = int(m.group(1))
        month_name = m.group(3).lower()
        year = int(m.group(4))
        month = _MONTHS.get(month_name)
        if not month:
            continue

        try:
            return dt.date(year, month, day).strftime("%Y-%m-%d")
        except ValueError:
            return None

    return None


# -----------------------------
# Fetch con requests + backoff + sesión
# -----------------------------
def backoff_sleep(attempt: int, base: float, cap: float) -> None:
    delay = min(cap, base * (2 ** attempt)) + random.uniform(0, base)
    time.sleep(delay)


def fetch_html_with_requests(
    target_url: str,
    *,
    seed_link_home: bool,
    max_retries: int,
    backoff_base: float,
    backoff_cap: float,
) -> str:
    """
    Usa requests (no Playwright) con sesión persistente y User-Agent real.
    """
    session = requests.Session()
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }

    last_html = ""

    for attempt in range(max_retries):
        try:
            # Seed cookies/sesión si es necesario
            if seed_link_home:
                try:
                    session.get(LINK_HOME, headers=headers, timeout=30)
                    time.sleep(random.uniform(1, 2))  # Pausa humana
                except Exception:
                    pass

            # Petición real
            resp = session.get(target_url, headers={**headers, 'Referer': LINK_HOME}, timeout=30)
            resp.raise_for_status()
            last_html = resp.text

            if not looks_blocked(last_html) and has_schedule_container(last_html):
                return last_html

            # Si bloqueado, reintenta
            if attempt < max_retries - 1:
                backoff_sleep(attempt, backoff_base, backoff_cap)

        except Exception as e:
            if attempt < max_retries - 1:
                backoff_sleep(attempt, backoff_base, backoff_cap)
            continue

    return last_html


# -----------------------------
# Extracción y M3U
# -----------------------------
def extract_entries_for_m3u(html: str) -> List[Tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    container = soup.find("div", class_="myDiv1")
    if not container:
        raise RuntimeError("No se encontró div.myDiv1 (bloqueo o estructura cambiada).")

    entries: List[Tuple[str, str]] = []
    current_league = "Unknown League"
    current_match = ""

    for node in container.children:
        if getattr(node, "name", None) is None:
            continue

        if node.name == "p":
            txt = node.get_text(strip=True)
            if txt:
                current_league = txt
            continue

        classes = node.get("class", []) or []
        if node.name == "div" and "match-title-bar" in classes:
            current_match = node.get_text(" ", strip=True)

            next_div = node.find_next_sibling("div")
            if next_div and "button-group" in (next_div.get("class", []) or []):
                for a in next_div.find_all("a"):
                    href = (a.get("href") or "").strip()
                    if href.startswith("acestream://"):
                        channel = a.get_text(" ", strip=True)
                        title = f"{current_league} | {current_match} | {channel}"
                        entries.append((title, href))

    return entries


def write_m3u(entries: List[Tuple[str, str]], output_path: str) -> None:
    seen = set()
    unique: List[Tuple[str, str]] = []
    for title, url in entries:
        if url in seen:
            continue
        seen.add(url)
        unique.append((title, url))

    with open(output_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("#EXTM3U\n")
        for title, url in unique:
            f.write(f"#EXTINF:-1,{title}\n")
            f.write(f"{url}\n")

    print(f"OK: {len(unique)} enlaces AceStream guardados en {output_path}")


# -----------------------------
# Fallback automático 3 fechas
# -----------------------------
def get_candidate_dates(
    date_forced: Optional[str],
    retries: int,
    backoff_base: float,
    backoff_cap: float
) -> List[str]:
    if date_forced:
        return [date_forced]

    today_m, yesterday_m = madrid_today_and_yesterday()
    candidates = [today_m, yesterday_m]

    link_html = fetch_html_with_requests(
        LINK_HOME,
        seed_link_home=False,
        max_retries=retries,
        backoff_base=backoff_base,
        backoff_cap=backoff_cap,
    )
    detected = parse_page_date_to_yyyy_mm_dd(link_html) if link_html else None
    if detected and detected not in candidates:
        candidates.append(detected)

    return candidates


def main() -> None:
    ap = argparse.ArgumentParser(description="Platinsport -> lista.m3u (requests + fallback)")
    ap.add_argument("--date", default=None, help="Forzar fecha (YYYY-MM-DD)")
    ap.add_argument("--output", default="lista.m3u", help="Salida (default: lista.m3u)")
    ap.add_argument("--retries", type=int, default=5, help="Reintentos por URL (default: 5)")
    ap.add_argument("--backoff-base", type=float, default=2.0, help="Backoff base (default: 2.0)")
    ap.add_argument("--backoff-cap", type=float, default=30.0, help="Backoff máximo (default: 30.0)")
    args = ap.parse_args()

    retries = max(1, args.retries)
    backoff_base = max(0.1, args.backoff_base)
    backoff_cap = max(0.1, args.backoff_cap)

    dates = get_candidate_dates(args.date, retries, backoff_base, backoff_cap)
    print(f"Fechas candidatas: {dates}")

    tried = []
    last_reason = None

    for d in dates:
        tried.append(d)
        url = make_source_list_url(d)
        print(f"Intentando fecha={d} url={url}")

        html = fetch_html_with_requests(
            url,
            seed_link_home=True,
            max_retries=retries,
            backoff_base=backoff_base,
            backoff_cap=backoff_cap,
        )

        if not html:
            last_reason = "HTML vacío"
            continue
        if looks_blocked(html):
            last_reason = "Bloqueo (403/captcha/challenge)"
            continue
        if not has_schedule_container(html):
            last_reason = "No aparece div.myDiv1"
            continue

        entries = extract_entries_for_m3u(html)
        if not entries:
            print("Aviso: no hay AceStream links (se genera cabecera vacía)")
        write_m3u(entries, args.output)
        return

    print(f"Fallo tras probar fechas: {tried}. Motivo: {last_reason}", file=sys.stderr)
    raise SystemExit(1)


if __name__ == "__main__":
    main()
