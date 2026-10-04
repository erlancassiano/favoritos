#!/usr/bin/env python3
"""Import Netscape bookmarks into data/links.json. Not used at runtime."""

from __future__ import annotations

import html
import json
import re
import sys
from collections import OrderedDict
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

ROOT = Path(__file__).resolve().parents[1]
BOOKMARKS = Path(
    sys.argv[1]
    if len(sys.argv) > 1
    else "/home/ubuntu/.cursor/projects/workspace/uploads/bookmarks_76f3.html"
)
OUT = ROOT / "data" / "links.json"
REPORT = Path("/tmp/favoritos_import_report.json")

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_content",
    "utm_term",
    "utm_id",
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "igshid",
    "si",
    "ref",
    "ref_",
    "referrer",
    "feature",
    "app",
    "pli",
}

TITLE_STRIP_SUFFIXES = [
    r"\s*[-–|]\s*YouTube\s*$",
    r"\s*[-–|]\s*GitHub\s*$",
    r"\s*[-–|]\s*Wikipedia\s*$",
    r"\s*[-–|]\s*Medium\s*$",
    r"\s*[-–|]\s*Stack Overflow\s*$",
    r"\s*[-–|]\s*Reddit\s*$",
    r"\s*\|.*Pelando\s*$",
]

SENSITIVE_QS_KEYS = re.compile(
    r"^(token|access_token|id_token|refresh_token|api[_-]?key|apikey|password|"
    r"passwd|secret|session|sessionid|sid|auth|authorization|signature|"
    r"x-amz-signature|x-amz-credential|credential|email|user_id|userid|"
    r"resid|appidkey)$",
    re.I,
)

PRIVATE_HOST = re.compile(
    r"^(localhost|127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|0\.0\.0\.0)",
    re.I,
)

# Host/path patterns that look private on a public repo.
SENSITIVE_HOST_PATH = [
    (re.compile(r"correio\.aeb\.gov\.br", re.I), "aeb_correio"),
    (re.compile(r"signin\.aws\.amazon\.com", re.I), "aws_signin"),
    (re.compile(r"console\.aws\.amazon\.com", re.I), "aws_console"),
    (re.compile(r"console\.cloud\.google\.com", re.I), "gcp_console"),
    (re.compile(r"console\.firebase\.google\.com", re.I), "firebase_console"),
    (re.compile(r"supabase\.com/.*/project/", re.I), "supabase_project"),
    (re.compile(r"docs\.google\.com", re.I), "google_docs"),
    (re.compile(r"drive\.google\.com", re.I), "google_drive"),
    (re.compile(r"sheets\.google\.com", re.I), "google_sheets"),
    (re.compile(r"forms\.gle", re.I), "google_forms"),
    (re.compile(r"(^|\.)notion\.so", re.I), "notion"),
    (re.compile(r"onedrive\.live\.com", re.I), "onedrive"),
    (re.compile(r"sharepoint\.com", re.I), "sharepoint"),
    (re.compile(r"atlassian\.net", re.I), "atlassian_cloud"),
    (re.compile(r"login\.microsoftonline\.com", re.I), "ms_login"),
    (re.compile(r"accounts\.google\.com", re.I), "google_accounts"),
    (re.compile(r"idmsa\.apple\.com", re.I), "apple_login"),
    (re.compile(r"visiona", re.I), "visiona"),
    (re.compile(r"intranet", re.I), "intranet"),
]


class BookmarkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.stack: list[str] = []
        self.links: list[dict] = []
        self._h3: str | None = None
        self._a: dict | None = None
        self._cap: str | None = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        t = tag.lower()
        if t == "h3":
            self._cap = "h3"
            self._h3 = ""
        elif t == "a":
            self._cap = "a"
            self._a = {
                "href": attrs.get("href", ""),
                "title": "",
                "path": list(self.stack),
            }

    def handle_endtag(self, tag):
        t = tag.lower()
        if t == "h3" and self._h3 is not None:
            self.stack.append(html.unescape(self._h3.strip()))
            self._h3 = None
            self._cap = None
        elif t == "a" and self._a is not None:
            self._a["title"] = html.unescape(self._a["title"].strip())
            self.links.append(self._a)
            self._a = None
            self._cap = None
        elif t == "dl":
            if self.stack:
                self.stack.pop()

    def handle_data(self, data):
        if self._cap == "h3" and self._h3 is not None:
            self._h3 += data
        elif self._cap == "a" and self._a is not None:
            self._a["title"] += data


