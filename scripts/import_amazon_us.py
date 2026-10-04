#!/usr/bin/env python3
"""Import Amazon.com (US) 'Comprar em Miami' wishlist into Compras."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, OrderedDict
from pathlib import Path
from urllib.parse import urlparse, urlunparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from compras_categories import all_category_defs, categorize, detect_store  # noqa: E402

SRC = Path(
    sys.argv[1]
    if len(sys.argv) > 1
    else "/home/ubuntu/.cursor/projects/workspace/uploads/amazon_us_6924.json"
)
LINKS = ROOT / "data" / "links.json"
AMZ_ICON = "https://www.google.com/s2/favicons?domain=www.amazon.com&sz=64"
STORE = "Amazon EUA"
LIST_NAME = "Comprar em Miami"
SOURCE = "amazon_us"
# Documented fixed rate for cross-currency price sort (USD → BRL).
USD_TO_BRL = 5.50

MERGE = {
    "compras-higiene": "compras-casa",
    "compras-esporte": "compras-camping",
}


def parse_usd(price: str | None) -> float | None:
    if not price:
        return None
    s = str(price).strip()
    if re.search(r"not available|unavailable|indispon", s, re.I):
        return None
    s = re.sub(r"[^\d.]", "", s)
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def format_usd(price: str | None) -> str | None:
    val = parse_usd(price)
    if val is None:
        return None
    # Keep two decimals like Amazon US display.
    if abs(val - round(val)) < 1e-9:
        return f"US$ {val:.0f}" if val >= 100 and val == int(val) else f"US$ {val:.2f}"
    return f"US$ {val:.2f}"


def clean_url(url: str) -> str:
    try:
        p = urlparse(url.strip())
        m = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", p.path, re.I)
        if m:
            host = p.netloc or "www.amazon.com"
            return f"https://{host}/dp/{m.group(1).upper()}"
        return urlunparse((p.scheme, p.netloc, p.path, "", "", ""))
    except Exception:
        return url.split("?")[0]


def norm_url(url: str) -> str:
    """Host-aware Amazon keys so .com and .com.br ASINs never collide."""
    try:
        p = urlparse(url.strip())
        host = (p.hostname or "").lower().removeprefix("www.")
        path = p.path.rstrip("/")
        m = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", path, re.I)
        if m and "amazon." in host:
            return f"{host}/{m.group(1).upper()}"
        m = re.search(r"(MLB-?\d+)", path, re.I)
        if m and ("mercadolivre" in host or "mercadolibre" in host):
            return f"mercadolivre/{m.group(1).upper().replace('MLB-', 'MLB')}"
        m = re.search(r"/item/(\d+)", path)
        if m and "aliexpress" in host:
            return f"aliexpress.com/item/{m.group(1)}"
        return f"{host}{path}"
    except Exception:
        return url.lower()


def shorten_title(title: str) -> str:
    t = re.sub(r"\s+", " ", (title or "").strip())
    t = re.sub(r"\s*[-–|]\s*Amazon.*$", "", t, flags=re.I)
    t = t.strip(" -–|,.")
    # Light PT polish where natural; keep English product names.
    replacements = (
        (r"\bSet\b", "Kit"),
        (r"\bPack\b", "Pacote"),
        (r"\bGloves\b", "Luvas"),
        (r"\bBatteries\b", "Pilhas"),
        (r"\bBattery\b", "Pilha"),
        (r"\bFlashlight\b", "Lanterna"),
        (r"\bFlashlights\b", "Lanternas"),
        (r"\bExtension Cord\b", "Extensão"),
        (r"\bCookware Set\b", "Jogo de panelas"),
        (r"\bWork Gloves\b", "Luvas de trabalho"),
    )
    for pat, repl in replacements:
        t = re.sub(pat, repl, t)
    if len(t) <= 60:
        return t
    cut = t[:60]
    for sep in (", ", " - ", " / ", " | ", " with ", " for ", " com ", " para ", " "):
        idx = cut.rfind(sep)
        if idx >= 28:
            return cut[:idx].rstrip(" -–,+|")
    return cut.rstrip() + "…"


def main() -> None:
    scrape = json.loads(SRC.read_text(encoding="utf-8"))
    data = json.loads(LINKS.read_text(encoding="utf-8"))

    wishlist = scrape.get("wishlist") or []
    cart_all = scrape.get("cart") or []

    by_key: OrderedDict[str, dict] = OrderedDict()
    skipped = 0

    def upsert(raw: dict) -> None:
        nonlocal skipped
        url = (raw.get("url") or "").strip()
        title = (raw.get("title") or "").strip()
        if not url or not title:
            skipped += 1
            return
        key = norm_url(url)
        full = title
        short = shorten_title(full)
        price = format_usd(raw.get("price"))
        # Account ships to Brazil → Amazon US marks many as unavailable.
        no_br = bool(raw.get("unavailable"))
        available = not no_br
        list_name = (raw.get("listName") or raw.get("list") or LIST_NAME).strip() or LIST_NAME
        cat_id, _ = categorize(full)
        cat_id = MERGE.get(cat_id, cat_id)

        if key in by_key:
            item = by_key[key]
            if price and not item.get("price"):
                item["price"] = price
                pv = parse_usd(raw.get("price"))
                if pv is not None:
                    item["price_value"] = round(pv * USD_TO_BRL, 2)
                    item["price_usd"] = pv
                item["currency"] = "USD"
            if no_br:
                item["available"] = False
                item["no_br_delivery"] = True
                item["note"] = "não entrega no Brasil / ver nos EUA"
            return

        item = {
            "title": short,
            "title_full": full,
            "url": clean_url(url),
            "section": "compras",
            "category": cat_id,
            "store": STORE,
            "icon": AMZ_ICON,
            "source": SOURCE,
            "available": available,
            "list": list_name,
            "tags": [list_name],
            "currency": "USD",
        }
        if no_br:
            item["no_br_delivery"] = True
            item["note"] = "não entrega no Brasil / ver nos EUA"
        if price:
            item["price"] = price
            pv = parse_usd(raw.get("price"))
            if pv is not None:
                item["price_usd"] = pv
                item["price_value"] = round(pv * USD_TO_BRL, 2)
        by_key[key] = item

    for raw in wishlist:
        upsert(raw)
    for raw in cart_all:
        upsert(raw)

    us_items = list(by_key.values())

    keep = []
    compras_existing = []
    for item in data["items"]:
        if item.get("section") != "compras":
            keep.append(item)
            continue
        if item.get("source") == SOURCE:
            continue
        key = norm_url(item.get("url") or "")
        if key in by_key:
            continue
        item = dict(item)
        blob = " ".join(
            filter(None, [item.get("title"), item.get("title_full"), item.get("note")])
        )
        cid, _ = categorize(blob)
        item["category"] = MERGE.get(cid, cid)
        if not item.get("store"):
            item["store"] = detect_store(item.get("url") or "")
        # Remap bare amazon.com bookmarks to Amazon EUA when still labeled Amazon
        host = (urlparse(item.get("url") or "").hostname or "").lower()
        if item.get("store") == "Amazon" and host.endswith("amazon.com") and not host.endswith(
            "amazon.com.br"
        ):
            item["store"] = STORE
        if "available" not in item:
            item["available"] = True
        compras_existing.append(item)

    all_compras = compras_existing + us_items
    for item in all_compras:
        blob = " ".join(
            filter(None, [item.get("title"), item.get("title_full"), item.get("note")])
        )
        cid, _ = categorize(blob)
        item["category"] = MERGE.get(cid, cid)

    used_ids = {i["category"] for i in all_compras}
    cat_defs = [c for c in all_category_defs() if c["id"] in used_ids]
    known = {c["id"] for c in cat_defs}
    for cid in sorted(used_ids - known):
        cat_defs.append({"id": cid, "title": cid, "section": "compras"})

    categories = [c for c in data["categories"] if c.get("section") != "compras"]
    categories.extend(cat_defs)
    data["categories"] = categories
    data["items"] = keep + all_compras

    LINKS.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    compras = [i for i in data["items"] if i["section"] == "compras"]
    us = [i for i in compras if i.get("source") == SOURCE]
    titles = {
        c["id"]: c["title"] for c in data["categories"] if c.get("section") == "compras"
    }
    print(f"wishlist={len(wishlist)} cart={len(cart_all)} skipped={skipped}")
    print(
        f"amazon_us_unique={len(us)} with_price={sum(1 for i in us if i.get('price'))} "
        f"no_br_delivery={sum(1 for i in us if i.get('no_br_delivery'))} "
        f"usd_to_brl={USD_TO_BRL}"
    )
    print(f"compras_total={len(compras)}")
    print("by_store", dict(Counter(i.get("store") or "Outros" for i in compras)))
    print("amazon_us by_category:")
    for cid, n in Counter(i["category"] for i in us).most_common():
        print(f"  {n:4d}  {titles.get(cid, cid)}")
    outros = [i for i in us if i["category"] == "compras-outros"]
    if outros:
        print("still Outros:")
        for i in outros:
            print(" ", (i.get("title_full") or i.get("title"))[:100])


if __name__ == "__main__":
    main()
