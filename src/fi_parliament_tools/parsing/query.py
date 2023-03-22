"""A module for querying the Finnish parliament open data API."""
import re
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

import requests
from lxml import etree


class Query:
    """Query template for fetching data from the API."""

    def __init__(self, table: str, **kwargs: Any):
        """Initialize query url and parameters.

        The 'perPage' key determines how many data rows the query response can have. Maximum value
        for the field is 100.

        If there are more than 'perPage' datarows, then the response will have several 'pages'.
        Each page needs to be separately queried.

        Args:
            table (str): name of the table to be queried
            kwargs (Any): additional query parameters
        """
        self.query_url = f"https://avoindata.eduskunta.fi/api/v1/tables/{table}/rows"
        self.query_params = {"perPage": 100, "page": 0, **kwargs}

    def get_json(self) -> Optional[Dict[str, Any]]:
        """Get the JSON response resulting from the query.

        Returns:
            dict: a JSON dictionary containing the response if succesful, otherwise None
        """
        with requests.get(self.query_url, params=self.query_params, timeout=35) as response:
            data: Dict[str, Any] = response.json()
            if data["rowData"]:
                return data
            return None

    def get_full_table(self) -> Tuple[List[List[str]], List[str]]:
        """Get the full table.

        Returns:
            Tuple[List[List[str]], List[str]]: each data row as a list and column names for the rows
        """
        data: List[List[str]] = []
        while response := self.get_json():
            columns = response["columnNames"]
            data += response["rowData"]
            if not response["hasMore"]:
                return (data, columns)
            self.query_params["page"] += 1
        return (data, [])


class VaskiQuery(Query):
    """A class for querying the VaskiData table.

    VaskiData holds for example the session and interpellation XMLs.
    """

    def __init__(self, doc_identifier: str, doc_type: str = "Record"):
        """Form an API query with given parameters.

        Document identifiers follow the format:
        "{document_type} {running_id}/{year} vp"

        Document types include for example PTK (parliament session transcript) and VK
        (interpellation) among others.

        Each document is identified in the databases with a running number and year according to
        parliamentary working seasons/years ('valtiopäivät'). Normally working seasons follow the
        calendar year. For example, the third parliament session in 2016 is identified as 3/2016.
        However, in parliamentary election years, each document before the elections in April is
        assigned to the previous working season/year. After the elections, the running id resets to
        1 and the year is updated to the current calendar year.

        The abbreviation 'vp' stands for valtiopäivät = 'parliamentary working season/year'.

        Args:
            doc_identifier (str): a unique string representing the session
            doc_type (str): an identifier for the correct XML, defaults to "Record"
        """
        super().__init__("VaskiData", columnName="Eduskuntatunnus", columnValue=doc_identifier)
        self.type = doc_type

    def get_xml(self) -> Optional[str]:
        """Return the XML within the query JSON response.

        The 'rowData' in the JSON has usually two rows i.e. XMLs in it. The XMLs are stored in the
        second field of each row. One XML represents the table of contents of the document, the
        other XML has the actual document. We are interested only in the latter. However, the
        actual document is missing sometimes, in which case the code will attempt to compose it
        from subsections using the table of contents. Occasionally, there is a third row of data
        that duplicates some of the XML fields, which is why the regexp matches both the 'type'
        and the element 'RakenneAsiakirja'.

        The method cleans any occurences of non-breaking space from the raw text because the
        character will cause difficult to detect bugs in later processing stages.

        Returns:
            string: full XML document
        """
        if response := self.get_json():
            for row in response["rowData"]:
                if re.search(f"VASKI_JULKVP_{self.type}_fi.*RakenneAsiakirja", row[1]):
                    cleaned: str = re.sub("\u00A0", " ", row[1])
                    return cleaned
            if len(response["rowData"]) == 1:
                return XMLCombiner(response["rowData"][0][1]).combine()
        return None


