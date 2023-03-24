"""Test the reading and writing of Kaldi files."""
import csv
from typing import List
from typing import Optional
from unittest.mock import MagicMock

import pytest
from pytest_mock.plugin import MockerFixture  # type: ignore

from fi_parliament_tools.segmentFiltering import io


def test_read_ctm_segmented() -> None:
    """Perform a surface level check that a ctm_edits.segmented file is correctly loaded."""
    df = io.KaldiCTMSegmented("tests/data/ctms/session-019-2016").get_df()
    assert list(df.columns) == [
        "word_start",
        "word_duration",
        "asr",
        "transcript",
        "edit",
        "segment_info",
        "speaker",
        "mpid",
        "lang",
        "seg_start",
        "seg_end",
        "word_id",
        "session_start",
    ]
    assert df.isna().sum().sum() == 0
    assert set(df.edit.unique()) == {"ins", "sil", "cor", "del", "sub"}


def test_read_segments() -> None:
    """Perform a surface level check that a Kaldi segments file is correctly loaded."""
    df = io.KaldiSegments("tests/data/ctms/session-019-2016").get_df()
    assert list(df.columns) == [
        "uttid",
        "recordid",
        "start",
        "end",
        "new_uttid",
        "seg_start",
        "seg_end",
        "seg_id",
    ]
    assert df.isna().sum().sum() == 0


def test_read_kaldi_text() -> None:
    """Perform a surface level check that a Kaldi text file is correctly loaded."""
    df = io.KaldiText("tests/data/ctms/session-019-2016").get_df()
    assert list(df.columns) == ["uttid", "text", "new_uttid"]
    assert df.isna().sum().sum() == 0


@pytest.fixture
def mock_df_to_csv(mocker: MockerFixture) -> MagicMock:
    """Mock the to_csv function of a Pandas DataFrame."""
    mock: MagicMock = mocker.patch("fi_parliament_tools.segmentFiltering.io.pd.DataFrame.to_csv")
    return mock


@pytest.mark.parametrize("cols", [None, ["new_uttid"]])
def test_kaldi_segments_save_df(mock_df_to_csv: MagicMock, cols: Optional[List[str]]) -> None:
    """Save Kaldi segments DataFrame to a file."""
    segments = io.KaldiSegments("tests/data/ctms/session-019-2016")
    segments.save_df(segments.df, suffix=".test", cols=cols)
    if cols is None:
        cols = ["new_uttid", "recordid", "start", "end"]
    mock_df_to_csv.assert_called_once_with(
        "tests/data/ctms/session-019-2016.segments.test",
        sep=" ",
        float_format="%.2f",
        columns=cols,
        header=False,
        index=False,
    )


@pytest.mark.parametrize("cols", [None, ["text"]])
def test_kaldi_text_save_df(mock_df_to_csv: MagicMock, cols: Optional[List[str]]) -> None:
    """Save Kaldi text DataFrame to a file."""
    kaldi_text = io.KaldiText("tests/data/ctms/session-019-2016")
    kaldi_text.save_df(kaldi_text.df, suffix=".test", cols=cols)
    if cols is None:
        cols = ["new_uttid", "text"]
    mock_df_to_csv.assert_called_once_with(
        "tests/data/ctms/session-019-2016.text.test",
        sep=" ",
        columns=cols,
        header=False,
        index=False,
        quoting=csv.QUOTE_NONE,
        escapechar=" ",
    )


@pytest.mark.parametrize(
    "segment_id, true_start, true_end, true_word_index",
    [
        ("session-003-2016-00000000-00090000[165]", 0.0, 900.0, 165),
        ("session-005-2019-00087000-00178692[1955]", 870.0, 1786.92, 1955),
        ("session-069-2015-02871000-02950494-737", 28710.0, 29504.94, 737),
        ("session-144-2017-05220000-05310000-8", 52200.0, 53100.0, 8),
    ],
)
def test_split_segment_id(
    segment_id: str, true_start: float, true_end: float, true_word_index: int
) -> None:
    """Check that the segment id is split correctly."""
    start, end, word_index = io.split_segment_id(segment_id)
    assert start == true_start
    assert end == true_end
    assert word_index == true_word_index


@pytest.mark.parametrize(
    "filename, message",
    [
        ("tests/data/ctms/session-061-2020", r"First segment is missing."),
        ("tests/data/ctms/session-129-2016", r"There is a missing segment."),
    ],
)
def test_missing_segments(filename: str, message: str) -> None:
    """Check that missing segments raise an error."""
    with pytest.raises(ValueError, match=message):
        io.KaldiCTMSegmented(filename).get_df()
