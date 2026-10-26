"""Which fetched documents are worth an extraction prompt. A document is relevant when its title or
text names the South China Sea or a feature in it: a term from TERMS (the sea, its parts, the
island groups, the dispute's vocabulary and the agencies, in the claimants' languages) or a
gazetteer name the gazetteer itself would match (`pipeline.gazetteer.usable_name`, same folding and
word boundaries). The filter is deliberately loose — it exists to spare the extractor the budget
speeches and hospital openings that general news feeds carry, not to judge assertiveness; a
relevant document with nothing in it costs one prompt and yields no candidate, while a wrongly
dropped document is lost, so the term list errs wide.

`select` also applies a per-run cap, taken round-robin across sources (newest first within each),
so that a few busy news feeds cannot crowd out the agency listings; the documents over the cap are
deferred and fetched again next run (the state mechanism retries them), the irrelevant ones are not."""
from __future__ import annotations

import re
from functools import lru_cache

from pipeline import gazetteer
from pipeline.gazetteer import _fold

# Latin terms match on word boundaries after accent folding and casefolding; CJK terms anywhere.
TERMS = [
    # the sea and its parts
    "South China Sea", "West Philippine Sea", "East Sea", "Bien Dong", "Biển Đông", "Laut China Selatan", "Laut Cina Selatan",
    "Laut Tiongkok Selatan", "Laut Natuna Utara", "North Natuna Sea", "Natuna", "Gulf of Tonkin", "Vinh Bac Bo", "Vịnh Bắc Bộ", "Beibu Gulf",
    "南海", "南中国海", "南沙", "西沙", "中沙", "东沙", "東沙", "黄岩岛", "黃岩島", "北部湾", "北部灣",
    # island groups
    "Spratly", "Spratlys", "Paracel", "Paracels", "Pratas", "Dongsha", "Nansha", "Xisha", "Zhongsha", "Macclesfield",
    "Scarborough", "Huangyan", "Truong Sa", "Trường Sa", "Hoang Sa", "Hoàng Sa", "Kalayaan", "Kepulauan Spratly",
    # the dispute's vocabulary
    "nine-dash line", "nine dash line", "ten-dash line", "U-shaped line", "đường lưỡi bò", "九段线", "九段線",
    "arbitral award", "arbitration award", "arbitral tribunal", "UNCLOS", "maritime militia",
    "exclusive economic zone", "EEZ", "EEZs", "ZEE", "zona ekonomi eksklusif", "vùng đặc quyền kinh tế", "专属经济区", "專屬經濟區",
    "continental shelf", "thềm lục địa", "fishing ban", "fishing moratorium", "lệnh cấm đánh bắt cá", "water cannon", "vòi rồng",
    # the agencies
    "China Coast Guard", "Chinese coast guard", "coast guard", "coastguard", "hải cảnh", "海警", "Philippine Coast Guard",
    "Pengawal Pantai China", "Pengawal Pantai Tiongkok", "Bakamla", "MMEA", "APMM", "Maritime Enforcement Agency",
    "Maritim Malaysia", "Agensi Penguatkuasaan Maritim", "海巡署", "Cảnh sát biển",
    # features often named without a group word
    "Second Thomas", "Ayungin", "Ren'ai", "Sierra Madre", "Thitu", "Pag-asa", "Reed Bank", "Recto Bank", "Sabina",
    "Escoda", "Mischief Reef", "Fiery Cross", "Subi", "Luconia", "Beting Patinggi Ali", "James Shoal", "Beting Serupai",
    "Layang-Layang", "Swallow Reef", "Itu Aba", "Taiping", "太平島", "太平岛", "Vanguard Bank", "Bãi Tư Chính",
]

_CJK = re.compile(r"[一-鿿]")


@lru_cache(maxsize=1)
def _patterns() -> tuple[re.Pattern, list[str]]:
    """One regex for every Latin term and usable gazetteer name (folded, bounded by non-alphanumerics
    as the gazetteer bounds its names, so "Spratly-based" matches), and the CJK terms and names,
    matched as substrings."""
    latin, cjk = set(), set()
    for t in TERMS:
        (cjk if _CJK.search(t) else latin).add(t)
    for feat in gazetteer.load().values():
        for name in feat["names"]:
            if gazetteer.usable_name(name):
                (cjk if _CJK.search(name) else latin).add(name)
    alts = sorted({re.escape(_fold(t)) for t in latin}, key=len, reverse=True)
    return re.compile(r"(?<![a-z0-9])(?:" + "|".join(alts) + r")(?![a-z0-9])"), sorted(cjk, key=len, reverse=True)


def is_relevant(capture: dict) -> bool:
    """Whether the capture's title or text names the sea, a part of it, a feature or the dispute's
    vocabulary. Looks at the whole captured text (the fetcher's 20,000-character cut), which is also
    what the prompt carries."""
    text = f"{capture.get('title', '')}\n{capture.get('text', '')}"
    if not text.strip():
        return False
    pattern, cjk = _patterns()
    if pattern.search(_fold(text)):
        return True
    return any(term in text for term in cjk)


def _newest_first(captures: list[dict]) -> list[dict]:
    """Publication date, then fetch time (listing pages carry no publication date), then id."""
    return sorted(captures, key=lambda c: (c.get("published") or "", c.get("fetched_at") or "", c.get("capture_id", "")), reverse=True)


def select(captures: list[dict], max_documents: int = 0, everything: bool = False) -> tuple[list[dict], list[dict], list[dict]]:
    """(selected captures, irrelevant captures, deferred captures). The cap is shared round-robin
    across sources, each source's documents newest first, so every source with documents gets a
    prompt before any source gets a second; max_documents 0 means no cap; everything=True skips
    the relevance filter (every document gets a prompt)."""
    relevant = captures if everything else [c for c in captures if is_relevant(c)]
    chosen = {id(c) for c in relevant}
    irrelevant = [c for c in captures if id(c) not in chosen]
    by_source: dict[str, list[dict]] = {}
    for c in _newest_first(relevant):
        by_source.setdefault(c.get("source_id", ""), []).append(c)
    selected: list[dict] = []
    queues = [by_source[s] for s in sorted(by_source)]
    while queues and (not max_documents or len(selected) < max_documents):
        for q in list(queues):
            if max_documents and len(selected) >= max_documents:
                break
            selected.append(q.pop(0))
            if not q:
                queues.remove(q)
    taken = {id(c) for c in selected}
    deferred = [c for c in _newest_first(relevant) if id(c) not in taken]
    return selected, irrelevant, deferred
