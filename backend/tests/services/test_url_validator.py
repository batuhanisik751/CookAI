from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.url_validator import (
    _is_host_allowed,
    _is_private_ip,
    _normalize_url,
    detect_platform,
    validate_url,
)


class TestDetectPlatform:
    def test_tiktok_standard_url(self):
        url = "https://www.tiktok.com/@user/video/1234567890123456789"
        assert detect_platform(url) == "tiktok"

    def test_tiktok_short_url(self):
        url = "https://vm.tiktok.com/ZMxxxxxxxxx/"
        assert detect_platform(url) == "tiktok"

    def test_tiktok_vt_url(self):
        url = "https://vt.tiktok.com/ZMxxxxxxxxx/"
        assert detect_platform(url) == "tiktok"

    def test_instagram_reel_url(self):
        url = "https://www.instagram.com/reel/ABC123def456/"
        assert detect_platform(url) == "instagram"

    def test_instagram_reels_url(self):
        url = "https://www.instagram.com/reels/ABC123def456/"
        assert detect_platform(url) == "instagram"

    def test_instagram_p_url(self):
        url = "https://www.instagram.com/p/ABC123def456/"
        assert detect_platform(url) == "instagram"

    def test_unsupported_youtube(self):
        assert detect_platform("https://www.youtube.com/watch?v=abc123") is None

    def test_unsupported_random_url(self):
        assert detect_platform("https://example.com/video") is None


class TestIsPrivateIp:
    def test_localhost(self):
        assert _is_private_ip("127.0.0.1") is True

    def test_private_10(self):
        assert _is_private_ip("10.0.0.1") is True

    def test_private_172(self):
        assert _is_private_ip("172.16.0.1") is True

    def test_private_192(self):
        assert _is_private_ip("192.168.1.1") is True

    def test_ipv6_loopback(self):
        assert _is_private_ip("::1") is True

    def test_public_ip(self):
        assert _is_private_ip("8.8.8.8") is False

    def test_invalid_ip(self):
        assert _is_private_ip("not-an-ip") is True


class TestNormalizeUrl:
    def test_strips_tracking_params(self):
        url = "https://www.tiktok.com/@user/video/123?utm_source=twitter&utm_medium=social"
        normalized = _normalize_url(url)
        assert "utm_source" not in normalized
        assert "utm_medium" not in normalized

    def test_strips_tiktok_tracking(self):
        url = "https://www.tiktok.com/@user/video/123?tt_from=copy&is_copy_url=1"
        normalized = _normalize_url(url)
        assert "tt_from" not in normalized
        assert "is_copy_url" not in normalized

    def test_strips_instagram_tracking(self):
        url = "https://www.instagram.com/reel/ABC123/?igshid=xyz"
        normalized = _normalize_url(url)
        assert "igshid" not in normalized

    def test_preserves_path(self):
        url = "https://www.tiktok.com/@user/video/123"
        normalized = _normalize_url(url)
        assert "/@user/video/123" in normalized

    def test_strips_trailing_slash(self):
        url = "https://www.tiktok.com/@user/video/123/"
        normalized = _normalize_url(url)
        assert normalized.endswith("123")

    def test_strips_fragment(self):
        url = "https://www.tiktok.com/@user/video/123#comments"
        normalized = _normalize_url(url)
        assert "#" not in normalized


class TestIsHostAllowed:
    def test_tiktok_allowed(self):
        assert _is_host_allowed("https://www.tiktok.com/video") is True

    def test_instagram_allowed(self):
        assert _is_host_allowed("https://www.instagram.com/reel/123") is True

    def test_random_not_allowed(self):
        assert _is_host_allowed("https://evil.com/video") is False

    def test_no_hostname(self):
        assert _is_host_allowed("not-a-url") is False


class TestValidateUrl:
    @pytest.mark.asyncio
    async def test_valid_tiktok_url(self, mock_httpx):
        result = await validate_url(
            "https://www.tiktok.com/@cookingwithme/video/7312345678901234567"
        )
        assert result.is_valid is True
        assert result.platform == "tiktok"
        assert result.normalized_url is not None

    @pytest.mark.asyncio
    async def test_unsupported_platform(self):
        result = await validate_url("https://www.youtube.com/watch?v=abc")
        assert result.is_valid is False
        assert result.error_code == "UNSUPPORTED_PLATFORM"

    @pytest.mark.asyncio
    async def test_url_timeout(self):
        with patch("app.services.url_validator.httpx.AsyncClient") as mock:
            client = AsyncMock()
            mock.return_value.__aenter__ = AsyncMock(return_value=client)
            mock.return_value.__aexit__ = AsyncMock(return_value=False)
            client.head.side_effect = httpx.TimeoutException("timeout")

            result = await validate_url("https://www.tiktok.com/@user/video/123")
            assert result.is_valid is False
            assert result.error_code == "URL_TIMEOUT"

    @pytest.mark.asyncio
    async def test_url_unreachable(self):
        with patch("app.services.url_validator.httpx.AsyncClient") as mock:
            client = AsyncMock()
            mock.return_value.__aenter__ = AsyncMock(return_value=client)
            mock.return_value.__aexit__ = AsyncMock(return_value=False)
            client.head.side_effect = httpx.ConnectError("connection refused")

            result = await validate_url("https://www.tiktok.com/@user/video/123")
            assert result.is_valid is False
            assert result.error_code == "URL_UNREACHABLE"

    @pytest.mark.asyncio
    async def test_redirect_to_disallowed_host(self):
        with patch("app.services.url_validator.httpx.AsyncClient") as mock:
            client = AsyncMock()
            mock.return_value.__aenter__ = AsyncMock(return_value=client)
            mock.return_value.__aexit__ = AsyncMock(return_value=False)
            response = MagicMock()
            response.url = "https://evil.com/steal-data"
            response.status_code = 200
            client.head.return_value = response

            result = await validate_url("https://vm.tiktok.com/ZMxxxxxxxxx/")
            assert result.is_valid is False
            assert result.error_code == "UNSUPPORTED_PLATFORM"

    @pytest.mark.asyncio
    async def test_ssrf_private_ip(self, mock_httpx):
        with patch(
            "app.services.url_validator._check_hostname_safe", return_value=False
        ):
            result = await validate_url("https://www.tiktok.com/@user/video/123")
            assert result.is_valid is False
            assert result.error_code == "INVALID_URL"
