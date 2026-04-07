from __future__ import annotations

import ipaddress
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx
from urllib.robotparser import RobotFileParser

USER_AGENT = "Pix2Poly/0.1 (+https://github.com/HEO-J-H/Pix2Poly)"


def _host_is_private(hostname: str) -> bool:
    try:
        infos = __import__("socket").getaddrinfo(hostname, None)
    except OSError:
        return True
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                return True
        except ValueError:
            continue
    return False


def check_robots_allowed(page_url: str) -> bool | None:
    """Return True if allowed, False if disallowed, None if robots.txt unreadable."""
    parsed = urlparse(page_url)
    if not parsed.scheme or not parsed.netloc:
        return None
    base = f"{parsed.scheme}://{parsed.netloc}"
    robots_url = f"{base}/robots.txt"
    rp = RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
        return rp.can_fetch(USER_AGENT, page_url)
    except Exception:
        return None


class _ImageURLCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.urls: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        ad = {k: v for k, v in attrs if v}
        if tag == "img" and "src" in ad:
            self.urls.append(ad["src"])
        elif tag in ("link", "meta"):
            prop = ad.get("property") or ad.get("name")
            if prop in ("og:image", "twitter:image") and "content" in ad:
                self.urls.append(ad["content"])
        if tag == "img" and "srcset" in ad:
            for part in ad["srcset"].split(","):
                u = part.strip().split()[0] if part.strip() else ""
                if u:
                    self.urls.append(u)


async def fetch_page_image_candidates(
    page_url: str,
    max_candidates: int,
    timeout_s: float = 15.0,
) -> tuple[list[str], bool | None, bool]:
    """
    Fetch HTML and extract image URL candidates. Does not download images.
    Returns (candidates, robots_allowed_or_none, truncated).
    """
    parsed = urlparse(page_url)
    if parsed.hostname and _host_is_private(parsed.hostname):
        return [], None, False

    robots_ok = check_robots_allowed(page_url)
    if robots_ok is False:
        return [], False, False

    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
        timeout=timeout_s,
    ) as client:
        r = await client.get(page_url)
        r.raise_for_status()
        text = r.text

    collector = _ImageURLCollector()
    collector.feed(text)
    base = page_url
    seen: set[str] = set()
    out: list[str] = []
    truncated = False
    for raw in collector.urls:
        if len(out) >= max_candidates:
            truncated = True
            break
        absolute = urljoin(base, raw.strip())
        if not absolute.lower().startswith(("http://", "https://")):
            continue
        if absolute not in seen:
            seen.add(absolute)
            out.append(absolute)
    return out, robots_ok, truncated
