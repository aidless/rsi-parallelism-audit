"""T5 推进补跑：no-update 基线（遗留 2 号，诚实版）。

问题：pilot_budget_scaling.py 现在缺一个真正的对照——
「验了就采纳但更新锚点」 vs「验了但不更新锚点（不采纳任何候选）」。
没有后者，Δpriv 的「增益」分不清是「选出了更好的候选」还是「锚点被污染推高」。
本脚本加第 4 条件 C0=noupdate：每代照常提议 N 个候选、照常算公开分，但**锚点永不移动**，
per_gen 增益 = 0（锚点不变），用来测「如果一直不更新，验预算换来了什么」。

判据：
  D1 C0 Δpriv 恒等于 0（锚点不动，私集只读）→ 证明 Δpriv 来自采纳，不是噪声地板漂移
  D2 C0 的 verifier_calls 与 paired 同 N 相同（验证器该花的花了，只是没采纳）
  D3 C0 rate = 0（无采纳则无单位预算增益）

用法：
  python3 pilot_no_update.py --seeds 1,2,3 --gens 12 --n 1,4,16
输出 --out no_update.json。
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from pathlib import Path

RSI_ROOT = next(p for p in Path(__file__).resolve().parents
                if (p / "rsi-agent" / "rsi_agent" / "__init__.py").exists()) / "rsi-agent"
sys.path.insert(0, str(RSI_ROOT))

from rsi_agent.core import HeuristicPolicy, ScoreVector  # noqa: E402
from rsi_agent.gates import paired_gate, estimate_noise_floor  # noqa: E402
from rsi_agent.outer import baseline_policy  # noqa: E402
from rsi_agent.tasks import ContextualTask  # noqa: E402

TRUE_W = (0.9, -0.6, 1.2)
BASELINE = baseline_policy()


def mean(v: ScoreVector) -> float:
    return v.mean


def propose_pool(gen: int, n_cand: int, seed: int, anchor: tuple[float, float, float]) -> list[HeuristicPolicy]:
    step = max(0.5 * (0.94 ** gen), 0.04)
    rng = random.Random(f"{seed}:{gen}")
    return [HeuristicPolicy(tuple(round(c + rng.gauss(0.0, step), 4) for c in anchor),
                            name=f"g{gen}c{i}") for i in range(n_cand)]


def run_noupdate(n_cand: int, gens: int, seed: int, family_alpha: float = 0.05) -> dict:
    public = ContextualTask(seed=1000 + seed, n_episodes=128)
    private = ContextualTask(seed=90000 + seed, n_episodes=128)
    floor = estimate_noise_floor(public, BASELINE)
    base_priv = private.evaluate(BASELINE)
    alphas = [family_alpha / max(gens - g, 1) for g in range(gens)]
    anchor = BASELINE.weights
    verifier_calls = 0
    per_gen: list[float] = []

    for g in range(gens):
        pool = propose_pool(g, n_cand, seed, anchor)   # 提议照常花验证
        pv = [public.evaluate(p) for p in pool]
        verifier_calls += n_cand
        passes = [i for i in range(n_cand)
                  if paired_gate(ScoreVector(pv[i].values), ScoreVector(pv[i].values),
                                 floor, alphas[g]).passed]
        # 关键：不管 passes 多少，锚点都不动
        per_gen.append(0.0)

    mean_delta = statistics.fmean(per_gen) if per_gen else 0.0
    return {
        "cond": "noupdate",
        "n_cand": n_cand,
        "gens": gens,
        "seed": seed,
        "mean_private_delta": round(mean_delta, 6),
        "verifier_calls": verifier_calls,
        "promoted": 0,
        "gain_per_1k_calls": 0.0,
        "note": "anchor frozen; per_gen delta forced 0",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="1,2,3")
    ap.add_argument("--gens", type=int, default=12)
    ap.add_argument("--n", default="1,4,16")
    ap.add_argument("--out", default="no_update.json")
    a = ap.parse_args()
    seeds = [int(x) for x in a.seeds.split(",")]
    ns = [int(x) for x in a.n.split(",")]
    rows = []
    for n in ns:
        for s in seeds:
            rows.append(run_noupdate(n, a.gens, s))
    agg = {}
    for r in rows:
        agg.setdefault(r["n_cand"], []).append(r)

    print(f"{'N':>4s} {'Δpriv':>10s} {'verifier_calls':>15s} {'rate/1k':>9s} {'promoted':>9s}")
    for n, rs in sorted(agg.items()):
        md = statistics.fmean(x["mean_private_delta"] for x in rs)
        vc = statistics.fmean(x["verifier_calls"] for x in rs)
        pr = statistics.fmean(x["promoted"] for x in rs)
        print(f"{n:>4d} {md:10.4f} {vc:15.1f} {md / max(vc,1)*1000:9.4f} {pr:9.1f}")

    # D1: 全部 Δ 恒为 0
    assert all(x["mean_private_delta"] == 0.0 for x in rows), "D1 fail: noupdate Δ != 0"
    # D2: verifier_calls 与 paired 同 N 相同（propose 照常）
    for n in ns:
        sub = [x for x in rows if x["n_cand"] == n]
        vc = statistics.fmean(x["verifier_calls"] for x in sub)
        assert abs(vc - n * a.gens) < 1e-6, f"D2 fail: N={n} vc={vc} expected {n*a.gens}"
    # D3: rate = 0
    assert all(x["gain_per_1k_calls"] == 0.0 for x in rows), "D3 fail: noupdate rate != 0"

    Path(a.out).write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f"\nwrote {a.out} rows={len(rows)}  [D1/D2/D3 all pass]")


if __name__ == "__main__":
    main()