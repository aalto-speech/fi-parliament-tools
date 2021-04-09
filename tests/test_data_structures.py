"""Test speaker and chairman statement classes."""
from dataclasses import asdict
from typing import Dict
from typing import Tuple
from typing import Union

import pytest

from fi_parliament_tools.transcriptParser.data_structures import EmbeddedStatement
from fi_parliament_tools.transcriptParser.data_structures import Statement


embedded_data = [
    {
        "mp_id": 0,
        "title": "",
        "firstname": "",
        "lastname": "",
        "language": "",
        "text": "",
        "offset": -1.0,
        "duration": -1.0,
    },
    {
        "mp_id": 0,
        "title": "Ensimmäinen varapuhemies",
        "firstname": "Mauri",
        "lastname": "Pekkarinen",
        "language": "",
        "text": "Vähän puhetta puheenjohtajalta.",
        "offset": -1.0,
        "duration": -1.0,
    },
    {
        "mp_id": 0,
        "title": "Puhemies",
        "firstname": "Anu",
        "lastname": "Vehviläinen",
        "language": "",
        "text": "Satunnaisia löpinöitä päiväjärjestyksestä.",
        "offset": -1.0,
        "duration": -1.0,
    },
    {
        "mp_id": 0,
        "title": "Puhemies",
        "firstname": "Paula",
        "lastname": "Risikko",
        "language": "",
        "text": "Ensimmäiseen käsittelyyn esitellään päiväjärjestyksen 4. asia.",
        "offset": -1.0,
        "duration": -1.0,
    },
]

speaker_data = [
    {
        "type": "L",
        "mp_id": 0,
        "firstname": "",
        "lastname": "",
        "party": "",
        "title": "",
        "start_time": "",
        "end_time": "",
        "language": "",
        "text": "",
        "offset": -1.0,
        "duration": -1.0,
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
    },
    {
        "type": "L",
        "mp_id": 1306,
        "firstname": "Anders",
        "lastname": "Adlercreutz",
        "party": "r",
        "title": "",
        "start_time": "2018-06-07T16:38:45",
        "end_time": "2018-06-07T16:39:01",
        "language": "sv",
        "text": "Men plasten är ingen ny utmaning. Vad har regeringen gjort tills nu?",
        "offset": -1.0,
        "duration": -1.0,
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
    },
    {
        "type": "L",
        "mp_id": 451,
        "firstname": "Tarja",
        "lastname": "Filatov",
        "party": "sd",
        "title": "",
        "start_time": "2018-04-25T14-24-10",
        "end_time": "2018-04-25T14-25-41",
        "language": "fi",
        "text": "On totta kai selvää, että vähäinenkin työ on parempi kuin ei työtä ollenkaan.",
        "offset": -1.0,
        "duration": -1.0,
        "embedded_statement": {
            "mp_id": 0,
            "title": "Puhemies",
            "firstname": "Paula",
            "lastname": "Risikko",
            "language": "",
            "text": "Vastauspuheenvuorona käytetään minuutin mittaisia puheita.",
            "offset": -1.0,
            "duration": -1.0,
        },
    },
]


@pytest.mark.parametrize(
    "embedded_statement",
    [(embedded_data[0]), (embedded_data[1]), (embedded_data[2]), (embedded_data[3])],
    indirect=True,
)
def test_embedded_statements(embedded_statement: Tuple[EmbeddedStatement, Dict[str, str]]) -> None:
    """Test the embedded statement dataclass."""
    statement, true_data = embedded_statement
    assert asdict(statement) == true_data


@pytest.mark.parametrize(
    "speaker_statement",
    [(speaker_data[0]), speaker_data[1], speaker_data[2]],
    indirect=True,
)
def test_statements(speaker_statement: Tuple[Statement, Dict[str, Union[str, int]]]) -> None:
    """Test the speaker statement dataclass."""
    statement, true_data = speaker_statement
    assert asdict(statement) == true_data
