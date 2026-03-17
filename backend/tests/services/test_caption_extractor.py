from unittest.mock import MagicMock, patch

import pytest

from app.services.caption_extractor import (
    CaptionExtractionError,
    CaptionResult,
    _clean_transcript,
    _parse_subtitles,
    extract_captions,
)


@pytest.fixture
def mock_ytdlp_captions():
    with patch("app.services.caption_extractor.yt_dlp.YoutubeDL") as mock:
        instance = MagicMock()
        mock.return_value.__enter__ = MagicMock(return_value=instance)
        mock.return_value.__exit__ = MagicMock(return_value=False)
        instance.extract_info.return_value = {
            "duration": 30,
            "uploader": "cookingwithme",
            "title": "Easy Pasta",
            "description": "Quick pasta recipe! #pasta #cooking",
            "thumbnail": "https://example.com/thumb.jpg",
            "tags": ["pasta", "cooking"],
            "subtitles": {"en": [{"ext": "vtt", "url": "http://example.com/subs.vtt"}]},
            "automatic_captions": {},
        }
        yield instance


@pytest.fixture
def sample_vtt_content():
    return (
        "WEBVTT\n"
        "\n"
        "00:00:01.000 --> 00:00:03.000\n"
        "First add the flour\n"
        "\n"
        "00:00:03.000 --> 00:00:05.000\n"
        "then mix in the eggs\n"
        "\n"
        "00:00:05.000 --> 00:00:08.000\n"
        "and pour in the milk\n"
    )


@pytest.fixture
def sample_srt_content():
    return (
        "1\n"
        "00:00:01,000 --> 00:00:03,000\n"
        "First add the flour\n"
        "\n"
        "2\n"
        "00:00:03,000 --> 00:00:05,000\n"
        "then mix in the eggs\n"
        "\n"
        "3\n"
        "00:00:05,000 --> 00:00:08,000\n"
        "and pour in the milk\n"
    )


class TestExtractCaptions:
    @patch("app.services.caption_extractor.settings")
    def test_extract_captions_manual_subs(
        self, mock_settings, mock_ytdlp_captions, tmp_path
    ):
        mock_settings.temp_media_dir = str(tmp_path)
        mock_settings.max_video_duration_seconds = 300
        mock_settings.download_timeout_seconds = 60
        mock_settings.subtitle_langs = "en,en-US"
        mock_settings.subtitle_format = "vtt"

        job_id = "test-job-123"
        sub_dir = tmp_path / job_id
        sub_dir.mkdir(parents=True, exist_ok=True)

        # Create a manual subtitle file
        sub_file = sub_dir / "subs.en.vtt"
        sub_file.write_text(
            "WEBVTT\n\n"
            "00:00:01.000 --> 00:00:03.000\n"
            "Add flour and eggs\n\n"
            "00:00:03.000 --> 00:00:05.000\n"
            "Mix well\n"
        )

        result = extract_captions("https://example.com/video", job_id)

        assert isinstance(result, CaptionResult)
        assert result.caption_source == "manual"
        assert "flour" in result.raw_transcript
        assert result.language == "en"

    @patch("app.services.caption_extractor.settings")
    def test_extract_captions_auto_subs(self, mock_settings, tmp_path):
        mock_settings.temp_media_dir = str(tmp_path)
        mock_settings.max_video_duration_seconds = 300
        mock_settings.download_timeout_seconds = 60
        mock_settings.subtitle_langs = "en,en-US"
        mock_settings.subtitle_format = "vtt"

        job_id = "test-job-auto"
        sub_dir = tmp_path / job_id
        sub_dir.mkdir(parents=True, exist_ok=True)

        # Create an auto subtitle file (has .auto. in name pattern)
        sub_file = sub_dir / "subs.en.auto.vtt"
        sub_file.write_text("WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nAdd flour\n")

        with patch("app.services.caption_extractor.yt_dlp.YoutubeDL") as mock_ydl:
            instance = MagicMock()
            mock_ydl.return_value.__enter__ = MagicMock(return_value=instance)
            mock_ydl.return_value.__exit__ = MagicMock(return_value=False)
            instance.extract_info.return_value = {
                "duration": 30,
                "uploader": "chef",
                "title": "Recipe",
                "description": "Good recipe",
                "subtitles": {},
                "automatic_captions": {"en": [{"ext": "vtt"}]},
            }

            result = extract_captions("https://example.com/video", job_id)

        assert result.caption_source == "auto"
        assert "flour" in result.raw_transcript

    @patch("app.services.caption_extractor.settings")
    def test_fallback_to_description_only(self, mock_settings, tmp_path):
        mock_settings.temp_media_dir = str(tmp_path)
        mock_settings.max_video_duration_seconds = 300
        mock_settings.download_timeout_seconds = 60
        mock_settings.subtitle_langs = "en,en-US"
        mock_settings.subtitle_format = "vtt"

        job_id = "test-job-desc"
        sub_dir = tmp_path / job_id
        sub_dir.mkdir(parents=True, exist_ok=True)
        # No subtitle files created

        with patch("app.services.caption_extractor.yt_dlp.YoutubeDL") as mock_ydl:
            instance = MagicMock()
            mock_ydl.return_value.__enter__ = MagicMock(return_value=instance)
            mock_ydl.return_value.__exit__ = MagicMock(return_value=False)
            instance.extract_info.return_value = {
                "duration": 30,
                "uploader": "chef",
                "title": "Recipe",
                "description": "Easy pasta with garlic and olive oil",
                "subtitles": {},
                "automatic_captions": {},
            }

            result = extract_captions("https://example.com/video", job_id)

        assert result.caption_source == "description_only"
        assert "pasta" in result.raw_transcript
        assert result.language is None

    @patch("app.services.caption_extractor.settings")
    def test_duration_exceeded(self, mock_settings, tmp_path):
        mock_settings.temp_media_dir = str(tmp_path)
        mock_settings.max_video_duration_seconds = 300
        mock_settings.download_timeout_seconds = 60
        mock_settings.subtitle_langs = "en"
        mock_settings.subtitle_format = "vtt"

        with patch("app.services.caption_extractor.yt_dlp.YoutubeDL") as mock_ydl:
            instance = MagicMock()
            mock_ydl.return_value.__enter__ = MagicMock(return_value=instance)
            mock_ydl.return_value.__exit__ = MagicMock(return_value=False)
            instance.extract_info.return_value = {
                "duration": 600,
                "description": "Long video",
            }

            with pytest.raises(CaptionExtractionError) as exc_info:
                extract_captions("https://example.com/video", "test-job")
            assert exc_info.value.code == "DURATION_EXCEEDED"

    @patch("app.services.caption_extractor.settings")
    def test_info_extraction_failure(self, mock_settings, tmp_path):
        import yt_dlp

        mock_settings.temp_media_dir = str(tmp_path)
        mock_settings.download_timeout_seconds = 60
        mock_settings.subtitle_langs = "en"
        mock_settings.subtitle_format = "vtt"

        with patch("app.services.caption_extractor.yt_dlp.YoutubeDL") as mock_ydl:
            instance = MagicMock()
            mock_ydl.return_value.__enter__ = MagicMock(return_value=instance)
            mock_ydl.return_value.__exit__ = MagicMock(return_value=False)
            instance.extract_info.side_effect = yt_dlp.utils.DownloadError("Failed")

            with pytest.raises(CaptionExtractionError) as exc_info:
                extract_captions("https://example.com/video", "test-job")
            assert exc_info.value.code == "INFO_EXTRACTION_FAILED"

    @patch("app.services.caption_extractor.settings")
    def test_empty_subtitles_falls_back_to_description(self, mock_settings, tmp_path):
        mock_settings.temp_media_dir = str(tmp_path)
        mock_settings.max_video_duration_seconds = 300
        mock_settings.download_timeout_seconds = 60
        mock_settings.subtitle_langs = "en"
        mock_settings.subtitle_format = "vtt"

        job_id = "test-job-empty"
        sub_dir = tmp_path / job_id
        sub_dir.mkdir(parents=True, exist_ok=True)

        # Create an empty subtitle file
        sub_file = sub_dir / "subs.en.vtt"
        sub_file.write_text("WEBVTT\n\n")

        with patch("app.services.caption_extractor.yt_dlp.YoutubeDL") as mock_ydl:
            instance = MagicMock()
            mock_ydl.return_value.__enter__ = MagicMock(return_value=instance)
            mock_ydl.return_value.__exit__ = MagicMock(return_value=False)
            instance.extract_info.return_value = {
                "duration": 30,
                "description": "Delicious soup recipe",
                "subtitles": {"en": [{"ext": "vtt"}]},
                "automatic_captions": {},
            }

            result = extract_captions("https://example.com/video", job_id)

        assert result.caption_source == "description_only"
        assert "soup" in result.raw_transcript


