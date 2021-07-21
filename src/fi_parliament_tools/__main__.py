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
from fi_parliament_tools import mptable
from fi_parliament_tools.postprocessing import PostProcessingPipeline
from fi_parliament_tools.preprocessing import PreprocessingPipeline


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
    pipeline = downloads.DownloadPipeline(log)

    try:
        if not video_only:
            df = downloads.query_transcripts(args)
            log.info(f"Found {len(df)} transcripts, proceed to download transcripts.")
            pipeline.run(df, "json", pipeline.download_transcript)
        if not transcript_only:
            df = downloads.query_videos(args)
            log.info(f"Found {len(df)} videos, proceed to download videos and extract audio.")
            pipeline.run(df, "mp4", pipeline.download_video)
    finally:
        final_report(log, pipeline.errors)


@main.command()
@click.argument("transcript-list", type=click.File(encoding="utf-8"))
@click.argument("lid-model", type=click.Path(exists=True))
@click.argument("mptable-file", type=click.Path(exists=True))
@click.argument("recipe-file", type=click.Path(exists=True))
def preprocess(
    transcript_list: TextIO, lid_model: str, mptable_file: str, recipe_file: str
) -> None:
    """Preprocess parliament transcripts in TRANSCRIPT_LIST using given file arguments.

    LID_MODEL predicts language (fi/sv/both) for those statements that do not have a language label
    in the XMLs.

    MPTABLE_FILE is used to add MP ids to (chairman) statements without them. Table can be created
    or updated with the 'mptable' command.

    RECIPE_FILE is used to preprocess text for speech recognition.
    """  # noqa: DAR101, DAR401, ignore missing arg documentation
    log = setup_logger(f"{date.today()}-preprocess.log")

    if spec := importlib.util.spec_from_file_location("recipe", recipe_file):
        recipe = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(recipe)  # type: ignore
        transcripts = transcript_list.read().split()
        pipeline = PreprocessingPipeline(log, transcripts, lid_model, mptable_file, recipe)
        try:
            log.info(f"Found {len(transcripts)} transcripts, begin preprocessing.")
            pipeline.run()
        finally:
            final_report(log, pipeline.errors)
    else:
        raise click.ClickException(f"Failed to import recipe '{recipe_file}', is it a python file?")


@main.command()
@click.argument("ctms-list", type=click.File(encoding="utf-8"))
@click.argument("recipe-file", type=click.Path(exists=True))
def postprocess(ctms_list: TextIO, recipe_file: str) -> None:
    """Postprocess segmentation results given a list of segmented CTMs in CTMS_LIST.

    RECIPE_FILE is needed for preprocessing the original transcript to the aligned text. Use the
    same RECIPE_FILE as with preprocess command.
    """  # noqa: DAR101, DAR401, ignore missing arg documentation
    log = setup_logger(f"{date.today()}-postprocess.log")

    if spec := importlib.util.spec_from_file_location("recipe", recipe_file):
        recipe = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(recipe)  # type: ignore
        ctms = ctms_list.read().split()
        pipeline = PostProcessingPipeline(log, ctms, recipe)
        try:
            log.info(f"Found {len(pipeline.inputs)} sessions in file list, begin postprocessing.")
            pipeline.run()
        finally:
            final_report(log, pipeline.errors)
            if not pipeline.stats.empty:
                pipeline.report_statistics()
    else:
        raise click.ClickException(f"Failed to import recipe '{recipe_file}', is it a python file?")


@main.command()
@click.option(
    "-e",
    "--get-english",
    is_flag=True,
    help="Get English data if available. If English data is not available, Finnish data is used instead.",
)
@click.option(
    "-u", "--update-old", is_flag=True, help="Update outdated values in an existing MP table."
)
def build_mptable(get_english: bool, update_old: bool) -> None:
    """Build an MP data table or update an existing one with new MPs.

    With --get-english handle, English data is used if available. English data is usually available
    only for current MPs. Using the handle will result in table with some MP entries in English and
    the rest in Finnish.

    If a previous table exists at 'generated/mp-table.csv', running this command will add new MP
    entries to it. Using --update-old handle will cause old MP entries to get updated as well. Be
    warned however, this may cause data loss (e.g. party or home city may change)!
    """  # noqa: DAR101, DAR401, ignore missing arg documentation
    log = setup_logger(f"{date.today()}-mptable.log")

    Path("generated").mkdir(exist_ok=True)

    try:
        log.info("Begin building MP data table.")
        mptable.build_table(get_english, update_old, log)
    finally:
        final_report(log, [])


if __name__ == "__main__":
    main(prog_name="fi-parliament-tools")  # pragma: no cover
