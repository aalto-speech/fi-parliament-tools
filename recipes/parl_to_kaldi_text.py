"""A recipe example for preprocessing Finnish parliament transcripts to a kaldi text file."""
import re
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Match
from typing import Tuple

import aalto_asr_preprocessor.fi.numbers.expansion as num_fi

SUFFIX_MAPPING: Dict[str, List[str]] = {
    "NOM": ["han", "hän", "kaan", "kään", "ko", "kö", "kin", "pa", "pä"],
    "PAR": ["a", "ä", "aa", "ää", "ta", "taa", "tta", "tä"],
    "GEN": ["n"],
    "INE": ["ssa", "ssä"],
    "ELA": ["sta", "stä"],
    "ILL": ["aan", "een", "iin", "teen", "ään"],
    "ADE": ["lla", "llä"],
    "ABL": ["lta", "ltä"],
    "ALL": ["lle"],
    "ESS": ["na", "nä"],
    "TRA": ["ksi"],
    "JNOM": ["nen", "s"],
    "JPAR": ["ttä"],  # overlaps with some #PAR cases, due to rarity overlaps are not handled
    "JGEN": ["nnen"],
    "JINE": ["nnessa", "nnessä"],
    "JELA": ["nnesta", "nnestä"],
    "JILL": ["nteen"],
    "JADE": ["nnella", "nnellä"],
    "JABL": ["nnelta", "nneltä"],
    "JALL": ["nnelle"],
    "JESS": ["ntena", "ntenä"],
    "JTRA": ["nneksi"],
}

WORD_INFLECTIONS: List[Tuple[str, str]] = [
    # 100 foobariksi -> sadaksi
    (r"[a-zåäö]{2,}ksi$", "TRA"),
    # 5 foobarilta -> viideltä
    (r"ll[aä]$", "ADE"),
    # 5 foobarilla -> viidellä
    (r"lt[aä]$", "ABL"),
    # 5 foobarille -> viidelle
    (r"lle$", "ALL"),
    # 5 foobarina -> viitenä
    (r"n[aä]$", "ESS"),
    # 6 foobarissa -> kuudessa
    (r"ss[aä]$", "INE"),
    # 6 foobarista -> kuudesta
    (r"st[aä]$", "ELA"),
    # 10 foobariin -> kymmeneen (require at least five chars because otherwise genitive cases of
    # short words like maa [maan], muu [muun] etc. get wrong case here)
    (r"[a-zåäö]{2,}(?:aa|ee|ii|oo|uu|yy|ää|öö)n$", "ILL"),
    # 3 foobarin -> kolmen (require at least three chars so 'on' is not mistakenly caught here)
    # Needs to be last, otherwise catches words in illative case too.
    (r"[a-zåäö]{2,}n$", "GEN"),
]

ELATIVE_WORDS = Path("recipes/words_elative.txt").read_text("utf-8").split()

SECTION_CHAR_MAPPING: Dict[str, Tuple[str, str]] = {
    "": ("pykälä", "JNOM"),
    "hän": ("pykälä", "JNOM"),
    "kin": ("pykälä", "JNOM"),
    "ää": ("pykäl", "JPAR"),
    "n": ("pykälä", "JGEN"),
    "ssä": ("pykälä", "JINE"),
    "ssään": ("pykälä", "JINE"),
    "stä": ("pykälä", "JELA"),
    "ään": ("pykäl", "JILL"),
    "llä": ("pykälä", "JADE"),
    "lle": ("pykälä", "JALL"),
    "nä": ("pykälä", "JESS"),
    "ksi": ("pykälä", "JTRA"),
    "t": ("pykälä", "NOM"),
    "iä": ("pykäl", "NOM"),
    "ien": ("pykäl", "NOM"),
    "iin": ("pykäl", "NOM"),
    "issä": ("pykäl", "NOM"),
    "s": ("pykälä", "NOM"),  # In swedish text, include here to prevent KeyError
}

ROMAN_TO_NUMBER: Dict[str, str] = {
    "I": "1",
    "II": "2",
    "III": "3",
    "IV": "4",
    "V": "5",
    "VI": "6",
    "VII": "7",
    "VIII": "8",
    "IX": "9",
    "X": "10",
}


