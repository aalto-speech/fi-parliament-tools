"""Test interpellation parsing."""
from dataclasses import asdict
from unittest.mock import MagicMock

import pytest
from lxml import etree
from pytest_mock.plugin import MockerFixture  # type: ignore

from fi_parliament_tools.parsing.documents import Interpellation


true_interpellation_statement = {
    "type": "L",
    "mp_id": 1144,
    "firstname": "Suna",
    "lastname": "Kymäläinen",
    "party": "sd",
    "title": "",
    "start_time": "2017-11-24 13:08:47.023",
    "end_time": "",
    "language": "fi",
    "offset": -1.0,
    "duration": -1.0,
    "text": "The true text is fetched from a file using a fixture.",
    "embedded_statement": {
        "mp_id": 0,
        "title": "",
        "firstname": "",
        "lastname": "",
        "language": "",
        "text": "",
        "offset": -1.0,
        "duration": -1.0,
    },
}


@pytest.fixture
def mock_query(mocker: MockerFixture) -> MagicMock:
    """Mock StatementQuery.search_interpellation_speaker_turn call."""
    mock: MagicMock = mocker.patch("fi_parliament_tools.parsing.documents.StatementQuery")
    mock.return_value.search_interpellation_speaker_turn.return_value = "2017-11-24 13:08:47.023"
    return mock


def test_interpellation(interpellation_4_2017_text: str, mock_query: MagicMock) -> None:
    """Test that interpellation is correctly parsed."""
    with open("tests/data/xmls/vk-04-2017.xml", encoding="utf-8", newline="") as infile:
        xml = etree.fromstring(infile.read())
    interpellation = Interpellation(4, 2017, xml, "2017/124")
    statement = interpellation.compose_speaker_statement()
    true_interpellation_statement["text"] = interpellation_4_2017_text
    assert asdict(statement) == true_interpellation_statement
    mock_query.assert_called_once_with(interpellation.session)
    mock_query.return_value.search_interpellation_speaker_turn.assert_called_once_with("1144")
