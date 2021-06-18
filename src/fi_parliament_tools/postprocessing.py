"""Command line client logic for postprocessing Finnish parliament data."""
import json
import re
from datetime import date
from logging import Logger
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Tuple

import pandas as pd
from alive_progress import alive_bar

from fi_parliament_tools.transcriptMatcher import IO
from fi_parliament_tools.transcriptMatcher import labeler
from fi_parliament_tools.transcriptParser.data_structures import decode_transcript

STATS_COLUMNS = [
    "length",
    "statements",
    "failed_statements",
    "segments",
    "dropped_segments",
    "failed_segments",
    "multiple_spk",
    "swedish",
    "segments_len",
    "dropped_len",
]


def iterate_sessions(
    sessions: List[str], recipe: Any, log: Logger, errors: List[str]
) -> pd.DataFrame:
    """Iterate through the given session list and gather statistics.

    Args:
        sessions (List[str]): sessions to postprocess
        recipe (Any): preprocessing recipe for text
        log (Logger): logger object
        errors (List[str]): descriptions of all encountered errors

    Returns:
        pd.DataFrame: statistics for reporting
    """
    with alive_bar(len(sessions)) as bar:
        statistics = pd.DataFrame(columns=STATS_COLUMNS)
        for session in sessions:
            log.info(f"Processing file {session} next.")
            statistics = postprocess_session(session, recipe, statistics, log, errors)
            bar()
        return statistics


def postprocess_session(
    session_path: str, recipe: Any, stats: pd.DataFrame, log: Logger, errors: List[str]
) -> pd.DataFrame:
    """Postprocess session and keep segments that are in Finnish and have only one speaker.

    Args:
        session_path (str): alignment CTM filepath
        recipe (Any): preprocessing recipe for text
        stats (pd.DataFrame): statistics for reporting
        log (Logger): logger object
        errors (List[str]): descriptions of all encountered errors

    Returns:
        pd.DataFrame: updated statistics for reporting
    """
    basepath = Path(session_path).resolve().parent
    if hit := re.search(r"session-(\d+)-(\d+)", session_path):
        num, year = hit.groups()
        session = f"{num}-{year}"
        json_file = f"corpus/{year}/session-{session}.json"
        try:
            with open(json_file, mode="r", encoding="utf-8", newline="") as infile:
                transcript = json.load(infile, object_hook=decode_transcript)
            ctm, segments, kalditext = load_kaldi_files(basepath, session)
            segments, kalditext = labeler.label_segments(
                transcript, ctm, segments, kalditext, recipe, errors
            )
            kept_segments = (segments.df.new_uttid != "") & (segments.df.lang == "fi")
            save_output(segments, kalditext, kept_segments)
            stats.loc[f"session-{session}"] = compose_stats(
                ctm.df, segments.df, segments.df[~kept_segments]
            )
            return stats
        except Exception as err:
            log.exception(f"Postprocessing failed in {session}. Caught error: {err}")
    else:
        errors.append(f"Session ID and year not in filename: {session_path}")
    return stats


def load_kaldi_files(
    basepath: Path, session: str
) -> Tuple[IO.KaldiCTMSegmented, IO.KaldiSegments, IO.KaldiText]:
    """Load Kaldi files needed for postprocessing.

    Args:
        basepath (Path): path to the folder with Kaldi files
        session (str): plenary session identifier

    Returns:
        Tuple[IO.KaldiCTMSegmented, IO.KaldiSegments, IO.KaldiText]: loaded files
    """
    session_path = f"{basepath}/session-{session}"
    kaldi_files = [IO.KaldiCTMSegmented, IO.KaldiSegments, IO.KaldiText]
    ctm, segments, kalditext = [file(session_path) for file in kaldi_files]
    ctm.df.attrs["session"] = session
    return ctm, segments, kalditext  # type: ignore


