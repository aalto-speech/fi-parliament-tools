#!/usr/bin/env python
# coding=utf-8
"""Configuration file for pytest.

Initialize different fixtures for automatically loading test transcripts and creating objects for
testing. Keeping the test data for full transcript (subsections) in csv files helps keep the test
files clean and readable. Other long strings, that do not need the hook for automatic generation,
are defined separately in `data/long_strings.py`.
"""
import json
from typing import Any
from typing import Dict
from typing import Tuple
from typing import Union

import pytest
from _pytest.fixtures import SubRequest
from lxml import etree

from fi_parliament_tools.transcriptParser.data_structures import EmbeddedStatement
from fi_parliament_tools.transcriptParser.data_structures import Statement
from fi_parliament_tools.transcriptParser.documents import Session
from fi_parliament_tools.transcriptParser.query import Query
from fi_parliament_tools.transcriptParser.query import SessionQuery
from fi_parliament_tools.transcriptParser.query import StatementQuery
from fi_parliament_tools.transcriptParser.query import VaskiQuery

pytest_plugins = ["tests.data.long_statement_strings", "tests.data.transcript_query"]


@pytest.fixture
def json_test_data(request: SubRequest) -> Any:
    """Read test input from a csv file (skip header). Each line corresponds to a speaker statement.

    Args:
        request: a FixtureRequest which contains the CSV filename

    Yields:
        list: lines of the csv file
    """
    input_json = open(request.param, "r", newline="")
    yield json.load(input_json)
    input_json.close()


@pytest.fixture(scope="module")
def session(request: SubRequest) -> Session:
    """Initialize and return a session object for given id and year."""
    number: int
    year: int
    number, year = request.param
    xml = etree.parse(f"tests/data/xmls/session-{number:03}-{year}.xml")
    return Session(number, year, xml)


@pytest.fixture(scope="module")
def embedded_statement(request: SubRequest) -> Tuple[EmbeddedStatement, Dict[str, str]]:
    """Initialize and return an embedded statement object for given data, return also the data."""
    return (EmbeddedStatement(*request.param.values()), request.param)


@pytest.fixture(scope="module")
def speaker_statement(
    request: SubRequest,
) -> Tuple[Statement, Dict[str, Union[str, int]]]:
    """Initialize and return a speaker statement object for given data, return also the data."""
    return (Statement(*request.param.values()), request.param)


@pytest.fixture(scope="module")
def query() -> Query:
    """Initialize a dummy Query object."""
    return Query("DummyTable")


@pytest.fixture(scope="module")
def vaski_query() -> VaskiQuery:
    """Initialize a dummy VaskiQuery object."""
    return VaskiQuery("PTK 0/0000 vp")


@pytest.fixture(scope="module")
def session_query() -> SessionQuery:
    """Initialize a dummy SessionQuery object."""
    return SessionQuery("0000/00")


@pytest.fixture(scope="module")
def statement_query() -> StatementQuery:
    """Initialize a dummy StatementQuery object."""
    return StatementQuery("0000/00")
