#!/usr/bin/env python3
# coding=utf-8
"""Helper functions for downloading plenary session videos.

The current video API is documented at `https://verkkolahetys.eduskunta.fi/api-documentation/`.
"""
import re
from typing import Dict


def form_date_parameter(date: str, name: str) -> str:
    """Form the date parameter for the API query after checking whether given date is valid.

    Args:
        date (str): date in format YYYY-MM-DD
        name (str): either 'startDate' or 'endDate', used to differentiate API query parameters

    Raises:
        ValueError: raised if the given date is not valid

    Returns:
        str: the name and and date formatted as a query parameter
    """
    date_regexp = (
        r"^(\d{4}-((0[13578]|1[02])-(0[1-9]|[12][0-9]|3[01])|(0[469]|11)-"
        r"(0[1-9]|[12][0-9]|30)|02-(0[1-9]|1\d|2[0-8]))|(\d{2}(0[48]|[2468][048]|[13579][26])|"
        r"([02468][048]|[1359][26])00)-02-29)"
    )
    match = re.match(date_regexp, date)
    if match is None:
        raise ValueError("{} {} is an invalid date.".format(name, date))
    return f"{name}={date}&"


def form_event_query(args: Dict[str, str]) -> str:
    """Form a query url to the Parliament video API from command line arguments.

    Args:
        args (argparse.Namespace): optional start and end date limits for the query

    Returns:
        str: a URL query to the video API
    """
    if (start_date := args["startDate"]) :
        start_date = form_date_parameter(start_date, "startDate")
    if (end_date := args["endDate"]) :
        end_date = form_date_parameter(end_date, "endDate")

    return (
        "https://eduskunta.videosync.fi/api/v1/categories/"
        f"{args['channelId']}?page=1&{start_date}{end_date}sort=-publishingDate&include=events"
    )
