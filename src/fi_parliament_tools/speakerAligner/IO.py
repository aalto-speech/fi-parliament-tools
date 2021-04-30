"""Functions for matching the speaker turns in Kaldi CTMs and segments files."""
import csv
from typing import Tuple

import pandas as pd


def split_segment_id(segment_id: str) -> Tuple[float, float, int]:
    """Split a segment ID to segment begin, segment end, and a running number.

    Args:
        segment_id (str): Segment ids are in the form session-001-2015-START-END[NUMBER] or
                        session-001-2015-START-END-NUMBER

    Returns:
        Tuple[float, float, int]: start, end, and number
    """
    if "[" in segment_id:
        _, begin, end = segment_id.rsplit("-", 2)
        end, number = end.split("[")
        number = number.replace("]", "")
    else:
        _, begin, end, number = segment_id.rsplit("-", 3)
    return float(begin) / 100.0, float(end) / 100.0, int(number)


def ctm_edits_to_dataframe(filename: str) -> pd.DataFrame:
    """Load a ctm_edits.segmented file to a DataFrame and prepare it for speaker alignment.

    The temporary columns are used to handle the varying number of space-separated tokens per line.

    Args:
        filename (str): the file to read

    Returns:
        pd.DataFrame: segmentation data for realignment
    """
    cols = [
        "session",
        "ch",
        "word_start",
        "word_duration",
        "asr",
        "prob",
        "transcript",
        "edit",
        "segment_info",
    ]
    rows = []
    with open(filename, "r") as infile:
        for row in csv.DictReader(
            infile, delimiter=" ", fieldnames=cols[:-1], restkey=cols[-1], skipinitialspace=True
        ):
            try:
                row["segment_info"] = " ".join(row["segment_info"])
            except KeyError:
                row["segment_info"] = ""
            rows.append(row)

    df = pd.DataFrame(rows, columns=cols)
    df = df.assign(speaker="unknown", mpid=0)
    df[["seg_start", "seg_end", "word_id"]] = df.session.apply(
        lambda x: pd.Series(split_segment_id(x))
    )
    df = df.astype({"word_start": "float64", "word_duration": "float64", "word_id": "int64"})
    df["session_start"] = df["seg_start"] + df["word_start"]

    df.drop(columns=["session", "ch", "prob"], inplace=True)
    check_missing_segments(df)

    return df


def check_missing_segments(df: pd.DataFrame) -> None:
    """Check that first segment starts from 0 and that there are no missing segments.

    The segmentation script splits each audio into equally long pieces (except for the last one).
    Therefore the distance to the start of the next item in the frame should be either 0 (same
    segment) or the length of the segments (adjacent segments).

    Args:
        df (pd.DataFrame): the dataframe to check

    Raises:
        ValueError: warn about a missing segment
    """
    if not df.seg_start.loc[0] == 0.0:
        raise ValueError("First segment is missing.")
    diffs = df.seg_start - df.seg_start.shift(1, fill_value=0.0)
    unique_diffs = diffs.unique()
    if not len(unique_diffs) <= 2 or 0.0 not in unique_diffs:
        raise ValueError("There is a missing segment.")


def segments_to_dataframe(filename: str) -> pd.DataFrame:
    """Load a segments file to a DataFrame and prepare it for rewrite.

    Args:
        filename (str): the file to read

    Returns:
        pd.DataFrame: segments file
    """
    cols = ["uttid", "recordid", "start", "end"]
    df = pd.read_csv(filename, sep=" ", names=cols)
    df = df.assign(new_uttid="")
    df[["seg_start", "seg_end", "seg_id"]] = df.uttid.apply(
        lambda x: pd.Series(split_segment_id(x))
    )
    df.start += df.seg_start
    df.end += df.seg_start
    return df