def map_suffix_to_inflection(match: Match[str]) -> str:
    """Expand inflected numbers captured with regexp.

    Can handle single numbers, decimal numbers and ranges. Possible clitics are handled too.
        3:sta -> kolmesta
        4,4:ään -> neljään pilkku neljään
        1 000-1 500:ssa -> tuhannessa viiva tuhannessaviidessäsadassa
        20:nkin -> kahdenkymmenenkin

    Args:
        match (Match): number(s) and inflection captured using regexp

    Returns:
        str: number(s) inflected in word format
    """
    numbers = match.group(2) if match.group(1) is None else match.group(1) + match.group(2)
    suffix, clitic = match.group(3), ""
    form = "NOM"
    if tmp := [(suffix.split(cl)[0], cl) for cl in SUFFIX_MAPPING["NOM"] if cl in suffix]:
        suffix, clitic = tmp[0]
    for f, suffixes in SUFFIX_MAPPING.items():
        if suffix in suffixes:
            form = f
    translation = str.maketrans({"+": " plus ", ",": " pilkku ", ".": " piste ", "/": " per "})
    numbers = numbers.translate(translation)
    numbers = re.sub(r"[-–—]", r" viiva ", numbers)
    numbers = re.sub(r"(\d+)\b", r"\1" + form, numbers)
    numbers = re.sub(r"(\d+)([A-Z]+)?", num_fi.expand, numbers)
    return f"{numbers}{clitic}"


def number_word_pair_inflection(match: Match[str]) -> Any:
    """Inflect number with the same case as following word.

    Elative overlaps with partitive which is solved using a separate lookup table collected from
    Finnish parliament text data. For other inflections, it is assumed that the suffix of the word
    informs the correct inflection for the number. Not 100% accurate/valid assumption but it more
    probable than leaving all numbers in nominal form.

    Args:
        match (Match): number(s) and word captured using regexp

    Returns:
        Any: captured regex with numbers inflected in word format
    """
    result, word = match.group(0), match.group(3)
    for regex, form in WORD_INFLECTIONS:
        if re.search(regex, word):
            if form == "ELA" and word not in ELATIVE_WORDS:
                form = "NOM"
            result = re.sub(r"(\d+\.?)", r"\1#" + form, result)
            break
    return re.sub(r"(\d+)\.([A-Z]+\b)", r"\1#J\2", result)


def change_to_ordinal(match: Match[str]) -> str:
    """Change number before specific captured words to ordinal form.

    Usually ordinals are marked like so: 4. päivänä -> neljäntenä päivänä. But periods are left
    out from numbers before words such as 'momentti' or 'kohta' even if the number is read as
    ordinal. However, if these words are preceded by a list of numbers then they are here expanded
    in nominal case because MPs are more likely to read them in nominal form.

    Args:
        match (Match): number(s) and word captured using regexp

    Returns:
        str: number(s) inflected in word format together with the following word
    """
    numbers = match.group(2) if match.group(1) is None else match.group(1) + match.group(2)
    form = match.group(3) if match.group(3) is not None else "NOM"
    word = match.group(4)
    numbers = re.sub(r"[-–—]", r" viiva ", numbers)
    if match.group(1):
        numbers = re.sub(r"(\d+),?", r"\1NOM", numbers)
    else:
        numbers = re.sub(r"(\d+)", r"\1J" + form, numbers)
    numbers = re.sub(r"(\d+)([A-Z]+)?", num_fi.expand, numbers)
    return f"{numbers} {word}"


