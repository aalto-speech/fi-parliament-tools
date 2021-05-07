"""Test the matching of Kaldi CTMs and segments to the transcript statements."""
import pytest

from fi_parliament_tools.speakerAligner import IO


@pytest.mark.parametrize(
    "segment_id, true_start, true_end, true_word_index",
    [
        ("session-003-2016-00000000-00090000[165]", 0.0, 900.0, 165),
        ("session-005-2019-00087000-00178692[1955]", 870.0, 1786.92, 1955),
        ("session-069-2015-02871000-02950494[737]", 28710.0, 29504.94, 737),
        ("session-144-2017-05220000-05310000[8]", 52200.0, 53100.0, 8),
    ],
)
def test_split_segment_id(
    segment_id: str, true_start: float, true_end: float, true_word_index: int
) -> None:
    """Check that the segment id is split correctly."""
    start, end, word_index = IO.split_segment_id(segment_id)
    assert start == true_start
    assert end == true_end
    assert word_index == true_word_index


def test_read_table() -> None:
    """Perform a surface level check that a ctm_edits.segmented file is correctly loaded."""
    df = IO.KaldiCTMSegmented("tests/data/ctms/session-071-2017_ctm_edits.segmented").get_df()
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
    assert set(df.edit.unique()) == set(["ins", "sil", "cor", "del", "sub"])


@pytest.mark.parametrize(
    "filename, message",
    [
        ("tests/data/ctms/session-061-2020_ctm_edits.segmented", r"First segment is missing."),
        ("tests/data/ctms/session-129-2016_ctm_edits.segmented", r"There is a missing segment."),
    ],
)
def test_missing_segments(filename: str, message: str) -> None:
    """Check that missing segments raise an error."""
    with pytest.raises(ValueError, match=message):
        IO.KaldiCTMSegmented(filename).get_df()
