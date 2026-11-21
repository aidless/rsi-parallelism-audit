#!/usr/bin/env python3
"""Q3 P2=0 样本假象复核（只读复算，不发网络请求）。

回答一个问题：旧 Q3 600 条样本 P2=0，是「未捕获」还是「真零」？
口径完全沿用 T9-verifier-share：
  est = round(union_api * P2_hits / sample_n)
  CI  = Wilson95(P2_hits/sample_n) * union_api，四舍五入为估计篇数区间
  per_10k = round(10000 * est / total, 2)
本脚本不把样本未命中写成真实零，也不做因果外推。

用法：
  python3 q3_reconfirm.py --self-test    # 自带夹具；不读盘；注入 P2 必须使点估计 > 0
  python3 q3_reconfirm.py --prove-red    # 故意换成恒零坏尺；必须 exit 1
  python3 q3_reconfirm.py                # 只读现有样本，写 q3_reconfirm.json
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SHARE = ROOT / "T9-verifier-share"
OLD_OUT = SHARE / "outputs_p2x"
RETRY_OUT = SHARE / "outputs_q3retry"
OUT_JSON = HERE / "q3_reconfirm.json"
QUARTER = "2026Q3"
TIERS = ("P1", "P2", "P3", "NONE")


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """与 verifier_share.py:299-306 同式；z=1.96。"""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def measure(name: str, source: str, k: int, n: int, union_api: float, total: int) -> dict:
    if n <= 0 or union_api <= 0 or total <= 0:
        raise ValueError("n/union_api/total must be positive")
    if k < 0 or k > n:
        raise ValueError("k out of range")
    lo, hi = wilson(k, n)
    est = round(union_api * k / n)
    art_lo, art_hi = round(lo * union_api), round(hi * union_api)
    per_10k = round(10000 * est / total, 2)
    ci_per_10k = [round(10000 * art_lo / total, 2), round(10000 * art_hi / total, 2)]
    if k > 0:
        verdict = "OBSERVED_POSITIVE"
    elif art_hi > 0:
        verdict = "UNOBSERVED_NOT_TRUE_ZERO"
    else:
        verdict = "NOT_ASSESSED"
    return {
        "name": name,
        "source": source,
        "sample_n": n,
        "p2_hits": k,
        "p_hat": round(k / n, 8),
        "wilson95_proportion": [round(lo, 8), round(hi, 8)],
        "union_api": union_api,
        "total": total,
        "p2_est_articles": est,
        "ci_articles": [art_lo, art_hi],
        "p2_per_10k": per_10k,
        "ci_per_10k": ci_per_10k,
        "sample_verdict": verdict,
        "true_zero_claim": "NOT_ASSESSABLE_FROM_SAMPLE",
    }


def constant_zero_estimator(name: str, source: str, k: int, n: int, union_api: float, total: int) -> dict:
    """故意坏尺：无论注入多少 P2 都报 0，用于证明 self-test 会红。"""
    out = measure(name, source, k, n, union_api, total)
    out["p2_est_articles"] = 0
    out["p2_per_10k"] = 0.0
    out["ci_articles"] = [0, 0]
    out["ci_per_10k"] = [0.0, 0.0]
    return out


def decide(old: dict, retry: dict, pooled: dict) -> dict:
    reasons = []
    if old["p2_hits"] == 0 and old["ci_per_10k"][1] > 0:
        reasons.append(
            f"旧 600 条样本 k=0 的 Wilson 95% 上界 = {old['ci_per_10k'][1]}/万 > 0；样本零不等于真实零"
        )
    if retry["p2_hits"] > 0:
        reasons.append(
            f"补抓 600 条样本已实测 k={retry['p2_hits']}，点估计 {retry['p2_per_10k']}/万 > 0"
        )
    if old["p2_hits"] == 0 and retry["p2_hits"] > 0:
        verdict = "OLD_ZERO_IS_UNOBSERVED_NOT_TRUE_ZERO"
    elif old["p2_hits"] == 0:
        verdict = "OLD_ZERO_UNRESOLVED_NOT_TRUE_ZERO"
    else:
        verdict = "OLD_ZERO_NOT_APPLICABLE"
    return {
        "question": "Q3 P2=0 是未捕获还是真零",
        "verdict": verdict,
        "reasons": reasons,
        "pooled_reading": {
            "sample_n": pooled["sample_n"],
            "p2_hits": pooled["p2_hits"],
            "p2_est_articles": pooled["p2_est_articles"],
            "p2_per_10k": pooled["p2_per_10k"],
            "ci_per_10k": pooled["ci_per_10k"],
        },
        "not_claimed": [
            "未做 union_api 全量枚举，不判定全季层面的真实零",
            "连续块/浅偏移抽样不等于随机覆盖全季，不外推因果",
            "CI 只反映样本内二项不确定性，不覆盖季内时间聚集与判据误判率",
        ],
    }


def sha12(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12]


def load_gauge():
    if str(SHARE) not in sys.path:
        sys.path.insert(0, str(SHARE))
    import verifier_share  # 现役量具：classify + wilson

    return verifier_share.classify, verifier_share.wilson


def read_csv_meta(d: Path, quarter: str = QUARTER) -> dict:
    with (d / "verifier_share.csv").open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["quarter"] == quarter:
                return row
    raise ValueError(f"missing quarter {quarter} in {d / 'verifier_share.csv'}")


def read_sample_rows(d: Path, quarter: str = QUARTER) -> list[dict]:
    rows = []
    p = d / "sample.jsonl"
    with p.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                if r.get("quarter") == quarter:
                    rows.append(r)
    return rows


def check_sample(name: str, d: Path, classify, gauge_wilson) -> tuple[dict, list[dict]]:
    meta = read_csv_meta(d)
    rows = read_sample_rows(d)
    stored = Counter(r["tier"] for r in rows)
    recomputed = Counter()
    tier_mismatches = []
    for r in rows:
        t, reason = classify(r["title"], r["abstract"])
        recomputed[t] += 1
        if t != r["tier"]:
            tier_mismatches.append({"id": r["id"], "stored": r["tier"], "recomputed": t, "reason": reason})

    n = len(rows)
    k = stored["P2"]
    union_api = int(meta["union_api"])
    total = int(meta["total"])
    m = measure(name, str((d / "sample.jsonl").relative_to(ROOT)), k, n, union_api, total)
    g_lo, g_hi = gauge_wilson(k, n)
    checks = {
        "sample_n": n == int(meta["sample_n"]),
        "tier_hits": all(stored[t] == int(meta[f"{t.lower()}_hits"]) for t in TIERS),
        "tier_recompute": not tier_mismatches,
        "p2_est": m["p2_est_articles"] == int(meta["p2_est"]),
        "p2_ci": m["ci_articles"] == [int(meta["p2_lo"]), int(meta["p2_hi"])],
        "p2_per_10k": abs(m["p2_per_10k"] - float(meta["p2_per_10k"])) < 0.005,
        "wilson_against_gauge": abs(m["wilson95_proportion"][0] - g_lo) < 1e-8 and abs(m["wilson95_proportion"][1] - g_hi) < 1e-8,
    }
    m["csv_meta"] = {key: meta[key] for key in (
        "quarter", "total", "union_api", "sample_n", "p1_hits", "p2_hits", "p3_hits", "none_hits",
        "p2_est", "p2_lo", "p2_hi", "p2_per_10k"
    )}
    m["stored_tier_counts"] = {t: stored[t] for t in TIERS}
    m["recomputed_tier_counts"] = {t: recomputed[t] for t in TIERS}
    m["reconciliation_checks"] = checks
    m["reconciliation_ok"] = all(checks.values())
    mismatches = []
    if tier_mismatches:
        mismatches.append({"sample": name, "kind": "tier_recompute", "rows": tier_mismatches[:20]})
    for key, ok in checks.items():
        if not ok:
            mismatches.append({"sample": name, "kind": key, "expected": True, "actual": ok})
    return m, mismatches


def pooled_measure(old: dict, retry: dict) -> dict:
    if old["total"] != retry["total"]:
        raise ValueError("pooled total mismatch")
    n = old["sample_n"] + retry["sample_n"]
    k = old["p2_hits"] + retry["p2_hits"]
    union_api = (old["union_api"] * old["sample_n"] + retry["union_api"] * retry["sample_n"]) / n
    m = measure("pooled_q3", "outputs_p2x+outputs_q3retry", k, n, union_api, int(retry["total"]))
    m["union_api_method"] = "n-weighted mean of two CSV union_api values"
    return m


def self_test(estimator=measure, label: str = "self-test") -> int:
    checks = []

    def ck(cond: bool, msg: str) -> None:
        if not cond:
            raise AssertionError(msg)
        checks.append(msg)

    try:
        zero = estimator("fixture_zero", "in_memory", 0, 600, 11718, 19989)
        one = estimator("fixture_one_p2", "in_memory", 1, 600, 11718, 19989)
        ck(zero["p2_est_articles"] == 0, "零命中夹具点估计为 0")
        ck(one["p2_est_articles"] > 0, "注入一条 P2 必须使点估计 > 0")
        ck(one["p2_per_10k"] > 0, "注入一条 P2 必须使每万点估计 > 0")
        ck(zero["ci_articles"][1] > 0, "零命中样本的 CI 上界必须 > 0")
        ck(zero["ci_per_10k"][1] > 0, "零命中样本的每万 CI 上界必须 > 0")
        ck(0 <= zero["wilson95_proportion"][0] <= zero["wilson95_proportion"][1] <= 1, "Wilson 区间在 [0,1] 内")
        ck(0 <= one["wilson95_proportion"][0] <= one["wilson95_proportion"][1] <= 1, "注入后 Wilson 区间在 [0,1] 内")
        ck(zero["sample_verdict"] == "UNOBSERVED_NOT_TRUE_ZERO", "零命中只判未捕获/不能判真零")
        ck(one["sample_verdict"] == "OBSERVED_POSITIVE", "注入后判实测阳性")
        dec = decide(zero, one, one)
        ck(dec["verdict"] == "OLD_ZERO_IS_UNOBSERVED_NOT_TRUE_ZERO", "整体判决抓住旧零为样本假象")
    except AssertionError as exc:
        print(f"{label} FAIL: {exc}")
        print(f"passed_before_fail={len(checks)}")
        return 1
    print(f"{label} {len(checks)}/{len(checks)} PASS")
    print("red_control: 恒零坏尺会在『注入一条 P2 必须使点估计 > 0』处失败")
    return 0


def run() -> int:
    classify, gauge_wilson = load_gauge()
    old, m_old = check_sample("p2x_q3_600", OLD_OUT, classify, gauge_wilson)
    retry, m_retry = check_sample("q3retry_q3_600", RETRY_OUT, classify, gauge_wilson)
    pooled = pooled_measure(old, retry)
    mismatches = m_old + m_retry
    decision = decide(old, retry, pooled)
    payload = {
        "instrument": "q3_reconfirm",
        "status": "OK" if not mismatches else "RECON_FAIL",
        "read_only": True,
        "network_calls": 0,
        "sim_machine_minutes": 0,
        "ran_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "against": "T9-verifier-share/verifier_share.py classify+wilson 与两份 verifier_share.csv/sample.jsonl",
        "inputs": {
            "old_csv": str((OLD_OUT / "verifier_share.csv").relative_to(ROOT)),
            "old_sample": str((OLD_OUT / "sample.jsonl").relative_to(ROOT)),
            "retry_csv": str((RETRY_OUT / "verifier_share.csv").relative_to(ROOT)),
            "retry_sample": str((RETRY_OUT / "sample.jsonl").relative_to(ROOT)),
            "sha256_12": {
                "old_csv": sha12(OLD_OUT / "verifier_share.csv"),
                "old_sample": sha12(OLD_OUT / "sample.jsonl"),
                "retry_csv": sha12(RETRY_OUT / "verifier_share.csv"),
                "retry_sample": sha12(RETRY_OUT / "sample.jsonl"),
            },
        },
        "samples": [old, retry],
        "pooled": pooled,
        "decision": decision,
        "cross_check_gate": {"against": "classify+wilson+CSV", "mismatches": mismatches},
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    for m in payload["samples"]:
        print(f"[{m['name']}] n={m['sample_n']} hits={m['p2_hits']} est={m['p2_est_articles']}篇 "
              f"CI篇={m['ci_articles']} per10k={m['p2_per_10k']} CI每万={m['ci_per_10k']} "
              f"verdict={m['sample_verdict']} recon={'OK' if m['reconciliation_ok'] else 'FAIL'}")
    print(f"[pooled] n={pooled['sample_n']} hits={pooled['p2_hits']} est={pooled['p2_est_articles']}篇 "
          f"per10k={pooled['p2_per_10k']} CI每万={pooled['ci_per_10k']}")
    print(f"DECISION = {decision['verdict']}")
    print(f"mismatches = {len(mismatches)}")
    print(f"-> {OUT_JSON.relative_to(ROOT)}")
    return 0 if not mismatches else 2


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true", help="自带 fixture；不读输入盘")
    ap.add_argument("--prove-red", action="store_true", help="恒零坏尺反证；预期 exit 1")
    args = ap.parse_args()
    if args.self_test and args.prove_red:
        print("choose one of --self-test / --prove-red")
        return 2
    if args.self_test:
        return self_test()
    if args.prove_red:
        return self_test(estimator=constant_zero_estimator, label="prove-red")
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
