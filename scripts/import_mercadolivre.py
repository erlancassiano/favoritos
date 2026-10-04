#!/usr/bin/env python3
"""Import Mercado Livre favorites/cart and reclassify all Compras items."""

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
    else "/home/ubuntu/.cursor/projects/workspace/uploads/mercadolivre_037e.json"
)
LINKS = ROOT / "data" / "links.json"
ML_ICON = "https://www.google.com/s2/favicons?domain=www.mercadolivre.com.br&sz=64"


def parse_price(price: str | None) -> float | None:
    if not price:
        return None
    s = re.sub(r"[^\d.,]", "", str(price).strip())
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
        return urlunparse((p.scheme, p.netloc, p.path, "", "", ""))
    except Exception:
        return url.split("?")[0]


def norm_url(url: str) -> str:
    try:
        p = urlparse(url.strip())
        host = (p.hostname or "").lower().removeprefix("www.")
        path = p.path.rstrip("/")
        # MLB product ids
        m = re.search(r"(MLB-?\d+)", path, re.I)
        if m and ("mercadolivre" in host or "mercadolibre" in host):
            return f"mercadolivre/{m.group(1).upper().replace('MLB-', 'MLB')}"
        m = re.search(r"/up/(MLBU\d+)", path, re.I)
        if m:
            return f"mercadolivre/{m.group(1).upper()}"
        m = re.search(r"/item/(\d+)", path)
        if m and "aliexpress" in host:
            return f"aliexpress.com/item/{m.group(1)}"
        return f"{host}{path}"
    except Exception:
        return url.lower()


def shorten_title(title: str) -> str:
    t = re.sub(r"\s+", " ", (title or "").strip())
    t = re.sub(r"\s*[-–|]\s*(Mercado Livre|AliExpress).*$", "", t, flags=re.I)
    t = t.strip(" -–|,")
    if len(t) <= 60:
        return t
    cut = t[:60]
    for sep in (", ", " - ", " / ", " com ", " para ", " + ", " "):
        idx = cut.rfind(sep)
        if idx >= 28:
            return cut[:idx].rstrip(" -–,+")
    return cut.rstrip() + "…"


