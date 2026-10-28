"""Main-content extraction from HTML. Scripts are stripped, never executed."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup, Tag

from app.core.errors import UnsafeURLError
from app.ingestion.url_safety import normalize_url

REMOVE_TAGS = ["script", "style", "noscript", "template", "svg", "canvas", "iframe", "form", "button",
               "select", "input", "textarea", "nav", "header", "footer", "aside", "object", "embed"]
BOILERPLATE_RE = re.compile(
    r"(^|[\s_-])(cookie|consent|banner|navbar|nav|menu|footer|sidebar|breadcrumb|share|social|"
    r"advert|ads|promo|popup|modal|newsletter|subscribe|related|comments?)([\s_-]|$)",
    re.IGNORECASE,
)
BLOCK_TAGS = {"p", "li", "td", "th", "blockquote", "pre", "dd", "dt", "figcaption", "caption"}
HEADING_TAGS = {"h1", "h2", "h3", "h4"}
SKIP_EXTENSIONS = (
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico", ".bmp", ".tif", ".tiff",
    ".zip", ".gz", ".tar", ".rar", ".7z", ".exe", ".dmg", ".msi", ".apk", ".mp3", ".mp4", ".avi",
    ".mov", ".wmv", ".webm", ".css", ".js", ".json", ".xml", ".rss", ".doc", ".docx", ".xls",
    ".xlsx", ".ppt", ".pptx", ".csv", ".woff", ".woff2", ".ttf",
)
SKIP_PATH_RE = re.compile(r"/(login|signin|sign-in|signup|register|account|cart|checkout|wp-admin|"
                          r"wp-login|logout|search|feed|tag|author|print)(/|$)", re.IGNORECASE)


@dataclass
class ExtractedPage:
    title: str
    text: str
    canonical_url: str | None
    description: str | None
    language: str | None
    published_at: str | None
    links: list[str] = field(default_factory=list)
    noindex: bool = False
    nofollow: bool = False


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _meta(soup: BeautifulSoup, *names: str) -> str | None:
    for name in names:
        tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
        if isinstance(tag, Tag) and tag.get("content"):
            return _clean(str(tag["content"]))[:1000]
    return None


def _is_boilerplate(tag: Tag) -> bool:
    if tag.attrs is None:
        return False
    role = str(tag.get("role", "")).lower()
    if role in {"navigation", "banner", "contentinfo", "complementary", "search", "dialog"}:
        return True
    if tag.get("aria-hidden") == "true" or tag.has_attr("hidden"):
        return True
    ident = " ".join([str(tag.get("id", "")), " ".join(tag.get("class", []) or [])])
    return bool(ident.strip()) and bool(BOILERPLATE_RE.search(ident))


def is_crawlable_link(url: str) -> bool:
    path = url.split("?", 1)[0].lower()
    return not path.endswith(SKIP_EXTENSIONS) and not SKIP_PATH_RE.search(path)


def extract(html: str, page_url: str) -> ExtractedPage:
    soup = BeautifulSoup(html, "html.parser")

    robots_meta = (_meta(soup, "robots") or "").lower()
    title = (_meta(soup, "og:title") or (soup.title.string if soup.title and soup.title.string else "")
             or "")
    description = _meta(soup, "description", "og:description")
    published = _meta(soup, "article:published_time", "article:modified_time", "date", "last-modified")
    html_tag = soup.find("html")
    language = str(html_tag.get("lang"))[:16] if isinstance(html_tag, Tag) and html_tag.get("lang") else None

    canonical = None
    link_tag = soup.find("link", rel=lambda v: v and "canonical" in (v if isinstance(v, list) else [v]))
    if isinstance(link_tag, Tag) and link_tag.get("href"):
        try:
            canonical = normalize_url(str(link_tag["href"]), base=page_url)
        except UnsafeURLError:
            canonical = None

    links: list[str] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = str(a["href"]).strip()
        if href.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
            continue
        try:
            absolute = normalize_url(href, base=page_url)
        except UnsafeURLError:
            continue
        if absolute not in seen and is_crawlable_link(absolute):
            seen.add(absolute)
            links.append(absolute)

    for tag_name in REMOVE_TAGS:
        for t in soup.find_all(tag_name):
            t.decompose()
    for t in soup.find_all(True):
        if isinstance(t, Tag) and t.attrs is not None and _is_boilerplate(t):
            t.decompose()

    root = soup.find("main") or soup.find("article") or soup.find(attrs={"role": "main"}) or soup.body or soup
    blocks: list[str] = []
    for el in root.find_all(list(HEADING_TAGS | BLOCK_TAGS)):
        if not isinstance(el, Tag):
            continue
        # Avoid duplicates from nested blocks (e.g. <li><p>..</p></li>).
        if el.name in BLOCK_TAGS and el.find(list(BLOCK_TAGS)):
            continue
        text = _clean(el.get_text(" "))
        if not text:
            continue
        if el.name in HEADING_TAGS:
            blocks.append(f"{'#' * int(el.name[1])} {text}")
        elif el.name == "li":
            blocks.append(f"- {text}")
        else:
            blocks.append(text)
    if not blocks:
        fallback = _clean(root.get_text(" "))
        if fallback:
            blocks.append(fallback)

    if not title:
        h1 = soup.find("h1")
        title = _clean(h1.get_text(" ")) if isinstance(h1, Tag) else ""
    return ExtractedPage(
        title=_clean(title)[:300] or page_url,
        text="\n\n".join(blocks),
        canonical_url=canonical,
        description=description,
        language=language,
        published_at=published,
        links=links,
        noindex="noindex" in robots_meta,
        nofollow="nofollow" in robots_meta,
    )
