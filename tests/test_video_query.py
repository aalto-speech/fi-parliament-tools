#!/usr/bin/env python3
# coding=utf-8
"""Test video query helper functions."""
from typing import Dict

import pytest

import fi_parliament_tools.video_query as vq


@pytest.mark.parametrize(
    "date, name, true_query",
    [
        ("1999-12-31", "startDate", "startDate=1999-12-31&"),
        ("2013-08-08", "endDate", "endDate=2013-08-08&"),
        ("2020-02-29", "endDate", "endDate=2020-02-29&"),
        ("2016-01-01", "startDate", "startDate=2016-01-01&"),
    ],
)
def test_form_date_query(date: str, name: str, true_query: str) -> None:
    """Test that date query parameters are correctly formatted."""
    query = vq.form_date_parameter(date, name)
    assert query == true_query


@pytest.mark.parametrize(
    "date, name",
    [
        ("2000-46-100", "startDate"),
        ("2017-02-29", "endDate"),
        ("2014-102-1", "endDate"),
        ("2020-09-31", "startDate"),
    ],
)
def test_invalid_date_query(date: str, name: str) -> None:
    """Test that invalid date query parameters are caught."""
    with pytest.raises(ValueError):
        vq.form_date_parameter(date, name)


@pytest.mark.parametrize(
    "cmd_line_args, true_query",
    [
        (
            {
                "channelId": "5c80dfc1febec3003eeb1e29",
                "startDate": "2009-01-01",
                "endDate": "2009-12-31",
                "startSession": "",
                "endSession": "",
            },
            (
                "https://eduskunta.videosync.fi/api/v1/categories/5c80dfc1febec3003eeb1e29?page=1&"
                "startDate=2009-01-01&endDate=2009-12-31&sort=-publishingDate&include=events"
            ),
        ),
        (
            {
                "channelId": "5c80dfc1febec3003eeb1e29",
                "startDate": "",
                "endDate": "2015-10-15",
                "startSession": "",
                "endSession": "",
            },
            (
                "https://eduskunta.videosync.fi/api/v1/categories/5c80dfc1febec3003eeb1e29?page=1&"
                "endDate=2015-10-15&sort=-publishingDate&include=events"
            ),
        ),
        (
            {
                "channelId": "5c80dfc1febec3003eeb1e29",
                "startDate": "2018-02-06",
                "endDate": "",
                "startSession": "",
                "endSession": "",
            },
            (
                "https://eduskunta.videosync.fi/api/v1/categories/5c80dfc1febec3003eeb1e29?page=1&"
                "startDate=2018-02-06&sort=-publishingDate&include=events"
            ),
        ),
    ],
)
def test_form_event_query(cmd_line_args: Dict[str, str], true_query: str) -> None:
    """Test that event queries are correctly formatted."""
    assert vq.form_event_query(cmd_line_args) == true_query