def expand_section_sign(match: Match[str]) -> str:
    """Handle the inflection of § sign and the numbers immediately preceding it.

    Determines the inflection from the suffix associated with §. If there are multiple numbers, then
    all numbers are expanded in nominal form because MPs are more likely read it that way.

    Args:
        match (Match): number(s) and the inflection of the section sign

    Returns:
        str: number(s) and the section sign expanded in the correct inflected form
    """
    numbers = match.group(2) if match.group(1) is None else match.group(1) + match.group(2)
    suffix, clitic = match.group(3), ""
    if tmp := [(suffix.split(cl)[0], cl) for cl in SUFFIX_MAPPING["NOM"] if cl in suffix]:
        suffix, clitic = tmp[0]
    section_word, form = SECTION_CHAR_MAPPING[suffix]
    numbers = re.sub(r"[-–—]", r" viiva ", numbers)
    numbers = re.sub(r"(\d+)([a-z])", r"\1 \2", numbers)
    numbers = re.sub(r"(\d+),?", r"\1" + form, numbers)
    numbers = re.sub(r"(\d+)([A-Z]+)?", num_fi.expand, numbers)
    if form == "NOM":
        return f"{section_word}{suffix} {numbers}"
    return f"{numbers} {section_word}{suffix}{clitic}"


def school_classes(match: Match[str]) -> Any:
    """Handle the specific reading of 1st and 2nd year school classes.

    Args:
        match (Match): captured school class(es)

    Returns:
        Any: school classes expanded in correct inflected form
    """
    result = " ".join([i or "" for i in match.groups()]).strip()
    translation = str.maketrans({"1": "ykkös", "2": "kakkos", "—": "viiva"})
    result = result.translate(translation)
    result = re.sub(r"(\d+)\b", r"\1JNOM", result)
    return re.sub(r"(\d+)([A-Z]+)?", num_fi.expand, result)


def roman_numerals(match: Match[str]) -> Any:
    """Map roman numerals to arabic numerals. Handles currently only 1 to 10.

    Args:
        match (Match): captured roman numeral

    Returns:
        Any: roman numeral as its corresponding arabic numeral
    """
    result, roman = match.group(0), match.group(2)
    number = ROMAN_TO_NUMBER[roman]
    result = result.replace(roman, number)
    return re.sub(r"(\d+)-", r"\1. ", result)


def years(match: Match[str]) -> Any:
    """Handle years when they have only two digits.

    Args:
        match (Match): captured years and words connecting them

    Returns:
        Any: year inflected in the nominal form
    """
    result = match.group(0)
    result = re.sub(r"[-–—]", r" viiva ", result)
    result = re.sub(r"(\d+)", r"\1NOM", result)
    return re.sub(r"(\d+)([A-Z]+)", num_fi.expand, result)


def lowercase(match: Match[str]) -> Any:
    """Convert match to lowercase.

    Args:
        match (Match): captured string

    Returns:
        Any: capture in lowercase
    """
    return match.group(0).lower()


UNACCEPTED_CHARS = r"[^a-zåäö \n]"

