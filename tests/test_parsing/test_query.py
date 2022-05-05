"""Test queries to the parliament open data API."""
from typing import Callable
from unittest.mock import MagicMock

import pytest
from pytest_mock.plugin import MockerFixture  # type: ignore

from fi_parliament_tools.parsing.query import Query
from fi_parliament_tools.parsing.query import SessionQuery
from fi_parliament_tools.parsing.query import StatementQuery
from fi_parliament_tools.parsing.query import VaskiQuery


@pytest.fixture
def mock_requests_get_none(mocker: MockerFixture) -> MagicMock:
    """Mock a return of an empty json from the parliament open data API."""
    mock: MagicMock = mocker.patch("requests.get")
    mock.return_value.__enter__.return_value.json.return_value = {
        "columnNames": ["column1", "column2"],
        "rowData": [],
        "hasMore": False,
    }
    return mock


@pytest.fixture
def mock_requests_get_multiple_rows(mocker: MockerFixture) -> MagicMock:
    """Mock a return of json with two data rows in 'rowData' from the parliament open data API."""
    mock: MagicMock = mocker.patch("requests.get")
    mock.return_value.__enter__.return_value.json.return_value = {
        "columnNames": ["column1", "column2"],
        "rowData": [["Lorem", "ipsum"], ["dolor", "sit", "amet"]],
        "hasMore": False,
    }
    return mock


@pytest.fixture
def mock_requests_get_json_once(mocker: MockerFixture) -> MagicMock:
    """Mock a return of a json with one page of results from the parliament open data API."""
    mock: MagicMock = mocker.patch("requests.get")
    mock.return_value.__enter__.return_value.json.return_value = {
        "columnNames": ["column1", "column2"],
        "rowData": [["Lorem", "ipsum", "", "", "", "", "", "", "", "", "2019-06-14 10:00:05"]],
        "hasMore": False,
    }
    return mock


@pytest.fixture
def mock_requests_get_json_twice(mocker: MockerFixture) -> MagicMock:
    """Mock two pages of results returned from the parliament open data API."""
    mock: MagicMock = mocker.patch("requests.get")
    mock.return_value.__enter__.return_value.json.side_effect = [
        {
            "columnNames": ["column1", "column2"],
            "rowData": [["Lorem ipsum", "dolor sit amet"]],
            "hasMore": True,
        },
        {
            "columnNames": ["column1", "column2"],
            "rowData": [["eripuit principes intellegam", "eos id"]],
            "hasMore": False,
        },
    ]
    return mock


@pytest.fixture
def read_xml_string() -> Callable[[int, int, str], str]:
    """Read an XML file to a string. Subsection string needs to include a prepending '-'."""

    def _read_xml_string(number: int, year: int, subsection: str) -> str:
        xmlfile = f"tests/data/xmls/session-{number:03}-{year}{subsection}.xml"
        with open(xmlfile, encoding="utf-8") as infile:
            lines = infile.readlines()
            return " ".join([line.strip() for line in lines])

    return _read_xml_string


@pytest.fixture
def mock_requests_get_json_for_xml_combine(
    read_xml_string: Callable[[int, int, str], str], mocker: MockerFixture
) -> MagicMock:
    """Mock the results of XML combine queries to the parliament open data API."""
    mock: MagicMock = mocker.patch("requests.get")
    mock.return_value.__enter__.return_value.json.side_effect = [
        {
            "columnNames": ["column1", "column2"],
            "rowData": [["", read_xml_string(61, 2020, "-tos")]],
            "hasMore": False,
        },
        {
            "columnNames": ["column1", "column2"],
            "rowData": [["", read_xml_string(61, 2020, "-3")]],
            "hasMore": False,
        },
        {
            "columnNames": ["column1", "column2"],
            "rowData": [["", read_xml_string(61, 2020, "-4")]],
            "hasMore": False,
        },
        {
            "columnNames": ["column1", "column2"],
            "rowData": [["", read_xml_string(61, 2020, "-5")]],
            "hasMore": False,
        },
        {
            "columnNames": ["column1", "column2"],
            "rowData": [],
            "hasMore": False,
        },
    ]
    return mock


