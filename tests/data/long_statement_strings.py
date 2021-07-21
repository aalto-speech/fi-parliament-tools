"""Long statement strings and other space consuming data definitions for testing are declared here.

This is done to avoid clutter in main test files.
"""
from typing import Dict
from typing import List
from typing import Tuple

import pytest
from _pytest.fixtures import SubRequest

from fi_parliament_tools.transcriptParser.data_structures import MP

chairman_texts = [
    "Ilmoitetaan, että valiokuntien ja kansliatoimikunnan vaalit toimitetaan ensi tiistaina 5. "
    "päivänä toukokuuta kello 14 pidettävässä täysistunnossa. Ehdokaslistat näitä vaaleja varten "
    "on jätettävä keskuskansliaan viimeistään ensi maanantaina 4. päivänä toukokuuta kello 12.",
    "Toimi Kankaanniemen ehdotus 5 ja Krista Kiurun ehdotus 6 koskevat samaa asiaa, joten ensin "
    "äänestetään Krista Kiurun ehdotuksesta 6 Toimi Kankaanniemen ehdotusta 5 vastaan ja sen "
    "jälkeen voittaneesta mietintöä vastaan.",
    "Kuhmosta oleva agrologi Tuomas Kettunen, joka varamiehenä Oulun vaalipiiristä on "
    "tullut Antti Rantakankaan sijaan, on tänään 28.11.2019 esittänyt puhemiehelle "
    "edustajavaltakirjansa ja ryhtynyt hoitamaan edustajantointaan.",
]

speaker_texts = [
    "Arvoisa puhemies! Hallituksen esityksen mukaisesti on varmasti hyvä jatkaa määräaikaisesti "
    "matkapuhelinliittymien telemarkkinointikieltoa. Kukaan kansalainen ei ole kyllä ainakaan "
    "itselleni valittanut siitä, että enää eivät puhelinkauppiaat soittele kotiliittymiin ja "
    "‑puhelimiin, ja myös operaattorit ovat olleet kohtuullisen tyytyväisiä tähän kieltoon. "
    "Ongelmia on kuitenkin muussa puhelinmyynnissä ja telemarkkinoinnissa. Erityisesti "
    "nettiliittymien puhelinmyynnissä on ongelmia. On aggressiivista myyntiä, ja ihmisillä on "
    "epätietoisuutta siitä, mitä he ovat lopulta ostaneet. Lisäksi mielestäni on ongelmallista "
    "rajata vain puhelinliittymät telemarkkinointikiellon piiriin, kun viestintä- ja "
    "mobiilipalveluiden puhelinkauppa on laajempi aihe ja se on laajempi ongelma ja ongelmia on "
    "tosiaan tässä muidenkin tyyppisten sopimusten myynnissä. Tämä laki tämänsisältöisenä on "
    "varmasti ihan hyvä, ja on hyvä määräaikaisesti jatkaa tätä, mutta näkisin, että sitten kun "
    "tämä laki on kulumassa umpeen, meidän on palattava asiaan ja on tehtävä joku lopullisempi "
    "ratkaisu tästä telemarkkinoinnista. Ei voida mennä tällaisen yhden sopimusalan "
    "määräaikaisuudella eteenpäin. Meidän täytyy tehdä ratkaisut, jotka ovat laajempia ja jotka "
    "koskevat viestintä-, tele- ja mobiilisopimusten puhelinmyyntiä laajemmin ja muutenkin "
    "puhelinmyynnin pelisääntöjä laajemmin. Varmaankin paras ratkaisu olisi se, että jatkossa "
    "puhelimessa tehty ostos pitäisi varmentaa kirjallisesti esimerkiksi sähköpostilla, "
    "tekstiviestillä tai kirjeellä. Meidän on ratkaistava jossain vaiheessa nämä puhelinmyynnissä "
    "olevat ongelmat ja käsiteltävä asia kokonaisvaltaisesti. — Kiitos. (Hälinää)",
    "Arvoisa puhemies! Pienen, vastasyntyneen lapsen ensimmäinen ote on samaan aikaan luja ja "
    "hento. Siihen otteeseen kiteytyy paljon luottamusta ja vastuuta. Luottamusta siihen, että "
    "molemmat vanhemmat ovat läsnä lapsen elämässä. Vastuuta siitä, että huominen on aina "
    "valoisampi. Luottamus ja vastuu velvoittavat myös meitä päättäjiä. Tämän hallituksen "
    "päätökset eivät perheiden kannalta ole olleet kovin hääppöisiä. Paljon on leikattu perheiden "
    "arjesta, mutta toivon kipinä heräsi viime vuonna, kun hallitus ilmoitti, että se toteuttaa "
    "perhevapaauudistuksen. Viime perjantaina hallituksen perheministeri kuitenkin yllättäen "
    "ilmoitti, että hän keskeyttää tämän uudistuksen. Vielä suurempi hämmästys oli se syy, jonka "
    "takia tämä keskeytettiin. Ministeri ilmoitti, että valmistellut mallit olisivat olleet "
    "huonoja suomalaisille perheille. Perheministeri Saarikko, kun te olette vastuussa tämän "
    "uudistuksen valmistelusta, niin varmasti suomalaisia perheitä kiinnostaisi tietää, miksi te "
    "valmistelitte huonoja malleja.",
    "Arvoisa puhemies! Lämpimät osanotot omasta ja perussuomalaisten eduskuntaryhmän "
    "puolesta pitkäaikaisen kansanedustajan Maarit Feldt-Rannan omaisille ja läheisille. "
    "Nuorten mielenterveysongelmat ovat vakava yhteiskunnallinen ongelma. "
    "Mielenterveysongelmat ovat kasvaneet viime vuosina räjähdysmäisesti, mutta "
    "terveydenhuoltoon ei ole lisätty vastaavasti resursseja, vaan hoitoonpääsy on "
    "ruuhkautunut. Masennuksesta kärsii jopa 15 prosenttia nuorista, ahdistuneisuudesta 10 "
    "prosenttia, ja 10—15 prosentilla on toistuvia itsetuhoisia ajatuksia. Monet näistä "
    "ongelmista olisivat hoidettavissa, jos yhteiskunta ottaisi asian vakavasti. Turhan "
    "usein hoitoon ei kuitenkaan pääse, vaan nuoret jätetään heitteille. Kysyn: mihin "
    "toimiin hallitus ryhtyy varmistaakseen, että mielenterveysongelmista kärsiville "
    "nuorille on tarjolla heidän tarvitsemansa hoito silloin kun he sitä tarvitsevat?",
]

