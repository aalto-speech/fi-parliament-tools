"""Functions for matching the speaker turns in Kaldi CTMs and segments files."""
from typing import Tuple


def convert_timestamp(
    segment_begin: float,
    subsegment_begin: float,
) -> float:
    """Compute the begin of a subsegment relative to the main session (in seconds).

    Args:
        segment_begin (float): begin time of the uniform segment Kaldi created for decoding
        subsegment_begin (float): begin time of a word/segmentation result within uniform segment

    Returns:
        float: the start of the word/segmentation in the main session
    """
    return segment_begin + subsegment_begin


def split_segment_id(segment_id: str) -> Tuple[str, float, float, int]:
    """Split a segment ID to session name, segment begin, segment end, and word id.

    Args:
        segment_id (str): Segment ids are in the form session-001-2015-START-END[WORD_ID]

    Returns:
        Tuple[str, float, float, int]: session name, start, end, and word id
    """
    session_id, begin, end = segment_id.rsplit("-", 2)
    end, word_id = end.split("[")
    word_id = word_id.replace("]", "")
    return session_id, float(begin) / 100.0, float(end) / 100.0, int(word_id)
