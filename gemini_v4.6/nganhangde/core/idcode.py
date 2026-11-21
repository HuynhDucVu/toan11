import re
from dataclasses import dataclass

ID_RE = re.compile(
    r"^(?P<lop>[0-9])(?P<mon>[A-Z])(?P<chuong>[0-9A-Z])(?P<muc_do>[NHVCYBKGTR])"
    r"(?:(?P<bai>[0-9A-Z])(?:-(?P<dang>[0-9A-Z]+))?)?$"
)
LEVEL_TO_NHVC = {"N": "N", "Y": "N", "B": "N", "H": "H", "V": "V", "K": "V", "T": "V", "C": "C", "G": "C", "R": "C"}
MATH_LEVEL_MAP = {"N": "N", "Y": "N", "H": "H", "B": "H", "V": "V", "K": "V", "C": "C", "G": "C"}
LEVEL_TO_CV7991 = {"N": "NB", "H": "TH", "V": "VD", "C": "VD"}


@dataclass(frozen=True)
class IDInfo:
    raw: str
    lop: str
    mon: str
    chuong: str
    muc_do: str
    muc_do_cv7991: str
    bai: str
    dang: str


def parse_id(code: str, math_mode: bool = True) -> IDInfo | None:
    clean = code.strip()
    m = ID_RE.match(clean)
    if not m:
        return None
    md_raw = m.group("muc_do")
    mapping = MATH_LEVEL_MAP if math_mode else LEVEL_TO_NHVC
    if md_raw not in mapping:
        return None
    md = mapping[md_raw]
    return IDInfo(
        clean, m.group("lop"), m.group("mon"), m.group("chuong"),
        md, LEVEL_TO_CV7991[md], m.group("bai") or "", m.group("dang") or "",
    )


def extract_ids_and_tags(header_text: str, math_mode: bool = True) -> tuple[list[str], list[str]]:
    ids, tags = [], []
    for lb in re.findall(r"%\[([^\]]+)\]", header_text):
        item = lb.strip()
        if parse_id(item, math_mode=math_mode):
            if item not in ids:
                ids.append(item)
        elif item and item not in tags:
            tags.append(item)
    return ids, tags
