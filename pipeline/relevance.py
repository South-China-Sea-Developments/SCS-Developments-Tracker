"""Which fetched documents are worth an extraction prompt. A document is relevant when its title or
text names the South China Sea or a feature in it: a term from TERMS (the sea, its parts and the
dispute's vocabulary in the claimants' languages) or a gazetteer name the gazetteer itself would
match (`pipeline.gazetteer.usable_name`). The filter is deliberately loose — it exists to spare the
extractor the budget speeches and hospital openings that general news feeds carry, not to judge
assertiveness; a relevant document with nothing in it costs one prompt and yields no candidate.

`select` also applies a per-run cap, newest first; the documents over the cap are deferred and
fetched again next run (the state mechanism retries them), the irrelevant ones are not."""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from pipeline import gazetteer

# Sea-level names and dispute vocabulary. Latin terms match on word boundaries after accent
# folding and casefolding; CJK terms match anywhere.
TERMS = [
    # the sea and its parts
    "South China Sea", "West Philippine Sea", "East Sea", "Bien Dong", "Biển Đông", "Laut China Selatan", "Laut Cina Selatan",
    "Laut Natuna Utara", "North Natuna Sea", "Natuna", "Gulf of Tonkin", "Vinh Bac Bo", "Vịnh Bắc Bộ", "Beibu Gulf",
    "南海", "南中国海", "南沙", "西沙", "中沙", "东沙", "東沙", "黄岩岛", "黃岩島", "北部湾", "北部灣",
    # island groups
    "Spratly", "Spratlys", "Paracel", "Paracels", "Pratas", "Dongsha", "Nansha", "Xisha", "Zhongsha", "Macclesfield",
    "Scarborough", "Huangyan", "Truong Sa", "Trường Sa", "Hoang Sa", "Hoàng Sa", "Kalayaan", "Kepulauan Spratly",
    # the dispute's vocabulary
    "nine-dash line", "nine dash line", "ten-dash line", "U-shaped line", "đường lưỡi bò", "九段线", "九段線",
    "arbitral award", "arbitration award", "arbitral tribunal", "UNCLOS", "maritime militia",
    "China Coast Guard", "Chinese coast guard", "hải cảnh", "海警", "coast guard", "Philippine Coast Guard", "Bakamla",
    "MMEA", "APMM", "Maritime Enforcement Agency", "海巡署", "Cảnh sát biển", "exclusive economic zone", "EEZ", "ZEE",
    "zona ekonomi eksklusif", "vùng đặc quyền kinh tế", "专属经济区", "專屬經濟區", "continental shelf", "thềm lục địa",
    "fishing ban", "fishing moratorium", "lệnh cấm đánh bắt cá", "water cannon", "vòi rồng",
    "Second Thomas", "Ayungin", "Ren'ai", "Sierra Madre", "Thitu", "Pag-asa", "Reed Bank", "Recto Bank", "Sabina",
    "Escoda", "Mischief Reef", "Fiery Cross", "Subi", "Luconia", "Beting Patinggi Ali", "James Shoal", "Beting Serupai",
    "Layang-Layang", "Swallow Reef", "Itu Aba", "Taiping", "太平島", "太平岛", "Vanguard Bank", "Bãi Tư Chính",
]

_CJK = re.compile(r"[一-鿿]")


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).replace("Đ", "D").replace("đ", "d")
    return "".join(c for c in s if not unicodedata.combining(c)).casefold()


@lru_cache(maxsize=1)
def _patterns() -> tuple[re.Pattern, list[str]]:
    """One regex for every Latin term and usable gazetteer name (word-bounded, folded), and the
    list of CJK terms and names (matched as substrings)."""
    latin, cjk = set(), set()
    for t in TERMS:
        (cjk if _CJK.search(t) else latin).add(t)
    for feat in gazetteer.load().values():
        for name in feat["names"]:
            if gazetteer.usable_name(name):
                (cjk if _CJK.search(name) else latin).add(name)
    alts = sorted({re.escape(_fold(t)) for t in latin}, key=len, reverse=True)
    return re.compile(r"(?<![\w-])(?:" + "|".join(alts) + r")(?![\w-])"), sorted(cjk, key=len, reverse=True)


def is_relevant(capture: dict) -> bool:
    text = f"{capture.get('title', '')}\n{capture.get('text', '')}"
    if not text.strip():
        return False
    pattern, cjk = _patterns()
    if pattern.search(_fold(text)):
        return True
    return any(term in text for term in cjk)


def select(captures: list[dict], max_documents: int = 0, everything: bool = False) -> tuple[list[dict], list[str], list[str]]:
    """(selected captures newest first, irrelevant capture ids, deferred capture ids). max_documents
    0 means no cap; everything=True skips the relevance filter (every document gets a prompt)."""
    order = sorted(captures, key=lambda c: (c.get("published") or "", c.get("capture_id", "")), reverse=True)
    relevant = order if everything else [c for c in order if is_relevant(c)]
    irrelevant = [c["capture_id"] for c in order if c not in relevant]
    if max_documents and len(relevant) > max_documents:
        return relevant[:max_documents], irrelevant, [c["capture_id"] for c in relevant[max_documents:]]
    return relevant, irrelevant, []