def slugify(text: str) -> str:
    text = html.unescape(text).strip().lower()
    text = text.replace("&", " e ")
    text = re.sub(r"[^\w\s\-›>]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_›>]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:64] or "geral"


def clean_title(title: str, url: str) -> str:
    title = html.unescape(title or "").strip()
    title = re.sub(r"\s+", " ", title)
    for pat in TITLE_STRIP_SUFFIXES:
        title = re.sub(pat, "", title, flags=re.I)
    title = title.strip(" -–|")
    if not title or title.startswith("http"):
        host = urlparse(url).hostname or "link"
        title = host.replace("www.", "")
    if len(title) > 90:
        title = title[:87].rstrip() + "…"
    return title


def clean_url(url: str) -> str:
    try:
        parts = urlparse(url.strip())
    except Exception:
        return url
    if parts.scheme not in ("http", "https"):
        return url
    q = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in TRACKING_PARAMS and not k.lower().startswith("utm_")
    ]
    # Drop noisy Amazon/ref path junk lightly: keep path, cleaned query.
    return urlunparse(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            "",
            urlencode(q, doseq=True),
            "",
        )
    )


def normalize_url_key(url: str) -> str:
    try:
        p = urlparse(url)
        host = (p.hostname or "").lower().removeprefix("www.")
        path = p.path.rstrip("/") or ""
        return f"{host}{path}"
    except Exception:
        return url.lower()


def is_private_host(host: str | None) -> bool:
    if not host:
        return True
    h = host.lower()
    if h in ("localhost",):
        return True
    return bool(PRIVATE_HOST.match(h))


def exclusion_reason(url: str) -> str | None:
    if not url or url.startswith("file:"):
        return "file_or_empty"
    try:
        p = urlparse(url)
    except Exception:
        return "bad_url"
    host = p.hostname or ""
    if is_private_host(host):
        return "private_host"
    full = f"{host}{p.path}?{p.query}"
    for rx, label in SENSITIVE_HOST_PATH:
        if rx.search(full) or rx.search(url):
            return label
    # AWS signed URLs
    if "X-Amz-Credential" in url or "X-Amz-Signature" in url:
        return "aws_signed_url"
    for key, _ in parse_qsl(p.query, keep_blank_values=True):
        if SENSITIVE_QS_KEYS.match(key):
            return f"sensitive_query:{key}"
        if key.lower().startswith("x-amz-"):
            return f"sensitive_query:{key}"
    # Gmail deep inbox with account index is ok as mail.google.com home,
    # but raw bookmark with personal mailbox path — still publicish; keep cleaned.
    return None


def folder_parts(path: list[str]) -> list[str]:
    parts = [html.unescape(x) for x in path]
    if parts and parts[0] == "Barra de favoritos":
        parts = parts[1:]
    return parts


def map_section_and_category(parts: list[str]) -> tuple[str, str, str]:
    """Return (section_id, category_id, category_title)."""
    if not parts:
        return "favoritos", "geral", "Geral"

    # Shopping folder → Compras section
    if parts[0] == "Compras":
        if len(parts) >= 2:
            sub = " › ".join(parts[1:])
            return "compras", slugify("compras-" + sub), f"Compras › {sub}"
        return "compras", "compras", "Compras"

    # Nested: Parent › Child as category label
    if len(parts) == 1:
        return "favoritos", slugify(parts[0]), parts[0]
    title = " › ".join(parts)
    return "favoritos", slugify(title), title


# Merge / rename tidy map applied to top-level folder names
FOLDER_ALIASES = {
    "Dell": "Desenvolvimento › Ferramentas",
}


