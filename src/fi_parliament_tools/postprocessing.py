"""Command line client logic for postprocessing Finnish parliament data."""
import json
import re
from datetime import date
from logging import Logger
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

import pandas as pd
from alive_progress import alive_bar

from fi_parliament_tools.pipeline import Pipeline
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


class PostProcessingPipeline(Pipeline):
    """Postprocess Kaldi segmentation results."""

    def __init__(self, log: Logger, ctm_paths: List[str], recipe: Any) -> None:
        """Initialize common parameters and postprocessing specific parameters.

        Recipe should be the same as the one used in the preprocessing pipeline.

        Args:
            log (Logger): logger object
            ctm_paths (List[str]): segmentation CTMs to postprocess
            recipe (Any): a preprocessing recipe file loaded as a module
        """
        super().__init__(log)
        self.inputs = list(filter(None, [self.form_input_tuple(path) for path in ctm_paths]))
        self.recipe = recipe
        self.stats = pd.DataFrame(columns=STATS_COLUMNS)

    def form_input_tuple(self, ctm_path: str) -> Optional[Tuple[Path, Path, str]]:
        """Form input tuple (ctm, json, session) from the given CTM path.

        Args:
            ctm_path (str): path to a ctm_edits.segmented file

        Returns:
            Tuple[Path, Path, str]: ctm, json transcript and session id (num-year)
        """
        if hit := re.search(r"session-(\d+)-(\d+)", ctm_path):
            num, year = hit.groups()
            json_file = Path(f"corpus/{year}/session-{num}-{year}.json").resolve()
            return (Path(ctm_path).resolve(), json_file, f"{num}-{year}")
        self.errors.append(f"Session number and year not in filename: {ctm_path}. Skipped.")
        return None

    def run(self) -> None:
        """Run postprocessing pipeline over the inputs."""
        with alive_bar(len(self.inputs)) as bar:
            for (ctm, json_file, session) in self.inputs:
                self.log.info(f"Processing {ctm} next.")
                self.postprocess_session(ctm, json_file, session)
                bar()

    def postprocess_session(self, path: Path, json_file: Path, session: str) -> None:
        """Postprocess session and keep segments that are in Finnish and have only one speaker.

        Args:
            path (Path): path to alignment CTM (.ctm_edits.segmented)
            json_file (Path): path to transcript JSON
            session (str): session identifier (format: num-year)
        """
        try:
            with open(json_file, mode="r", encoding="utf-8", newline="") as infile:
                transcript = json.load(infile, object_hook=decode_transcript)
            ctm, segments, kalditext = self.load_kaldi_files(path.parent, session)
            segments, kalditext = labeler.label_segments(
                transcript, ctm, segments, kalditext, self.recipe, self.errors
            )
            kept_segments = (segments.df.new_uttid != "") & (segments.df.lang == "fi")
            self.save_output(segments, kalditext, kept_segments)
            self.stats.loc[f"session-{session}"] = self.compose_stats(
                ctm.df, segments.df, segments.df[~kept_segments]
            )
        except Exception as err:
            self.log.exception(f"Postprocessing failed in {session}. Caught error: {err}")

    def load_kaldi_files(
        self, basepath: Path, session: str
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

    def save_output(
        self, segments: IO.KaldiSegments, kalditext: IO.KaldiText, kept_segments: pd.Series
    ) -> None:
        """Save kept segments and dropped segments to separate files.

        Args:
            segments (IO.KaldiSegments): updated segments with speaker and language info
            kalditext (IO.KaldiText): transcripts corresponding to segments
            kept_segments (pd.Series): mask to separate kept and dropped segments
        """
        segments.save_df(segments.df[kept_segments])
        kalditext.save_df(kalditext.df[kept_segments])
        segments.save_df(
            segments.df[~kept_segments],
            ".dropped",
            ["uttid", "recordid", "start", "end", "mpid", "lang"],
        )
        kalditext.save_df(
            kalditext.df[~kept_segments], ".dropped", ["uttid", "lang", "mpid", "text"]
        )

    def compose_stats(
        self, df: pd.DataFrame, segments_df: pd.DataFrame, dropped_segments: pd.DataFrame
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

    def report_statistics(self) -> None:
        """Write a summary of collected statistics to the log and save detailed stats to a file."""
        csv_name = f"logs/{date.today()}-postprocess-statistics.csv"
        i, f, td = ("int64", "float64", "timedelta64[s]")

        self.stats.loc["total"] = self.stats.sum()
        self.stats["segments_p"] = 100 * self.stats.segments_len / self.stats.length
        self.stats["failed_p"] = 100 * self.stats.failed_statements / self.stats.statements
        self.stats["dropped_p"] = 100 * self.stats.dropped_segments / self.stats.segments
        self.stats["dropped_p_len"] = 100 * self.stats.dropped_len / self.stats.segments_len
        self.stats = self.stats.astype(
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

        total = self.stats.loc["total"]
        self.log.info("*************************************************")
        self.log.info("****** Statistics of the speaker alignment ******")
        self.log.info("*************************************************")
        self.log.info(f"Total length of the sessions was {total.length}.")
        self.log.info(
            f"Kaldi segmentation resulted in {total.segments_len} of data, or {total.segments_p:.2f}% "
            "of the total length."
        )
        self.log.info(
            f"Out of the Kaldi segments, {total.segments_len - total.dropped_len} of audio was kept "
            f"after speaker alignment and {total.dropped_len} ({total.dropped_p_len:.2f}%) was dropped."
        )
        self.log.info(
            f"{total.failed_statements} out of {total.statements} statements ({total.failed_p:.2f}%) "
            "could not be aligned with speaker info."
        )
        self.log.info(
            f"Because of this, {total.failed_segments} segments had no speaker info. In addition, "
            f"{total.multiple_spk} segments had more than one speaker and {total.swedish} segments "
            f"contained Swedish."
        )
        self.log.info(
            f"In total, {total.dropped_segments} ({total.dropped_p:.2f}%) out of {total.segments} "
            "segments were dropped."
        )
        self.log.info(f"Full statistics are saved to {csv_name}.")
        self.stats.to_csv(csv_name, sep="\t", float_format="%.2f")
