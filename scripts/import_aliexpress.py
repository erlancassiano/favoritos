#!/usr/bin/env python3
"""Import AliExpress wishlist/cart scrape into data/links.json Compras section."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, OrderedDict
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
SRC = Path(
    sys.argv[1]
    if len(sys.argv) > 1
    else "/home/ubuntu/.cursor/projects/workspace/uploads/aliexpress_97f6.json"
)
LINKS = ROOT / "data" / "links.json"
ALI_ICON = "https://www.google.com/s2/favicons?domain=www.aliexpress.com&sz=64"

# (category_id, title, keyword patterns) — first match wins
CATEGORY_RULES: list[tuple[str, str, list[str]]] = [
    (
        "compras-impressao-3d",
        "Impressão 3D",
        [
            r"\b3d printer\b",
            r"\bender\b",
            r"\bvoron\b",
            r"\bbambu\b",
            r"\bhotend\b",
            r"\bnozzle\b",
            r"\bextruder\b",
            r"\bpei\b",
            r"\bfilament\b",
            r"\bmgn12\b",
            r"\bsd card extension\b",
            r"printer grease",
            r"creality",
            r"anycubic",
        ],
    ),
    (
        "compras-eletronica",
        "Eletrônica / Maker",
        [
            r"\besp32\b",
            r"\blilygo\b",
            r"\bm5stack\b",
            r"\bheltec\b",
            r"\blora\b",
            r"\bmeshtastic\b",
            r"\boscilloscope\b",
            r"\bmultimeter\b",
            r"\blogic analyzer\b",
            r"\bgeiger\b",
            r"\bthermal (camera|imager)\b",
            r"\bsoldering\b",
            r"\bsolder\b",
            r"\bdesolder\b",
            r"\bpcb\b",
            r"\bprogrammer\b",
            r"\brt809\b",
            r"\bwaveshare\b",
            r"\brdk\b",
            r"\bfnirsi\b",
            r"\baneng\b",
            r"\bqianli\b",
            r"\bkingst\b",
            r"\bzoyi\b",
            r"\bferrofluid\b",
            r"\btact switch\b",
            r"\btweezers\b",
            r"\bultrasonic cleaner\b",
            r"\bpower supply\b",
            r"\bswitching power\b",
            r"\benergy (meter|power)\b",
            r"\bkwh meter\b",
            r"\buv curing\b",
            r"\brosin\b",
            r"\bflux\b",
            r"\bmotherboard\b",
            r"\bcircuit board\b",
            r"\bmetering module\b",
            r"\bionizing\b",
            r"\bantistatic\b",
            r"\bcardputer\b",
            r"\bt-echo\b",
            r"\bt-deck\b",
            r"\bfpga\b",
            r"\btang nano\b",
            r"\bgowin\b",
            r"\bmcb\b",
            r"\bbusbar\b",
            r"\bcircuit breaker\b",
            r"\bvoltmeter\b",
            r"\bdiode\b",
            r"\btransistor\b",
            r"\btriodo\b",
            r"\bpogo pin\b",
            r"\bhygrometer\b",
            r"\bthermometer\b",
            r"\bwater cooling mat\b",
            r"\b18650\b",
            r"\bbattery (case|holder|storage)\b",
            r"\btuya\b",
            r"\bzigbee\b",
            r"\bwire stripper\b",
            r"\bfd charging test\b",
            r"\bcharge trigger\b",
            r"\btin sn\b",
            r"\bcopper sheet\b",
            r"\bstainless steel ball\b",
            r"\bhemispherical\b",
        ],
    ),
    (
        "compras-ferramentas",
        "Ferramentas",
        [
            r"\bcnc\b",
            r"\blathe\b",
            r"\bmilling\b",
            r"\bdrill\b",
            r"\bmicrometer\b",
            r"\brotary tool\b",
            r"\bhoto\b",
            r"\bhex cross\b",
            r"\bpolishing\b",
            r"\babrasive\b",
            r"\bsanding\b",
            r"\bdspiae\b",
            r"\bstedi\b",
            r"\bvacuum (chamber|pump|pistol)\b",
            r"\bdefoaming\b",
            r"\bswaging\b",
            r"\bexpander\b",
            r"\bspring ball plunger\b",
            r"\bball plunger\b",
            r"\bmeasuring\b",
            r"\bruler\b",
            r"\bgeometric\b",
            r"\bmelting furnace\b",
            r"\bsmelting\b",
            r"\btin melting\b",
            r"\brefractory\b",
            r"\bcopper grease\b",
            r"\bpottery\b",
            r"\brock tumbler\b",
            r"\blaser level\b",
            r"\bstretch belts?\b",
            r"\bcable ties\b",
            r"\bcable (organizer|winder|management)\b",
            r"\btarpaulin\b",
            r"\bcanvas tarp\b",
        ],
    ),
    (
        "compras-marcenaria",
        "Marcenaria",
        [
            r"\bwoodwork",
            r"\bclamping\b",
            r"\bfixing clip\b",
            r"\bright angle\b",
            r"\bl-shaped\b",
            r"\bpanel fixing\b",
        ],
    ),
    (
        "compras-couro-facas",
        "Couro / Facas",
        [
            r"\bleather\b",
            r"\bknife\b",
            r"\bthinning knife\b",
            r"\btailoring\b",
            r"\bkudo whip\b",
            r"\bself defense\b",
        ],
    ),
    (
        "compras-carro",
        "Carro",
        [
            r"\bdash cam\b",
            r"\bcar dvr\b",
            r"\bddpai\b",
            r"\bcar (radio|stereo|wash|soundproof|soundproofing)\b",
            r"\bvolkswagen\b",
            r"\bjetta\b",
            r"\bvw\b",
            r"\brear view camera\b",
            r"\bturn signal\b",
            r"\bbrake fluid\b",
            r"\bautomotive\b",
            r"\bnoise insulation\b",
            r"\bdeadener\b",
            r"\bmicrofiber\b.*\bcar\b",
            r"\btrailer loads\b",
        ],
    ),
    (
        "compras-audio-video",
        "Áudio / Vídeo",
        [
            r"\bmicrophone\b",
            r"\bmixer\b",
            r"\bfifine\b",
            r"\bheadset\b",
            r"\bheadphones?\b",
            r"\bearbuds?\b",
            r"\bearphone\b",
            r"\bmp3\b",
            r"\bwalkman\b",
            r"\bfiio\b",
            r"\bsnowsky\b",
            r"\bsony alpha\b",
            r"\bzv-e10\b",
            r"\bcamera\b",
            r"\bhdmi\b",
            r"\bdisplay port\b",
            r"\bstream controller\b",
            r"\bqkz\b",
            r"\bbaseus eh10\b",
            r"\bbaseus ep10\b",
            r"\bugreen max5c\b",
            r"\bprojector\b",
            r"\bmagcubic\b",
            r"\bkeycaps?\b",
            r"\bgaming ke",
        ],
    ),
    (
        "compras-eletronicos",
        "Eletrônicos",
        [
            r"\bcharger\b",
            r"\bpower bank\b",
            r"\busb\b",
            r"\bhdd docking\b",
            r"\bhard drive\b",
            r"\borico\b",
            r"\blaptop stand\b",
            r"\bhub\b",
            r"\bgan\b",
            r"\bmovespeed\b",
            r"\bbaseus\b",
            r"\bugreen\b",
            r"\bcabletime\b",
            r"\bessager\b",
            r"\bflashlight\b",
            r"\bsofirn\b",
            r"\bportable fan\b",
            r"\bdesk table personal fan\b",
            r"\bfind my\b",
            r"\bsmart finder\b",
            r"\bayn odin\b",
            r"\bgame console\b",
            r"\b8bitdo\b",
            r"\bmouse\b",
            r"\brc (foam|fighter|aircraft|plane|excavator)\b",
            r"\bglider\b",
            r"\bhelicopter\b",
            r"\bquadcopter\b",
            r"\bcarbon fiber rods?\b",
            r"\bsmartphone\b",
            r"\bmobile phone\b",
            r"\bulefone\b",
            r"\brugged\b",
            r"\bjoypad\b",
            r"\bgamepad\b",
            r"\bjoystick\b",
            r"\bnintendo\b",
            r"\bswitch controller\b",
            r"\bmobapad\b",
            r"\blighter\b",
            r"\bbutane\b",
            r"\bwater gun\b",
            r"\bhand exercise\b",
            r"\bmassag",
        ],
    ),
    (
        "compras-casa",
        "Casa",
        [
            r"\bwindow cleaning\b",
            r"\bcleaning robot\b",
            r"\bfood storage\b",
            r"\bcat dog food\b",
            r"\bweather\b",
            r"\bkitchen\b",
            r"\bsoap\b",
            r"\bapron\b",
        ],
    ),
]

STORE_HOSTS = [
    ("AliExpress", ("aliexpress.com", "aliexpress.us", "aliexpress.ru")),
    ("Mercado Livre", ("mercadolivre.com.br", "mercadolibre.com", "mercadolibre.com.ar")),
    ("Shopee", ("shopee.com.br", "shopee.com")),
    ("Amazon", ("amazon.com.br", "amazon.com", "amzn.to")),
]


def detect_store(url: str) -> str:
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    for name, hosts in STORE_HOSTS:
        if any(host == h or host.endswith("." + h) for h in hosts):
            return name
    return "Outros"


def norm_url(url: str) -> str:
    try:
        p = urlparse(url.strip())
        host = (p.hostname or "").lower().removeprefix("www.")
        # Keep AliExpress item id path
        path = p.path.rstrip("/")
        m = re.search(r"/item/(\d+)", path)
        if m and "aliexpress" in host:
            return f"aliexpress.com/item/{m.group(1)}"
        return f"{host}{path}"
    except Exception:
        return url.lower()


def parse_price(price: str | None) -> float | None:
    if not price:
        return None
    s = price.strip()
    s = re.sub(r"[^\d.,]", "", s)
    if not s:
        return None
    # BR format: 3.716,99 or 44,39
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def shorten_title(title: str) -> str:
    t = re.sub(r"\s+", " ", title).strip()
    # Drop common SEO junk phrases
    junk = [
        r"\bfor iphone[\w\s,/]*$",
        r"\bcompatible with[\w\s,/]*$",
        r"\bhigh quality\b",
        r"\bnew sale\b",
        r"\bship from brazil\b",
        r"\beu/us/br ship\b",
        r"\bfree shipping\b",
        r"\bwholesale\b",
        r"\bdropshipping\b",
        r"^【[^】]+】\s*",
        r"\s*[-–|]\s*aliexpress.*$",
    ]
    for pat in junk:
        t = re.sub(pat, "", t, flags=re.I)
    t = re.sub(r"\s+", " ", t).strip(" -–|,")

    # Prefer first clause up to ~60 chars at a word/comma boundary
    if len(t) <= 60:
        return t
    cut = t[:60]
    # Prefer break at comma / slash / dash
    for sep in (", ", " - ", " / ", " with ", " for ", " "):
        idx = cut.rfind(sep)
        if idx >= 28:
            return cut[:idx].rstrip(" -–,/")
    return cut.rstrip() + "…"


# Light PT-leaning renames when the English start is awkward SEO
PT_HINTS = [
    (r"(?i)^140mm Right Angle Fixing Clip.*", "Grampo ângulo 90° 140mm"),
    (r"(?i)^Magnetic PEI Powder Sheet.*", "Folha PEI magnética"),
    (r"(?i)^Essager USB C Charger.*", "Carregador USB-C Essager 33W GaN"),
    (r"(?i)^Window Cleaning Robot.*", "Robô limpa-vidros ABIR WD9"),
    (r"(?i)^TOPK 4Inch USB Mini Portable Fan.*", "Mini ventilador USB TOPK"),
    (r"(?i)^13/33LB Collapsible Cat Dog Food.*", "Container ração pet"),
    (r"(?i)^628ml Ultrasonic Cleaner.*", "Cuba ultrassônica 628ml"),
]


def polish_title(short: str, full: str) -> str:
    for pat, repl in PT_HINTS:
        if re.search(pat, full):
            return repl[:60]
    return short[:60]


def categorize(title: str) -> tuple[str, str]:
    low = title.lower()
    for cat_id, cat_title, patterns in CATEGORY_RULES:
        for pat in patterns:
            if re.search(pat, low):
                return cat_id, cat_title
    return "compras-outros", "Outros"


def categorize_existing(item: dict) -> tuple[str, str]:
    blob = " ".join(
        filter(
            None,
            [item.get("title"), item.get("title_full"), item.get("url"), item.get("note")],
        )
    )
    return categorize(blob)


def main() -> None:
    scrape = json.loads(SRC.read_text(encoding="utf-8"))
    data = json.loads(LINKS.read_text(encoding="utf-8"))

    wishlist = scrape.get("wishlist") or []
    cart = scrape.get("cart") or []

    by_key: OrderedDict[str, dict] = OrderedDict()

    def upsert(raw: dict, *, in_cart: bool) -> None:
        url = raw["url"].strip()
        key = norm_url(url)
        full = raw.get("title") or ""
        short = polish_title(shorten_title(full), full)
        price = raw.get("price") or None
        available = bool(price)
        cat_id, cat_title = categorize(full)
        qty = raw.get("qty")

        if key in by_key:
            item = by_key[key]
            if in_cart:
                item["in_cart"] = True
                if qty is not None:
                    item["qty"] = qty
            if price and not item.get("price"):
                item["price"] = price
                item["available"] = True
            return

        item = {
            "title": short,
            "title_full": full,
            "url": url.split("?")[0],
            "section": "compras",
            "category": cat_id,
            "store": "AliExpress",
            "icon": ALI_ICON,
            "source": "aliexpress",
            "available": available,
            "in_cart": in_cart,
        }
        if price:
            item["price"] = price
            pv = parse_price(price)
            if pv is not None:
                item["price_value"] = pv
        else:
            item["note"] = "Indisponível"
        if in_cart and qty is not None:
            item["qty"] = qty
        # stash for category registry
        item["_cat_title"] = cat_title
        by_key[key] = item

    # Wishlist first, then cart (cart marks overlap)
    for raw in wishlist:
        upsert(raw, in_cart=False)
    for raw in cart:
        upsert(raw, in_cart=True)

    ali_items = list(by_key.values())

    # Prepare category registry for compras (replace flat "compras")
    new_cats: OrderedDict[str, dict] = OrderedDict()
    for item in ali_items:
        cid = item["category"]
        if cid not in new_cats:
            new_cats[cid] = {
                "id": cid,
                "title": item.pop("_cat_title"),
                "section": "compras",
            }
        else:
            item.pop("_cat_title", None)

    # Re-home existing bookmark compras into subcategories + store tags
    keep_items = []
    existing_compras = []
    for item in data["items"]:
        if item.get("section") != "compras":
            keep_items.append(item)
            continue
        # Skip if already from a previous aliexpress import (re-run safe)
        if item.get("source") == "aliexpress":
            continue
        # Dedupe against new AliExpress items by URL
        key = norm_url(item.get("url") or "")
        if key in by_key:
            continue
        cid, ctitle = categorize_existing(item)
        item = dict(item)
        item["category"] = cid
        item["section"] = "compras"
        if not item.get("store"):
            item["store"] = detect_store(item.get("url") or "")
        if "available" not in item:
            item["available"] = True
        if cid not in new_cats:
            new_cats[cid] = {"id": cid, "title": ctitle, "section": "compras"}
        existing_compras.append(item)

    # Ensure Outros exists if needed
    if "compras-outros" not in new_cats:
        # only add if used
        pass

    # Merge categories: keep non-compras cats, replace compras cats
    categories = [c for c in data["categories"] if c.get("section") != "compras"]
    # Stable order by rule order then outros
    order = [cid for cid, _, _ in CATEGORY_RULES] + ["compras-outros"]
    for cid in order:
        if cid in new_cats:
            categories.append(new_cats.pop(cid))
    for c in new_cats.values():
        categories.append(c)

    data["categories"] = categories
    data["items"] = keep_items + existing_compras + ali_items

    # Update compras section description
    for s in data["sections"]:
        if s["id"] == "compras":
            s["description"] = (
                "Itens da wishlist/carrinho e favoritos de compras — filtre por loja"
            )

    LINKS.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # Stats
    compras = [i for i in data["items"] if i["section"] == "compras"]
    by_cat = Counter(i["category"] for i in compras)
    by_store = Counter(i.get("store") or "Outros" for i in compras)
    ali = [i for i in compras if i.get("source") == "aliexpress"]
    print(f"wishlist={len(wishlist)} cart={len(cart)}")
    print(
        f"aliexpress_unique={len(ali)} in_cart={sum(1 for i in ali if i.get('in_cart'))} "
        f"unavailable={sum(1 for i in ali if not i.get('available'))}"
    )
    print(f"compras_total={len(compras)} existing_kept={len(existing_compras)}")
    print("by_store", dict(by_store))
    print("by_category:")
    titles = {c["id"]: c["title"] for c in data["categories"] if c["section"] == "compras"}
    for cid, n in by_cat.most_common():
        print(f"  {n:4d}  {titles.get(cid, cid)}")


if __name__ == "__main__":
    main()
