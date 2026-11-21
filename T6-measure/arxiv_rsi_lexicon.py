#!/usr/bin/env python3
"""arXiv RSI 词频量表：量"从递归到演化"是不是真的发生了。

三类词（本地严格正则复核，不直接信 arXiv 的词干化命中）：
  ARCH  archive / population-based / lineage / open-ended / novelty search ...
  REC   recursive self-improvement / recursion / self-rewrite / iterative refinement
  VER   verifier / LLM-as-a-judge / acceptance gate / sealed evaluation / audit

每季输出：API 命中数、本地复核数、比例、证据（id/title/命中词/摘要片段）。
自检：注入真阴/真阳样本，必须判对，否则退出码 2（门要能红）。

用法：
  python3 arxiv_rsi_lexicon.py --self-test
  python3 arxiv_rsi_lexicon.py --quarters 2025Q4 2026Q1 2026Q2 2026Q3 --out outputs
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

NS = {"a": "http://www.w3.org/2005/Atom", "o": "http://a9.com/-/spec/opensearch/1.1/"}
API = "https://export.arxiv.org/api/query"

QUARTERS = {
    "2025Q1": ("202501010000", "202503312359"),
    "2025Q2": ("202504010000", "202506302359"),
    "2025Q3": ("202507010000", "202509302359"),
    "2025Q4": ("202510010000", "202512312359"),
    "2026Q1": ("202601010000", "202603312359"),
    "2026Q2": ("202604010000", "202606302359"),
    "2026Q3": ("202607010000", "202609302359"),
    "2026Q4": ("202610010000", "202612312359"),
}

# arXiv 侧查询词（宽，负责召回）；本地正则（严，负责判据）
API_TERMS = {
    "ARCH": ["open-ended", "archive", "population-based", "lineage", "island model", "novelty search"],
    "REC": ["recursive", "recursion", "self-improvement", "self-rewrite", "iterative refinement"],
    "VER": ["verifier", "LLM judge", "acceptance gate", "sealed", "audit"],
}

LOCAL_PATTERNS = {
    "ARCH": {
        "open-ended": re.compile(r"\bopen[\s-]?ended(ness)?\b", re.I),
        "population-based": re.compile(r"\bpopulation[\s-]?based\b", re.I),
        "archive-of-agents": re.compile(r"\barchive\s+of\s+(?:coding\s+|generated\s+|diverse\s+)?(?:agents?|versions?|candidates?|skills?|ideas?|programs?)\b", re.I),
        "maintains-archive": re.compile(r"\bmaintains?\s+an?\s+(?:growing\s+)?archive\b", re.I),
        "lineage": re.compile(r"\blineages?\b", re.I),
        "island-model": re.compile(r"\bisland\s+models?\b", re.I),
        "novelty-search": re.compile(r"\bnovelty\s+search\b", re.I),
    },
    "REC": {
        "recursive-self-improvement": re.compile(r"\brecursive[\s-]+self[\s-]?improvement\b", re.I),
        "recursion": re.compile(r"\brecursions?\b|\brecursive\b", re.I),
        "self-rewrite": re.compile(r"\bself[\s-]?rewri(te|ting|tten)\b", re.I),
        "iterative-refinement": re.compile(r"\biterative(ly)?\s+refin(e|ement|ing)\b", re.I),
        "feedback-loop": re.compile(r"\b(?:feedback|improvement)\s+loops?\b", re.I),
    },
    "VER": {
        "verifier": re.compile(r"\bverifiers?\b", re.I),
        "judge": re.compile(r"\b(?:llm[\s-]?as[\s-]?a[\s-]?judge|judge\s+models?|grader)\b", re.I),
        "acceptance-gate": re.compile(r"\bacceptance\s+gates?\b|\bheld[\s-]?out\s+(?:set|gate|test)\b", re.I),
        "sealed-eval": re.compile(r"\b(?:sealed|private)\s+(?:test|set|evaluation|benchmark)\b", re.I),
        "audit": re.compile(r"\baudit(?:ing|ed|s)?\b", re.I),
        "evaluator": re.compile(r"\bevaluators?\b", re.I),
    },
}

# 判据：ARCH 需 ≥1 个强信号（泛词 "archive/lineage" 单独出现不算，避免把 arXiv 的 "archive" 误计）
ARCH_STRONG = {"open-ended", "population-based", "archive-of-agents", "maintains-archive",
               "island-model", "novelty-search"}

SELFTEST_CASES = [
    # (摘要, 类别, 期望：是否命中)
    ("We study population dynamics in a biological ecology model.", "ARCH", False),
    ("The system is described in an earlier technical archive on our website.", "ARCH", False),
    ("We maintain an archive of generated coding agents and evolve it via novelty search.", "ARCH", True),
    ("Recursive self-improvement of the agent is measured on a sealed private test set.", "REC", True),
    ("We fine-tune a transformer and report accuracy on a public benchmark.", "REC", False),
    ("A verifier and an LLM-as-a-judge independently score each candidate.", "VER", True),
    ("The audit trail is verified by a hash chain.", "VER", True),
    ("The dataset is available on arXiv; we report the mean and variance.", "VER", False),
]


def local_match(text: str, category: str) -> list[str]:
    hits = []
    for name, pat in LOCAL_PATTERNS[category].items():
        if pat.search(text):
            hits.append(name)
    if category == "ARCH" and not any(h in ARCH_STRONG for h in hits):
        return []  # 只有弱信号，不算
    return hits


def self_test() -> bool:
    ok = True
    for text, cat, expected in SELFTEST_CASES:
        got = bool(local_match(text, cat))
        flag = "OK" if got == expected else "FAIL"
        if got != expected:
            ok = False
        print(f"[{flag}] expect={expected!s:5} got={got!s:5} {cat:4} | {text[:62]}")
    return ok


def api_query(query: str, max_results: int, retries: int = 2) -> tuple[int, list[dict]]:
    url = API + "?" + urllib.parse.urlencode(
        {"search_query": query, "start": 0, "max_results": max_results}
    )
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "rsi-lexicon/1.0 (research)"})
            raw = urllib.request.urlopen(req, timeout=45).read()
            root = ET.fromstring(raw)
            total = int(root.findtext("o:totalResults", default="0", namespaces=NS))
            rows = []
            for e in root.findall("a:entry", NS):
                eid = (e.findtext("a:id", default="", namespaces=NS) or "").rstrip("/").split("/")[-1]
                rows.append({
                    "id": eid,
                    "title": " ".join((e.findtext("a:title", default="", namespaces=NS) or "").split()),
                    "abstract": " ".join((e.findtext("a:summary", default="", namespaces=NS) or "").split()),
                })
            return total, rows
        except Exception as exc:  # noqa: BLE001
            if attempt == retries:
                print(f"WARN api failed: {exc} | {query[:90]}", file=sys.stderr)
                return -1, []
            time.sleep(3 * (attempt + 1))
    return -1, []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true", help="只跑反证自检，不发网络请求")
    ap.add_argument("--quarters", nargs="+", default=["2025Q4", "2026Q1", "2026Q2", "2026Q3"])
    ap.add_argument("--out", default="outputs")
    ap.add_argument("--sample", type=int, default=100, help="每类每季拉取的最大证据条数")
    ap.add_argument("--sleep", type=float, default=3.0, help="arXiv API 请求间隔秒")
    args = ap.parse_args()

    if args.self_test:
        return 0 if self_test() else 2

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    evidence = []
    rows = []
    for q in args.quarters:
        if q not in QUARTERS:
            print(f"ERR unknown quarter {q}", file=sys.stderr)
            return 2
        lo, hi = QUARTERS[q]
        base = f"(cat:cs.AI OR cat:cs.CL) AND submittedDate:[{lo} TO {hi}]"
        total, _ = api_query(base, 1)
        print(f"{q} total={total}")
        time.sleep(args.sleep)
        rec = {"quarter": q, "total_api": total}
        for cat, terms in API_TERMS.items():
            clause = " OR ".join(f'abs:"{t}"' for t in terms)
            api_total, fetched = api_query(f"{base} AND ({clause})", args.sample)
            local_hits = [(r, local_match(r["abstract"], cat)) for r in fetched]
            local_hits = [(r, h) for r, h in local_hits if h]
            rec[f"{cat.lower()}_api"] = api_total
            rec[f"{cat.lower()}_local_sample"] = len(local_hits)
            for r, h in local_hits:
                evidence.append({
                    "quarter": q, "category": cat, "id": r["id"], "title": r["title"],
                    "matched": h, "snippet": r["abstract"][:280],
                })
            print(f"  {cat}: api={api_total} local(sample {len(fetched)})={len(local_hits)}")
            time.sleep(args.sleep)
        for cat in API_TERMS:
            n = rec[f"{cat.lower()}_api"]
            rec[f"{cat.lower()}_per_10k"] = round(10000 * n / total, 2) if isinstance(n, int) and n >= 0 and total > 0 else None
        rows.append(rec)

    fields = ["quarter", "total_api"] + [f"{c.lower()}_{s}" for c in API_TERMS for s in ("api", "local_sample")] + [f"{c.lower()}_per_10k" for c in API_TERMS]
    with (out / "lexicon_report.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})
    with (out / "evidence.jsonl").open("w", encoding="utf-8") as f:
        for e in evidence:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    by_cat = Counter(e["category"] for e in evidence)
    print("evidence:", dict(by_cat), "->", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
