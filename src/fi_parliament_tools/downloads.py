"""Command line client for downloading Finnish parliament data."""
import pathlib
import shutil
import subprocess
from logging import Logger
from pathlib import Path
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional

import pandas as pd
import requests
import toml
from alive_progress import alive_bar
from lxml import etree

from fi_parliament_tools import video_query
from fi_parliament_tools.transcriptParser.documents import Session
from fi_parliament_tools.transcriptParser.query import Query
from fi_parliament_tools.transcriptParser.query import VaskiQuery

CONFIG = toml.load("src/fi_parliament_tools/config.toml")
VIDEO_API = "https://eduskunta.videosync.fi/api/v1/events"


def form_path(num: int, year: int, suffix: str, errors: List[str]) -> Optional[pathlib.Path]:
    """Create and validate path if file by the same name does not exist.

    Args:
        num (int): running number of the session, used to form filename
        year (int): year of the session, used to form filename
        suffix (str): file extension
        errors (list): a list of error strings for reporting

    Returns:
        pathlib.Path: path to a new file or None if duplicate exists already
    """
    p = Path(f"{CONFIG['paths']['corpus_dir']}/{year}/session-{num:03}-{year}.{suffix}")
    if p.exists():
        errors.append(f"File {p} exists, will not overwrite.")
        return None
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def filter_metadata_table(df: pd.DataFrame, args: Dict[str, str]) -> pd.DataFrame:
    """Filter metadata table with given constraints.

    Args:
        df (pandas.DataFrame): a metadata table to filter
        args (Dict[str,str]): parsed command line args that contain the constraints

    Returns:
        pandas.DataFrame: a filtered metadata table
    """
    if args["startDate"]:
        df = df[(df["date"] >= args["startDate"])]
    if args["endDate"]:
        df = df[(df["date"] <= args["endDate"])]
    if args["startSession"]:
        num, year = map(int, args["startSession"].split("/"))
        df = df[(df["year"] >= year) & ~((df["year"] == year) & (df["num"] < num))]
    if args["endSession"]:
        num, year = map(int, args["endSession"].split("/"))
        df = df[(df["year"] <= year) & ~((df["year"] == year) & (df["num"] > num))]
    return df


def query_transcripts(args: Dict[str, str]) -> pd.DataFrame:
    """Query the parliament open data API for plenary transcript metadata and filter it.

    Args:
        args (Dict[str,str]): command line arguments from the client

    Returns:
        pandas.DataFrame: a metadata table
    """
    data, columns = Query("SaliDBIstunto").get_full_table()
    df = pd.DataFrame([row[:10] for row in data], columns=columns[:10])
    cols = {
        "IstuntoNumero": "num",
        "IstuntoVPVuosi": "year",
        "IstuntoIlmoitettuAlkuaika": "date",
    }
    df.rename(columns=cols, inplace=True)
    df[["num", "year"]] = df[["num", "year"]].apply(pd.to_numeric)
    return filter_metadata_table(df, args)


def query_videos(args: Dict[str, str]) -> pd.DataFrame:
    """Query video metadata from the video API and filter it.

    The video table may contain events that are not plenary sessions ('taysistunto'). These can be
    left out based on the urlName (format: 'taysistunto-number-year').

    Args:
        args (list): command line args to use in query

    Returns:
        pandas.DataFrame: a metadata table
    """
    query_url = video_query.form_event_query(args)
    with requests.get(query_url) as response:
        video_meta = response.json()
    df = pd.DataFrame(video_meta["events"], columns=["_id", "urlName", "publishingDate"])
    df.set_index("_id", inplace=True)
    df.rename(columns={"publishingDate": "date"}, inplace=True)
    df = df[df.urlName.str.contains("taysistunto")]
    name_components = df.urlName.str.split("-", expand=True)
    df[["num", "year"]] = name_components[[1, 2]].apply(pd.to_numeric)
    return filter_metadata_table(df, args)


def process_metadata_table(
    df: pd.DataFrame,
    extension: str,
    processing_func: Callable[..., None],
    log: Logger,
    errors: List[str],
) -> None:
    """Iterate through metadata table and apply given download function.

    Progress bar is included to show progress since the table might have hundreds of entries.

    Args:
        df (pandas.DataFrame): metadata of files to download
        extension (str): file extension for the file resulting from processing
        processing_func (func): processing function applied to the table entries
        log (Logger): for logging output
        errors (list): a list of error strings for reporting
    """
    with alive_bar(len(df)) as bar:
        for index, num, year in zip(df.index, df.num, df.year):
            if (path := form_path(num, year, extension, errors)) is not None:
                processing_func(path, log, errors, **{"index": index, "num": num, "year": year})
            bar()


def download_transcript(path: pathlib.Path, log: Logger, errors: List[str], **kwargs: Any) -> None:
    """Try downloading and parsing a transcript from the parliament open data API.

    Saves both the original XML transcript and a parsed JSON.

    Args:
        path (pathlib.Path): path to save the parsed transcript to
        log (Logger): for logging output
        errors (list): a list of error strings for reporting
        kwargs (dict): expected to contain 'num' and 'year', which identify a plenary session
    """
    num, year = kwargs["num"], kwargs["year"]
    log.debug(f"Parsing transcript {num}/{year} next.")
    if xml_str := VaskiQuery(f"PTK {num}/{year} vp").get_xml():
        xml = etree.fromstring(xml_str)
        etree.ElementTree(xml).write(
            str(path.with_suffix(".xml")), encoding="utf-8", pretty_print=True
        )
        Session(num, year, xml).parse_to_json(path)
    else:
        errors.append(f"XML for transcript {num}/{year} is not found.")


def download_video(path: pathlib.Path, log: Logger, errors: List[str], **kwargs: Any) -> None:
    """Try downloading a single video from the video API and extracting the audio stream as wav.

    Args:
        path (pathlib.Path): path to save the video file to
        log (Logger): for logging output
        errors (list): a list of error strings for reporting
        kwargs (dict): expected to contain 'index', an unique identifier for the video
    """
    url = f"{VIDEO_API}/{kwargs['index']}/video/download"
    log.debug(f"Will attempt to download {path.name} from {url}.")
    try:
        with requests.get(url, stream=True) as r, open(path, "wb") as f:
            shutil.copyfileobj(r.raw, f)
    except shutil.Error:
        errors.append(f"Video download failed for {path.name} from {url}.")
    extract_wav(path, log, errors)


def extract_wav(path: pathlib.Path, log: Logger, errors: List[str]) -> None:
    """Try extracting the audio stream from the video file in path using ffmpeg.

    Args:
        path (pathlib.Path): path to the video file
        log (Logger): for logging output
        errors (list): a list of error strings for reporting
    """
    log.debug(f"Will attempt to extract audio from the video {path.name}.")
    try:
        audio = str(path.with_suffix(".wav"))
        args = ["ffmpeg", "-i", str(path), "-f", "wav", "-ar", "16000", "-ac", "1", audio]
        subprocess.run(args, capture_output=True, text=True)
    except ValueError:
        errors.append(f"Wav extraction failed for video {path.name}.")