@pytest.fixture
def mock_requests_get_json_with_statement_timestamp(mocker: MockerFixture) -> MagicMock:
    """Mock two pages of results returned from the parliament open data API."""
    mock: MagicMock = mocker.patch("requests.get")
    mock.return_value.__enter__.return_value.json.side_effect = [
        {
            "columnNames": ["column1", "column2"],
            "rowData": [
                [
                    "",
                    "",
                    "",
                    "",
                    "2018-06-14 13:01:33",
                    "",
                    "486",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "1",
                    "1",
                ]
            ],
            "hasMore": True,
        },
        {
            "columnNames": ["column1", "column2"],
            "rowData": [
                [
                    "",
                    "",
                    "",
                    "",
                    "2018-06-14 13:04:08",
                    "",
                    "486",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "2",
                    "1",
                ]
            ],
            "hasMore": False,
        },
    ]
    return mock


def test_get_full_table_none(query: Query, mock_requests_get_none: MagicMock) -> None:
    """Test we get empty lists when the parliament API returns an empty json."""
    data, columns = query.get_full_table()
    assert data == []
    assert columns == []


def test_get_full_table_one_page(query: Query, mock_requests_get_json_once: MagicMock) -> None:
    """Test we get the data and column names from the returned JSON."""
    data, columns = query.get_full_table()
    assert data == [["Lorem", "ipsum", "", "", "", "", "", "", "", "", "2019-06-14 10:00:05"]]
    assert columns == ["column1", "column2"]


def test_get_full_table_two_pages(query: Query, mock_requests_get_json_twice: MagicMock) -> None:
    """Test we get the combined data when there are more than one page of results in the API."""
    data, columns = query.get_full_table()
    assert data == [["Lorem ipsum", "dolor sit amet"], ["eripuit principes intellegam", "eos id"]]
    assert columns == ["column1", "column2"]


def test_get_session_start_time_empty(
    session_query: SessionQuery, mock_requests_get_none: MagicMock
) -> None:
    """Test we get an empty string when the parliament API returns an empty json."""
    assert session_query.get_session_start_time() == ""


def test_get_session_start_time(
    session_query: SessionQuery, mock_requests_get_json_once: MagicMock
) -> None:
    """Test we get session start time from the data."""
    assert session_query.get_session_start_time() == "2019-06-14 10:00:05"


def test_search_interpellation_speaker_turn_empty(
    statement_query: StatementQuery, mock_requests_get_none: MagicMock
) -> None:
    """Test we get an empty string when the parliament API returns an empty json."""
    assert statement_query.search_interpellation_speaker_turn("0") == ""


def test_search_interpellation_speaker_turn_not_found(
    statement_query: StatementQuery, mock_requests_get_json_once: MagicMock
) -> None:
    """Test we get an empty string when the table does not have a timestamp with given mp_id."""
    assert statement_query.search_interpellation_speaker_turn("0") == ""


def test_search_interpellation_speaker_turn_found(
    statement_query: StatementQuery, mock_requests_get_json_with_statement_timestamp: MagicMock
) -> None:
    """Test we get an timestamp string when the table doeshave a timestamp with given mp_id."""
    assert statement_query.search_interpellation_speaker_turn("486") == "2018-06-14 13:04:08"


def test_get_xml(vaski_query: VaskiQuery, mock_requests_get_none: MagicMock) -> None:
    """Test we get None when the parliament API returns an empty json."""
    assert vaski_query.get_xml() is None


def test_get_xml_skip_xml_combine(
    vaski_query: VaskiQuery, mock_requests_get_multiple_rows: MagicMock
) -> None:
    """Test that XMLCombine is skipped when there at least two data rows."""
    assert vaski_query.get_xml() is None


def test_xml_combine(
    read_xml_string: Callable[[int, int, str], str],
    vaski_query: VaskiQuery,
    mock_requests_get_json_for_xml_combine: MagicMock,
) -> None:
    """Test a transcript is composed from subsections if the main transcript is missing."""
    combined_xml = vaski_query.get_xml()
    true_file = read_xml_string(61, 2020, "")
    assert combined_xml == true_file