def main() -> None:
    scrape = json.loads(SRC.read_text(encoding="utf-8"))
    data = json.loads(LINKS.read_text(encoding="utf-8"))

    favorites = scrape.get("favorites") or []
    cart = scrape.get("cart") or []

    by_key: OrderedDict[str, dict] = OrderedDict()
    skipped = 0

    def upsert(raw: dict, *, in_cart: bool) -> None:
        nonlocal skipped
        url = (raw.get("url") or "").strip()
        title = (raw.get("title") or "").strip()
        if not url or not title:
            skipped += 1
            return
        key = norm_url(url)
        full = title
        short = shorten_title(full)
        price = raw.get("price") or None
        unavailable = bool(raw.get("unavailable")) or not price
        available = not unavailable
        qty = raw.get("qty")
        cat_id, cat_title = categorize(full)

        if key in by_key:
            item = by_key[key]
            if in_cart:
                item["in_cart"] = True
                if qty is not None:
                    item["qty"] = qty
            if price and not item.get("price"):
                item["price"] = price
                pv = parse_price(price)
                if pv is not None:
                    item["price_value"] = pv
                item["available"] = True
                if item.get("note") == "Indisponível":
                    item.pop("note", None)
            if unavailable:
                item["available"] = False
                item["note"] = "Indisponível"
            return

        item = {
            "title": short,
            "title_full": full,
            "url": clean_url(url),
            "section": "compras",
            "category": cat_id,
            "store": "Mercado Livre",
            "icon": ML_ICON,
            "source": "mercadolivre",
            "available": available,
            "in_cart": in_cart,
        }
        if price:
            item["price"] = price if str(price).strip().startswith("R$") else f"R$ {price}"
            # normalize double spaces in "R$ 56,90"
            item["price"] = re.sub(r"R\$\s*", "R$ ", str(item["price"])).strip()
            pv = parse_price(item["price"])
            if pv is not None:
                item["price_value"] = pv
        else:
            item["note"] = "Indisponível"
        if in_cart and qty is not None:
            item["qty"] = qty
        item["_cat_title"] = cat_title
        by_key[key] = item

    for raw in favorites:
        upsert(raw, in_cart=False)
    for raw in cart:
        upsert(raw, in_cart=True)

    ml_items = list(by_key.values())
    for item in ml_items:
        item.pop("_cat_title", None)

    # Rebuild all items: keep non-compras; reclassify existing compras; append ML
    # Drop previous mercadolivre source on re-run
    keep = []
    compras_existing = []
    for item in data["items"]:
        if item.get("section") != "compras":
            keep.append(item)
            continue
        if item.get("source") == "mercadolivre":
            continue
        # Dedup against new ML by URL
        key = norm_url(item.get("url") or "")
        if key in by_key:
            continue
        item = dict(item)
        blob = " ".join(
            filter(
                None,
                [
                    item.get("title"),
                    item.get("title_full"),
                    item.get("url"),
                    item.get("note"),
                    item.get("store"),
                ],
            )
        )
        cid, _ = categorize(blob)
        item["category"] = cid
        if not item.get("store"):
            item["store"] = detect_store(item.get("url") or "")
        if "available" not in item:
            item["available"] = True
        compras_existing.append(item)

    # Also reclassify freshly imported ML (already categorized) + existing
    # Re-run categorize on existing again after merge for consistency
    all_compras = compras_existing + ml_items
    # Merge tiny categories into neighbors to keep ~12–18 buckets.
    MERGE = {
        "compras-higiene": "compras-casa",
        "compras-esporte": "compras-camping",
    }
    for item in all_compras:
        blob = " ".join(
            filter(
                None,
                [
                    item.get("title"),
                    item.get("title_full"),
                    item.get("url"),
                    item.get("note"),
                ],
            )
        )
        cid, _ = categorize(blob)
        item["category"] = MERGE.get(cid, cid)

    # Category registry: only those used + stable order from rules
    used_ids = {i["category"] for i in all_compras}
    cat_defs = [c for c in all_category_defs() if c["id"] in used_ids]
    # Ensure any unexpected ids appear
    known = {c["id"] for c in cat_defs}
    for cid in sorted(used_ids - known):
        cat_defs.append({"id": cid, "title": cid, "section": "compras"})

    categories = [c for c in data["categories"] if c.get("section") != "compras"]
    categories.extend(cat_defs)

    data["categories"] = categories
    data["items"] = keep + all_compras

    for s in data["sections"]:
        if s["id"] == "compras":
            s["description"] = (
                "Wishlist, carrinho e favoritos — filtre por loja e ordene por preço"
            )

    LINKS.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    compras = [i for i in data["items"] if i["section"] == "compras"]
    titles = {c["id"]: c["title"] for c in data["categories"] if c["section"] == "compras"}
    by_cat = Counter(i["category"] for i in compras)
    by_store = Counter(i.get("store") or "Outros" for i in compras)
    ml = [i for i in compras if i.get("source") == "mercadolivre"]

    print(f"favorites={len(favorites)} cart={len(cart)} skipped_no_url={skipped}")
    print(
        f"ml_unique={len(ml)} in_cart={sum(1 for i in ml if i.get('in_cart'))} "
        f"unavailable={sum(1 for i in ml if not i.get('available'))}"
    )
    print(f"compras_total={len(compras)}")
    print("by_store", dict(by_store.most_common()))
    print("by_category:")
    for cid, n in by_cat.most_common():
        print(f"  {n:4d}  {titles.get(cid, cid)}")
    outros = by_cat.get("compras-outros", 0)
    print(f"outros={outros}")
    if outros > 25:
        print("WARN: Outros still high; listing titles:")
        for i in compras:
            if i["category"] == "compras-outros":
                print("   ", i.get("store"), "|", (i.get("title_full") or i["title"])[:80])


if __name__ == "__main__":
    main()