def save_output(segments: pd.DataFrame, kalditext: pd.DataFrame, kept_segments: pd.Series) -> None:
    """Save kept segments and dropped segments to separate files.

    Args:
        segments (pd.DataFrame): updated segments with speaker and language info
        kalditext (pd.DataFrame): transcripts corresponding to segments
        kept_segments (pd.Series): mask to separate kept and dropped segments
    """
    segments.save_df(segments.df[kept_segments])
    kalditext.save_df(kalditext.df[kept_segments])
    segments.save_df(
        segments.df[~kept_segments],
        ".dropped",
        ["uttid", "recordid", "start", "end", "mpid", "lang"],
    )
    kalditext.save_df(kalditext.df[~kept_segments], ".dropped", ["uttid", "lang", "mpid", "text"])


def compose_stats(
    df: pd.DataFrame, segments_df: pd.DataFrame, dropped_segments: pd.DataFrame
) -> Dict[str, Any]:
    """Compose statistics on postprocessing results for the session.

    Args:
        df (pd.DataFrame): alignment CTM
        segments_df (pd.DataFrame): segments file
        dropped_segments (pd.Series): masked segments file

    Returns:
        Dict[str, Any]: a collection of statistics for given session
    """
    return {
        "length": df.session_start.iloc[-1] + df.word_duration.iloc[-1],
        "statements": df.attrs["statements"],
        "failed_statements": df.attrs["failed"],
        "segments": len(segments_df),
        "dropped_segments": len(dropped_segments),
        "failed_segments": sum(dropped_segments.mpid == 0),
        "multiple_spk": sum(dropped_segments.mpid == -1),
        "swedish": sum(dropped_segments.lang.str.contains("sv")),
        "segments_len": (segments_df.end - segments_df.start).sum(),
        "dropped_len": (dropped_segments.end - dropped_segments.start).sum(),
    }


def report_statistics(log: Logger, stats: pd.DataFrame) -> None:
    """Write a summary of collected statistics to the log and save detailed stats to a file.

    Args:
        log (Logger): logger object
        stats (pd.DataFrame): collected statistics
    """
    csv_name = f"logs/{date.today()}-postprocess-statistics.csv"
    i, f, td = ("int64", "float64", "timedelta64[s]")

    stats.loc["total"] = stats.sum()
    stats["segments_p"] = 100 * stats.segments_len / stats.length
    stats["failed_p"] = 100 * stats.failed_statements / stats.statements
    stats["dropped_p"] = 100 * stats.dropped_segments / stats.segments
    stats["dropped_p_len"] = 100 * stats.dropped_len / stats.segments_len
    stats = stats.astype(
        {
            "statements": i,
            "failed_statements": i,
            "segments": i,
            "dropped_segments": i,
            "length": td,
            "segments_len": td,
            "dropped_len": td,
            "failed_p": f,
            "dropped_p": f,
        }
    )

    total = stats.loc["total"]
    log.info("*************************************************")
    log.info("****** Statistics of the speaker alignment ******")
    log.info("*************************************************")
    log.info(f"Total length of the sessions was {total.length}.")
    log.info(
        f"Kaldi segmentation resulted in {total.segments_len} of data, or {total.segments_p:.2f}% "
        "of the total length."
    )
    log.info(
        f"Out of the Kaldi segments, {total.segments_len - total.dropped_len} of audio was kept "
        f"after speaker alignment and {total.dropped_len} ({total.dropped_p_len:.2f}%) was dropped."
    )
    log.info(
        f"{total.failed_statements} out of {total.statements} statements ({total.failed_p:.2f}%) "
        "could not be aligned with speaker info."
    )
    log.info(
        f"Because of this, {total.failed_segments} segments had no speaker info. In addition, "
        f"{total.multiple_spk} segments had more than one speaker and {total.swedish} segments "
        f"contained Swedish."
    )
    log.info(
        f"In total, {total.dropped_segments} ({total.dropped_p:.2f}%) out of {total.segments} "
        "segments were dropped."
    )
    log.info(f"Full statistics are saved to {csv_name}.")
    stats.to_csv(csv_name, sep="\t", float_format="%.2f")