class XMLCombiner:
    """A class for combining XMLs of transcript subsections.

    This class is used when the main XML is missing the transcribed speech but the transcriptions
    are still available in separate subsection XMLs.
    """

    def __init__(self, main_xml: str):
        """Initialize the combined XML by using the main document XML as base."""
        self.root = etree.fromstring(main_xml)
        self.subsections: Any = self.root.xpath("//*[local-name() = 'Asiakohta']")

    def combine(self) -> str:
        """Replace subsection elements in the main transcript with corresponding subsection XMLs.

        Returns:
            str: the combined transcript as a string
        """
        for subsec in self.subsections:
            if num := subsec.xpath("string(. /*[local-name() = 'KohtaNumero']/text())"):
                main_id: Any = self.root.xpath(
                    "//*[local-name() = 'Poytakirja']/@*[local-name() = 'eduskuntaTunnus']"
                )
                self.replace_element(main_id[0][:-3] + f"/{num} vp", subsec)
        xml_string: str = etree.tostring(self.root, encoding="unicode")
        return xml_string

    def replace_element(self, doc_id: str, subsec: etree._Element) -> None:
        """Fetch the subsection XML from the API.

        Args:
            doc_id: the subsection document ID
            subsec: subsection element in the main XML
        """
        if xml_str := VaskiQuery(doc_id, doc_type="RecordArticle").get_xml():
            sub_xml: Any = etree.fromstring(xml_str)
            [replacement] = sub_xml.xpath("//*[local-name() = 'Asiakohta']")
            parent: Any = subsec.getparent()
            parent.replace(subsec, replacement)


class SessionQuery(Query):
    """A class for querying the SaliDBIstunto table for a particular session.

    The table contains info about the status of a session, including whether it is ongoing/finished,
    announced start time, actual start time and date.
    """

    def __init__(self, session_key: str):
        """Form an API query with given parameters.

        Session key is similar to the document identifier in `VaskiQuery`, but it contains only the
        running number and year of the parliament session in question.

        Args:
            session_key (str): year and id of the session in the format '{year}/{id}'
        """
        super().__init__("SaliDBIstunto", columnName="TekninenAvain", columnValue=session_key)

    def get_session_start_time(self) -> str:
        """Search the true start timestamp of a session.

        Each session has only one entry in the table, so the result is in the first row of the
        response data. The method accesses the field 'IstuntoAlkuaika' in the table row.

        Returns:
            str: true start timestamp of a session
        """
        if response := self.get_json():
            row: List[str] = response["rowData"][0]
            return row[10]
        return ""


class StatementQuery(Query):
    """A class for querying the SaliDBPuheenvuoro table.

    The table contains statistics about requested speaker turns in parliament sessions such as
    speaker name, whether the request was accepted/denied and various timestamps (like request time
    and speaker turn beginning).
    """

    def __init__(self, session_key: str):
        """Form an API query with given parameters.

        Session key is similar to the document identifier in `VaskiQuery`, but it contains only the
        running number and year of the parliament session in question.

        Args:
            session_key (str): year and id of the session in the format '{year}/{id}'
        """
        super().__init__(
            "SaliDBPuheenvuoro",
            columnName="IstuntoTekninenAvain",
            columnValue=session_key,
        )

    def search_interpellation_speaker_turn(self, mp_id: str) -> str:
        """Search the begin time for an interpellation speaker turn.

        Args:
            mp_id (str): id is used to find correct speaker

        Returns:
            str: speaker turn begin timestamp
        """
        while response := self.get_json():
            begin_time = self.check_page_for_interpellation_timestamp(mp_id, response["rowData"])
            if begin_time or not response["hasMore"]:
                return begin_time
            self.query_params["page"] += 1
        return ""

    def check_page_for_interpellation_timestamp(self, mp_id: str, data: List[str]) -> str:
        """Search through one page of response data for an interpellation speaker turn.

        Each row in the data table contains following fields:
        ["Id","IstuntoTekninenAvain","KohtaTekninenAvain","TekninenAvain","Jarjestys","PVTyyppi",
        "henkilonumero","Etunimi","Sukunimi","Sukupuoli","PyyntoTapa","PyyntoAika","XmlData",
        "Created","Modified","RyhmaLyhenneFI","RyhmaLyhenneSV","Puhunut","JarjestysNro","ADtunnus",
        "MinisteriysFI","MinisteriysSV","Imported"]

        Args:
            mp_id (str): id is used to find correct speaker (matched to field 'henkilonumero')
            data (list): table of speaker turns

        Returns:
            str: speaker turn begin timestamp
        """
        for row in data:
            if row[6] == mp_id:
                empty_statement_type_and_manner = row[5] == "" and row[10] == ""
                has_spoker_first = row[17] == "2" and row[18] == "1"
                if empty_statement_type_and_manner and has_spoker_first:
                    return row[4]
        return ""


class MPQuery(Query):
    """A class for querying the MemberOfParliament table.

    The table contains information about members of parliament.
    """

    def __init__(self) -> None:
        """Form an API query with given parameters."""
        super().__init__("MemberOfParliament")
