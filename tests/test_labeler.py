"""Test the matching of Kaldi CTMs and segments to the transcript statements."""
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest
from _pytest.fixtures import SubRequest
from pytest_mock.plugin import MockerFixture  # type: ignore

from fi_parliament_tools.transcriptMatcher import labeler


@pytest.fixture
def info_df_row(request: SubRequest) -> pd.Series:
    """Create a pd.Series that mimicks a row from the info DataFrame."""
    name, num, start, end, word = request.param
    data = {"seg_num": num, "seg_start_idx": start, "seg_end_idx": end, "word_id": word}
    return pd.Series(data=data, name=name)


@pytest.fixture
def test_df() -> pd.DataFrame:
    """Read a customized ctm_edits test file to a pandas DataFrame for testing.

    Returns:
        pd.DataFrame: custom ctm_edits file
    """
    cols = ["word_start", "word_duration", "asr", "transcript", "edit", "mpid", "lang"]
    filename = "tests/data/ctms/custom_test.ctm_edits.segmented"
    df = pd.read_csv(filename, sep=" ", usecols=[2, 3, 4, 6, 7, 8, 9], names=cols, quotechar="'")
    return df.replace(np.nan, "", regex=True)


@pytest.fixture
def mock_statement(mocker: MockerFixture) -> MagicMock:
    """Mock a Statement object."""
    mock: MagicMock = mocker.patch("fi_parliament_tools.transcriptMatcher.labeler.Statement")
    mock.language = "sv.p"
    mock.mp_id = 1
    mock.firstname = "Test"
    mock.lastname = "Person"
    return mock


@pytest.fixture
def mock_find_statement(mocker: MockerFixture) -> MagicMock:
    """Mock find_statement method."""
    mock: MagicMock = mocker.patch("fi_parliament_tools.transcriptMatcher.labeler.find_statement")
    mock.return_value = (10, 15)
    return mock


@pytest.mark.parametrize(
    "start_idx, end_idx, true_start, true_end",
    [(159, 177, 162, 177), (241, 260, 241, 260), (417, 453, 417, 449), (778, 828, 784, 822)],
)
def test_adjust_indices(
    start_idx: int, end_idx: int, true_start: int, true_end: int, test_df: pd.DataFrame
) -> None:
    """Adjust indices so that first and last words are cor edits."""
    adjusted_start, adjusted_end = labeler.adjust_indices(test_df, start_idx, end_idx)
    assert adjusted_start == true_start
    assert adjusted_end == true_end


def test_adjust_indices_error(test_df: pd.DataFrame) -> None:
    """Fail adjust indices if start and end indices are the same."""
    with pytest.raises(ValueError):
        labeler.adjust_indices(test_df, 8, 8)


def test_assign_speaker_swedish(
    mock_statement: MagicMock, mock_find_statement: MagicMock, test_df: pd.DataFrame
) -> None:
    """Index adjustment is skipped for statements in Swedish."""
    df = labeler.assign_speaker(test_df, "dummy text", mock_statement)
    mock_find_statement.assert_called_once()
    assert df.iloc[10:16].speaker.unique()[0] == "Test Person"
    assert df.iloc[10:16].mpid.unique()[0] == 1
    assert df.iloc[10:16].lang.unique()[0] == "sv.p"


def test_find_statement(test_df: pd.DataFrame) -> None:
    """Find a correctly aligned statement amidst wronly aligned statements."""
    start, end = labeler.find_statement(
        test_df,
        "this speaker says something but alignment is correct".split(),
        "fi",
        size=40,
        step=30,
    )
    assert start == 309
    assert end == 319


@pytest.mark.parametrize(
    "masked_start, text, true_end",
    [
        (
            0,
            "this speaker says something in swedish the member of parliament speaks here some more "
            "and then says thank you",
            187,
        ),
        (
            133,
            "this speaker repeats their words often and the repetitions need to be handled as well "
            "somehow because the transcribers omit them these are the last words",
            417,
        ),
    ],
)
def test_find_end_index(masked_start: int, text: str, true_end: int, test_df: pd.DataFrame) -> None:
    """Find the end of statement in the CTM."""
    masked = test_df[(test_df.transcript != "<eps>") & (test_df.transcript != "<UNK>")]
    end_idx = labeler.find_end_index(masked.transcript[masked_start:], text.split(), added_range=10)
    assert end_idx == true_end


def test_find_end_index_error(test_df: pd.DataFrame) -> None:
    """End index search should fail the statement end is not found in the CTM."""
    masked = test_df[(test_df.transcript != "<eps>") & (test_df.transcript != "<UNK>")]
    statement = "this statement does not exist in the test ctm"
    with pytest.raises(ValueError, match="Statement end index not found."):
        labeler.find_end_index(masked.transcript[150:], statement.split())


def test_sliding_window() -> None:
    """Test the sliding window function."""
    windows = [["a", "b", "c"], ["c", "d", "e"], ["e", "f", "f"]]
    iterable = ["a", "b", "c", "d", "e"]
    for i, window in enumerate(labeler.sliding_window(iterable, size=3, step=2, fillvalue="f")):
        assert list(window) == windows[i]


def test_sliding_window_empty_iterable() -> None:
    """Empty iterable should stop iteration."""
    with pytest.raises(StopIteration):
        next(labeler.sliding_window([], size=0, step=2))


def test_sliding_window_value_error() -> None:
    """Too small step size should raise a ValueError."""
    with pytest.raises(ValueError):
        next(w for w in labeler.sliding_window(["test", "iterable"], size=-1, step=0))


@pytest.mark.parametrize(
    "info_df_row, true_mpid",
    [
        (((77, 0), 1, 77, 87, 77), 0),
        (((240, 0), 2, 78, 98, 78), 1742),
        (((446, 0), 1, 284, 298, 284), -1),
        (((682, 0), 1, 189, 202, 188), -1),
    ],
    indirect=["info_df_row"],
)
def test_get_segment_speaker(info_df_row: pd.Series, true_mpid: int, test_df: pd.DataFrame) -> None:
    """Segment has either one speaker or multiple."""
    mask = (test_df.edit != "sil") & (test_df.edit != "fix")
    mpid = labeler.get_segment_speaker(info_df_row, test_df, mask)
    assert mpid == true_mpid


@pytest.mark.parametrize(
    "info_df_row, true_lang",
    [
        (((162, 0), 1, 0, 25, 0), "sv"),
        (((240, 0), 1, 78, 98, 78), "fi+sv"),
        (((590, 0), 1, 96, 110, 96), "fi+sv"),
        (((628, 0), 1, 134, 149, 133), "fi"),
    ],
    indirect=["info_df_row"],
)
def test_get_segment_lang(info_df_row: pd.Series, true_lang: str, test_df: pd.DataFrame) -> None:
    """Segment has either one speaker or multiple."""
    mask = (test_df.edit != "sil") & (test_df.edit != "fix")
    lang = labeler.get_segment_language(info_df_row, test_df, mask)
    assert lang == true_lang
