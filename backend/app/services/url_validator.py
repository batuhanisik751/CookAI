import ipaddress
import logging
import re
import socket
from dataclasses import dataclass
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import httpx

logger = logging.getLogger(__name__)

# Allowed hostnames after redirect resolution
ALLOWED_HOSTS = {
    "tiktok.com",
    "www.tiktok.com",
    "vm.tiktok.com",
    "vt.tiktok.com",
    "m.tiktok.com",
    "instagram.com",
    "www.instagram.com",
    "m.instagram.com",
}

# Regex patterns for supported platforms
TIKTOK_PATTERNS = [
    re.compile(r"https?://(www\.)?tiktok\.com/@[\w.]+/video/\d+"),
    re.compile(r"https?://vm\.tiktok\.com/[\w]+"),
    re.compile(r"https?://vt\.tiktok\.com/[\w]+"),
    re.compile(r"https?://m\.tiktok\.com/v/\d+"),
]

INSTAGRAM_PATTERNS = [
    re.compile(r"https?://(www\.)?instagram\.com/(reel|reels|p)/[\w-]+"),
    re.compile(r"https?://m\.instagram\.com/(reel|reels|p)/[\w-]+"),
]

# Tracking params to strip
TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "igshid",
    "ig_rid",
    "tt_from",
    "tt_ref",
    "share_id",
    "share_app_id",
    "share_author_id",
    "is_copy_url",
    "is_from_webapp",
    "sender_device",
    "sender_web_id",
    "fbclid",
    "ref",
}


@dataclass
class ValidationResult:
    is_valid: bool
    platform: str | None = None
    normalized_url: str | None = None
    error_code: str | None = None
    error_message: str | None = None


def detect_platform(url: str) -> str | None:
    """Detect the platform from a URL using regex patterns."""
    for pattern in TIKTOK_PATTERNS:
        if pattern.match(url):
            return "tiktok"
    for pattern in INSTAGRAM_PATTERNS:
        if pattern.match(url):
            return "instagram"
    return None


def _is_private_ip(ip_str: str) -> bool:
    """Check if an IP address is in a private/reserved range."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        )
    except ValueError:
        return True  # Invalid IP → treat as private for safety


def _check_hostname_safe(hostname: str) -> bool:
    """Resolve hostname and verify it doesn't point to private IPs."""
    try:
        results = socket.getaddrinfo(hostname, None)
        for result in results:
            ip_str = result[4][0]
            if _is_private_ip(ip_str):
                return False
        return True
    except socket.gaierror:
        return False


def _normalize_url(url: str) -> str:
    """Strip tracking params and normalize the URL."""
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query, keep_blank_values=False)
    filtered_params = {
        k: v for k, v in query_params.items() if k.lower() not in TRACKING_PARAMS
    }
    clean_query = urlencode(filtered_params, doseq=True) if filtered_params else ""
    normalized = urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path.rstrip("/"),
            parsed.params,
            clean_query,
            "",  # strip fragment
        )
    )
    return normalized


def _is_host_allowed(url: str) -> bool:
    """Check if URL's hostname is in the allowlist."""
    parsed = urlparse(url)
    hostname = parsed.hostname
    if hostname is None:
        return False
    return hostname in ALLOWED_HOSTS


async def validate_url(url: str) -> ValidationResult:
    """
    Validate and normalize a video URL.

    Performs:
    1. Regex-based platform detection
    2. URL normalization (strip tracking params)
    3. SSRF prevention (allowlist + private IP check)
    4. HEAD request to verify reachability
    """
    url = url.strip()

    # Step 1: Check hostname is in allowlist
    if not _is_host_allowed(url):
        # Could be a short link — try to detect platform from pattern
        platform = detect_platform(url)
        if platform is None:
            return ValidationResult(
                is_valid=False,
                error_code="UNSUPPORTED_PLATFORM",
                error_message="URL must be from TikTok or Instagram.",
            )

    # Step 2: Resolve redirects and re-check hostname
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            max_redirects=5,
            timeout=httpx.Timeout(10.0),
        ) as client:
            response = await client.head(url)
            final_url = str(response.url)
    except httpx.TimeoutException:
        return ValidationResult(
            is_valid=False,
            error_code="URL_TIMEOUT",
            error_message="The URL took too long to respond.",
        )
    except httpx.RequestError as e:
        logger.warning("URL validation request failed: %s", e)
        return ValidationResult(
            is_valid=False,
            error_code="URL_UNREACHABLE",
            error_message="Could not reach the URL. Please check it and try again.",
        )

    # Step 3: Verify final URL hostname is allowed
    if not _is_host_allowed(final_url):
        return ValidationResult(
            is_valid=False,
            error_code="UNSUPPORTED_PLATFORM",
            error_message="URL must be from TikTok or Instagram.",
        )

    # Step 4: SSRF check — verify resolved IP is not private
    parsed = urlparse(final_url)
    if not _check_hostname_safe(parsed.hostname):
        return ValidationResult(
            is_valid=False,
            error_code="INVALID_URL",
            error_message="URL resolves to a restricted address.",
        )

    # Step 5: Detect platform from final URL
    platform = detect_platform(final_url)
    if platform is None:
        # Try broader hostname-based detection
        hostname = parsed.hostname or ""
        if "tiktok.com" in hostname:
            platform = "tiktok"
        elif "instagram.com" in hostname:
            platform = "instagram"
        else:
            return ValidationResult(
                is_valid=False,
                error_code="UNSUPPORTED_PLATFORM",
                error_message="URL must be a TikTok video or Instagram Reel.",
            )

    # Step 6: Normalize
    normalized = _normalize_url(final_url)

    return ValidationResult(
        is_valid=True,
        platform=platform,
        normalized_url=normalized,
    )
