#!/usr/bin/env python3
"""T6 两个量表的独立 cross-check 仪器。

独立实现：不 import 原 arxiv_rsi_lexicon.py / verifier_throughput_rsi.py。
底物：T6-measure/outputs 下 README.md、lexicon_report.csv、evidence.jsonl、
throughput.json、throughput-random.json。所有比较逐项落进报告，mismatches 必须为空。

用法：
  python3 analyses/tracks/rsi-after/T6-deep/crosscheck_measure.py
  python3 analyses/tracks/rsi-after/T6-deep/crosscheck_measure.py --self-test
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import re
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

BASE = Path("analyses/tracks/rsi-after/T6-measure/outputs")
DEFAULT_OUT = Path("analyses/tracks/rsi-after/T6-deep/crosscheck_report.json")
SOURCE_NAMES = [
    "README.md",
    "lexicon_report.csv",
    "evidence.jsonl",
    "throughput.json",
    "throughput-random.json",
]


def sha12(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def jsonable(value):
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, list):
        return [jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    return value


def num(raw: str) -> float:
    s = str(raw).strip().replace("*", "").replace("+", "").replace("%", "").strip()
    return float(s)


def split_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def parse_tables(text: str) -> list[dict]:
    lines = text.splitlines()
    tables: list[dict] = []
    i = 0
    while i < len(lines):
        if not lines[i].lstrip().startswith("|"):
            i += 1
            continue
        block = []
        while i < len(lines) and lines[i].lstrip().startswith("|"):
            block.append(lines[i])
            i += 1
        if len(block) >= 2:
            sep = split_row(block[1])
            if sep and all(set(cell) <= set("-:") for cell in sep):
                tables.append({
                    "header": split_row(block[0]),
                    "rows": [split_row(r) for r in block[2:] if split_row(r)],
                })
    return tables


def parse_slash_seq(raw: str) -> tuple[int, ...]:
    return tuple(int(x) for x in raw.split("/") if x.strip())


def parse_readme_claims(text: str) -> dict:
    claimed: dict = {}
    tables = parse_tables(text)

    lex_tables = [t for t in tables if t["header"] and t["header"][0] == "季度"]
    if len(lex_tables) != 1:
        raise ValueError(f"README lexicon table count != 1: {len(lex_tables)}")
    for row in lex_tables[0]["rows"]:
        if len(row) < 9:
            raise ValueError(f"short lexicon row: {row}")
        q = row[0]
        claimed[f"lex.{q}.total"] = num(row[1])
        claimed[f"lex.{q}.arch_api"] = num(row[2])
        claimed[f"lex.{q}.arch_per_10k"] = num(row[3])
        claimed[f"lex.{q}.rec_api"] = num(row[4])
        claimed[f"lex.{q}.rec_per_10k"] = num(row[5])
        claimed[f"lex.{q}.ver_api"] = num(row[6])
        claimed[f"lex.{q}.ver_per_10k"] = num(row[7])
        claimed[f"lex.{q}.arch_rec_ratio"] = num(row[8])

    tp_tables = [t for t in tables if any("rate/1k" in h for h in t["header"])]
    if len(tp_tables) < 2:
        raise ValueError(f"README throughput table count < 2: {len(tp_tables)}")
    for idx, arm in ((0, "main"), (1, "random")):
        for row in tp_tables[idx]["rows"]:
            if len(row) < 5:
                raise ValueError(f"short throughput row: {row}")
            n = int(num(row[0]))
            claimed[f"tp.{arm}.N{n}.mean_calls"] = num(row[1])
            claimed[f"tp.{arm}.N{n}.mean_delta"] = num(row[2])
            claimed[f"tp.{arm}.N{n}.mean_rate"] = num(row[3])
            claimed[f"tp.{arm}.N{n}.mean_promoted"] = num(row[4])

    patterns = [
        (r"ARCH/万 从 ([\d.]+) 涨到 ([\d.]+)（\+(\d+)%）",
         ["claim.arch_per10k_first", "claim.arch_per10k_last", "claim.arch_growth_pct"]),
        (r"VER/万 从 ([\d.]+) 涨到 ([\d.]+)（\+(\d+)%）",
         ["claim.ver_per10k_first", "claim.ver_per10k_last", "claim.ver_growth_pct"]),
    ]
    for pat, keys in patterns:
        m = re.search(pat, text)
        if not m:
            raise ValueError(f"README inline pattern not found: {pat}")
        for key, raw_value in zip(keys, m.groups()):
            claimed[key] = num(raw_value)

    m = re.search(r"本地复核（每季每类抽 100）：ARCH 命中 ([\d/]+)，REC ([\d/]+)，VER ([\d/]+)", text)
    if not m:
        raise ValueError("README local-sample pattern not found")
    for cat, raw_value in zip(("ARCH", "REC", "VER"), m.groups()):
        claimed[f"claim.local_{cat.lower()}"] = parse_slash_seq(raw_value)

    for label, key in (("open-ended", "claim.open_ended_hits"),
                       ("audit", "claim.audit_hits"),
                       ("verifier", "claim.verifier_hits")):
        m = re.search(rf"`{re.escape(label)}`（(\d+)/(\d+)）", text)
        if not m:
            raise ValueError(f"README hit distribution pattern not found: {label}")
        claimed[key] = (int(m.group(1)), int(m.group(2)))

    m = re.search(r"ARCH/REC 在 (\d{4}Q\d) 跨过 1", text)
    if m:
        claimed["claim.cross_transition_from"] = m.group(1)

    m = re.search(r"速率再降 (\d+)%/(\d+)%", text)
    if m:
        claimed["claim.neg_rate_drop_n4"] = num(m.group(1))
        claimed["claim.neg_rate_drop_n16"] = num(m.group(2))

    m = re.search(r"主 Δ−随机 Δ = ([\d.]+)\(N=4\)/([\d.]+)\(N=16\)", text)
    if m:
        claimed["claim.neg_delta_n4"] = num(m.group(1))
        claimed["claim.neg_delta_n16"] = num(m.group(2))

    return claimed


def compute_lex(csv_rows: list[dict]) -> tuple[dict, dict]:
    computed: dict = {}
    ratios: list[tuple[str, float]] = []
    quarters = [r["quarter"] for r in csv_rows]
    per10k = {"ARCH": {}, "REC": {}, "VER": {}}
    for row in csv_rows:
        q = row["quarter"]
        total = int(row["total_api"])
        api = {cat: int(row[f"{cat.lower()}_api"]) for cat in per10k}
        for cat in per10k:
            value = round(10000 * api[cat] / total, 2)
            per10k[cat][q] = value
            computed[f"lex.{q}.{cat.lower()}_api"] = float(api[cat])
            computed[f"lex.{q}.{cat.lower()}_per_10k"] = value
        computed[f"lex.{q}.total"] = float(total)
        ratio = round(api["ARCH"] / api["REC"], 2)
        computed[f"lex.{q}.arch_rec_ratio"] = ratio
        ratios.append((q, api["ARCH"] / api["REC"]))

    first_q, last_q = quarters[0], quarters[-1]
    computed["claim.arch_per10k_first"] = per10k["ARCH"][first_q]
    computed["claim.arch_per10k_last"] = per10k["ARCH"][last_q]
    computed["claim.ver_per10k_first"] = per10k["VER"][first_q]
    computed["claim.ver_per10k_last"] = per10k["VER"][last_q]
    computed["claim.arch_growth_pct"] = float(round(100 * (per10k["ARCH"][last_q] / per10k["ARCH"][first_q] - 1)))
    computed["claim.ver_growth_pct"] = float(round(100 * (per10k["VER"][last_q] / per10k["VER"][first_q] - 1)))

    above = [(idx, q, r) for idx, (q, r) in enumerate(ratios) if r > 1.0]
    cross_detail = {"first_above_1": None, "last_below_1": None, "transition_from": None}
    if above:
        idx, q, _ = above[0]
        cross_detail["first_above_1"] = q
        cross_detail["last_below_1"] = quarters[idx - 1] if idx > 0 else None
        cross_detail["transition_from"] = quarters[idx - 1] if idx > 0 else q
        computed["claim.cross_transition_from"] = cross_detail["transition_from"]
    cross_detail["ratios_raw"] = {q: round(r, 6) for q, r in ratios}
    return computed, cross_detail


def compute_evidence(evidence: list[dict], quarters: list[str]) -> tuple[dict, dict]:
    computed: dict = {}
    for cat in ("ARCH", "REC", "VER"):
        key = cat.lower()
        counts = [sum(1 for e in evidence if e["category"] == cat and e["quarter"] == q) for q in quarters]
        computed[f"claim.local_{key}"] = tuple(counts)
        for q, count in zip(quarters, counts):
            computed[f"csv.{q}.{key}_local_sample"] = float(count)

    arch_rows = [e for e in evidence if e["category"] == "ARCH"]
    ver_rows = [e for e in evidence if e["category"] == "VER"]
    arch_hits = Counter(w for e in arch_rows for w in e["matched"])
    ver_hits = Counter(w for e in ver_rows for w in e["matched"])
    computed["claim.open_ended_hits"] = (arch_hits["open-ended"], len(arch_rows))
    computed["claim.audit_hits"] = (ver_hits["audit"], len(ver_rows))
    computed["claim.verifier_hits"] = (ver_hits["verifier"], len(ver_rows))
    audit = {
        "evidence_total": len(evidence),
        "by_category": dict(Counter(e["category"] for e in evidence)),
        "arch_hits": dict(arch_hits),
        "ver_hits": dict(ver_hits),
    }
    return computed, audit


def compute_throughput(data: dict, arm: str) -> dict:
    computed: dict = {}
    for n in data["protocol"]["Ns"]:
        rows = [r for r in data["per_trial"] if r["N"] == n]
        if len(rows) != len(data["protocol"]["seeds"]):
            raise ValueError(f"{arm} N={n}: trial count {len(rows)} != seeds")
        computed[f"tp.{arm}.N{n}.mean_calls"] = round(statistics.mean(r["verifier_calls"] for r in rows), 1)
        computed[f"tp.{arm}.N{n}.mean_delta"] = round(statistics.mean(r["delta"] for r in rows), 6)
        computed[f"tp.{arm}.N{n}.mean_rate"] = round(statistics.mean(r["rate_per_1k_verifications"] for r in rows), 6)
        computed[f"tp.{arm}.N{n}.mean_promoted"] = round(statistics.mean(r["promoted"] for r in rows), 2)
    return computed


def compute_negative_control(main: dict, rand: dict, ns: list[int]) -> dict:
    computed: dict = {}
    for n in ns:
        if n not in (4, 16):
            continue
        mrate = main[f"tp.main.N{n}.mean_rate"]
        rrate = rand[f"tp.random.N{n}.mean_rate"]
        mdelta = main[f"tp.main.N{n}.mean_delta"]
        rdelta = rand[f"tp.random.N{n}.mean_delta"]
        computed[f"claim.neg_rate_drop_n{n}"] = float(round(100 * (1 - rrate / mrate)))
        computed[f"claim.neg_delta_n{n}"] = round(mdelta - rdelta, 4)
    return computed


def csv_local_claims(csv_rows: list[dict]) -> dict:
    claims: dict = {}
    for row in csv_rows:
        q = row["quarter"]
        for cat in ("ARCH", "REC", "VER"):
            claims[f"csv.{q}.{cat.lower()}_local_sample"] = float(row[f"{cat.lower()}_local_sample"])
    return claims


def json_summary_pair(data: dict, stem: str) -> tuple[dict, dict]:
    arm = "random" if stem.endswith("-random") else "main"
    claims: dict = {}
    computed: dict = {}
    fields = (
        ("mean_calls", "mean_calls"),
        ("mean_delta", "mean_delta"),
        ("mean_rate_per_1k", "mean_rate"),
        ("mean_promoted", "mean_promoted"),
    )
    for row in data["summary"]:
        n = row["N"]
        for src, dst in fields:
            key = f"jsonsummary.{stem}.N{n}.{dst}"
            claims[key] = row[src]
            computed[key] = data["recomputed"][f"tp.{arm}.N{n}.{dst}"]
    return claims, computed


def tolerance_for(key: str) -> float:
    # README 表按展示位数取整：delta 4 位、rate 3 位、calls 1 位、promoted 2 位。
    # 容差只吸收展示取整，不吸收实质差异（self-test 注入仍必须变红）。
    if key.endswith("mean_delta") or key.startswith("claim.neg_delta"):
        return 5e-5
    if key.endswith("mean_rate"):
        return 5e-4
    if key.endswith("mean_calls"):
        return 0.05
    if key.endswith("mean_promoted"):
        return 0.005
    if ".arch_rec_ratio" in key or "_per_10k" in key:
        return 0.005
    if key in ("claim.arch_growth_pct", "claim.ver_growth_pct") or key.startswith("claim.neg_rate_drop"):
        return 0.5
    return 1e-9


def values_equal(a, b, key: str = "") -> bool:
    if isinstance(a, (tuple, list)) and isinstance(b, (tuple, list)):
        return len(a) == len(b) and all(values_equal(x, y, key) for x, y in zip(a, b))
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) <= tolerance_for(key)
    return a == b


def compare(source: str, claimed: dict, computed: dict) -> list[dict]:
    items: list[dict] = []
    for key in sorted(claimed):
        got = computed.get(key, None)
        ok = key in computed and values_equal(claimed[key], got, key)
        items.append({
            "source": source,
            "key": key,
            "status": "OK" if ok else "MISMATCH",
            "claim": jsonable(claimed[key]),
            "computed": jsonable(got),
        })
    return items


def extract_unverified(text: str) -> list[dict]:
    m = re.search(
        r"剔除 `audit`/`evaluator` 后重算 VER API 命中为 ([\d/]+)，即每万篇 ([\d./]+)（\+(\d+)%）",
        text,
    )
    claimed = m.group(0) if m else "README 声称剔除 audit/evaluator 后 VER 仍 +87%"
    return [{
        "key": "claim.ver_adjusted_no_generic_terms",
        "status": "未核",
        "claimed_text": claimed,
        "reason": "T6-measure 落盘 lexicon_report.csv / evidence.jsonl / throughput*.json 未记录剔除 audit/evaluator 后的 API 计数；analyses/tracks/rsi-after 内 grep 未找到生成载体。按工作纪律停该方向，不计入 mismatches。",
    }]


def load_all() -> dict:
    paths = {name: BASE / name for name in SOURCE_NAMES}
    missing = [str(p) for p in paths.values() if not p.is_file()]
    if missing:
        raise FileNotFoundError("missing source files: " + ", ".join(missing))

    texts = {name: paths[name].read_text(encoding="utf-8") for name in ("README.md", "evidence.jsonl")}
    with paths["lexicon_report.csv"].open(newline="", encoding="utf-8") as f:
        csv_rows = list(csv.DictReader(f))
    if not csv_rows:
        raise ValueError("lexicon_report.csv has no rows")
    evidence = [json.loads(line) for line in texts["evidence.jsonl"].splitlines() if line.strip()]
    quarters = [r["quarter"] for r in csv_rows]

    readme_claims = parse_readme_claims(texts["README.md"])
    lex_computed, cross_detail = compute_lex(csv_rows)
    ev_computed, evidence_audit = compute_evidence(evidence, quarters)

    tp_data = {}
    tp_computed = {}
    for stem in ("throughput", "throughput-random"):
        data = json.loads(paths[f"{stem}.json"].read_text(encoding="utf-8"))
        arm = "main" if stem == "throughput" else "random"
        comp = compute_throughput(data, arm)
        data["recomputed"] = comp
        tp_data[stem] = data
        tp_computed.update(comp)

    neg_computed = compute_negative_control(
        tp_computed, tp_computed, tp_data["throughput"]["protocol"]["Ns"]
    )
    computed = {}
    computed.update(lex_computed)
    computed.update(ev_computed)
    computed.update(tp_computed)
    computed.update(neg_computed)

    csv_claims = csv_local_claims(csv_rows)
    csv_computed = {k: ev_computed[k] for k in csv_claims}

    json_claims: dict = {}
    json_comp: dict = {}
    for stem in ("throughput", "throughput-random"):
        c, p = json_summary_pair(tp_data[stem], stem)
        json_claims.update(c)
        json_comp.update(p)

    return {
        "paths": paths,
        "digests": {name: sha12(path) for name, path in paths.items()},
        "readme_claims": readme_claims,
        "computed": computed,
        "csv_claims": csv_claims,
        "csv_computed": csv_computed,
        "json_claims": json_claims,
        "json_comp": json_comp,
        "unverified": extract_unverified(texts["README.md"]),
        "audit": {
            "cross": cross_detail,
            "evidence": evidence_audit,
            "quarters": quarters,
            "protocol": {
                stem: dict(tp_data[stem]["protocol"])
                for stem in ("throughput", "throughput-random")
            },
        },
    }


def build_items(data: dict) -> tuple[list[dict], list[dict]]:
    pairs = (
        ("README", data["readme_claims"], data["computed"]),
        ("CSV-local", data["csv_claims"], data["csv_computed"]),
        ("JSON-summary", data["json_claims"], data["json_comp"]),
    )
    items: list[dict] = []
    for source, claimed, computed in pairs:
        items.extend(compare(source, claimed, computed))
    mismatches = [item for item in items if item["status"] != "OK"]
    return items, mismatches


def self_test() -> int:
    data = load_all()
    before = dict(data["digests"])
    _, clean_mismatches = build_items(data)
    if clean_mismatches:
        print(f"SELFTEST FAIL control_mismatches={len(clean_mismatches)}")
        for m in clean_mismatches[:5]:
            print("  MISMATCH", m["source"], m["key"], m["claim"], m["computed"])
        return 2

    injections = [
        ("lex.2025Q4.arch_rec_ratio", 0.76),
        ("tp.main.N4.mean_rate", 8.620),
    ]
    all_red = True
    for key, bad_value in injections:
        bad_claims = copy.deepcopy(data["readme_claims"])
        original = bad_claims[key]
        bad_claims[key] = bad_value
        bad_items = compare("README-injected", bad_claims, data["computed"])
        red = [item for item in bad_items if item["status"] != "OK"]
        red_keys = {item["key"] for item in red}
        ok = len(red) == 1 and red_keys == {key}
        all_red = all_red and ok
        print(
            f"[{'OK' if ok else 'FAIL'}] inject {key}: {original}->{bad_value} "
            f"red={len(red)} red_keys={sorted(red_keys)}"
        )

    after = {name: sha12(path) for name, path in data["paths"].items()}
    unchanged = before == after
    print(
        f"SELFTEST {'PASS' if all_red and unchanged else 'FAIL'} "
        f"control_mismatches=0 injected_red={len(injections)} "
        f"source_digests_unchanged={unchanged}"
    )
    return 0 if all_red and unchanged else 2


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--self-test", action="store_true", help="注入已知错，证明本闸能红；不改文件")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="报告输出路径")
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()

    try:
        data = load_all()
    except Exception as exc:
        print(f"ERR load failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    items, mismatches = build_items(data)
    report = {
        "instrument": "analyses/tracks/rsi-after/T6-deep/crosscheck_measure.py",
        "against": "T6-measure/outputs/README.md + lexicon_report.csv + evidence.jsonl + throughput.json + throughput-random.json",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "independent_implementation": True,
        "imports_original_scripts": False,
        "source_sha256_12": data["digests"],
        "items": items,
        "mismatches": mismatches,
        "unverified": data["unverified"],
        "audit": data["audit"],
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        f"PASS={not mismatches} items={len(items)} mismatches={len(mismatches)} "
        f"unverified={len(data['unverified'])} report={out}"
    )
    for item in items:
        print(
            f"  [{item['status']}] {item['source']} {item['key']}: "
            f"claim={item['claim']} computed={item['computed']}"
        )
    for u in data["unverified"]:
        print(f"  [UNVERIFIED] {u['key']}: {u['reason']}")
    return 0 if not mismatches else 1


if __name__ == "__main__":
    raise SystemExit(main())
