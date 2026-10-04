#!/usr/bin/env python3
"""Import Amazon.com.br wishlist/cart/saved into Compras."""

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
    else "/home/ubuntu/.cursor/projects/workspace/uploads/amazon_6add.json"
)
LINKS = ROOT / "data" / "links.json"
AMZ_ICON = "https://www.google.com/s2/favicons?domain=www.amazon.com.br&sz=64"

MERGE = {
    "compras-higiene": "compras-casa",
    "compras-esporte": "compras-camping",
}


def parse_price(price: str | None) -> float | None:
    if not price:
        return None
    s = str(price).strip()
    if re.search(r"não disponível|indispon", s, re.I):
        return None
    s = re.sub(r"[^\d.,]", "", s)
    if not s:
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def clean_url(url: str) -> str:
    try:
        p = urlparse(url.strip())
        # Prefer /dp/ASIN form
        m = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", p.path, re.I)
        if m:
            host = p.netloc or "www.amazon.com.br"
            return f"https://{host}/dp/{m.group(1).upper()}"
        return urlunparse((p.scheme, p.netloc, p.path, "", "", ""))
    except Exception:
        return url.split("?")[0]


def norm_url(url: str) -> str:
    try:
        p = urlparse(url.strip())
        host = (p.hostname or "").lower().removeprefix("www.")
        path = p.path.rstrip("/")
        m = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", path, re.I)
        if m and "amazon." in host:
            return f"amazon/{m.group(1).upper()}"
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
    if len(t) <= 60:
        return t
    cut = t[:60]
    for sep in (", ", " - ", " / ", " | ", " com ", " para ", " "):
        idx = cut.rfind(sep)
        if idx >= 28:
            return cut[:idx].rstrip(" -–,+|")
    return cut.rstrip() + "…"


def format_price(price: str | None) -> str | None:
    if price is None:
        return None
    s = str(price).strip()
    if not s or re.search(r"não disponível|indispon", s, re.I):
        return None
    if not s.startswith("R$"):
        s = f"R$ {s}"
    return re.sub(r"R\$\s*", "R$ ", s).strip()


def main() -> None:
    scrape = json.loads(SRC.read_text(encoding="utf-8"))
    data = json.loads(LINKS.read_text(encoding="utf-8"))

    wishlist = scrape.get("wishlist") or []
    cart_all = scrape.get("cart") or []

    by_key: OrderedDict[str, dict] = OrderedDict()
    skipped = 0

    def upsert(raw: dict, *, in_cart: bool = False, saved: bool = False) -> None:
        nonlocal skipped
        url = (raw.get("url") or "").strip()
        title = (raw.get("title") or "").strip()
        if not url or not title:
            skipped += 1
            return
        key = norm_url(url)
        full = title
        short = shorten_title(full)
        price = format_price(raw.get("price"))
        unavailable = bool(raw.get("unavailable")) or price is None
        available = not unavailable
        qty = raw.get("qty")
        cat_id, _ = categorize(full)
        cat_id = MERGE.get(cat_id, cat_id)

        if key in by_key:
            item = by_key[key]
            if in_cart:
                item["in_cart"] = True
                if qty is not None:
                    item["qty"] = qty
            if saved:
                item["saved_for_later"] = True
            if price and not item.get("price"):
                item["price"] = price
                pv = parse_price(price)
                if pv is not None:
                    item["price_value"] = pv
                item["available"] = True
                if item.get("note") == "Indisponível":
                    item.pop("note", None)
            if unavailable and not item.get("price"):
                item["available"] = False
                item["note"] = "Indisponível"
            return

        item = {
            "title": short,
            "title_full": full,
            "url": clean_url(url),
            "section": "compras",
            "category": cat_id,
            "store": "Amazon",
            "icon": AMZ_ICON,
            "source": "amazon",
            "available": available,
            "in_cart": in_cart,
        }
        if saved:
            item["saved_for_later"] = True
        if price:
            item["price"] = price
            pv = parse_price(price)
            if pv is not None:
                item["price_value"] = pv
        else:
            item["note"] = "Indisponível"
        if in_cart and qty is not None:
            item["qty"] = qty
        list_name = raw.get("list")
        if list_name:
            item["list"] = list_name
        by_key[key] = item

    for raw in wishlist:
        upsert(raw)
    for raw in cart_all:
        where = (raw.get("where") or "cart").lower()
        if where == "saved":
            upsert(raw, saved=True)
        else:
            upsert(raw, in_cart=True)

    amz_items = list(by_key.values())

    # Keep non-compras + existing compras (except prior amazon import); append Amazon
    keep = []
    compras_existing = []
    for item in data["items"]:
        if item.get("section") != "compras":
            keep.append(item)
            continue
        if item.get("source") == "amazon":
            continue
        key = norm_url(item.get("url") or "")
        if key in by_key:
            # Prefer marketplace scrape; merge flags onto Amazon entry
            amz = by_key[key]
            if item.get("in_cart"):
                amz["in_cart"] = True
            if item.get("saved_for_later"):
                amz["saved_for_later"] = True
            continue
        item = dict(item)
        blob = " ".join(
            filter(None, [item.get("title"), item.get("title_full"), item.get("note")])
        )
        cid, _ = categorize(blob)
        item["category"] = MERGE.get(cid, cid)
        if not item.get("store"):
            item["store"] = detect_store(item.get("url") or "")
        if "available" not in item:
            item["available"] = True
        compras_existing.append(item)

    all_compras = compras_existing + amz_items
    for item in all_compras:
        # Title/note only — URLs like amazon.com.br must not hit "Serviços / Lojas".
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
    amz = [i for i in compras if i.get("source") == "amazon"]
    titles = {
        c["id"]: c["title"] for c in data["categories"] if c.get("section") == "compras"
    }
    print(f"wishlist={len(wishlist)} cart_entries={len(cart_all)} skipped={skipped}")
    print(
        f"amazon_unique={len(amz)} in_cart={sum(1 for i in amz if i.get('in_cart'))} "
        f"saved={sum(1 for i in amz if i.get('saved_for_later'))} "
        f"unavailable={sum(1 for i in amz if not i.get('available'))}"
    )
    print(f"compras_total={len(compras)}")
    print("by_store", dict(Counter(i.get("store") or "Outros" for i in compras)))
    print("amazon by_category:")
    for cid, n in Counter(i["category"] for i in amz).most_common():
        print(f"  {n:4d}  {titles.get(cid, cid)}")


if __name__ == "__main__":
    main()
