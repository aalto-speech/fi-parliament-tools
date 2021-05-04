"""Command line client logic for postprocessing Finnish parliament data."""
import re
from datetime import date
from logging import Logger
from pathlib import Path
from typing import Any
from typing import List

import pandas as pd
from alive_progress import alive_bar

from fi_parliament_tools.speakerAligner import match

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


def process_sessions(
    sessions: List[str], recipe: Any, log: Logger, errors: List[str]
) -> pd.DataFrame:
    """Postprocess the given sessions one by one and visualize progress.

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
            statistics = match_session(session, recipe, statistics, log, errors)
            bar()
        return statistics


def match_session(
    session_path: str, recipe: Any, stats: pd.DataFrame, log: Logger, errors: List[str]
) -> pd.DataFrame:
    """Find original JSON transcript and match the statements in it to the alignment CTM.

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
            return match.rewrite_segments_and_text(
                basepath, session, json_file, recipe, stats, errors
            )
        except Exception as err:
            log.exception(f"Postprocessing failed in {session}. Caught error: {err}")
    else:
        errors.append(f"Session ID and year not in filename: {session_path}")
    return stats


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
