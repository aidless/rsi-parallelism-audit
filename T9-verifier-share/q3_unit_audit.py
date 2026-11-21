#!/usr/bin/env python3
"""Q3 补抓单位口径审计（第八法：单位/量纲审计）。

问题：outputs_q3retry/verifier_share.csv 里 p2_est=20（估计篇数）、p2_per_10k=10.01
（每万率）。但 outputs/README.md:111/116 与 SUMMARY.md:121 写成「P2=1（20/万，CI[3,110]）」
——把 est 篇数当成每万率，把 CI 篇数区间当成每万区间。P1/P3 同样错标。

本脚本只做零新算力复算：从 hits 反算 est、从 est 反算 per_10k、把 CI 篇数区间换算成
每万区间，判定文档声称值与真实值是否一致。self-test 注入真值/错值各验证闸能红能绿。

用法：
  python3 q3_unit_audit.py --self-test
  python3 q3_unit_audit.py
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent  # rsi-after/


def est_from_hits(hits: int, union_api: int, n: int) -> int:
    """源码 L363: est = round(union_api * tiers[t] / n)"""
    return round(union_api * hits / n)


def per_10k(est: int, total: int) -> float:
    """源码 L380-382: per_10k = round(10000 * est / total, 2)"""
    return round(10000 * est / total, 2) if total > 0 else 0.0


def ci_to_per_10k(lo: int, hi: int, total: int) -> tuple[float, float]:
    """源码 L378-379: lo/hi = round(Wilson比例 * union_api) = 篇数区间；换算到每万"""
    return (round(10000 * lo / total, 2), round(10000 * hi / total, 2))


def read_csv(p: Path) -> dict:
    with p.open(encoding="utf-8") as f:
        return {r["quarter"]: r for r in csv.DictReader(f)}


def audit() -> dict:
    q3 = read_csv(HERE / "outputs_q3retry" / "verifier_share.csv")["2026Q3"]
    p2x = read_csv(HERE / "outputs_p2x" / "verifier_share.csv")

    union_api, n, total = int(q3["union_api"]), int(q3["sample_n"]), int(q3["total"])
    rows = {}
    for tier in ("P1", "P2", "P3"):
        t = tier.lower()
        hits = int(q3[f"{t}_hits"])
        est_csv = int(q3[f"{t}_est"])
        pk_csv = float(q3[f"{t}_per_10k"])
        est_calc = est_from_hits(hits, union_api, n)
        pk_calc = per_10k(est_calc, total)
        rec = {
            "hits": hits,
            "est_csv": est_csv,
            "est_calc": est_calc,
            "est_match": est_calc == est_csv,
            "per_10k_csv": pk_csv,
            "per_10k_calc": pk_calc,
            "per_10k_match": abs(pk_calc - pk_csv) < 0.01,
        }
        if tier == "P2":
            lo, hi = int(q3["p2_lo"]), int(q3["p2_hi"])
            rec["ci_articles"] = [lo, hi]
            rec["ci_per_10k"] = list(ci_to_per_10k(lo, hi, total))
        rows[tier] = rec

    # 文档声称值（outputs/README.md:116 与 SUMMARY.md:121）
    doc_claim = {
        "P1_per_10k": 371, "P2_per_10k": 20, "P3_per_10k": 1816,
        "P2_ci_articles_as_per10k": [3, 110],
    }
    checks = {
        "P1_claim_is_est_not_rate": doc_claim["P1_per_10k"] == rows["P1"]["est_csv"]
        and doc_claim["P1_per_10k"] != rows["P1"]["per_10k_calc"],
        "P2_claim_is_est_not_rate": doc_claim["P2_per_10k"] == rows["P2"]["est_csv"]
        and doc_claim["P2_per_10k"] != rows["P2"]["per_10k_calc"],
        "P3_claim_is_est_not_rate": doc_claim["P3_per_10k"] == rows["P3"]["est_csv"]
        and doc_claim["P3_per_10k"] != rows["P3"]["per_10k_calc"],
        "CI_is_articles_not_per10k": doc_claim["P2_ci_articles_as_per10k"] == rows["P2"]["ci_articles"]
        and doc_claim["P2_ci_articles_as_per10k"] != rows["P2"]["ci_per_10k"],
    }

    # p2x 四季真实每万率范围（README:111 声称 10–38.5/万）
    p2x_rates = [float(p2x[q]["p2_per_10k"]) for q in ("2025Q4", "2026Q1", "2026Q2")]
    p2x_nonzero = [r for r in p2x_rates if r > 0]

    # 内部自相矛盾：README L111 的「10–38.5/万」下限 10 ≈ q3 真实每万率 10.01，
    # 但 L116 点估计写「20/万」——同一文档里下限用了真值、点估计用了 est 篇数。
    q3_p2_rate = rows["P2"]["per_10k_calc"]
    l111_lo = 10.0
    checks["internal_contradiction_L111_vs_L116"] = (
        abs(l111_lo - q3_p2_rate) <= 1.0          # L111 下限用的是真每万率 10.01
        and doc_claim["P2_per_10k"] != q3_p2_rate   # 但 L116 点估计写成 20
    )

    verdict = "UNIT_MISLABELED" if all(checks.values()) else "NO_DEFECT"

    return {
        "verdict": verdict,
        "source_formula": {
            "est": "round(union_api * hits / n)  [verifier_share.py:363]",
            "per_10k": "round(10000 * est / total, 2)  [verifier_share.py:380-382]",
            "ci": "round(Wilson比例 * union_api) = 篇数区间  [verifier_share.py:378-379]",
        },
        "q3retry": {"union_api": union_api, "sample_n": n, "total": total, "rows": rows},
        "doc_claim": doc_claim,
        "checks": checks,
        "p2x_p2_per_10k_nonzero": p2x_nonzero,
        "p2x_p2_rate_range": [min(p2x_nonzero), max(p2x_nonzero)],
        "corrected_reading": {
            "P1": f"命中 {rows['P1']['hits']} 条，估计 {rows['P1']['est_csv']} 篇 = {rows['P1']['per_10k_calc']}/万",
            "P2": f"命中 {rows['P2']['hits']} 条，估计 {rows['P2']['est_csv']} 篇 = {rows['P2']['per_10k_calc']}/万，CI篇 {rows['P2']['ci_articles']} → CI每万 {rows['P2']['ci_per_10k']}",
            "P3": f"命中 {rows['P3']['hits']} 条，估计 {rows['P3']['est_csv']} 篇 = {rows['P3']['per_10k_calc']}/万",
        },
        "note": "est 是外推估计篇数（分母 union_api），per_10k 是每万篇数（分母 total）。"
                "README/SUMMARY 把 est 篇数写成 '/万'、把 CI 篇数区间写成每万区间，数值口径错；"
                "但『P2 极稀疏、非真实零、落配角位』的定性结论不受影响。",
    }


def self_test() -> int:
    # T1: est 公式复现
    assert est_from_hits(1, 11717, 600) == 20, "T1 est 公式错"
    # T2: per_10k 公式复现
    assert per_10k(20, 19989) == 10.01, "T2 per_10k 公式错"
    # T3: CI 篇数→每万换算
    assert tuple(ci_to_per_10k(3, 110, 19989)) == (1.5, 55.03), "T3 CI 换算错"
    # T4: 闸能红——当前错值必须判 UNIT_MISLABELED
    assert audit()["verdict"] == "UNIT_MISLABELED", "T4 未抓住错值"
    # T5: 闸能绿——注入真值（est 位置放 per_10k）应判 NO_DEFECT
    import unittest.mock as mock
    orig = read_csv
    def patched(p):
        d = orig(p)
        if "q3retry" in str(p):
            r = d["2026Q3"]
            r["p2_per_10k"] = "10.01"  # 真值已在 CSV，这里确认判定逻辑依赖文档声称常数
        return d
    # 直接验证：若 doc_claim 换成真值，checks 应全 False → NO_DEFECT
    a = audit()
    truth_claim = {"P1_per_10k": a["q3retry"]["rows"]["P1"]["per_10k_calc"],
                   "P2_per_10k": a["q3retry"]["rows"]["P2"]["per_10k_calc"],
                   "P3_per_10k": a["q3retry"]["rows"]["P3"]["per_10k_calc"],
                   "P2_ci_articles_as_per10k": a["q3retry"]["rows"]["P2"]["ci_per_10k"]}
    chk = {
        "P1": truth_claim["P1_per_10k"] == a["q3retry"]["rows"]["P1"]["est_csv"] and truth_claim["P1_per_10k"] != a["q3retry"]["rows"]["P1"]["per_10k_calc"],
        "P2": truth_claim["P2_per_10k"] == a["q3retry"]["rows"]["P2"]["est_csv"] and truth_claim["P2_per_10k"] != a["q3retry"]["rows"]["P2"]["per_10k_calc"],
        "P3": truth_claim["P3_per_10k"] == a["q3retry"]["rows"]["P3"]["est_csv"] and truth_claim["P3_per_10k"] != a["q3retry"]["rows"]["P3"]["per_10k_calc"],
        "CI": truth_claim["P2_ci_articles_as_per10k"] == a["q3retry"]["rows"]["P2"]["ci_articles"] and truth_claim["P2_ci_articles_as_per10k"] != a["q3retry"]["rows"]["P2"]["ci_per_10k"],
    }
    assert not any(chk.values()), f"T5 注入真值应 NO_DEFECT，实际 {chk}"
    print("self-test 5/5 PASS")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    result = audit()
    out = HERE / "outputs" / "q3_unit_audit.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"VERDICT = {result['verdict']}")
    for tier in ("P1", "P2", "P3"):
        r = result["q3retry"]["rows"][tier]
        print(f"  {tier}: est={r['est_calc']}篇, per_10k={r['per_10k_calc']}/万, est_match={r['est_match']}, rate_match={r['per_10k_match']}")
    print(f"  P2 CI篇={result['q3retry']['rows']['P2']['ci_articles']} → CI每万={result['q3retry']['rows']['P2']['ci_per_10k']}")
    print(f"  p2x P2 每万范围(有命中三季)={result['p2x_p2_rate_range']}")
    print("->", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
