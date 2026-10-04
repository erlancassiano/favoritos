#!/usr/bin/env python3
"""Import Shopee cart TSV into Compras."""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter, OrderedDict
from pathlib import Path
from urllib.parse import quote, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from compras_categories import all_category_defs, categorize, detect_store  # noqa: E402

SRC = Path(
    sys.argv[1]
    if len(sys.argv) > 1
    else "/home/ubuntu/.cursor/projects/workspace/uploads/shopee_cart_59eb.tsv"
)
LINKS = ROOT / "data" / "links.json"
SHOPEE_ICON = "https://www.google.com/s2/favicons?domain=shopee.com.br&sz=64"
SOURCE = "shopee"

MERGE = {
    "compras-higiene": "compras-casa",
    "compras-esporte": "compras-camping",
}


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


def format_price(price: str | None) -> str | None:
    if price is None:
        return None
    s = str(price).strip()
    if not s:
        return None
    if not s.startswith("R$"):
        s = f"R$ {s}"
    return re.sub(r"R\$\s*", "R$ ", s).strip()


def product_url(shop_item: str, title: str) -> str:
    sid = (shop_item or "").strip()
    if sid and "." in sid:
        shop, item = sid.split(".", 1)
        if shop.isdigit() and item.isdigit():
            return f"https://shopee.com.br/product/{shop}/{item}"
    return f"https://shopee.com.br/search?keyword={quote(title)}"


def product_key(shop_item: str, title: str) -> str:
    """Keep variations of the same shopid.itemid as separate rows."""
    sid = (shop_item or "").strip()
    t = re.sub(r"\s+", " ", (title or "").strip().lower())
    if sid and "." in sid:
        shop, item = sid.split(".", 1)
        if shop.isdigit() and item.isdigit():
            return f"shopee/{shop}/{item}|{t}"
    return f"shopee/search|{t}"


def norm_existing_url(url: str) -> str | None:
    """Return shopee/shop/item key without variation (for bookmark replace)."""
    try:
        p = urlparse(url.strip())
        host = (p.hostname or "").lower().removeprefix("www.")
        if "shopee." not in host:
            return None
        m = re.search(r"/product/(\d+)/(\d+)", p.path)
        if m:
            return f"shopee/{m.group(1)}/{m.group(2)}"
        m = re.search(r"-i\.(\d+)\.(\d+)", p.path)
        if m:
            return f"shopee/{m.group(1)}/{m.group(2)}"
        return None
    except Exception:
        return None


def shorten_title(title: str) -> str:
    t = re.sub(r"\s+", " ", (title or "").strip())
    t = re.sub(r"\s*[|]\s*Shopee.*$", "", t, flags=re.I)
    if len(t) <= 70:
        return t
    cut = t[:70]
    for sep in (", ", " - ", " / ", " | ", " com ", " para ", " "):
        idx = cut.rfind(sep)
        if idx >= 32:
            return cut[:idx].rstrip(" -–,+|")
    return cut.rstrip() + "…"


def main() -> None:
    with SRC.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))

    data = json.loads(LINKS.read_text(encoding="utf-8"))
    by_key: OrderedDict[str, dict] = OrderedDict()
    product_ids: set[str] = set()

    for raw in rows:
        title = (raw.get("title") or "").strip()
        if not title:
            continue
        shop_item = (raw.get("shopid.itemid") or "").strip()
        url = product_url(shop_item, title)
        key = product_key(shop_item, title)
        status = (raw.get("status") or "ok").strip().lower()
        available = status == "ok"
        price = format_price(raw.get("price"))
        qty_raw = (raw.get("qty") or "").strip()
        qty = int(qty_raw) if qty_raw.isdigit() else None
        cat_id, _ = categorize(title)
        cat_id = MERGE.get(cat_id, cat_id)

        if shop_item and "." in shop_item:
            shop, item = shop_item.split(".", 1)
            if shop.isdigit() and item.isdigit():
                product_ids.add(f"shopee/{shop}/{item}")

        item = {
            "title": shorten_title(title),
            "title_full": title,
            "url": url,
            "section": "compras",
            "category": cat_id,
            "store": "Shopee",
            "icon": SHOPEE_ICON,
            "source": SOURCE,
            "available": available,
            "in_cart": True,
        }
        if price:
            item["price"] = price
            pv = parse_price(price)
            if pv is not None:
                item["price_value"] = pv
        if qty is not None:
            item["qty"] = qty
        if status == "esgotado":
            item["note"] = "Esgotado"
        elif status == "inativo":
            item["note"] = "Inativo"
        by_key[key] = item

    shopee_items = list(by_key.values())

    keep = []
    compras_existing = []
    replaced = 0
    for item in data["items"]:
        if item.get("section") != "compras":
            keep.append(item)
            continue
        if item.get("source") == SOURCE:
            continue
        pid = norm_existing_url(item.get("url") or "")
        # Replace prior Shopee bookmark only when it is the same product id.
        if pid and pid in product_ids:
            replaced += 1
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

    all_compras = compras_existing + shopee_items
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
    sh = [i for i in compras if i.get("source") == SOURCE]
    titles = {
        c["id"]: c["title"] for c in data["categories"] if c.get("section") == "compras"
    }
    print(f"tsv_rows={len(rows)} unique={len(sh)} replaced_bookmarks={replaced}")
    print(
        f"in_cart={sum(1 for i in sh if i.get('in_cart'))} "
        f"ok={sum(1 for i in sh if i.get('available'))} "
        f"unavailable={sum(1 for i in sh if not i.get('available'))} "
        f"search_urls={sum(1 for i in sh if '/search?' in i.get('url', ''))}"
    )
    print(f"compras_total={len(compras)}")
    print("by_store", dict(Counter(i.get("store") or "Outros" for i in compras)))
    print("shopee by_category:")
    for cid, n in Counter(i["category"] for i in sh).most_common():
        print(f"  {n:4d}  {titles.get(cid, cid)}")
    outros = [i for i in sh if i["category"] == "compras-outros"]
    if outros:
        print("still Outros:")
        for i in outros:
            print(" ", i.get("title_full") or i.get("title"))


if __name__ == "__main__":
    main()
