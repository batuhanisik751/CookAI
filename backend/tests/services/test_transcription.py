from unittest.mock import MagicMock, patch

import openai
import pytest

from app.services.transcription import (
    TranscriptionError,
    _clean_transcript,
    transcribe_audio,
)


@pytest.fixture
def mock_whisper_response():
    response = MagicMock()
    response.text = "Add one cup of flour and two eggs to the bowl."
    response.language = "en"
    response.duration = 45.0
    return response


@pytest.fixture
def mock_openai_client(mock_whisper_response):
    with patch("app.services.transcription.openai.OpenAI") as mock_cls:
        client = MagicMock()
        mock_cls.return_value = client
        client.audio.transcriptions.create.return_value = mock_whisper_response
        yield client


class TestTranscribeAudio:
    def test_success(self, mock_openai_client, tmp_path):
        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"fake audio data")

        result = transcribe_audio(str(audio_file))

        assert result.raw_transcript == "Add one cup of flour and two eggs to the bowl."
        assert result.language == "en"
        assert result.duration_seconds == 45.0
        assert result.cleaned_transcript  # should be non-empty
        mock_openai_client.audio.transcriptions.create.assert_called_once()

    def test_file_not_found(self):
        with pytest.raises(TranscriptionError) as exc_info:
            transcribe_audio("/nonexistent/audio.wav")
        assert exc_info.value.code == "FILE_NOT_FOUND"

    def test_api_error(self, tmp_path):
        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"fake audio data")

        with patch("app.services.transcription.openai.OpenAI") as mock_cls:
            client = MagicMock()
            mock_cls.return_value = client
            client.audio.transcriptions.create.side_effect = openai.APIError(
                message="Server error",
                request=MagicMock(),
                body=None,
            )

            with pytest.raises(TranscriptionError) as exc_info:
                transcribe_audio(str(audio_file))
            assert exc_info.value.code == "TRANSCRIPTION_API_ERROR"

    def test_timeout(self, tmp_path):
        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"fake audio data")

        with patch("app.services.transcription.openai.OpenAI") as mock_cls:
            client = MagicMock()
            mock_cls.return_value = client
            client.audio.transcriptions.create.side_effect = openai.APITimeoutError(
                request=MagicMock()
            )

            with pytest.raises(TranscriptionError) as exc_info:
                transcribe_audio(str(audio_file))
            assert exc_info.value.code == "TRANSCRIPTION_TIMEOUT"


class TestCleanTranscript:
    def test_removes_filler_words(self):
        text = "So um add like a cup of flour and uh stir it"
        cleaned = _clean_transcript(text)
        assert "um" not in cleaned.split()
        assert "uh" not in cleaned.split()
        assert "like" not in cleaned.split()

    def test_normalizes_a_cup(self):
        text = "Add a cup of sugar"
        cleaned = _clean_transcript(text)
        assert "1 cup" in cleaned

    def test_normalizes_a_teaspoon(self):
        text = "Add a teaspoon of salt"
        cleaned = _clean_transcript(text)
        assert "1 teaspoon" in cleaned

    def test_normalizes_a_tablespoon(self):
        text = "Use a tablespoon of olive oil"
        cleaned = _clean_transcript(text)
        assert "1 tablespoon" in cleaned

    def test_normalizes_half_a_cup(self):
        text = "Add half a cup of milk"
        cleaned = _clean_transcript(text)
        assert "1/2 cup" in cleaned

    def test_normalizes_quarter_cup(self):
        text = "Use a quarter cup of water"
        cleaned = _clean_transcript(text)
        assert "1/4 cup" in cleaned

    def test_preserves_cooking_content(self):
        text = "Preheat the oven to 350 degrees and mix the batter"
        cleaned = _clean_transcript(text)
        assert cleaned == text

    def test_collapses_whitespace(self):
        text = "Add  flour   and   sugar"
        cleaned = _clean_transcript(text)
        assert "  " not in cleaned
