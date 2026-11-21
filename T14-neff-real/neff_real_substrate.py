"""T14: N_eff 在真实闸底物上的连续 rho 检验。

复用 T13 的 rsi-agent 原语（ContextualTask/paired_gate/estimate_noise_floor），
只换 propose 为可控相关的 controlled 构造；不改 rsi-agent 源码。
预注册判据见 PRE_REGISTRATION.md（执行前定死，禁止事后挑数）。

用法:
  python3 neff_real_substrate.py --self-test
  python3 neff_real_substrate.py --seeds 1,2,3 --gens 12 --n 1,4,16 --out real_substrate.json
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from pathlib import Path

T13_DIR = Path(__file__).resolve().parents[1] / "T13-proposer-diversity"
sys.path.insert(0, str(T13_DIR))
import proposer_diversity as P  # noqa: E402

from rsi_agent.core import HeuristicPolicy, ScoreVector  # noqa: E402
from rsi_agent.gates import paired_gate, estimate_noise_floor  # noqa: E402
from rsi_agent.tasks import ContextualTask  # noqa: E402

BASELINE = P.BASELINE
RHO_GRID = (0.0, 0.25, 0.5, 0.75, 0.9, 0.945, 1.0)


def controlled_propose(rho, gen, n, seed, anchor):
    """共享随机方向 + 独立方向：rho 参数与实测 rho_bar 单调同向。"""
    rng = random.Random(f"t14:{seed}:{gen}")
    step = max(0.5 * (0.94 ** gen), 0.04)
    shared = tuple(rng.gauss(0.0, 1.0) for _ in range(3))
    out = []
    for i in range(n):
        ind = tuple(rng.gauss(0.0, 1.0) for _ in range(3))
        w = tuple(round(anchor[j] + step * ((rho ** 0.5) * shared[j]
                                          + ((1.0 - rho) ** 0.5) * ind[j]), 4)
                  for j in range(3))
        out.append(HeuristicPolicy(w, name=f"g{gen}c{i}"))
    return out


def bad_propose(rho, gen, n, seed, anchor):
    """旧反直觉构造（sqrt(rho)*anchor+sqrt(1-rho)*v）——只用于 S6 证明门能红。"""
    rng = random.Random(f"bad:{seed}:{gen}")
    step = max(0.5 * (0.94 ** gen), 0.04)
    out = []
    for i in range(n):
        v = tuple(rng.gauss(0.0, step) for _ in range(3))
        w = tuple(round((rho ** 0.5) * anchor[j] + ((1.0 - rho) ** 0.5) * v[j], 4)
                  for j in range(3))
        out.append(HeuristicPolicy(w, name=f"g{gen}c{i}"))
    return out


def measured_rho(prop_fn, rho, n, seed, gen=0):
    """在 public 探针任务上量 per-episode Δ 向量两两 Pearson（与 T13 同口径）。"""
    task = ContextualTask(seed=1001, n_episodes=128)
    base = task.evaluate(BASELINE)
    pool = prop_fn(rho, gen, n, seed, BASELINE.weights)
    dvecs = [P.delta_vector(task.evaluate(p), base) for p in pool]
    return P.mean_pairwise_rho(dvecs)


def run_arm(rho, n, gens, seed, family_alpha=0.05):
    """与 T13 run_arm 同底物同门，仅换 propose；额外记 pass_rate。"""
    public = ContextualTask(seed=1000 + seed, n_episodes=128)
    private = ContextualTask(seed=90000 + seed, n_episodes=128)
    floor = estimate_noise_floor(public, BASELINE)
    base_pub = public.evaluate(BASELINE)
    base_priv = private.evaluate(BASELINE)
    base_view = ScoreVector(base_pub.values)
    alphas = [family_alpha / max(gens - g, 1) for g in range(gens)]

    anchor = BASELINE.weights
    per_gen_delta = []
    per_gen_rho = []
    verifier_calls = 0
    promoted = 0
    passes_total = 0

    for g in range(gens):
        pool = controlled_propose(rho, g, n, seed, anchor)
        pv_pub = [public.evaluate(p) for p in pool]
        pv_priv = [private.evaluate(p) for p in pool]
        verifier_calls += n

        if n >= 2:
            dvecs = [P.delta_vector(x, base_pub) for x in pv_pub]
            per_gen_rho.append(P.mean_pairwise_rho(dvecs))

        views = [ScoreVector(x.values) for x in pv_pub]
        passes = [i for i in range(n)
                  if paired_gate(base_view, views[i], floor, alphas[g]).passed]
        passes_total += len(passes)
        k = max(passes, key=lambda i: views[i].mean) if passes else None
        if k is None:
            continue
        anchor = pool[k].weights
        per_gen_delta.append(pv_priv[k].mean - base_priv.mean)
        promoted += 1

    rho_bar = statistics.fmean(per_gen_rho) if per_gen_rho else 1.0
    delta_priv = statistics.fmean(per_gen_delta) if per_gen_delta else 0.0
    return {
        "rho_param": rho, "N": n, "seed": seed, "gens": gens,
        "rho_bar": round(rho_bar, 6),
        "N_eff": round(P.n_eff(n, rho_bar), 4),
        "N_eff_over_N": round(P.n_eff(n, rho_bar) / n, 4),
        "delta_priv": round(delta_priv, 6),
        "verifier_calls": verifier_calls,
        "rate_per_1k": round(delta_priv / max(verifier_calls, 1) * 1000, 4),
        "promoted": promoted,
        "pass_rate": round(passes_total / max(gens * n, 1), 6),
        "gen_pass_rate": round(promoted / max(gens, 1), 6),
    }


def self_test():
    v = (0.1, -0.2, 0.3, 0.0, 0.5, -0.1)
    assert abs(P.pearson(v, v) - 1.0) < 1e-9, "S1 fail"
    assert P.pearson((1, 0, 1, 0), (0, 1, 0, 1)) < 0.5, "S2 fail"
    assert abs(P.n_eff(16, 1.0) - 1.0) < 1e-9 and abs(P.n_eff(16, 0.0) - 16.0) < 1e-9, "S3 fail"
    assert P.mean_pairwise_rho([v]) == 1.0, "S4 fail"
    same = (1.0, -0.5, 0.3, 0.8, -0.2, 0.6)
    assert abs(P.mean_pairwise_rho([same for _ in range(4)]) - 1.0) < 1e-9, "S5 fail"
    good = [measured_rho(controlled_propose, r, 16, 1) for r in RHO_GRID]
    bad = [measured_rho(bad_propose, r, 16, 1) for r in RHO_GRID]
    assert all(good[i] <= good[i + 1] + 1e-9 for i in range(len(good) - 1)), f"S6a fail good={good}"
    assert good[0] < 0.5 and abs(good[-1] - 1.0) < 1e-6, f"S6b fail good={good}"
    assert not all(bad[i] <= bad[i + 1] + 1e-9 for i in range(len(bad) - 1)), f"S6c fail bad={bad}"
    assert P.pearson((2.0, 2.0, 2.0), (2.0, 2.0, 2.0)) == 0.0, "S7 fail"
    print("self-test 7/7 PASS; good_rho=" + ",".join(f"{x:.3f}" for x in good)
          + " | bad_rho=" + ",".join(f"{x:.3f}" for x in bad))


def verdict(summary):
    d1_gap = abs(summary[(0.0, 16)]["delta_priv"] - summary[(1.0, 16)]["delta_priv"])
    d1 = "SHAPE_PRESERVED" if d1_gap >= 0.05 else "FLAT_GATE_DOMINANT"
    flips = []
    for r in RHO_GRID:
        if summary[(r, 16)]["rate_per_1k"] >= summary[(r, 4)]["rate_per_1k"]:
            flips.append(r)
    d2 = "RATE_FLIP_ANY" if flips else "RATE_ROBUST_ACROSS_RHO"
    pr4 = [summary[(r, 4)]["pass_rate"] for r in RHO_GRID]
    pr16 = [summary[(r, 16)]["pass_rate"] for r in RHO_GRID]
    dp16 = [summary[(r, 16)]["delta_priv"] for r in RHO_GRID]
    pr_up = all(pr16[i] >= pr4[i] for i in range(len(RHO_GRID)))
    dp_flat = max(dp16) - min(dp16) < 0.05
    if pr_up and dp_flat:
        d3 = "GATE_CENSUS_CONFIRMED"
    elif all(dp16[i] >= dp16[i + 1] - 1e-9 for i in range(len(dp16) - 1)) and pr_up:
        d3 = "GATE_BOTTLENECK"
    else:
        d3 = "MIXED"
    taxes = [summary[(r, 4)]["rate_per_1k"] / max(summary[(r, 16)]["rate_per_1k"], 1e-9)
             for r in RHO_GRID]
    d4 = "TAX_ROBUST" if min(taxes) >= 3.0 else ("TAX_RHO_SENSITIVE" if min(taxes) < 2.0 else "TAX_MIDDLE")
    return {
        "D1_d1_gap": round(d1_gap, 6), "D1": d1,
        "D2_flip_rho": flips, "D2": d2,
        "D3_pass_rate_N4": [round(x, 4) for x in pr4],
        "D3_pass_rate_N16": [round(x, 4) for x in pr16],
        "D3_delta_priv_N16": [round(x, 4) for x in dp16],
        "D3_pass_up": pr_up, "D3_delta_flat": dp_flat, "D3": d3,
        "D4_tax_by_rho": [round(x, 4) for x in taxes],
        "D4_tax_min": round(min(taxes), 4), "D4_tax_max": round(max(taxes), 4), "D4": d4,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--seeds", default="1,2,3")
    ap.add_argument("--gens", type=int, default=12)
    ap.add_argument("--n", default="1,4,16")
    ap.add_argument("--out", default="real_substrate.json")
    a = ap.parse_args()
    if a.self_test:
        self_test()
        return

    seeds = [int(x) for x in a.seeds.split(",")]
    ns = [int(x) for x in a.n.split(",")]
    rows = []
    for r in RHO_GRID:
        for n in ns:
            for s in seeds:
                rows.append(run_arm(r, n, a.gens, s))

    summary = {}
    for r in RHO_GRID:
        for n in ns:
            sub = [x for x in rows if x["rho_param"] == r and x["N"] == n]
            summary[(r, n)] = {k: statistics.fmean(x[k] for x in sub)
                               for k in ("rho_bar", "N_eff", "N_eff_over_N",
                                         "delta_priv", "rate_per_1k",
                                         "pass_rate", "gen_pass_rate")}

    v = verdict(summary)
    print(f"{'rho':>6s} {'N':>3s} {'rho_bar':>8s} {'N_eff':>7s} {'dPriv':>8s} {'rate/1k':>8s} {'pass':>7s}")
    for r in RHO_GRID:
        for n in ns:
            d = summary[(r, n)]
            print(f"{r:6.3f} {n:3d} {d['rho_bar']:8.4f} {d['N_eff']:7.3f} "
                  f"{d['delta_priv']:8.4f} {d['rate_per_1k']:8.3f} {d['pass_rate']:7.4f}")
        print()
    for k, val in v.items():
        print(f"  {k} = {val}")

    Path(a.out).write_text(json.dumps({
        "config": {"rho_grid": RHO_GRID, "seeds": seeds, "ns": ns, "gens": a.gens,
                   "substrate": "T13 ContextualTask + paired_gate, controlled propose"},
        "rows": rows,
        "summary": [{"rho_param": r, "N": n, **summary[(r, n)]} for r in RHO_GRID for n in ns],
        "verdict": v,
    }, indent=1), encoding="utf-8")
    print("\nwrote " + a.out + " rows=" + str(len(rows)))


if __name__ == "__main__":
    main()