speaker_lists = [
    [
        (1301, "Jani", "Mäkelä", "ps", ""),
        (1108, "Juha", "Sipilä", "", "Pääministeri"),
        (1301, "Jani", "Mäkelä", "ps", ""),
        (1108, "Juha", "Sipilä", "", "Pääministeri"),
        (1141, "Peter", "Östman", "kd", ""),
        (947, "Petteri", "Orpo", "", "Valtiovarainministeri"),
        (1126, "Tytti", "Tuppurainen", "sd", ""),
        (1108, "Juha", "Sipilä", "", "Pääministeri"),
        (1317, "Simon", "Elo", "sin", ""),
        (1108, "Juha", "Sipilä", "", "Pääministeri"),
    ],
    [
        (1093, "Juho", "Eerola", "ps", ""),
        (1339, "Kari", "Kulmala", "sin", ""),
        (887, "Sirpa", "Paatero", "sd", ""),
        (967, "Timo", "Heinonen", "kok", ""),
    ],
    [
        (971, "Johanna", "Ojala-Niemelä", "sd", ""),
        (1129, "Arja", "Juvonen", "ps", ""),
        (1388, "Mari", "Rantanen", "ps", ""),
        (1391, "Ari", "Koponen", "ps", ""),
        (1325, "Sari", "Tanus", "kd", ""),
        (971, "Johanna", "Ojala-Niemelä", "sd", ""),
    ],
]

