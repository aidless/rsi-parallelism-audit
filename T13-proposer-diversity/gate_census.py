
"""T13 闸门原因普查 + 松弛反事实：加宽亏损到底是「过不了闸」还是「饱和」？

背景（T13 遗留）：T13 的机制解释是「多样池里多数候选过不了闸 → 多出的候选纯付
验证费、零采纳」。但 paired_gate 有五道判据（ESS / delta>0 / N_floor / p<alpha /
regression_burden），T13 只换了 alpha 的 schedule，从未记录**哪一道**在拒。
本脚本做两件事：

  A. 原因普查（census）：逐候选记录 GateResult.reason 的类别，给出每档
     提案器 × N 的拒绝原因分布与采纳率。
  B. 松弛反事实（relax）：一次只放松一道判据（alpha / noise floor / ESS /
     burden），看 rate(N=16)/rate(N=4) 是否翻正。翻正 = 亏损是闸参数造成（可调）；
     不翻正 = 亏损是饱和造成（结构性）。

纪律：不改 rsi_agent 源码，只用 paired_gate 的既有 kwargs 与 noise_floor 实参。

用法：
  python3 gate_census.py --self-test
  python3 gate_census.py --census --relax --seeds 1,2,3 --gens 12 --out census.json
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import proposer_diversity as P  # noqa: E402

from rsi_agent.gates import paired_gate, estimate_noise_floor  # noqa: E402
from rsi_agent.core import ScoreVector  # noqa: E402

REASONS = ("PASS", "ESS_TOO_LOW", "NO_GAIN", "BELOW_NOISE",
           "NOT_SIGNIFICANT", "REGRESSION_BURDEN", "INVALID")


def classify(reason: str) -> str:
    r = reason.split()[0].rstrip(":")
    for k in REASONS:
        if r.startswith(k):
            return k
    return "OTHER"


def gate(base_view, view, floor, alpha, min_ess=8.0, burden=0.25):
    return paired_gate(base_view, view, floor, alpha,
                       min_ess=min_ess, max_regression_burden=burden)


def run_arm_census(mode: str, n: int, gens: int, seed: int,
                   relax: dict | None = None, family_alpha: float = 0.05) -> dict:
    """与 P.run_arm 逐步等价，只是记录每道闸的裁决。"""
    relax = relax or {}
    public = P.ContextualTask(seed=1000 + seed, n_episodes=128)
    private = P.ContextualTask(seed=90000 + seed, n_episodes=128)
    floor = estimate_noise_floor(public, P.BASELINE)
    if relax.get("floor_off"):
        floor = floor * 1e-4                       # 让 N_floor 门失效
    base_pub = public.evaluate(P.BASELINE)
    base_priv = private.evaluate(P.BASELINE)
    base_view = ScoreVector(base_pub.values)
    alphas = [family_alpha / max(gens - g, 1) for g in range(gens)]
    if relax.get("alpha"):
        alphas = [float(relax["alpha"])] * gens
    min_ess = 1.0 if relax.get("ess_off") else 8.0
    burden = None if relax.get("burden_off") else 0.25

    anchor = P.BASELINE.weights
    per_gen_delta, per_gen_rho = [], []
    verifier_calls = promoted = 0
    reason_counts: dict[str, int] = {k: 0 for k in REASONS + ("OTHER",)}

    for g in range(gens):
        pool = P.propose(mode, g, n, seed, anchor)
        pv_pub = [public.evaluate(p) for p in pool]
        pv_priv = [private.evaluate(p) for p in pool]
        verifier_calls += n
        if n >= 2:
            dvecs = [P.delta_vector(x, base_pub) for x in pv_pub]
            per_gen_rho.append(P.mean_pairwise_rho(dvecs))
        views = [ScoreVector(x.values) for x in pv_pub]
        results = [gate(base_view, views[i], floor, alphas[g], min_ess, burden)
                   for i in range(n)]
        for res in results:
            reason_counts[classify(res.reason)] += 1
        passes = [i for i, r in enumerate(results) if r.passed]
        k = max(passes, key=lambda i: views[i].mean) if passes else None
        if k is None:
            continue
        anchor = pool[k].weights
        per_gen_delta.append(pv_priv[k].mean - base_priv.mean)
        promoted += 1

    rho_bar = statistics.fmean(per_gen_rho) if per_gen_rho else 1.0
    delta_priv = statistics.fmean(per_gen_delta) if per_gen_delta else 0.0
    return {
        "mode": mode, "N": n, "seed": seed, "gens": gens, "relax": relax,
        "rho_bar": round(rho_bar, 6),
        "delta_priv": round(delta_priv, 6),
        "promoted": promoted,
        "pass_rate": round(promoted / gens, 4),
        "cand_pass_rate": round(reason_counts["PASS"] / max(verifier_calls, 1), 4),
        "verifier_calls": verifier_calls,
        "rate_per_1k": round(delta_priv / max(verifier_calls, 1) * 1000, 4),
        "reasons": reason_counts,
    }


def aggregate(rows):
    out = []
    keys = sorted({(r["mode"], r["N"], json.dumps(r["relax"], sort_keys=True)) for r in rows})
    for mode, n, rk in keys:
        rs = [r for r in rows if r["mode"] == mode and r["N"] == n
              and json.dumps(r["relax"], sort_keys=True) == rk]
        m = {
            "mode": mode, "N": n, "relax": json.loads(rk), "seeds": len(rs),
            "rho_bar": statistics.fmean(r["rho_bar"] for r in rs),
            "delta_priv": statistics.fmean(r["delta_priv"] for r in rs),
            "pass_rate": statistics.fmean(r["pass_rate"] for r in rs),
            "cand_pass_rate": statistics.fmean(r["cand_pass_rate"] for r in rs),
            "rate_per_1k": statistics.fmean(r["rate_per_1k"] for r in rs),
        }
        agg: dict[str, float] = {}
        for r in rs:
            for k, v in r["reasons"].items():
                agg[k] = agg.get(k, 0.0) + v / len(rs)
        m["reasons"] = {k: round(v, 2) for k, v in agg.items()}
        m["_rk"] = rk
        out.append(m)

    # 相对 默认闸 的 rate(16)/rate(4)
    for m in out:
        b = next((x for x in out if x["mode"] == m["mode"] and x["N"] == 4
                  and x["_rk"] == m["_rk"]), None)
        m["rate16_over_rate4"] = (round(m["rate_per_1k"] / b["rate_per_1k"], 3)
                                  if b and b["rate_per_1k"] else None)
    return out


def cmd_census(args, relax_list):
    seeds = [int(s) for s in args.seeds.split(",")]
    ns = [int(x) for x in args.n.split(",")]
    modes = args.modes.split(",")
    rows = []
    for relax in relax_list:
        for mode in modes:
            for n in ns:
                for seed in seeds:
                    rows.append(run_arm_census(mode, n, args.gens, seed, relax))
    agg = aggregate(rows)
    (HERE / args.out).write_text(json.dumps({"rows": rows, "agg": agg}, indent=2),
                                 encoding="utf-8")
    print(f"\n{'mode':<14}{'N':>3} {'relax':<22}{'rho':>6}{'pass':>6}"
          f"{'candP':>6}{'rate/1k':>9}{'r16/r4':>8}  reasons")
    for m in agg:
        r = ", ".join(f"{k[:6]}={v:g}" for k, v in m["reasons"].items() if v)
        print(f"{m['mode']:<14}{m['N']:>3} {m['_rk'][:22]:<22}{m['rho_bar']:>6.2f}"
              f"{m['pass_rate']:>6.2f}{m['cand_pass_rate']:>6.2f}"
              f"{m['rate_per_1k']:>9.3f}"
              f"{(m['rate16_over_rate4'] if m['N'] == 16 else float('nan')):>8.3f}  {r}")
    return agg


# ------------------------------------------------ self-test（门可红可绿）
def self_test() -> int:
    fails = []

    def check(name, cond, detail=""):
        if cond:
            print(f"  [PASS] {name} {detail}")
        else:
            print(f"  [FAIL] {name} {detail}")
            fails.append(name)

    # T1 原因分类：每条真实 reason 字符串都必须落到唯一类别
    samples = {
        "PASS delta=0.1 N/floor=2.0 p=0.01": "PASS",
        "ESS_TOO_LOW ess=2.00<8.0": "ESS_TOO_LOW",
        "NO_GAIN delta=-0.001": "NO_GAIN",
        "BELOW_NOISE delta=0.0100<floor=0.0200": "BELOW_NOISE",
        "NOT_SIGNIFICANT p=0.4000>=alpha=0.0500": "NOT_SIGNIFICANT",
        "REGRESSION_BURDEN burden=0.900>max=0.25": "REGRESSION_BURDEN",
    }
    ok = all(classify(k) == v for k, v in samples.items())
    check("T1 六类 reason 唯一归并", ok,
          str({k: classify(k) for k in samples}))

    # T2 等价性：普查臂必须逐位复现 run_arm 的出版数字（同一 seed）
    ref = P.run_arm("multi-anchor", 16, 12, 1)
    got = run_arm_census("multi-anchor", 16, 12, 1)
    same = (abs(ref["rho_bar"] - got["rho_bar"]) < 1e-9
            and abs(ref["delta_priv"] - got["delta_priv"]) < 1e-9
            and ref["promoted"] == got["promoted"])
    check("T2 复现 T13 已发布读数（N=16 multi-anchor s1）", same,
          f"ref=({ref['rho_bar']:.4f},{ref['delta_priv']:.4f},{ref['promoted']}) "
          f"got=({got['rho_bar']:.4f},{got['delta_priv']:.4f},{got['promoted']})")

    # T3 burden 闸可红可绿：一段「多数负 delta」的候选在默认闸下被 burden 拒，
    #    关掉 burden 后必须不再以同一原因被拒（证明该旋钮真的咬合）。
    base = ScoreVector(tuple([0.5] * 40))
    # 均值正（+0.155）、但负向总量/正向总量 = 7.8/14 = 0.557 > 0.25 -> burden 拒
    wide = ScoreVector(tuple([0.5 + (1.0 if i % 3 == 0 else -0.3) for i in range(40)]))
    r_strict = gate(base, wide, 1e-6, 0.2)
    r_loose = gate(base, wide, 1e-6, 0.2, burden=None)
    check("T3 burden 旋钮可红可绿",
          (not r_strict.passed) and r_loose.passed,
          f"strict={classify(r_strict.reason)} loose={r_loose.passed}")

    # T4 floor 旋钮可红可绿：抬 floor 必然造出 BELOW_NOISE，压 floor 后消失
    small = ScoreVector(tuple([0.501] * 40))
    hi = gate(base, small, 10.0, 0.05, burden=None)
    lo = gate(base, small, 1e-6, 0.05, burden=None)
    check("T4 floor 旋钮可红可绿",
          classify(hi.reason) == "BELOW_NOISE" and classify(lo.reason) != "BELOW_NOISE",
          f"hi={classify(hi.reason)} lo={classify(lo.reason)}")

    # T5 alpha 旋钮可红可绿
    # 均值 +0.002、sd 0.1 -> z≈0.13、p≈0.45：只在 alpha 极小时被拒
    mid = ScoreVector(tuple([0.5 + (0.102 if i % 2 == 0 else -0.098) for i in range(40)]))
    tight = gate(base, mid, 1e-6, 1e-3, burden=None)
    loose = gate(base, mid, 1e-6, 0.9, burden=None)
    check("T5 alpha 旋钮可红可绿",
          (not tight.passed) and loose.passed,
          f"tight={classify(tight.reason)} loose={loose.passed}")

    if fails:
        print(f"\nSELF-TEST FAILED: {len(fails)} -> {fails}")
        return 1
    print("\nSELF-TEST ALL PASS")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--census", action="store_true")
    ap.add_argument("--relax", action="store_true")
    ap.add_argument("--modes", default="single-small,multi-anchor,structured")
    ap.add_argument("--n", default="4,16")
    ap.add_argument("--seeds", default="1,2,3")
    ap.add_argument("--gens", type=int, default=12)
    ap.add_argument("--out", default="census.json")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    relax_list = [{}]
    if args.relax:
        relax_list += [{"alpha": 0.5}, {"floor_off": True},
                       {"ess_off": True}, {"burden_off": True}]
    if args.census or args.relax:
        cmd_census(args, relax_list)
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
