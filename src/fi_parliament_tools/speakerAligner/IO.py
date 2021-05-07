"""Functions for matching the speaker turns in Kaldi CTMs and segments files."""
import csv
from typing import List
from typing import Optional
from typing import Tuple

import pandas as pd


class KaldiFile:
    """Kaldi file template for loading different Kaldi files processing."""

    def __init__(self, filename: str) -> None:
        """Initialize basic properties filename and column names.

        Args:
            filename (str): path to the file
        """
        self.filename = filename
        self.cols = ["left", "right"]

    def load(self, separator: str = " ") -> pd.DataFrame:
        """Load a Kaldi file with even columns into a DataFrame.

        Args:
            separator (str): character that separates columns. Defaults to " ".

        Returns:
            pd.DataFrame: loaded DataFrame
        """
        return pd.read_csv(self.filename, sep=separator, names=self.cols)

    def load_uneven_columns(self) -> pd.DataFrame:
        """Load a Kaldi file with uneven columns into a DataFrame.

        Returns:
            pd.DataFrame: loaded DataFrame
        """
        rows = []
        last = self.cols[-1]
        with open(self.filename, "r") as input:
            for row in csv.DictReader(
                input, delimiter=" ", fieldnames=self.cols[:-1], restkey=last, skipinitialspace=True
            ):
                try:
                    row[last] = " ".join(row[last])
                except KeyError:
                    row[last] = ""
                rows.append(row)
        return pd.DataFrame(rows, columns=self.cols)


class KaldiCTMSegmented(KaldiFile):
    """Kaldi CTM edits segmented file."""

    def __init__(self, filename: str) -> None:
        """Initialize and define columns specific to this filetype.

        Args:
            filename (str): path to the file
        """
        super().__init__(filename)
        self.cols = [
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

    def get_df(self) -> pd.DataFrame:
        """Convert data in the file into a DataFrame that can be used in postprocessing.

        Returns:
            pd.DataFrame: prepared DataFrame
        """
        df = self.load_uneven_columns()
        df = df.assign(speaker="unknown", mpid=0, lang="")
        df[["seg_start", "seg_end", "word_id"]] = df.session.apply(
            lambda x: pd.Series(split_segment_id(x))
        )
        numtypes = {"word_start": "float64", "word_duration": "float64", "word_id": "int64"}
        df = df.astype(numtypes)
        df["session_start"] = df["seg_start"] + df["word_start"]
        df.drop(columns=["session", "ch", "prob"], inplace=True)
        check_missing_segments(df)
        return df


class KaldiSegments(KaldiFile):
    """Kaldi segments file."""

    def __init__(self, filename: str) -> None:
        """Initialize and define columns specific to this filetype.

        Args:
            filename (str): path to the file
        """
        super().__init__(filename)
        self.cols = ["uttid", "recordid", "start", "end"]

    def get_df(self) -> pd.DataFrame:
        """Convert data in the file into a DataFrame that can be used in postprocessing.

        Returns:
            pd.DataFrame: prepared DataFrame
        """
        df = self.load()
        df = df.assign(new_uttid="")
        df[["seg_start", "seg_end", "seg_id"]] = df.uttid.apply(
            lambda x: pd.Series(split_segment_id(x))
        )
        df.start += df.seg_start
        df.end += df.seg_start
        return df

    def save_df(
        self, df: pd.DataFrame, suffix: str = ".new", cols: Optional[List[str]] = None
    ) -> None:
        """Save DataFrame into a CSV file.

        Args:
            df (pd.DataFrame): data to save
            suffix (str): suffix for the file
            cols (List[str], optional): columns to save, defaults to None
        """
        if cols is None:
            cols = ["new_uttid", "recordid", "start", "end"]
        df.to_csv(
            f"{self.filename}{suffix}",
            sep=" ",
            float_format="%.2f",
            columns=cols,
            header=False,
            index=False,
        )


class KaldiText(KaldiFile):
    """Kaldi text file."""

    def __init__(self, filename: str) -> None:
        """Initialize and define columns specific to this filetype.

        Args:
            filename (str): path to the file
        """
        super().__init__(filename)
        self.cols = ["uttid"]

    def get_df(self) -> pd.DataFrame:
        """Convert data in the file into a DataFrame that can be used in postprocessing.

        Returns:
            pd.DataFrame: prepared DataFrame
        """
        df = self.load(separator="\n")
        split = df.uttid.str.split(" ", n=1, expand=True)
        df.uttid = split[0]
        df = df.assign(text=split[1], new_uttid="")
        return df

    def save_df(
        self, df: pd.DataFrame, suffix: str = ".new", cols: Optional[List[str]] = None
    ) -> None:
        """Save DataFrame into a CSV file.

        Args:
            df (pd.DataFrame): data to save
            suffix (str): suffix for the file
            cols (List[str], optional): columns to save, defaults to None
        """
        if cols is None:
            cols = ["new_uttid", "text"]
        df.to_csv(
            f"{self.filename}{suffix}",
            sep=" ",
            columns=cols,
            header=False,
            index=False,
            quoting=csv.QUOTE_NONE,
            escapechar=" ",
        )


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