def tidy_parts(parts: list[str]) -> list[str]:
    if not parts:
        return parts
    # Merge tiny Engenharia leaves into FABLAB when alone
    if parts == ["Engenharia", "Hardware"]:
        return ["Engenharia", "FABLAB"]
    if parts == ["Engenharia", "Impressão 3D"]:
        return ["Engenharia", "FABLAB"]
    if parts == ["Desenvolvimento", "Dell"]:
        return ["Desenvolvimento", "Ferramentas"]
    # Flatten Bitcoin under Investimentos label
    if parts[:2] == ["Bancos & Finanças", "Investimentos"] and len(parts) >= 3:
        return ["Bancos & Finanças", "Investimentos › " + " › ".join(parts[2:])]
    return parts


def build_diarios(all_links: list[dict]) -> tuple[list[dict], list[dict]]:
    """Return (diarios items, notes for report)."""
    by_host_title = all_links
    notes = []

    def find_url(pred):
        for l in by_host_title:
            if pred(l):
                return l["href"]
        return None

    def host_of(l):
        return (urlparse(l["href"]).hostname or "").lower().removeprefix("www.")

    specs = [
        ("Gmail", "https://mail.google.com/", lambda l: host_of(l) == "mail.google.com"),
        (
            "YouTube",
            "https://www.youtube.com/",
            lambda l: host_of(l) == "youtube.com" and "/watch" not in l["href"],
        ),
        (
            "Mural",
            "https://www.mural.co/",
            lambda l: host_of(l) in ("mural.co", "app.mural.co", "mural.com"),
        ),
        (
            "Gemini notebook",
            "https://notebooklm.google.com/",
            lambda l: host_of(l) == "notebooklm.google.com",
        ),
        (
            "Pelando",
            "https://www.pelando.com.br/",
            lambda l: host_of(l) == "pelando.com.br",
        ),
        (
            "X",
            "https://x.com/",
            lambda l: host_of(l) in ("x.com", "twitter.com"),
        ),
        (
            "Perplexity",
            "https://www.perplexity.ai/",
            lambda l: host_of(l) == "perplexity.ai",
        ),
        (
            "Gemini",
            "https://gemini.google.com/",
            lambda l: host_of(l) == "gemini.google.com",
        ),
        (
            "Torrent Bay",
            "https://torrentbay.st/",
            lambda l: "torrentbay" in host_of(l),
        ),
        (
            "Cursor",
            "https://cursor.com/",
            lambda l: host_of(l) in ("cursor.com", "cursor.sh"),
        ),
        (
            "Kick",
            "https://kick.com/",
            lambda l: host_of(l) == "kick.com",
        ),
        (
            "Instagram",
            "https://www.instagram.com/",
            lambda l: host_of(l) == "instagram.com" and "/p/" not in l["href"],
        ),
        (
            "Crunchyroll",
            "https://www.crunchyroll.com/",
            lambda l: host_of(l) == "crunchyroll.com",
        ),
        (
            "Jellyfin",
            None,
            lambda l: "jellyfin" in host_of(l) or "jellyfin" in l["title"].lower(),
        ),
        (
            "YouTube Music",
            "https://music.youtube.com/",
            lambda l: host_of(l) == "music.youtube.com",
        ),
        (
            "tplink",
            None,
            lambda l: "tplink" in host_of(l)
            or "tp-link" in host_of(l)
            or "tplink" in l["title"].lower(),
        ),
    ]

    diarios = []
    for title, fallback, pred in specs:
        found = find_url(pred)
        url = found or fallback
        note = None
        if title == "Mural" and found:
            # Deep workspace board URLs are account-specific; use public home.
            host = urlparse(found).hostname or ""
            if is_private_host(host):
                url = "#"
                note = "definir URL"
                notes.append({"title": title, "host": host, "reason": "private_host"})
            else:
                url = "https://www.mural.co/"
                notes.append(
                    {
                        "title": title,
                        "host": host,
                        "reason": "used_public_home_not_workspace_deep_link",
                    }
                )
        elif title in ("Jellyfin", "tplink"):
            if found:
                host = urlparse(found).hostname or ""
                if is_private_host(host):
                    url = "#"
                    note = "definir URL"
                    notes.append({"title": title, "host": host, "reason": "private_host"})
                else:
                    url = clean_url(found)
            else:
                url = "#"
                note = "definir URL"
                notes.append({"title": title, "host": "(não encontrado)", "reason": "missing_bookmark"})
        elif found and title == "Gmail":
            url = "https://mail.google.com/"
        elif found and title == "Kick":
            url = "https://kick.com/"
        elif found and title == "Instagram":
            url = "https://www.instagram.com/"
        elif found and title == "Crunchyroll":
            url = "https://www.crunchyroll.com/"
        elif found and title == "Torrent Bay":
            url = clean_url(found)
        elif found and title == "Pelando":
            url = "https://www.pelando.com.br/"
        elif found and title == "Gemini notebook":
            url = "https://notebooklm.google.com/"
        elif not found and fallback:
            url = fallback

        item = {
            "title": title,
            "url": url,
            "section": "diarios",
            "category": "diarios",
            "pinned": True,
        }
        if note:
            item["note"] = note
        diarios.append(item)
    return diarios, notes


