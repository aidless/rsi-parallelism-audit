#!/usr/bin/env python3
"""从 outputs_p2x/sample.jsonl 重算主表，验证与 verifier_share.csv 逐格一致（可复算性自检）。

用法: python3 recompute_p2x.py
任何一格不一致 -> exit 2。
"""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from verifier_share import classify, wilson  # noqa: E402

OUT = HERE / "outputs_p2x"


def main() -> int:
    rows = [json.loads(l) for l in (OUT / "sample.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    meta = {}
    for r in csv.DictReader((OUT / "verifier_share.csv").open(encoding="utf-8")):
        meta[r["quarter"]] = (int(r["total"]), int(r["union_api"]), r)

    tiers = defaultdict(lambda: defaultdict(int))
    mismatch = 0
    for r in rows:
        t, reason = classify(r["title"], r["abstract"])
        if t != r["tier"]:
            mismatch += 1
            print(f"TIER MISMATCH {r['id']} {r['quarter']} stored={r['tier']} recomputed={t} reason={reason}")
        tiers[r["quarter"]][t] += 1

    print(f"tier recompute mismatches: {mismatch}/{len(rows)}")
    print(f"{'quarter':8} {'n':>5} {'P1':>4} {'P2':>4} {'P3':>4} {'NONE':>5} {'P2est':>6} {'P2 CI':>12} {'P2/10k':>7}  check")
    all_ok = mismatch == 0
    for q in sorted(tiers):
        total, union_api, csvrow = meta[q]
        c = tiers[q]
        n = sum(c.values())
        est = {t: round(union_api * c[t] / n) for t in ("P1", "P2", "P3")}
        lo, hi = wilson(c["P2"], n)
        p2lo, p2hi = round(lo * union_api), round(hi * union_api)
        p2_10k = round(10000 * est["P2"] / total, 2)
        ok = (
            n == int(csvrow["sample_n"])
            and c["P1"] == int(csvrow["p1_hits"]) and c["P2"] == int(csvrow["p2_hits"])
            and c["P3"] == int(csvrow["p3_hits"]) and c["NONE"] == int(csvrow["none_hits"])
            and est["P1"] == int(csvrow["p1_est"]) and est["P2"] == int(csvrow["p2_est"])
            and est["P3"] == int(csvrow["p3_est"])
            and p2lo == int(csvrow["p2_lo"]) and p2hi == int(csvrow["p2_hi"])
            and abs(p2_10k - float(csvrow["p2_per_10k"])) < 0.005
        )
        all_ok &= ok
        print(f"{q:8} {n:5} {c['P1']:4} {c['P2']:4} {c['P3']:4} {c['NONE']:5} "
              f"{est['P2']:6} [{p2lo:3},{p2hi:3}] {p2_10k:7}  {'OK' if ok else 'MISMATCH'}")
    print("RESULT:", "ALL OK" if all_ok else "MISMATCH FOUND")
    return 0 if all_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
