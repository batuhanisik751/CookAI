import json
from unittest.mock import MagicMock, patch

import anthropic
import pytest

from app.services.visual_analyzer import (
    VisualAnalysis,
    VisualAnalysisError,
    _sample_frames,
    analyze_frames,
)


@pytest.fixture
def sample_vision_response():
    return {
        "ingredients_observed": ["flour", "eggs", "butter"],
        "techniques_observed": ["whisking", "folding"],
        "equipment_observed": ["mixing bowl", "whisk"],
        "plating_notes": "Served on a white plate with garnish",
        "frame_observations": [
            {"frame_index": 0, "description": "Ingredients laid out on counter"},
        ],
    }


@pytest.fixture
def mock_claude_client(sample_vision_response):
    with patch("app.services.visual_analyzer.anthropic.Anthropic") as mock_cls:
        client = MagicMock()
        mock_cls.return_value = client
        response = MagicMock()
        response.content = [MagicMock(text=json.dumps(sample_vision_response))]
        client.messages.create.return_value = response
        yield client


@pytest.fixture
def frame_files(tmp_path):
    """Create fake JPEG frame files."""
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    paths = []
    for i in range(5):
        frame = frames_dir / f"frame_{i:04d}.jpg"
        frame.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)  # fake JPEG header
        paths.append(str(frame))
    return paths


class TestAnalyzeFrames:
    def test_success(self, mock_claude_client, frame_files):
        result = analyze_frames(frame_files)

        assert isinstance(result, VisualAnalysis)
        assert "flour" in result.ingredients_observed
        assert "eggs" in result.ingredients_observed
        assert "whisking" in result.techniques_observed
        assert "mixing bowl" in result.equipment_observed
        assert result.plating_notes is not None
        mock_claude_client.messages.create.assert_called_once()

    def test_empty_frames(self):
        result = analyze_frames([])
        assert result.ingredients_observed == []
        assert result.techniques_observed == []

    def test_api_error(self, frame_files):
        with patch("app.services.visual_analyzer.anthropic.Anthropic") as mock_cls:
            client = MagicMock()
            mock_cls.return_value = client
            client.messages.create.side_effect = anthropic.APIError(
                message="Server error",
                request=MagicMock(),
                body=None,
            )

            with pytest.raises(VisualAnalysisError) as exc_info:
                analyze_frames(frame_files)
            assert exc_info.value.code == "VISION_API_ERROR"

    def test_timeout(self, frame_files):
        with patch("app.services.visual_analyzer.anthropic.Anthropic") as mock_cls:
            client = MagicMock()
            mock_cls.return_value = client
            client.messages.create.side_effect = anthropic.APITimeoutError(
                request=MagicMock()
            )

            with pytest.raises(VisualAnalysisError) as exc_info:
                analyze_frames(frame_files)
            assert exc_info.value.code == "VISION_TIMEOUT"

    def test_invalid_json_response(self, frame_files):
        with patch("app.services.visual_analyzer.anthropic.Anthropic") as mock_cls:
            client = MagicMock()
            mock_cls.return_value = client
            response = MagicMock()
            response.content = [MagicMock(text="not valid json")]
            client.messages.create.return_value = response

            with pytest.raises(VisualAnalysisError) as exc_info:
                analyze_frames(frame_files)
            assert exc_info.value.code == "VISION_PARSE_ERROR"


class TestSampleFrames:
    def test_under_limit(self):
        paths = [f"frame_{i}.jpg" for i in range(5)]
        result = _sample_frames(paths, max_frames=10)
        assert result == paths

    def test_at_limit(self):
        paths = [f"frame_{i}.jpg" for i in range(10)]
        result = _sample_frames(paths, max_frames=10)
        assert result == paths

    def test_over_limit(self):
        paths = [f"frame_{i}.jpg" for i in range(30)]
        result = _sample_frames(paths, max_frames=10)
        assert len(result) == 10
        # First and last always included
        assert result[0] == paths[0]
        assert result[-1] == paths[-1]

    def test_includes_first_and_last(self):
        paths = [f"frame_{i}.jpg" for i in range(50)]
        result = _sample_frames(paths, max_frames=5)
        assert result[0] == paths[0]
        assert result[-1] == paths[-1]

    def test_single_frame(self):
        paths = ["frame_0.jpg"]
        result = _sample_frames(paths, max_frames=15)
        assert result == paths
