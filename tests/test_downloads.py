"""Test cases for the downloads module."""
import shutil
import subprocess
from logging import Logger
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock

import pytest
from pytest_mock.plugin import MockerFixture  # type: ignore

from fi_parliament_tools.downloads import DownloadPipeline


@pytest.fixture
def download_pipeline(logger: Logger) -> DownloadPipeline:
    """Initialize DownloadPipeline with logger."""
    pipeline = DownloadPipeline(logger)
    return pipeline


@pytest.fixture
def mock_downloads_path(mocker: MockerFixture) -> MagicMock:
    """Mock path formed in form_path of downloads module."""
    mock: MagicMock = mocker.patch("fi_parliament_tools.downloads.Path")
    mock.return_value.resolve.return_value.__str__.return_value = "tests/testing.test"
    mock.return_value.resolve.return_value.exists.side_effect = [False, True]
    return mock


@pytest.fixture
def mock_shutil_error(mocker: MockerFixture) -> MagicMock:
    """Trigger an error once in a shutil.copyfileobj call."""
    mock: MagicMock = mocker.patch("fi_parliament_tools.downloads.shutil.copyfileobj")
    mock.side_effect = shutil.Error("Video download failure.")
    return mock


@pytest.fixture
def mock_subprocess_run(mocker: MockerFixture) -> MagicMock:
    """Trigger the potential errors during a subprocess.run call."""
    mock: MagicMock = mocker.patch("fi_parliament_tools.downloads.subprocess.run")
    mock.side_effect = [subprocess.CalledProcessError(1, "sub", stderr="failed"), KeyboardInterrupt]
    return mock


def test_downloads_form_path(
    mock_downloads_path: MagicMock,
    download_pipeline: DownloadPipeline,
) -> None:
    """Check path forming separately."""
    assert str(download_pipeline.form_path(0, 0, "test")) == "tests/testing.test"
    assert len(download_pipeline.errors) == 0
    mock_downloads_path.assert_called_once()

    assert download_pipeline.form_path(0, 0, "test") is None
    assert download_pipeline.errors[0] == "File tests/testing.test exists, will not overwrite."
    assert mock_downloads_path.call_count == 2


@mock.patch("fi_parliament_tools.downloads.DownloadPipeline.extract_wav")
@mock.patch("fi_parliament_tools.downloads.shutil.copyfileobj")
@mock.patch("fi_parliament_tools.downloads.atomic_write")
@mock.patch("fi_parliament_tools.downloads.requests.get")
def test_download_video(
    mocked_get: MagicMock,
    mocked_atomic_write: MagicMock,
    mocked_copyfileobj: MagicMock,
    mocked_extract_wav: MagicMock,
    download_pipeline: DownloadPipeline,
) -> None:
    """Test single video download."""
    path = Path("test_path")
    url = "https://eduskunta.videosync.fi/api/v1/events/abc012345/video/download"
    download_pipeline.download_video(path, **{"index": "abc012345"})
    mocked_get.assert_called_once_with(url, stream=True)
    mocked_atomic_write.assert_called_once_with(path, mode="wb")
    mocked_copyfileobj.assert_called_once()
    mocked_extract_wav.assert_called_once_with(path)


@mock.patch("fi_parliament_tools.downloads.DownloadPipeline.extract_wav")
@mock.patch("fi_parliament_tools.downloads.atomic_write")
@mock.patch("fi_parliament_tools.downloads.requests.get")
def test_download_video_exception(
    mocked_get: MagicMock,
    mocked_atomic_write: MagicMock,
    mocked_extract_wav: MagicMock,
    mock_shutil_error: MagicMock,
    download_pipeline: DownloadPipeline,
) -> None:
    """Test error capture in video download."""
    path = Path("test_path")
    url = "https://eduskunta.videosync.fi/api/v1/events/abc012345/video/download"
    download_pipeline.download_video(path, **{"index": "abc012345"})
    mocked_get.assert_called_once_with(url, stream=True)
    mocked_atomic_write.assert_called_once_with(path, mode="wb")
    mock_shutil_error.assert_called_once()
    mocked_extract_wav.assert_not_called()
    assert download_pipeline.errors[0] == f"Video download failed for test_path from {url}."


@mock.patch("fi_parliament_tools.downloads.subprocess.run")
def test_extract_wav(mocked_subprocess: MagicMock, download_pipeline: DownloadPipeline) -> None:
    """Test wav extraction in a subprocess."""
    path = Path("test.mp4")
    args = ["ffmpeg", "-i", "test.mp4", "-f", "wav", "-ar", "16000", "-ac", "1", "test.wav"]
    download_pipeline.extract_wav(path)
    mocked_subprocess.assert_called_once_with(args, capture_output=True, check=True, text=True)


@mock.patch("fi_parliament_tools.downloads.DownloadPipeline.cleanup_subprocess")
def test_extract_wav_errors(
    mocked_cleanup: MagicMock, mock_subprocess_run: MagicMock, download_pipeline: DownloadPipeline
) -> None:
    """Test subprocess errors in extracting wavs."""
    path = Path("test.mp4")
    args = ["ffmpeg", "-i", "test.mp4", "-f", "wav", "-ar", "16000", "-ac", "1", "test.wav"]
    download_pipeline.extract_wav(path)
    mock_subprocess_run.assert_called_once_with(args, capture_output=True, check=True, text=True)
    mocked_cleanup.assert_called_once_with(
        "ffmpeg returned non-zero exit status 1. Stderr:\n failed", [Path("test.wav"), path]
    )
    download_pipeline.extract_wav(path)
    mock_subprocess_run.assert_called_with(args, capture_output=True, check=True, text=True)
    mocked_cleanup.assert_called_with("Caught keyboard interrupt.", [Path("test.wav"), path])


@mock.patch("fi_parliament_tools.downloads.Path.unlink")
def test_cleanup_subprocess(mocked_unlink: MagicMock, download_pipeline: DownloadPipeline) -> None:
    """Test clean up after a subprocess error."""
    download_pipeline.cleanup_subprocess("failed", [Path("one"), Path("two")])
    mocked_unlink.assert_called_with(missing_ok=True)
    assert mocked_unlink.call_count == 2
