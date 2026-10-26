from __future__ import annotations

import ipaddress
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx
from urllib.robotparser import RobotFileParser

USER_AGENT = "Pix2Poly/0.1 (+https://github.com/HEO-J-H/Pix2Poly)"


def _host_is_private(hostname: str) -> bool:
    """공인(global) 주소가 아니면 True — 사설·루프백·링크로컬(169.254 메타데이터)·예약·멀티캐스트·0.0.0.0 모두 차단."""
    try:
        infos = __import__("socket").getaddrinfo(hostname, None)
    except OSError:
        return True
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0].split("%")[0])
        except ValueError:
            return True
        if not ip.is_global:
            return True
    return False


class BlockedURL(ValueError):
    pass


def check_public_url(url: str) -> None:
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise BlockedURL("http/https 주소만 가능합니다")
    if _host_is_private(p.hostname):
        raise BlockedURL("내부망·로컬 주소는 가져올 수 없습니다")


async def safe_get(client: httpx.AsyncClient, url: str, max_bytes: int, max_redirects: int = 5) -> httpx.Response:
    """리다이렉트를 직접 따라가며 단계마다 공인 주소인지 다시 검사하고, max_bytes 를 넘으면 중단 (SSRF·메모리 보호).
    client 는 follow_redirects=False 여야 함. 반환 응답의 .content 에 본문이 담김."""
    for _ in range(max_redirects + 1):
        check_public_url(url)
        async with client.stream("GET", url) as r:
            if r.is_redirect and r.headers.get("location"):
                url = urljoin(url, r.headers["location"])
                continue
            r.raise_for_status()
            if int(r.headers.get("content-length") or 0) > max_bytes:
                raise ValueError(f"파일이 너무 큽니다 (>{max_bytes // 1048576}MB)")
            buf = bytearray()
            async for chunk in r.aiter_bytes(65536):
                buf += chunk
                if len(buf) > max_bytes:
                    raise ValueError(f"파일이 너무 큽니다 (>{max_bytes // 1048576}MB)")
            r._content = bytes(buf)
            return r
    raise BlockedURL("리다이렉트가 너무 많습니다")


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

    robots_ok = await __import__("asyncio").to_thread(check_robots_allowed, page_url)  # urllib 동기 호출 → 스레드
    if robots_ok is False:
        return [], False, False

    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        follow_redirects=False,
        timeout=timeout_s,
    ) as client:
        r = await safe_get(client, page_url, 5 * 1024 * 1024)
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
