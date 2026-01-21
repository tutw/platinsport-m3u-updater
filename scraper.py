import argparse
import base64
import datetime as dt
import random
import re
import sys
import time
from typing import List, Optional, Tuple

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:  # pragma: no cover
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
# Playwright + backoff
# -----------------------------
def backoff_sleep(attempt: int, base: float, cap: float) -> None:
    delay = min(cap, base * (2 ** attempt)) + random.uniform(0, base)
    time.sleep(delay)


def fetch_html_with_playwright(
    target_url: str,
    *,
    seed_link_home: bool,
    max_retries: int,
    backoff_base: float,
    backoff_cap: float,
) -> str:
    last_html = ""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for attempt in range(max_retries):
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                locale="en-US",
                viewport={"width": 1366, "height": 768},
            )
            page = context.new_page()
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")

            def goto(url: str, wait_selector: Optional[str] = None) -> str:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                if wait_selector:
                    try:
                        page.wait_for_selector(wait_selector, timeout=30000)
                    except PlaywrightTimeoutError:
                        pass
                return page.content()

            try:
                if seed_link_home:
                    try:
                        goto(LINK_HOME)
                    except PlaywrightTimeoutError:
                        pass

                html = goto(target_url, wait_selector="div.myDiv1")
                last_html = html
                context.close()

                if has_schedule_container(html) and not looks_blocked(html):
                    browser.close()
                    return html

                if attempt < max_retries - 1:
                    backoff_sleep(attempt, backoff_base, backoff_cap)

            except Exception:
                try:
                    context.close()
                except Exception:
                    pass
                if attempt < max_retries - 1:
                    backoff_sleep(attempt, backoff_base, backoff_cap)

        browser.close()

    return last_html


# -----------------------------
# Extracción y salida M3U
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

    link_html = fetch_html_with_playwright(
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
    ap = argparse.ArgumentParser(description="Platinsport -> lista.m3u (Playwright + fallback + backoff)")
    ap.add_argument("--date", default=None, help="Forzar fecha (YYYY-MM-DD) para la key")
    ap.add_argument("--output", default="lista.m3u", help="Salida (default: lista.m3u)")
    ap.add_argument("--retries", type=int, default=4, help="Reintentos por URL (default: 4)")
    ap.add_argument("--backoff-base", type=float, default=1.0, help="Backoff base (default: 1.0)")
    ap.add_argument("--backoff-cap", type=float, default=10.0, help="Backoff máximo (default: 10.0)")
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

        html = fetch_html_with_playwright(
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
            last_reason = "No aparece div.myDiv1 (desfase/estructura)"
            continue

        entries = extract_entries_for_m3u(html)
        if not entries:
            print("Aviso: no se encontraron enlaces AceStream en la página (se genera solo cabecera).")
        write_m3u(entries, args.output)
        return

    print(f"Fallo tras probar fechas: {tried}. Motivo final: {last_reason}", file=sys.stderr)
    raise SystemExit(1)


if __name__ == "__main__":
    main()