class TestParseSubtitles:
    def test_vtt_parsing(self, tmp_path, sample_vtt_content):
        vtt_file = tmp_path / "test.vtt"
        vtt_file.write_text(sample_vtt_content)

        result = _parse_subtitles(str(vtt_file))

        assert "First add the flour" in result
        assert "then mix in the eggs" in result
        assert "and pour in the milk" in result
        # No timestamps
        assert "-->" not in result
        assert "WEBVTT" not in result

    def test_srt_parsing(self, tmp_path, sample_srt_content):
        srt_file = tmp_path / "test.srt"
        srt_file.write_text(sample_srt_content)

        result = _parse_subtitles(str(srt_file))

        assert "First add the flour" in result
        assert "then mix in the eggs" in result
        assert "-->" not in result

    def test_deduplicates_consecutive_lines(self, tmp_path):
        """Auto-captions often repeat lines across overlapping segments."""
        content = (
            "WEBVTT\n\n"
            "00:00:01.000 --> 00:00:03.000\n"
            "Add the flour\n\n"
            "00:00:02.000 --> 00:00:04.000\n"
            "Add the flour\n\n"
            "00:00:04.000 --> 00:00:06.000\n"
            "Mix well\n"
        )
        vtt_file = tmp_path / "test.vtt"
        vtt_file.write_text(content)

        result = _parse_subtitles(str(vtt_file))
        assert result.count("Add the flour") == 1

    def test_strips_html_tags(self, tmp_path):
        content = (
            "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\n<c>Add the</c> <b>flour</b>\n"
        )
        vtt_file = tmp_path / "test.vtt"
        vtt_file.write_text(content)

        result = _parse_subtitles(str(vtt_file))
        assert "Add the flour" in result
        assert "<c>" not in result
        assert "<b>" not in result


class TestCleanTranscript:
    def test_removes_filler_words(self):
        text = "So um basically you just like add the flour you know"
        result = _clean_transcript(text)
        assert "um" not in result.split()
        assert "like" not in result.split()
        assert "basically" not in result.split()
        assert "you know" not in result
        assert "flour" in result

    def test_normalizes_measurements(self):
        text = "Add half a cup of sugar and a teaspoon of salt"
        result = _clean_transcript(text)
        assert "1/2 cup" in result
        assert "1 teaspoon" in result

    def test_collapses_spaces(self):
        text = "Add  the   flour    now"
        result = _clean_transcript(text)
        assert "  " not in result

    def test_preserves_normal_text(self):
        text = "Preheat the oven to 350 degrees and prepare the baking sheet."
        result = _clean_transcript(text)
        assert result == text
