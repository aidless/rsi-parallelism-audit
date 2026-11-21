#!/usr/bin/env python3
"""T9 量表：验证器是不是「论文的主要贡献」——三档占比（P1 标题级 / P2 贡献句级 / P3 配角级）。

与 T6 的区别：T6 只量「摘要里出现 verifier 类词」；本脚本量的是「verifier 位于贡献断言位置」。
召回靠 arXiv API 的宽查询（ti:/abs: 词命中），判据靠本地严格正则 + 成分扫描（不信任 arXiv 的词干化）。

分档（互斥，优先级 P1 > P2 > P3）：
  P1 标题级：标题含 verifier|evaluator|judge|reward model|critic|rubric（标题命中即 P1，且不计 P3）
  P2 贡献句级：摘要中 ①"we/our ... (propose|introduce|present|develop|build) <verb-object>" 且该宾语的中心名词是
             verifier 类词（宾语里出现 benchmark/dataset/framework... 等竞争中心名词则否）；或 ②"a/the <verifier 类词> that/which"
             且不是被 use/require/with/via 等「使用类」谓语支配的定语从句。
  P3 配角级：摘要命中 verifier 类词，但不满足 P1/P2。
未命中：摘要与标题都没有 verifier 类词（不该出现在 abs 抽样里，出现即记为 NONE 并单独计数）。

计数口径：
  total      = arXiv API 对 (cat:cs.AI OR cat:cs.CL) AND submittedDate:[lo TO hi] 的 totalResults（精确）
  p1_api     = 标题 OR 查询的 totalResults（宽召回，含 judge→judgement 之类的词干噪声）
  p1_exact   = 把 p1_api 的全部候选分页拉回、本地正则复核后的条数（精确到「API 召回集内」）
  abs_api    = 摘要命中集的 totalResults（P2/P3 的定义域）
  p2/p3      = 对 abs_api 做确定性随机抽样（seed 固定），抽 n 条本地分档，按比例外推；附 Wilson 95% CI
  per_10k    = 10000 * 计数 / total

用法：
  python3 verifier_share.py --self-test
  python3 verifier_share.py --quarters 2025Q4 2026Q1 2026Q2 2026Q3 --out outputs
  python3 verifier_share.py --agreement outputs/review_sample.jsonl outputs/review_labels.json
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

NS = {"a": "http://www.w3.org/2005/Atom", "o": "http://a9.com/-/spec/opensearch/1.1/"}
API = "https://export.arxiv.org/api/query"
UA = "t9-verifier-share/1.0 (academic bibliometrics; local research)"

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

# 标题侧保持宽召回；摘要侧把裸 "judge" 换成 "LLM judge"/"judge model"：
# 2025Q4 实测 abs:"judge" 把 8303 条召回进来，200 条随机抽样里只有 19 条本地真含 verifier
# 类词（其余是 judgement/judging/evaluation 等词干噪声），会把 P2 外推成 0。
TITLE_TERMS = ["verifier", "evaluator", "judge", "reward model", "critic", "rubric"]
ABS_TERMS = ["verifier", "evaluator", "LLM judge", "judge model", "reward model", "critic", "rubric"]

# ---- 本地判据 -----------------------------------------------------------------
# verifier 类词（多词项必须先匹配、并从宾语里「挖掉」，否则 "reward model" 里的 model
# 会被下游误当成竞争中心名词）
VER_RE = re.compile(
    r"\b(reward[-\s]models?|judge[-\s]models?|llm[-\s]as[-\s]a[-\s]judges?|"
    r"verifiers?|evaluators?|judges?|critics?|rubrics?)\b",
    re.I,
)
# 标题级：只认单词/短语本身，不收 "critical"/"critique"/"judgement" 这类同形词
TITLE_RE = re.compile(
    r"\b(verifiers?|evaluators?|judges?|judge[-\s]models?|reward[-\s]models?|critics?|rubrics?)\b",
    re.I,
)
# 竞争中心名词：宾语里出现这些词，说明 verifier 只是修饰语或从属成分，不是被提出的对象
RIVAL_RE = re.compile(
    r"\b(benchmarks?|datasets?|data[-\s]?sets?|corpus|corpora|suites?|frameworks?|pipelines?|"
    r"systems?|methods?|approaches?|techniques?|algorithms?|networks?|modules?|toolkits?|tools?|"
    r"librar(?:y|ies)|platforms?|environments?|agents?|tasks?|protocols?|schemes?|"
    r"objectives?|functions?|budgets?|schedules?)\b",
    re.I,
)
CONTRIB_RE = re.compile(r"\bwe\b(?:\s+[a-z][a-z-]*){0,3}?\s+(propose|introduce|present|develop|build)\b", re.I)
# 宾语边界：遇到这些词/标点就截断
BOUNDARY_RE = re.compile(
    r"(?:\b(?:that|which|who|whom|whose|where|when|while|and|or|but|for|with|using|via|by|to|"
    r"so\s+that|in\s+order\s+to)\b|[,;:.!?])",
    re.I,
)
# 同位语式：必须是 "a/the <verifier 类词> that/which ..." —— 缺了关系代词就退化成
# "a critic network" 这类修饰结构（本轮 self-test 的 FAIL 就是它，见 outputs/README.md）
APPOS_RE = re.compile(
    r"\b(?:a|an|the)\s+(?:[a-z][a-z-]*\s+){0,2}?" + VER_RE.pattern + r"\s+(?:that|which)\b",
    re.I,
)
USE_VERB_RE = re.compile(
    r"\b(?:uses?|used|using|utiliz\w+|employ\w*|rel(?:y|ies|ied)|requires?|requiring|contain\w*|"
    r"includ\w*|incorporat\w*|leverage\w*|quer(?:y|ies|ied)|invokes?|calls?|with|via|by)\b",
    re.I,
)
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|;\s+")


def sentences(text: str) -> list[str]:
    return [s.strip() for s in SENT_SPLIT.split(text or "") if s.strip()]


def mask_verifier(obj: str) -> tuple[str, bool]:
    """把 verifier 类词挖成 <V>，返回 (masked, 是否有命中)。"""
    hit = False
    spans = []
    for m in VER_RE.finditer(obj):
        spans.append(m.span())
        hit = True
    if not hit:
        return obj, False
    out, last = [], 0
    for lo, hi in spans:
        out.append(obj[last:lo])
        out.append(" <V> ")
        last = hi
    out.append(obj[last:])
    return "".join(out), True


def object_of(tail: str) -> str:
    """取贡献动词之后的直接宾语短语（到第一个边界为止）。"""
    tail = " " + tail.strip()
    m = BOUNDARY_RE.search(tail, 1)
    obj = tail[: m.start()] if m else tail[:80]
    return obj.strip()


def p2_by_contrib_verb(sent: str) -> str | None:
    for m in CONTRIB_RE.finditer(sent):
        obj = object_of(sent[m.end():])
        if not obj:
            continue
        masked, has_v = mask_verifier(obj)
        if not has_v:
            continue
        if RIVAL_RE.search(masked):
            continue  # 'a new benchmark (that uses a verifier)' / 'a verifier network'
        return f"contrib:{m.group(1).lower()}:{obj[:60]}"
    return None


def p2_by_appositive(sent: str) -> str | None:
    has_contrib = bool(CONTRIB_RE.search(sent))
    for m in APPOS_RE.finditer(sent):
        pre = sent[: m.start()]
        if USE_VERB_RE.search(pre[-70:]):
            continue  # 'our pipeline uses a verifier that ...' -> 配角
        # 同位语：前面是 'Name, ' 形式，或同句里有贡献动词
        if has_contrib or re.search(r",\s*$", pre[-3:]):
            return f"appositive:{m.group(0)[:60]}"
    return None


def classify(title: str, abstract: str) -> tuple[str, str]:
    """返回 (tier, reason)；tier ∈ {P1,P2,P3,NONE}。"""
    if TITLE_RE.search(title or ""):
        m = TITLE_RE.search(title)
        return "P1", f"title:{m.group(0).lower()}"
    if not VER_RE.search(abstract or ""):
        return "NONE", "no-verifier-term"
    for s in sentences(abstract):
        if not VER_RE.search(s):
            continue
        r = p2_by_contrib_verb(s)
        if r:
            return "P2", r
        r = p2_by_appositive(s)
        if r:
            return "P2", r
    return "P3", "mentioned-only"


# 反证用「朴素判据」：只要 we+贡献动词 与 verifier 词同句就判 P2（会误吃陷阱样本）
def classify_naive(title: str, abstract: str) -> str:
    if TITLE_RE.search(title or ""):
        return "P1"
    for s in sentences(abstract):
        if re.search(
            r"\bwe\b(?:\s+\w+){0,3}?\s+(?:propose|introduce|present|develop|build)\b.{0,90}"
            r"(?:verifier|evaluator|judge|critic|rubric|reward model)",
            s,
            re.I,
        ):
            return "P2"
    if VER_RE.search(abstract or ""):
        return "P3"
    return "NONE"


SELFTEST_CASES = [
    # (title, abstract, expected_tier, note)
    ("A Verifier for Step-Wise Mathematical Reasoning",
     "We propose a verifier that filters incorrect intermediate steps.",
     "P1", "标题级优先于贡献句级"),
    ("Scaling Test-Time Compute",
     "We propose a verifier that filters incorrect intermediate steps.",
     "P2", "真阳：贡献动词 + verifier 作直接宾语"),
    ("Scaling Test-Time Compute",
     "Our pipeline uses a verifier to check each candidate answer.",
     "P3", "真阴：uses 支配，非贡献"),
    ("A New Benchmark for Code Review",
     "We propose a new benchmark for code review and release it publicly.",
     "NONE", "真阴：全文无 verifier 类词"),
    ("A New Benchmark for Code Review",
     "We propose a new benchmark that uses a verifier at inference time.",
     "P3", "陷阱：benchmark 是贡献对象，verifier 只是工具"),
    ("Learning from Preferences",
     "We introduce an LLM-based evaluator trained on human preference pairs.",
     "P2", "真阳：introduce + 复合名词宾语，中心名词是 evaluator"),
    ("Reward Hacking Revisited",
     "This paper studies reward hacking; we build a critic network from scratch.",
     "P3", "陷阱：critic 修饰 network，中心名词是 network"),
    ("Preference Optimization",
     "We present a rubric that captures fine-grained quality dimensions.",
     "P2", "真阳：present + rubric"),
    ("Code Reward Modeling",
     "We develop a general reward model for code correctness.",
     "P2", "真阳：多词项 reward model 作中心名词"),
    ("Judging Verdicts",
     "Our system relies on a judge that scores responses along five axes.",
     "P3", "真阴：relies on 支配的定语从句"),
    ("Scaling Critique Models",
     "We propose a framework that uses a critic to rank candidate solutions.",
     "P3", "陷阱：framework 是贡献对象"),
    ("VeriReasoner: Better Reasoning",
     "We propose VeriReasoner, a verifier that checks each derivation step.",
     "P2", "真阳：同位语式（名称后接 a verifier that）"),
]

NAIVE_TRAP_CASES = {
    "We propose a new benchmark that uses a verifier at inference time.",
    "We propose a framework that uses a critic to rank candidate solutions.",
    "This paper studies reward hacking; we build a critic network from scratch.",
}


def self_test() -> int:
    ok = True
    rows = []
    for title, abstract, expected, note in SELFTEST_CASES:
        got, reason = classify(title, abstract)
        good = got == expected
        ok &= good
        rows.append((good, expected, got, reason, abstract[:56], note))
        print(f"[{'OK' if good else 'FAIL'}] expect={expected:4} got={got:4} | {abstract[:56]!r} | {note}")

    # 门要能红：朴素判据必须在至少一个陷阱样本上与期望不同，否则这些断言没有牙
    red_cases = 0
    for title, abstract, expected, note in SELFTEST_CASES:
        if abstract in NAIVE_TRAP_CASES:
            naive = classify_naive(title, abstract)
            if naive != expected:
                red_cases += 1
                print(f"[RED] naive={naive} != expect={expected} | {abstract[:56]!r}（朴素判据被此样本否决）")
    if red_cases < 3:
        ok = False
        print(f"[FAIL] 反证不足：朴素判据只被 {red_cases}/3 个陷阱样本否决，断言无牙")

    print(f"\nself-test: {sum(1 for r in rows if r[0])}/{len(rows)} 通过；反证样本 {red_cases}/{len(NAIVE_TRAP_CASES)} 命中")
    return 0 if ok else 2


# ---- arXiv API ----------------------------------------------------------------
def api_query(query: str, start: int = 0, max_results: int = 1, retries: int = 5) -> tuple[int, list[dict]]:
    params = {"search_query": query, "start": start, "max_results": max_results,
              "sortBy": "submittedDate", "sortOrder": "ascending"}
    url = API + "?" + urllib.parse.urlencode(params)
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            raw = urllib.request.urlopen(req, timeout=90).read()
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
                print(f"WARN api failed after {retries} retries: {exc} | {query[:80]}", file=sys.stderr)
                return -1, []
            time.sleep(min(90, 20 * (attempt + 1)))
    return -1, []


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def quarter_run(q: str, args, out: Path, ev_file, sample_file, review_pool: dict) -> dict:
    """每季 2 次 API 请求：base 取 total；union 查询随机偏移取 n 条，本地分档后按比例外推。"""
    lo, hi = QUARTERS[q]
    base = f"(cat:cs.AI OR cat:cs.CL) AND submittedDate:[{lo} TO {hi}]"
    total, _ = api_query(base, 0, 1)
    if total < 0:
        raise RuntimeError(f"API failed while fetching total for {q}")
    print(f"[{q}] total={total}")
    time.sleep(args.sleep)

    ti = " OR ".join(f'ti:"{t}"' for t in TITLE_TERMS)
    ab = " OR ".join(f'abs:"{t}"' for t in ABS_TERMS)
    union = f"{base} AND (({ti}) OR ({ab}))"
    time.sleep(args.sleep)
    union_api, _ = api_query(union, 0, 1)
    if union_api < 0:
        raise RuntimeError(f"API failed while fetching union total for {q}")
    rnd = random.Random(f"{args.seed}|{q}")
    span = max(1, args.sample_pages) * args.page
    off = rnd.randrange(0, max(1, union_api - span + 1))
    sample = []
    for i in range(max(1, args.sample_pages)):
        page_off = off + i * args.page
        if page_off >= union_api:
            break
        time.sleep(args.sleep)
        _, page = api_query(union, page_off, args.page)
        sample.extend(page)
        print(f"[{q}] union_api={union_api} offset={page_off} fetched={len(page)}")
        if not page:
            break
    if not sample:
        raise RuntimeError(f"empty sample for {q}")

    tiers = {"P1": 0, "P2": 0, "P3": 0, "NONE": 0}
    p1_examples, p2_examples, p3_examples = [], [], []
    for r in sample:
        tier, reason = classify(r["title"], r["abstract"])
        tiers[tier] += 1
        sample_file.write(json.dumps({"quarter": q, "tier": tier, "id": r["id"], "title": r["title"],
                                      "reason": reason, "abstract": r["abstract"]},
                                     ensure_ascii=False) + "\n")
        rec = {"quarter": q, "tier": tier, "id": r["id"], "title": r["title"],
               "reason": reason, "snippet": r["abstract"][:280]}
        if tier == "P1":
            p1_examples.append({**r, "reason": reason})
        if tier in {"P1", "P2"} or (tier == "P3" and len(p3_examples) < 8):
            ev_file.write(json.dumps(rec, ensure_ascii=False) + "\n")
        if tier == "P2":
            p2_examples.append({**r, "reason": reason})
        elif tier == "P3" and len(p3_examples) < 8:
            p3_examples.append({**r, "reason": reason})

    n = len(sample)
    est = {t: round(union_api * tiers[t] / n) for t in ("P1", "P2", "P3")}
    ci = {t: wilson(tiers[t], n) for t in ("P1", "P2", "P3")}
    print(f"[{q}] n={n} P1={tiers['P1']} P2={tiers['P2']} P3={tiers['P3']} NONE={tiers['NONE']} "
          f"est P1={est['P1']} P2={est['P2']} P3={est['P3']}")

    r1 = random.Random(f"review1|{q}"); r2 = random.Random(f"review2|{q}")
    review_pool[q] = {
        "P1": r1.sample(p1_examples, min(5, len(p1_examples))),
        "P2": r2.sample(p2_examples, min(5, len(p2_examples))),
    }
    return {
        "quarter": q, "total": total, "union_api": union_api, "sample_n": n,
        "p1_hits": tiers["P1"], "p2_hits": tiers["P2"], "p3_hits": tiers["P3"],
        "none_hits": tiers["NONE"],
        "p1_est": est["P1"], "p2_est": est["P2"], "p3_est": est["P3"],
        "p1_lo": round(ci["P1"][0] * union_api), "p1_hi": round(ci["P1"][1] * union_api),
        "p2_lo": round(ci["P2"][0] * union_api), "p2_hi": round(ci["P2"][1] * union_api),
        "p1_per_10k": round(10000 * est["P1"] / total, 2) if total > 0 else "",
        "p2_per_10k": round(10000 * est["P2"] / total, 2) if total > 0 else "",
        "p3_per_10k": round(10000 * est["P3"] / total, 2) if total > 0 else "",
    }

def agreement(sample_path: Path, labels_path: Path) -> int:
    sample = [json.loads(l) for l in sample_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    labels = json.loads(labels_path.read_text(encoding="utf-8"))
    agree = 0
    judged = 0
    per_tier: dict[str, list[int]] = {}
    for rec in sample:
        lab = labels.get(rec["id"])
        if lab is None:
            continue
        judged += 1
        pred_tier = rec.get("tier_pred", rec.get("tier"))
        # 人判口径：is_tier=yes 表示「确实属于 pred 档」（机器对）；
        # is_tier=no 表示「不属于该档，真实档见 tier」（机器错）；uncertain 计入分母但不计一致。
        ok = (lab["is_tier"] == "yes") and (pred_tier == lab.get("tier", pred_tier))
        agree += ok
        per_tier.setdefault(pred_tier, []).append(int(ok))
        if not ok:
            print(f"[DISAGREE] {rec['id']} pred={pred_tier} human={lab}")
    print(f"agreement: {agree}/{judged} = {agree/judged:.3f}" if judged else "agreement: 无标签")
    for t, v in sorted(per_tier.items()):
        print(f"  {t}: {sum(v)}/{len(v)}")
    return 0 if judged else 2


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true", help="只跑反证自检，不发网络请求")
    ap.add_argument("--agreement", nargs=2, metavar=("SAMPLE", "LABELS"), help="重算本地复核一致率")
    ap.add_argument("--quarters", nargs="+", default=["2025Q4", "2026Q1", "2026Q2", "2026Q3"])
    ap.add_argument("--out", default="outputs")
    ap.add_argument("--page", type=int, default=100, help="每页拉取条数（arXiv 上限 2000，100 更稳）")
    ap.add_argument("--max-p1-pages", type=int, default=3, help="P1 分页上限（超出则标记 truncated；P1 按比例外推）")
    ap.add_argument("--sample-pages", type=int, default=3, help="abs 抽样页数（每页 --page 条）")
    ap.add_argument("--seed", default="t9", help="抽样种子（确定性）")
    ap.add_argument("--sleep", type=float, default=5.0, help="arXiv API 请求间隔秒")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    if args.agreement:
        return agreement(Path(args.agreement[0]), Path(args.agreement[1]))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows, review_pool = [], {}
    with (out / "evidence.jsonl").open("w", encoding="utf-8") as ev, \
         (out / "sample.jsonl").open("w", encoding="utf-8") as sf:
        for q in args.quarters:
            if q not in QUARTERS:
                print(f"ERR unknown quarter {q}", file=sys.stderr)
                return 2
            rows.append(quarter_run(q, args, out, ev, sf, review_pool))

    fields = ["quarter", "total", "union_api", "sample_n", "p1_hits", "p2_hits", "p3_hits", "none_hits",
              "p1_est", "p1_lo", "p1_hi", "p1_per_10k", "p2_est", "p2_lo", "p2_hi", "p2_per_10k",
              "p3_est", "p3_per_10k"]
    with (out / "verifier_share.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})

    with (out / "review_sample.jsonl").open("w", encoding="utf-8") as f:
        for q, pools in review_pool.items():
            for tier, recs in pools.items():
                for r in recs:
                    f.write(json.dumps({"id": r["id"], "quarter": q, "tier_pred": tier,
                                        "reason": r["reason"], "title": r["title"],
                                        "abstract": r["abstract"][:1200]}, ensure_ascii=False) + "\n")

    for r in rows:
        print(f"{r['quarter']}: total={r['total']} P1est={r['p1_est']} ({r['p1_per_10k']}/10k) "
              f"P2est={r['p2_est']} ({r['p2_per_10k']}/10k) P3est={r['p3_est']} ({r['p3_per_10k']}/10k)")
    print("->", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
