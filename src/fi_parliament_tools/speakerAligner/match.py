"""Functions for matching the speaker turns in Kaldi CTMs and segments files."""
from typing import Tuple

import numpy as np
import pandas as pd


def split_segment_id(segment_id: str) -> Tuple[float, float, int]:
    """Split a segment ID to session name, segment begin, segment end, and word id.

    Args:
        segment_id (str): Segment ids are in the form session-001-2015-START-END[WORD_ID]

    Returns:
        Tuple[float, float, int]: start, end, and word id
    """
    _, begin, end = segment_id.rsplit("-", 2)
    end, word_id = end.split("[")
    word_id = word_id.replace("]", "")
    return float(begin) / 100.0, float(end) / 100.0, int(word_id)


def load_to_dataframe(filename: str) -> pd.DataFrame:
    """Load a ctm_edits.segmented file to a DataFrame and prepare it for realignment.

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
        "taint",
        "tmpA",
        "tmpB",
    ]
    df = pd.read_csv(filename, sep=" ", names=cols)
    df = df.replace(np.nan, "", regex=True)
    df = df.assign(kaldi_start="", kaldi_end="")

    for old_col in ("taint", "tmpA", "tmpB"):
        for substring, new_col in (("start-", "kaldi_start"), ("end-", "kaldi_end")):
            mask = df[old_col].str.startswith(substring)
            df.loc[mask, new_col] = df.loc[mask, old_col]
            if old_col == "taint":
                df.loc[mask, old_col] = ""

    df[["seg_start", "seg_end", "word_id"]] = df.session.apply(
        lambda x: pd.Series(split_segment_id(x))
    )
    df["session_start"] = df["seg_start"] + df["word_start"]
    df.drop(columns=["session", "ch", "prob", "tmpA", "tmpB"], inplace=True)
    return df