REGEXPS = [
    (r"\n", r" "),
    # Initials
    (r"\b([A-ZÄÖÅ])\.", r"\1 "),
    # Välihuudot pois = Remove shouts and interruptions
    (r"\s*(?:\(|\[).*?(?:\)|\])\s*", r" "),
    # Typos that have been encountered: Unmatched bracket in the beginning or unmatched bracket in
    # an interruption at the end
    (r"^(?:\(|\[)", r""),
    (r"(?:\(|\[)[^)\]]*?$", r" "),
    # (r"\s*\[.*?\]\s*", r" "),
    # Urlit pois = Remove URLs
    (r"http:\S*", r""),
    (r"www\.[a-zA-Z]\S*", r""),
    (r"\S*\.html?", r""),
    # Peräkkäiset pisteet yhdeksi = Substitute repeated periods with a single period
    (r"\.+", r"."),
    # Vuosiluvut = Years
    (
        r"(?<!ensi )(?<!viime )([Vv]uo[nds]\w{1,5} )(\d{2,4}(?:—| ja | tai ))?(\d{2})(?!.?\d)",
        years,
    ),
    (r"(\d{4})[–—]", r"\1 viiva "),
    (r"([^\/])(\d{4})\b", r"\1\2#NOM"),
    # Välit pois numeroiden välistä = Remove spaces between digits
    (r"(\d)\s+(\d)", r"\1\2"),
    # Roomalaiset numerot 1-10 = Roman numerals between 1 and 10
    (r"( |-)(X|IX|IV|V|V?I{1,3})( |-|:|\.)", roman_numerals),
    # Jotain erikoissanontoja = Some abbreviations
    (r"\bjr.", r"junior "),
    (r"\binc.", r"inc "),
    (r"(\d+)\s*m/s", r"\1 metriä sekunnissa"),
    (r"(\d+)\s*r/min", r"\1 kierrosta minuutissa"),
    (r"(\d+)\s+kpm\b", r"\1 kilopondimetriä"),
    (r"(\d+)\s+kW/l\b", r"\1 kilowattia litraa kohti"),
    (r"(\d+)\s+kW\b", r"\1 kilowattia"),
    (r"(\d+)\s+hv/l\b", r"\1 hevosvoimaa litraa kohti"),
    (r"1½", r" yksi ja puoli "),
    (r"½", r" puoli "),
    (r"m²:n", r"neliömetrin"),
    (r"\/\s*m²", r" per neliömetri"),
    (r"\S*[²³]\S*", r""),
    (r"±", r"plus miinus "),
    (r"(\d+)\s*°C", r"\1 Celcius astetta"),
    (r"(\d+)\s*°", r"\1 astetta"),
    (
        r"(?:klo|[kK]ello)\s+(\d+)\.(\d+)—(\d+)\.(\d+)",
        r"kello \1#NOM \2#NOM viiva \3#NOM \4#NOM",
    ),
    (r"(?:klo|[kK]ello)\s+(on\s+)?(\d+)\.(\d+)?", r"kello \1 \2#NOM \3"),
    (r"£", r"puntaa"),
    (r"\$", r"dollaria"),
    (r"\%", r"prosenttia"),
    (r"\besim\.", r"esimerkiksi "),
    (r"\bpat\. no\.?", r"patentti numero "),
    (r"\bo\.s\.", r"omaa sukua "),
    (r"\s+n\.", r" noin"),
    (r"\bts\.", r"tai siis "),
    (r"\bev\. ?lut\.", r"evankelisluterilainen "),
    (r"\bpros\.", r"prosenttia"),
    (r"\bk\.?o\.", r"kyseessä oleva "),
    (r"\bjne.", r"ja niin edelleen "),
    (r"\bem\.", r"edellä mainittu "),
    (r"\bent\.", r"entinen "),
    (r"\bop\.\s*(\d+)", r"opus \1 "),
    (r"\bkv\.", r"kansainvälinen "),
    (r"\s+ns\.", r" niin sanottu "),
    (r"\s+nk\.", r" niin kutsuttu "),
    (r"\s+vt\.", r" virkaatekevä "),
    (r"\s+p\.\s+(\d+)", r" puhelin \1"),
    (r"\bpuh\.\s+(\d+)", r"puhelin \1"),
    (r"\s+v\.\s+(\d+)", r" vuonna \1"),
    (r"\s+(s|synt)\.\s*(\d{4})", r" syntynyt \1"),
    (r"\bym\.", r"ynnä muuta "),
    (r"\byms\.", r"ynnä muuta sellaista "),
    (r"\boy\.", r"osakeyhtiö "),
    (r"\s+ry\.", r" rekisteröity yhdistys "),
    (r"\s+mm\.", r" muun muassa "),
    (r"\bmrd\. mk\.", r"miljardia markkaa "),
    (r"\bmrd\.", r"miljardia "),
    (r"\bmilj\.", r"miljoonaa "),
    (r"\bvas\.", r"vasemmistoliitto "),
    (r"\bvihr\.", r"vihreä liitto "),
    (r"\bV65\b", r"vee kuusi viisi "),
    (r"\be. ?Kr.", r"ennen kristusta "),
    (r"\beKr\.?", r"ennen kristusta "),
    (r"\bks\. ?ed.", r"kansanedustaja "),
    (r"\bpj\. ?ed.", r"puheenjohtaja "),
    (r"\b[Tt]oim\. ?joht.", r"toimitusjohtaja "),
    (r"\b[Oo]pett\. ?", r"opettaja "),
    (r"\b[Pp]uh\. ?joht.", r"puheenjohtaja "),
    (r"\b[Kk]auppat\.", r"kauppatieteiden "),
    (r"\b[Kk]asvatustiet\.", r"kasvatustieteiden "),
    (r"\b[Vv]altiotiet\.", r"valtiotieteiden "),
    (r"\b[Ll]ääket\.", r"lääketieteen "),
    (r"\b[Mm]aist\.", r"maisteri "),
    (r"\b[Ll]is\.", r"lisensiaatti "),
    (r"(\d+)\s+hv\b", r"\1 hevosvoimaa"),
    (r"(\d+)\s+g\s+(?!§)", r"\1 grammaa"),
    (r"(\d+)\s+mg\b", r"\1 milligrammaa"),
    (r"(\d+)\s+dl\b", r"\1 desilitraa"),
    (r"(\d+)\s+l\b", r"\1 litraa"),
    (r"(\d+)\s+bar\b", r"\1 baaria"),
    (r"(\d+)\s+kg\b", r"\1 kilogrammaa"),
    (r"(\d+)\s+km\b", r"\1 kilometriä"),
    (r"(\d+)\s+kk\b", r"\1 kuukautta"),
    (r"(\d+)\s+mm\b", r"\1 millimetriä"),
    (r"(\d+)\s+cm\b", r"\1 senttimetriä"),
    (r"(\d+)\s+min\b", r"\1 minuuttia"),
    (r"(\d+)\s+m\b", r"\1 metriä"),
    (r"(\d+)\s+h\b", r"\1 tuntia"),
    (r"(\d+)\s+mk\b", r"\1 markkaa"),
    (r"(\d+)\s*v\b", r"\1 vuotta"),
    (r"\.000(?=\D)", r"000"),
    (r"-(\d+)\s", r"miinus \1"),
    (r" (\d)\.0", r" \1 piste nolla"),
    # Eduskunta-aineiston erikoistapauksia = Some parliament data special cases
    (r"AM/121", r"am yksi kaksi yksi"),
    (r"112-", r"yksi yksi kaksi "),
    (r"Sr2:ia", r"sr kakkosia"),
    (r"Sr3:ia", r"sr kolmosia"),
    # Separate letter-digit codes which begin with a capital letter (H5N8 -> H 5N 8, K18 -> K 18)
    # [the '5N' is separated by a later regex]
    (r"([a-zA-Z]+)(\d+)", r"\1 \2"),
    # Kaikki pykälämerkit ja niihen liittyvät numerot = Catch section symbol and all
    # associated numbers
    (
        r"((?:\d+(?: [a-z])?, )*\d+(?: [a-z])?(?:—|-| ja ))?(\d+(?: *[a-z])?) *§:?([a-zåäö]*)",
        expand_section_sign,
    ),
    # Ruotsinkielisessä tekstissä pykälämerkki tulee ennen numeroa. Käsitellään toistaiseksi näin
    # koska pelkällä poistolla virheet edellisessä regexpissä jäävät huomaamatta = This format
    # appears in Swedish texts, handle like this for now so errors with above regexp aren't missed
    (r"§ (\d+)", r"\1"),
    # Taivutetut numerot = Handle numbers with inflections attached
    (
        r"(\d+[/+,.–—-])?(\d+):([a-zåäö]+)\b",
        map_suffix_to_inflection,
    ),
    # Ykkös- ja kakkosluokkalaisten tapaus = Exception in pronouncing school classes
    (
        r"(?:(\d+)[. -]*(—|ja )?)?(\d+)[. ]*-(luokkal)",
        school_classes,
    ),
    # Numerovälit = Number ranges
    (r"((?:\d+[. ]*)+)[–—-]+((?:\d+[. ]*)+)", r"\1 viiva \2"),
    # Eduskunnan dokumenttinumerot = Document numbers in parliament (the second number = year
    # and the committee abbreviation in the beginning are usually not pronounced)
    (r"[A-Z][a-zA-Z]{1,2}[A-Z]{0,2} (\d+)\/\d+(?: vp)?", r" \1#NOM"),
    # Budjetin kohta
    (r"(moment[a-z]+) (\d{2})\.(\d{2})\.(\d{2})", r"\1 \2#NOM \3#NOM \4#NOM"),
    # Päivämäärät = Dates
    (r"(\d+)\s*\.\s*(\d+)\s*\.", r" \1#JNOM \2#JPAR "),
    # Numerot joissa välimerkkejä = Numbers with punctuation
    (r"(\d+)\.(\d+)", r"\1 piste \2"),
    (r"(\d+),(\d+)", r"\1 pilkku \2"),
    (r"(\d+)\/(\d+)", r"\1 kautta \2"),
    (r"\+", r" plus "),
    (r"(\d+):(\d+)", r"\1#GEN suhde \2#ILL"),
    # Numeroitu luettelo = Numbered list item
    (r"(\d+)\)", r"\1#NOM"),
    # Separate codes which start with a digit and are combined with combined capital letters.
    # May also contain inflections (3G:tä -> 3 G tä, 3D:ssä -> 3 D ssä)
    (r"(\d)([A-Za-zåäö]+):?([a-zåäö]+)?", r"\1#NOM \2 \3"),
    # Separate when number and word are accidentally missing a space between
    (r"(\d+)([a-z]+)", r"\1 \2"),
    # Nollalla alkavat numerot erikseen = Separate numbers that begin with a zero
    (r"(?<![0-9])(0\d*)(#[A-Z#]+)?", r"\1#ERI"),
    # Expand numbers to correct case
    (
        r"(\d+\.? (?:viiva|pilkku|piste) )?(\d+\.?)\s+([A-Za-zåäö-]+)",
        number_word_pair_inflection,
    ),
    # Muuta järjestyslukujen sijamuodot = Change to ordinal if number is followed by a period
    (r"(\d+)\.\#([A-Z]+\b)", r"\1#J\2"),
    # 12. [a-z] -> kahdestoista
    (r"(\d+)\.\s+([a-zäöå])", r"\1#JNOM \2"),
    # Sanaa momentti ja kohta edeltävät luvut ovat järjestysnumeroita vaikka niissä ei ole pistettä
    (
        r"((?:\d+, )*\d+(?:—|-| ja ))?(\d+)#?([A-Z]{3})?\s+(moment|koh[dt]|artikl)",
        change_to_ordinal,
    ),
    # Lavenna jäljellä olevat numerot = Expand remaining numbers
    (r"(\d+)\#?([A-Z]+)?", num_fi.expand),
    # Väliviivat sanarajoiksi = Use hyphens as word boundaries
    (r"[–—‑-]+", r" "),
    # Ilmiselviä välimerkkejä lauserajoiksi = Turn obvious punctuation to sentence boundaries
    (r"[.:?!]\s+", r"\n"),
    # Muut välimerkit = Other punctuation
    (r"[!\?;…\/]", r"\n"),
    (r"[>¤¶†ªðÐº¨¦¾Þ\\©®þ\«,­¸:_\»<=&\*()\]¿¡#@~\"'`´‘’“”]", r""),
    (r"\s?—\s?", r" "),
    # Loput pisteet pois = Remove rest of periods
    (r"\.", r" "),
    # Strip any remaining extra spaces and turn output into one long line of text
    (r"^\s+", r""),
    (r"\s+", r" "),
    (r" $", r""),
    # Lowercase all
    (r"^.*$", lowercase),
]

TRANSLATIONS = {
    "à": "a",
    "á": "a",
    "â": "a",
    "ã": "a",
    "é": "e",
    "è": "e",
    "ë": "e",
    "ê": "e",
    "í": "i",
    "ì": "i",
    "ï": "i",
    "î": "i",
    "ó": "o",
    "ò": "o",
    "õ": "o",
    "ô": "o",
    "ü": "u",
    "ú": "u",
    "ù": "u",
    "û": "u",
    "ý": "y",
    "ÿ": "y",
    "ç": "c",
    "ć": "c",
    "č": "c",
    "ñ": "nj",
    "ø": "ö",
    "æ": "ä",
    "š": "s",
    "ß": "ss",
    # Weird special characters encountered in Swedish text
    "ı": "i",
    "ﬁ": "fi",
    "ﬂ": "fl",
}
