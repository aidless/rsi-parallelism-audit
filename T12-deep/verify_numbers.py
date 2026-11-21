"""T12-deep 报告数字的落盘复算闸。

所有 EXPECTED 值都来自 outputs/ 下的原始 JSON，可由 compute_claims() 重算。
--self-test : 全量重算并与 EXPECTED 对账；必须全绿
--prove-red : 注入一个错误期望值，断言必须变红（防「空闸」）

用法：
  python3 verify_numbers.py --self-test
  python3 verify_numbers.py --prove-red
  python3 verify_numbers.py --show
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"
TOL = 5e-4

EXPECTED = {
    # ---- raw run counts
    "n_c1": 1120, "n_c2": 1120, "n_c3": 1120, "n_c4": 1120, "n_c5": 560,
    "n_n1": 2100, "n_n2": 2100, "n_n3": 840,
    # ---- C1 (dim9/len4, capped) baseline partition
    "c1.r1B8.singleA": 0.725,
    "c1.r1B8.taxA": 0.1553,
    "c1.r1B8.swarmEwin": 0.0,
    "c1.r1B64.gainE": 0.0053,
    "c1.B64.lowrho.swarmEwin": 0.93,
    "c1.r0B64.idE": 0.0578,
    "c1.r0B64.gap": 0.0184,
    "c1.r1B64.gap": 0.0297,
    "c1.r0B64.B1": 0.0,
    "c1.r0.9B64.B1": 0.68,
    "c1.r1B64.B1": 0.76,
    # ---- C2 (dim16/len6) widened partition
    "c2.r1B8.singleA": 0.525,
    "c2.r1B8.taxA": 0.0888,
    "c2.r1B8.swarmEwin": 0.0,
    "c2.r1B64.gainE": -0.0250,
    "c2.B64.lowrho.swarmEwin": 0.875,
    "c2.r0B64.idE": 0.0271,
    "c2.r0B64.gap": 0.0100,
    "c2.r1B64.gap": 0.0284,
    "c2.r0B64.B1": 0.12,
    "c2.r0.9B64.B1": 0.63,
    "c2.r1B64.B1": 0.73,
    # ---- C3/C4 ablations
    "c3.r1B8.taxA": 0.0769,
    "c4.r1B8.taxA": 0.2754,
    "c3.r1B64.gainE": 0.0006,
    "c4.r1B64.gainE": 0.0222,
    "c3.r0B64.idE": 0.0389,
    "c4.r0B64.idE": 0.0418,
    # ---- C5 budget catch-up (rho=1)
    "c5.r1B64.gainE": -0.0303,
    "c5.r1B128.gainE": -0.0349,
    "c5.r1B256.gainE": 0.0021,
    "c5.r1B512.gainE": 0.0021,
    # ---- N_eff audit (paired gain_E diff vs rho=0, Bonferroni)
    "n1.r1.gainE": 0.0189, "n1.r1.diff": -0.1643, "n1.r1.t": -16.26, "n1.r1.win": 0.06,
    "n2.r0.gainE": 0.0952, "n2.r0.E_single": 0.0374,
    "n2.r1.gainE": -0.0229, "n2.r1.E_single": 0.2180,
    "n2.r1.diff": -0.1181, "n2.r1.t": -15.23, "n2.r1.win": 0.04,
    "n2.r0.75.proxy": 17.93,
    "n3.r1.gainE": 0.0169, "n3.r1.diff": -0.1505, "n3.r1.t": -16.05,
}


def _load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def _cell(rows, rho, B):
    return [r for r in rows if abs(r["rho"] - rho) < 1e-9 and r["budget"] == B]


def _mean(rows, key):
    xs = [r[key] for r in rows if r[key] is not None]
    return statistics.fmean(xs) if xs else None


def _win(rows, a, b):
    return sum(1 for r in rows if r[a] > r[b]) / len(rows)


def compute_claims():
    out = {}
    cols = {
        "c1": "collision_c1_d9_l4.json", "c2": "collision_c2_d16_l6.json",
        "c3": "collision_c3_d9_l6.json", "c4": "collision_c4_d16_l4.json",
        "c5": "collision_c5_d16_l6_bigB.json",
    }
    data = {k: _load(v) for k, v in cols.items()}
    for k, rows in data.items():
        out[f"n_{k}"] = len(rows)

    for tag in ("c1", "c2"):
        rows = data[tag]
        c8 = _cell(rows, 1.0, 8)
        c64 = _cell(rows, 1.0, 64)
        low = [r for rho in (0, 0.25, 0.5, 0.75, 0.9) for r in _cell(rows, rho, 64)]
        out[f"{tag}.r1B8.singleA"] = _win(c8, "A_single", "A_swarm")
        out[f"{tag}.r1B8.taxA"] = round(_mean(c8, "tax_A"), 4)
        out[f"{tag}.r1B8.swarmEwin"] = _win(c8, "E_swarm", "E_single")
        out[f"{tag}.r1B64.gainE"] = round(_mean(c64, "gain_E"), 4)
        out[f"{tag}.B64.lowrho.swarmEwin"] = round(_win(low, "E_swarm", "E_single"), 3)
        out[f"{tag}.r0B64.idE"] = round(_mean(_cell(rows, 0.0, 64), "E_identity"), 4)
        out[f"{tag}.r0B64.gap"] = round(_mean(_cell(rows, 0.0, 64), "B2_gap_swarm"), 4)
        out[f"{tag}.r1B64.gap"] = round(_mean(c64, "B2_gap_swarm"), 4)
        for rho, key in ((0.0, "r0B64"), (0.9, "r0.9B64"), (1.0, "r1B64")):
            out[f"{tag}.{key}.B1"] = round(_mean(_cell(rows, rho, 64), "B1_swarm"), 2)

    for tag, rho, B, key in (
        ("c3", 1.0, 8, "c3.r1B8.taxA"), ("c4", 1.0, 8, "c4.r1B8.taxA"),
        ("c3", 1.0, 64, "c3.r1B64.gainE"), ("c4", 1.0, 64, "c4.r1B64.gainE"),
    ):
        out[key] = round(_mean(_cell(data[tag], rho, B), "tax_A" if B == 8 else "gain_E"), 4)
    for tag in ("c3", "c4"):
        out[f"{tag}.r0B64.idE"] = round(_mean(_cell(data[tag], 0.0, 64), "E_identity"), 4)

    for B in (64, 128, 256, 512):
        out[f"c5.r1B{B}.gainE"] = round(_mean(_cell(data["c5"], 1.0, B), "gain_E"), 4)

    audits = {
        "n1": "neff_audit_n1_d9_l4.json",
        "n2": "neff_audit_n2_d16_l6.json",
        "n3": "neff_audit_n3_d16_l6_B512.json",
    }
    for tag, fn in audits.items():
        a = _load(fn)
        out[f"n_{tag}"] = a["seeds"] * len(a["rhos"])
        by = {round(r["rho"], 3): r for r in a["per_rho"]}
        out[f"{tag}.r1.gainE"] = round(by[1.0]["gain_E"], 4)
        out[f"{tag}.r1.diff"] = round(by[1.0]["mean"], 4)
        out[f"{tag}.r1.t"] = round(by[1.0]["t"], 2)
        out[f"{tag}.r1.win"] = round(by[1.0]["win_rate"], 2)
        if tag == "n2":
            out["n2.r0.gainE"] = round(by[0.0]["gain_E"], 4)
            out["n2.r0.E_single"] = round(by[0.0]["E_single"], 4)
            out["n2.r1.E_single"] = round(by[1.0]["E_single"], 4)
            out["n2.r0.75.proxy"] = round(by[0.75]["proxy_N_eff"], 2)
        if tag == "n3":
            pass
    return out


def compare(expected=None):
    expected = EXPECTED if expected is None else expected
    got = compute_claims()
    bad = []
    for k, v in expected.items():
        g = got.get(k)
        if g is None or abs(g - v) > (TOL if isinstance(v, float) else 0):
            bad.append((k, v, g))
    return bad, got


def self_test():
    bad, got = compare()
    for k in sorted(EXPECTED):
        print(f"  [{'PASS' if all(b[0] != k for b in bad) else 'FAIL'}] {k} = {got.get(k)}")
    if bad:
        print(f"\nSELF-TEST FAILED: {len(bad)} -> {bad}")
        return 1
    print(f"\nSELF-TEST ALL PASS ({len(EXPECTED)} claims, tol={TOL})")
    return 0


def prove_red():
    poisoned = dict(EXPECTED)
    poisoned["c2.r1B8.taxA"] = EXPECTED["c2.r1B8.taxA"] + 0.01
    bad, _ = compare(poisoned)
    caught = any(b[0] == "c2.r1B8.taxA" for b in bad)
    print(f"  [{'CAUGHT' if caught else 'MISSED'}] injected wrong value c2.r1B8.taxA")
    print("\nRED BATTERY " + ("ALL CAUGHT" if caught else "HAS MISSES"))
    return 0 if caught else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--prove-red", action="store_true")
    ap.add_argument("--show", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if args.prove_red:
        return prove_red()
    if args.show:
        _, got = compare()
        for k in sorted(got):
            print(f"{k:<28} {got[k]}")
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
