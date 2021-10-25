"""Build a table with basic info on members of parliament."""
from logging import Logger
from pathlib import Path
from typing import List

import pandas as pd
from lxml import etree

from fi_parliament_tools import MPID_FILTER
from fi_parliament_tools.parsing.documents import MPInfo
from fi_parliament_tools.parsing.query import MPQuery


def build_table(get_english: bool, update_old: bool, log: Logger) -> None:
    """Build a new or update an existing table containing MP information.

    Args:
        get_english (bool): parse English XMLs if available
        update_old (bool): update old, existing table with new values
        log (Logger): logger object
    """
    log.info("Fetch all MP data.")
    data = get_data()
    log.info("Parse fetched data.")
    new_table = parse_mp_data(data, get_english)
    if Path("generated/mp-table.csv").exists():
        log.info("Existing table found at 'generated/mp-table.csv'.")
        old_table = pd.read_csv("generated/mp-table.csv", sep="|", index_col="mp_id")
        new_table = add_new_mps(old_table, new_table, log, update_old=update_old)
    log.info("Saving resulting table to 'generated/mp-table.csv'.")
    new_table.to_csv("generated/mp-table.csv", sep="|")


def get_data() -> List[List[str]]:
    """Get all entries in the parliament MP database and filter it.

    Filtering will remove MPs that will not appear in the available transcripts or Finnish
    Parliament ASR datasets.

    Returns:
        List[List[str]]: filtered data
    """
    data, _ = MPQuery().get_full_table()
    filtered = [item for item in data if item[0] not in MPID_FILTER]
    return filtered


def parse_mp_data(data: List[List[str]], get_english: bool = False) -> pd.DataFrame:
    """Parse MP data from XMLs to a pandas DataFrame table.

    The code will parse either Finnish or English XML. English translation is usually available only
    for the current MPs. Thus, using English will result in a table with both English and Finnish
    entries.

    Args:
        data (List[List[str]]): MPQuery results
        get_english (bool): parse English XML if available, defaults to False.

    Returns:
        pd.DataFrame: parsed MP data
    """
    mps = []
    for item in data:
        mpid, lastname, firstname = item[0:3]
        if get_english and not contains_empty_tag("Ammatti", item[8]):
            xml = etree.fromstring(item[8])
        else:
            xml = etree.fromstring(item[7])
        mp = MPInfo(xml).parse(int(mpid), firstname.strip(), lastname.strip())
        mps.append(mp)
    return pd.DataFrame(mps).set_index("mp_id")


def contains_empty_tag(tag: str, xml: str) -> bool:
    """Check whether the XML contains an empty tag.

    Args:
        tag (str): tag name
        xml (str): xml to check from

    Returns:
        bool: true if XML contains given empty tag, false otherwise
    """
    return f"<{tag}/>" in xml


def add_new_mps(
    old_table: pd.DataFrame, new_table: pd.DataFrame, log: Logger, update_old: bool = False
) -> pd.DataFrame:
    """Add new MP entries from a freshly built table to an existing table.

    Optionally, updates old MP entries with new information.

    Args:
        old_table (pd.DataFrame): existing table
        new_table (pd.DataFrame): freshly built table
        log (Logger): logger object
        update_old (bool): update values in old table, defaults to False

    Returns:
        pd.DataFrame: existing table updated with new entries
    """
    log.info("Add new MPs to existing table.")
    combined_table = old_table.combine_first(new_table)
    if update_old:
        log.info("Update old entries with new data.")
        log.warning("Updating old entries may cause data loss!")
        combined_table.update(new_table)
    return combined_table
