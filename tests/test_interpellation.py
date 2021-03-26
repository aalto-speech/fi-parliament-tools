"""Test interpellation parsing."""
from dataclasses import asdict

from lxml import etree

from fi_parliament_tools.transcriptParser.documents import Interpellation

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
    "text": "The true text is fetched from a file using a fixture.",
    "embedded_statement": {"title": "", "firstname": "", "lastname": "", "text": ""},
}


def test_interpellation(interpellation_4_2017_text: str) -> None:
    """Test that interpellation is correctly parsed."""
    xml = etree.parse("tests/data/xmls/vk-04-2017.xml")
    interpellation = Interpellation(4, 2017, xml, "2017/124")
    statement = interpellation.compose_speaker_statement()
    true_interpellation_statement["text"] = interpellation_4_2017_text
    assert asdict(statement) == true_interpellation_statement