def main() -> None:
    parser = BookmarkParser()
    parser.feed(BOOKMARKS.read_text(encoding="utf-8", errors="replace"))
    raw_count = len(parser.links)

    excluded = []
    kept = []
    for link in parser.links:
        url = (link.get("href") or "").strip()
        reason = exclusion_reason(url)
        if reason:
            host = urlparse(url).hostname or "(sem host)"
            excluded.append(
                {
                    "title": clean_title(link.get("title") or "", url)[:80],
                    "host": host,
                    "reason": reason,
                }
            )
            continue
        kept.append(link)

    # Dedupe by normalized URL
    deduped = []
    seen = set()
    dup_count = 0
    for link in kept:
        cleaned = clean_url(link["href"])
        key = normalize_url_key(cleaned)
        if key in seen:
            dup_count += 1
            continue
        seen.add(key)
        link = dict(link)
        link["href"] = cleaned
        link["title"] = clean_title(link.get("title") or "", cleaned)
        deduped.append(link)

    categories: OrderedDict[str, dict] = OrderedDict()
    items = []

    for link in deduped:
        parts = tidy_parts(folder_parts(link["path"]))
        section, cat_id, cat_title = map_section_and_category(parts)
        if cat_id not in categories:
            categories[cat_id] = {
                "id": cat_id,
                "title": cat_title,
                "section": section,
            }
        items.append(
            {
                "title": link["title"],
                "url": link["href"],
                "section": section,
                "category": cat_id,
                "added": None,
            }
        )

    # Drop null added
    for it in items:
        it.pop("added", None)

    diarios, diario_notes = build_diarios(parser.links)

    # Ensure diarios category exists for docs consistency (items live in diarios array)
    data = {
        "meta": {
            "owner": "Erlan",
            "title": "Favoritos",
            "github": {
                "owner": "erlancassiano",
                "repo": "favoritos",
                "branch": "main",
                "dataPath": "data/links.json",
            },
        },
        "diarios": diarios,
        "sections": [
            {
                "id": "favoritos",
                "title": "Favoritos",
                "description": "Atalhos e sites organizados pelas pastas do navegador",
            },
            {
                "id": "compras",
                "title": "Compras",
                "description": "Itens e lojas da pasta Compras",
            },
            {
                "id": "desejos",
                "title": "Lista de desejos",
                "description": "Coisas que gostaria de ter um dia",
            },
        ],
        "categories": list(categories.values()),
        "items": items,
    }

    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Category counts
    cat_counts = {}
    for it in items:
        cat_counts[it["category"]] = cat_counts.get(it["category"], 0) + 1
    tree = []
    for c in categories.values():
        tree.append(
            {
                "section": c["section"],
                "title": c["title"],
                "id": c["id"],
                "count": cat_counts.get(c["id"], 0),
            }
        )

    report = {
        "raw": raw_count,
        "excluded": len(excluded),
        "deduped": dup_count,
        "imported": len(items),
        "diarios": len(diarios),
        "excluded_list": excluded,
        "diario_notes": diario_notes,
        "tree": tree,
        "compras": sum(1 for i in items if i["section"] == "compras"),
        "favoritos": sum(1 for i in items if i["section"] == "favoritos"),
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"raw={raw_count} imported={len(items)} deduped={dup_count} "
        f"excluded={len(excluded)} diarios={len(diarios)}"
    )
    print(f"wrote {OUT}")
    print(f"report {REPORT}")


if __name__ == "__main__":
    main()
