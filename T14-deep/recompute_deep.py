"""独立复算 frozen_anchor.json：从 rows 重算 summary/verdict 并与落盘值逐项比对。

  python3 recompute_deep.py --self-test   # 2/2：真值对得上 + 篡改底物必须判红
  python3 recompute_deep.py               # 打印可引用数字
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path

KEYS = ("rho_bar", "N_eff", "N_eff_over_N", "delta_inst", "delta_priv",
        "rate_cand", "rate_total", "pass_rate", "cos_z_truew")


def ranks(xs):
    o = sorted(range(len(xs)), key=lambda i: xs[i])
    rk = [0.0] * len(xs)
    i = 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[o[j + 1]] == xs[o[i]]:
            j += 1
        for k in range(i, j + 1):
            rk[o[k]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return rk


def pearson(a, b):
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    num = sum((a[i] - ma) * (b[i] - mb) for i in range(len(a)))
    da = sum((x - ma) ** 2 for x in a)
    db = sum((x - mb) ** 2 for x in b)
    return num / math.sqrt(da * db) if da > 1e-15 and db > 1e-15 else 0.0


def spearman(a, b):
    return pearson(ranks(list(a)), ranks(list(b)))


def recompute(d):
    rows, g = d["rows"], d["config"]["rho_grid"]
    sm = {}
    for r in g:
        for n in d["config"]["ns"]:
            sub = [x for x in rows if x["rho_param"] == r and x["N"] == n]
            sm[(r, n)] = {k: statistics.fmean(x[k] for x in sub) for k in KEYS}
    rb = [sm[(r, 16)]["rho_bar"] for r in g]
    mono = all(rb[i] <= rb[i + 1] + 1e-9 for i in range(len(g) - 1))
    v1 = (mono and rb[0] <= 0.40 and abs(rb[-1] - 1.0) <= 0.002
          and pearson(g, rb) >= 0.95)
    span = sm[(0.0, 16)]["N_eff"] / sm[(1.0, 16)]["N_eff"]
    di = [sm[(r, 16)]["delta_inst"] for r in g]
    gap = di[0] - di[-1]
    sp = spearman(g, di)
    shape = ("COLLAPSE_REPRODUCED" if sp <= -0.8 and gap >= 0.05 else
             "REVERSED_SIGNAL_DOMINANT" if sp >= 0.8 and gap <= -0.05 else "MIXED_SHAPE")
    ft = [r for r in g if sm[(r, 16)]["rate_total"] >= sm[(r, 4)]["rate_total"]]
    fc = [r for r in g if sm[(r, 16)]["rate_cand"] >= sm[(r, 4)]["rate_cand"]]
    tt = [sm[(r, 4)]["rate_total"] / max(sm[(r, 16)]["rate_total"], 1e-9) for r in g]
    tc = [sm[(r, 4)]["rate_cand"] / max(sm[(r, 16)]["rate_cand"], 1e-9) for r in g]
    v = {
        "V1_rho_bar16": [round(x, 4) for x in rb], "V1_monotone": mono,
        "V1_span_low": round(rb[0], 4), "V1_pearson": round(pearson(g, rb), 4),
        "V1": "PASS" if v1 else "FAIL",
        "V2_neff_span": round(span, 4), "V2": "PASS" if span >= 3.0 else "FAIL",
        "D1": "JUDGEABLE" if (v1 and span >= 3.0) else "DEGRADED_INSTRUMENT",
        "D1_shape": shape,
        "attribution": {
            "spearman_dinst_rho": round(sp, 4),
            "spearman_dinst_neff": round(spearman([sm[(r, 16)]["N_eff"] for r in g], di), 4),
            "spearman_dinst_cos": round(spearman([sm[(r, 16)]["cos_z_truew"] for r in g], di), 4),
            "gap_dinst_0_minus_1": round(gap, 6)},
        "D2_flip_total": ft, "D2_flip_cand": fc,
        "D2": "RATE_FLIP_ANY" if ft else "RATE_ROBUST_ACROSS_RHO",
        "D4_tax_min": round(min(tt), 4), "D4_tax_max": round(max(tt), 4),
        "D4_tax_min_cand": round(min(tc), 4), "D4_tax_max_cand": round(max(tc), 4),
        "D4": ("TAX_ROBUST" if min(tt) >= 3.0 else
               "TAX_RHO_SENSITIVE" if min(tt) < 2.0 else "TAX_MIDDLE"),
    }
    return sm, v


def load():
    return json.loads((Path(__file__).parent / "frozen_anchor.json").read_text(encoding="utf-8"))


def check(d):
    sm, v = recompute(d)
    stored_sm = {(x["rho_param"], x["N"]): x for x in d["summary"]}
    for k, row in sm.items():
        for f in KEYS:
            assert abs(row[f] - stored_sm[k][f]) < 1e-4, f"summary mismatch {k} {f}"
    assert v == d["verdict"], f"verdict mismatch\n{v}\n{d['verdict']}"
    return sm, v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    d = load()
    sm, v = check(d)
    if a.self_test:
        bad = json.loads(json.dumps(d))
        bad["rows"][0]["rho_bar"] += 0.10
        caught = False
        try:
            check(bad)
        except AssertionError:
            caught = True
        assert caught, "tamper guard failed: mutation not detected"
        print("recompute self-test 2/2 PASS (truth matches, tamper detected)")
        return
    g = d["config"]["rho_grid"]
    print(f"{'rho':>5s} {'rho_bar':>8s} {'N_eff':>7s} {'d_inst':>8s} {'d_priv':>8s} "
          f"{'rate_t':>7s} {'rate_c':>7s} {'tax_t':>6s}")
    for r in g:
        x, y = sm[(r, 16)], sm[(r, 4)]
        print(f"{r:5.2f} {x['rho_bar']:8.4f} {x['N_eff']:7.3f} {x['delta_inst']:8.4f} "
              f"{x['delta_priv']:8.4f} {x['rate_total']:7.3f} {x['rate_cand']:7.3f} "
              f"{y['rate_total']/x['rate_total']:6.3f}")
    print("verdict:", json.dumps(v, ensure_ascii=False))


if __name__ == "__main__":
    main()
