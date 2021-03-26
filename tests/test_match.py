"""Test the matching of Kaldi CTMs and segments to the transcript statements."""
import pytest

from fi_parliament_tools.speakerAligner import match


@pytest.mark.parametrize(
    "segment_begin, subsegment_begin, true_start",
    [
        (0.0, 0.0, 0.0),
        (870.0, 40.32, 910.32),
    ],
)
def test_timestamp_conversion(
    segment_begin: float, subsegment_begin: float, true_start: float
) -> None:
    """Check that conversions from segment timestamps to the full session are accurate."""
    converted_start = match.convert_timestamp(segment_begin, subsegment_begin)
    assert converted_start == true_start


@pytest.mark.parametrize(
    "segment_id, true_main_id, true_start, true_end, true_word_index",
    [
        ("session-003-2016-00000000-00090000[165]", "session-003-2016", 0.0, 900.0, 165),
        ("session-005-2019-00087000-00178692[1955]", "session-005-2019", 870.0, 1786.92, 1955),
        ("session-069-2015-02871000-02950494[737]", "session-069-2015", 28710.0, 29504.94, 737),
        ("session-144-2017-05220000-05310000[8]", "session-144-2017", 52200.0, 53100.0, 8),
    ],
)
def test_split_segment_id(
    segment_id: str, true_main_id: str, true_start: float, true_end: float, true_word_index: int
) -> None:
    """Check that the segment id is split correctly."""
    main_id, start, end, word_index = match.split_segment_id(segment_id)
    assert main_id == true_main_id
    assert start == true_start
    assert end == true_end
    assert word_index == true_word_index
