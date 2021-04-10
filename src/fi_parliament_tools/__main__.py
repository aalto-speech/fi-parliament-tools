"""Command-line interface."""
import importlib
import logging
from datetime import date
from datetime import timedelta
from pathlib import Path
from typing import List
from typing import TextIO

import click

from fi_parliament_tools import downloads
from fi_parliament_tools import preprocessing


def setup_logger(logfile: str) -> logging.Logger:
    """Initialize a logger that outputs to stdout and given logfile name.

    Args:
        logfile (str): name of the logfile

    Returns:
        logging.Logger: the initialized logger
    """
    log = logging.getLogger(__name__)
    log.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    log_path = f"logs/{logfile}"
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    log.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)
    log.addHandler(stream_handler)

    log.info(f"Output is logged to {log_path}.")
    return log


def final_report(log: logging.Logger, errors: List[str]) -> None:
    """List all encountered errors at the end of log for easy browsing.

    Args:
        log (logging.Logger): logger object
        errors (List[str]): descriptions of all encountered errors
    """
    log.warning(f"Encountered {len(errors)} non-breaking error(s).")
    for error_text in errors:
        log.error(error_text)
    log.info("Finished successfully!")


@click.group()
@click.version_option()
def main() -> None:
    """Finnish Parliament data tools."""
    pass


@main.command()
@click.option(
    "-s",
    "--start-date",
    type=str,
    help="Search only for parliament sessions from this date onwards. Format: YYYY-MM-DD",
)
@click.option(
    "-e",
    "--end-date",
    type=str,
    help=(
        "Search only for parliament sessions until this date. If no end date or session are "
        "provided, the end date will default to one week before today. Format: YYYY-MM-DD"
    ),
)
@click.option(
    "--start-session",
    show_default=True,
    default="1/2015",
    help="Search only for parliament sessions from this session onwards. Format: id/year",
)
@click.option(
    "--end-session",
    type=str,
    help="Search only for parliament sessions until this session. Format: id/year",
)
@click.option("-v", "--video-only", is_flag=True, help="Download only videos.")
@click.option("-t", "--transcript-only", is_flag=True, help="Download only transcripts.")
@click.option(
    "-c",
    "--channel-id",
    show_default=True,
    default="5c80dfc1febec3003eeb1e29",
    help=(
        "The channel/category ID for the video API call. Default channel is for plenary sessions."
        " See README for more info."
    ),
)
def download(
    channel_id: str,
    start_date: str,
    end_date: str,
    start_session: str,
    end_session: str,
    video_only: bool,
    transcript_only: bool,
) -> None:
    """Download Finnish parliament videos and transcripts."""
    log = setup_logger(f"{date.today()}-download.log")
    errors: List[str] = []

    if not end_date and not end_session:
        week_before = date.today() - timedelta(weeks=1)
        end_date = week_before.isoformat()
        log.info(f"No end date or session given, will download sessions up to {end_date}.")

    args = {
        "channelId": channel_id,
        "startDate": start_date,
        "endDate": end_date,
        "startSession": start_session,
        "endSession": end_session,
    }

    try:
        if not video_only:
            df = downloads.query_transcripts(args)
            log.info(f"Found {len(df)} transcripts, proceed to download transcripts.")
            downloads.process_metadata_table(df, "json", downloads.download_transcript, log, errors)
        if not transcript_only:
            df = downloads.query_videos(args)
            log.info(f"Found {len(df)} videos, proceed to download videos and extract audio.")
            downloads.process_metadata_table(df, "mp4", downloads.download_video, log, errors)
    finally:
        final_report(log, errors)


@main.command()
@click.argument("transcript-list", type=click.File(encoding="utf-8"))
@click.argument("recipe-file", type=click.Path(exists=True))
def preprocess(transcript_list: TextIO, recipe_file: str) -> None:
    """Preprocessing parliament transcripts listed in TRANSCRIPT_LIST using RECIPE_FILE."""
    log = setup_logger(f"{date.today()}-preprocess.log")
    errors: List[str] = []

    try:
        transcripts = transcript_list.read().split()
        spec = importlib.util.spec_from_file_location("recipe", recipe_file)
        recipe = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(recipe)  # type: ignore
        log.info(f"Found {len(transcripts)} transcripts in file list, proceed to preprocessing.")
        preprocessing.apply_recipe(recipe, transcripts, log, errors)
    finally:
        final_report(log, errors)


@main.command()
@click.argument("segments-list", type=click.File(encoding="utf-8"))
@click.argument("recipe-file", type=click.Path(exists=True))
def postprocess(segments_list: TextIO, recipe_file: str) -> None:
    """Assign speakers to segmentation results listed in SEGMENTS_LIST.

    RECIPE_FILE is needed for preprocessing the original transcript to the aligned text. Use the
    same RECIPE_FILE as with preprocess command.
    """  # noqa: DAR101, ignore missing argument docs
    log = setup_logger(f"{date.today()}-postprocess.log")
    errors: List[str] = []

    try:
        pass
    finally:
        final_report(log, errors)


if __name__ == "__main__":
    main(prog_name="fi-parliament-tools")  # pragma: no cover
