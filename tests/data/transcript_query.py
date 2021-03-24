"""Definitions for mocking the result of Query("SaliDBIstunto").get_full_table()."""
from typing import List
from typing import Optional
from typing import Tuple

import pytest


@pytest.fixture(scope="module")
def query_get_full_table() -> Tuple[List[List[Optional[str]]], List[str]]:
    """Return values for get_full_table() call."""
    data = [
        [
            "651",
            "2018/133",
            "TAYSISTUN",
            "LOPETETTU",
            "Istunto päättynyt",
            "Plenum avslutat",
            "2018",
            "133",
            "2018-12-17 22:00:00",
            "2018-12-18 08:00:00",
            "2018-12-18 08:01:05",
            None,
        ],
        [
            "652",
            "2018/134",
            "TAYSISTUN",
            "PJLAADITTU",
            "Laadittu",
            "Preliminär dagordning",
            "2018",
            "134",
            "2018-12-18 22:00:00",
            "2018-12-19 08:00:00",
            None,
            None,
        ],
        [
            "653",
            "2018/135",
            "TAYSISTUN",
            "LOPETETTU",
            "Istunto päättynyt",
            "Plenum avslutat",
            "2018",
            "135",
            "2018-12-19 22:00:00",
            "2018-12-20 08:00:00",
            "2018-12-20 08:00:28",
            None,
        ],
        [
            "654",
            "2018/136",
            "TAYSISTUN",
            "LOPETETTU",
            "Istunto päättynyt",
            "Plenum avslutat",
            "2018",
            "136",
            "2018-12-20 22:00:00",
            "2018-12-21 08:00:00",
            "2018-12-21 08:00:27",
            None,
        ],
        [
            "655",
            "2018/137",
            "TAYSISTUN",
            "PJLAADITTU",
            "Laadittu",
            "Preliminär dagordning",
            "2018",
            "137",
            "2019-01-07 22:00:00",
            "2019-01-08 12:00:00",
            None,
            None,
        ],
        [
            "656",
            "2018/138",
            "TAYSISTUN",
            "LOPETETTU",
            "Istunto päättynyt",
            "Plenum avslutat",
            "2018",
            "138",
            "2019-01-08 22:00:00",
            "2019-01-09 12:00:00",
            "2019-01-09 12:06:03",
            None,
        ],
    ]
    columns = [
        "Id",
        "TekninenAvain",
        "IstuntoTyyppi",
        "IstuntoTila",
        "IstuntoTilaSeliteFI",
        "IstuntoTilaSeliteSV",
        "IstuntoVPVuosi",
        "IstuntoNumero",
        "IstuntoPvm",
        "IstuntoIlmoitettuAlkuaika",
        "IstuntoAlkuaika",
        "IstuntoLoppuaika",
    ]
    return data, columns