chairman_statements = [
    {
        "type": "C",
        "mp_id": 0,
        "firstname": "Mauri",
        "lastname": "Pekkarinen",
        "party": "",
        "title": "Ensimmäinen varapuhemies",
        "start_time": "",
        "end_time": "",
        "language": "",
        "text": "Ainoaan käsittelyyn esitellään päiväjärjestyksen 4. asia. Käsittelyn pohjana on "
        "talousvaliokunnan mietintö TaVM 18/2016 vp.",
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
        "type": "C",
        "mp_id": 0,
        "firstname": "Mauri",
        "lastname": "Pekkarinen",
        "party": "",
        "title": "Ensimmäinen varapuhemies",
        "start_time": "",
        "end_time": "",
        "language": "",
        "text": "Toiseen käsittelyyn esitellään päiväjärjestyksen 3. asia. Keskustelu asiasta "
        "päättyi 6.6.2017 pidetyssä täysistunnossa. Keskustelussa on Anna Kontula Matti Semin "
        "kannattamana tehnyt vastalauseen 2 mukaisen lausumaehdotuksen.",
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
        "type": "C",
        "mp_id": 0,
        "firstname": "Tuula",
        "lastname": "Haatainen",
        "party": "",
        "title": "Toinen varapuhemies",
        "start_time": "",
        "end_time": "",
        "language": "",
        "text": "Toiseen käsittelyyn esitellään päiväjärjestyksen 6. asia. Nyt voidaan hyväksyä "
        "tai hylätä lakiehdotukset, joiden sisällöstä päätettiin ensimmäisessä käsittelyssä.",
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
]

embedded_statements = [
    {
        "mp_id": 0,
        "title": "Puhemies",
        "firstname": "Maria",
        "lastname": "Lohela",
        "language": "",
        "text": "Edustaja Laukkanen, ja sitten puhujalistaan.",
        "offset": -1.0,
        "duration": -1.0,
    },
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
        "text": "Tämä valtiovarainministerin puheenvuoro saattaa antaa aihetta muutamaan "
        "debattipuheenvuoroon. Pyydän niitä edustajia, jotka haluavat käyttää vastauspuheenvuoron, "
        "nousemaan ylös ja painamaan V-painiketta.",
        "offset": -1.0,
        "duration": -1.0,
    },
    {
        "mp_id": 0,
        "title": "Ensimmäinen varapuhemies",
        "firstname": "Antti",
        "lastname": "Rinne",
        "language": "",
        "text": "Meillä on puoleenyöhön vähän reilu kolme tuntia aikaa, ja valtioneuvoston pitää "
        "sitä ennen soveltamisasetus saattaa voimaan. Pyydän ottamaan tämän huomioon "
        "keskusteltaessa.",
        "offset": -1.0,
        "duration": -1.0,
    },
]

mps = [
    MP(
        103,
        "Matti",
        "Ahde",
        "o",
        "fi",
        1945,
        "Sosialidemokraattinen eduskuntaryhmä",
        "",
        "",
        "Oulu",
    ),
    MP(
        1432,
        "Marko",
        "Kilpi",
        "m",
        "fi",
        1969,
        "Parliamentary Group of the National Coalition Party",
        "police officer, writer",
        "Kuopio",
        "Rovaniemi",
    ),
    MP(
        1374,
        "Veronica",
        "Rehn-Kivi",
        "f",
        "sv",
        1956,
        "Swedish Parliamentary Group",
        "architect, building supervision manager",
        "Kauniainen",
        "Helsinki",
    ),
    MP(
        1423,
        "Iiris",
        "Suomela",
        "f",
        "fi",
        1994,
        "Green Parliamentary Group",
        "student of social sciences",
        "Tampere",
        "",
    ),
]


@pytest.fixture
def true_chairman_text(request: SubRequest) -> str:
    """Return a long chairman statement for testing from a list at the top of the file."""
    index: int = request.param
    return chairman_texts[index]


@pytest.fixture
def true_speaker_text(request: SubRequest) -> str:
    """Return a long speaker statement for testing from a list at the top of the file."""
    index: int = request.param
    return speaker_texts[index]


@pytest.fixture
def true_speaker_list(request: SubRequest) -> List[Tuple[int, str, str, str, str]]:
    """Return a list of speakers for testing from a list at the top of the file."""
    index: int = request.param
    return speaker_lists[index]


@pytest.fixture
def true_chairman_statement(request: SubRequest) -> Dict[str, object]:
    """Return a chairman statement for testing from a list at the top of the file."""
    index: int = request.param
    return chairman_statements[index]


@pytest.fixture
def true_embedded_statement(request: SubRequest) -> Dict[str, object]:
    """Return an embedded statement for testing from a list at the top of the file."""
    index: int = request.param
    return embedded_statements[index]


@pytest.fixture
def true_mp(request: SubRequest) -> MP:
    """Return an MP data object for testing from a list at the top of the file."""
    index: int = request.param
    return mps[index]


@pytest.fixture
def interpellation_4_2017_text() -> str:
    """Read interpellation 4/2017 text transcript from a file.

    Returns:
        str: full interpellation statement as one very long string
    """
    with open("tests/data/interpellation_4_2017_text.txt", "r", encoding="utf-8") as infile:
        interpellation_text = infile.read().replace("\n", " ")
    return interpellation_text.strip()
