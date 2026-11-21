
"""T12「中等相关迁移红利 / N_eff 不降反升」的取证审计。

被审的句子（T12.md / SUMMARY.md）：
  「N_eff 在 rho<=0.75 不降反升（16->17/16），只在 rho>0.9 断崖」

两条独立的可疑点：
  1. N_eff 是怎么算的？spse.py cmd_nesurf 里是
        neff = gain_E(rho) / gain_E(0) * 16
     这是「相对收益比 × 满刻度假独立数」，不是独立样本数——它天然可以 >N。
     把它当 N_eff 读，等于允许「16 个候选买到 17 条独立臂」。
  2. 该比值是「群体收益 ÷ rho=0 的群体收益」，而 rho=0 与 rho>0 的**任务本身不同**
     （rho 高 = 各族共享真值 = 任务更简单）。所以要同时看端点水平：
     若 E_single 也随 rho 单调上升，则分母与被比较对象都在漂移，
     比值上升不能读成「独立性提高」。

本脚本只复算 nesurf.json，不重新采样底物：
  - 逐 rho：gain_E 均值/sd/SE、配对差 vs rho=0（同 seed）、bootstrap 95% CI、
    t 值、逐 seed 胜率（等价符号检验）
  - 端点水平：E_single / E_swarm / A_single / T_single 随 rho 的漂移（难度混杂）
  - 判决：PROXY_INVALID / LEVEL_CONFOUND / BONUS_ESTABLISHED / BONUS_NOT_ESTABLISHED
    判定用 Bonferroni：只有某 rho 的配对差 CI 全 >0 且 p < 0.05/m（m=被测 rho 数）
    才算「红利成立」。

用法：
  python3 neff_proxy_audit.py --self-test
  python3 neff_proxy_audit.py --in outputs/nesurf.json --out outputs/neff_audit.json
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _paired(diffs, rng, iters=4000):
    mu = statistics.fmean(diffs)
    sd = statistics.stdev(diffs) if len(diffs) > 1 else 0.0
    se = sd / len(diffs) ** 0.5 if sd else 0.0
    boot = sorted(statistics.fmean(rng.choice(diffs) for _ in range(len(diffs)))
                  for _ in range(iters))
    lo = boot[int(0.025 * iters)]
    hi = boot[int(0.975 * iters)]
    # 退化方差（所有配对差恒定）：se=0 时 z 无定义，按符号取 ±inf，p -> 0/1
    if se > 1e-12:
        t = mu / se
    else:
        t = float("inf") if mu > 0 else (float("-inf") if mu < 0 else 0.0)
    return {"mean": mu, "sd": sd, "se": se, "ci95": [lo, hi],
            "t": t, "win_rate": sum(1 for d in diffs if d > 0) / len(diffs)}


def audit(rows, n_scale=16, rng_seed=7):
    """rows: [{'rho','seed','gain_E','E_single','E_swarm','A_single','T_single',...}]"""
    by_rho: dict[float, dict[int, dict]] = {}
    for r in rows:
        by_rho.setdefault(r["rho"], {})[r["seed"]] = r
    rhos = sorted(by_rho)
    seeds = sorted(set.intersection(*[set(v) for v in by_rho.values()]))
    base = by_rho[rhos[0]]
    gain0 = statistics.fmean(base[s]["gain_E"] for s in seeds)
    out = {"rhos": rhos, "seeds": len(seeds), "base_gain_E": gain0, "per_rho": []}
    m = max(1, len(rhos) - 1)
    alpha_bonf = 0.05 / m
    rng = random.Random(rng_seed)

    for rho in rhos:
        d = by_rho[rho]
        g = statistics.fmean(d[s]["gain_E"] for s in seeds)
        e_single = statistics.fmean(d[s]["E_single"] for s in seeds)
        e_swarm = statistics.fmean(d[s]["E_swarm"] for s in seeds)
        proxy = (g / gain0 * n_scale) if gain0 > 0 else float("nan")
        rec = {"rho": rho, "gain_E": g, "E_single": e_single, "E_swarm": e_swarm,
               "proxy_N_eff": proxy, "proxy_gt_N": bool(proxy > n_scale + 1e-9)}
        if rho != rhos[0]:
            diffs = [d[s]["gain_E"] - base[s]["gain_E"] for s in seeds]
            rec.update(_paired(diffs, rng))
            rec["significant_bonf"] = bool(rec["ci95"][0] > 0 and
                                           _p_two_sided(rec["t"]) < alpha_bonf)
        out["per_rho"].append(rec)

    out["alpha_bonferroni"] = alpha_bonf
    out["flags"] = {
        "PROXY_INVALID": any(r["proxy_gt_N"] for r in out["per_rho"]),
        "LEVEL_CONFOUND": (out["per_rho"][-2]["E_single"] / out["per_rho"][0]["E_single"]
                           if out["per_rho"][0]["E_single"] else 1.0) > 1.2,
        "BONUS_ESTABLISHED": any(r.get("significant_bonf") for r in out["per_rho"]),
    }
    pos = [r for r in out["per_rho"] if r.get("mean", 0) > 0]
    if out["flags"]["BONUS_ESTABLISHED"]:
        out["verdict"] = "BONUS_ESTABLISHED"
    else:
        out["verdict"] = "BONUS_NOT_ESTABLISHED"
    out["max_positive_shift"] = max((r["mean"] for r in pos), default=0.0)
    return out


def _p_two_sided(t: float) -> float:
    """正态近似双侧 p（只用于 Bonferroni 粗判，样本 300 下足够）。"""
    import math
    return math.erfc(abs(t) / math.sqrt(2.0))


# --------------------------------------------------- self-test
def _mk(rows_spec):
    """rows_spec: {rho: (gain, E_single, spread)} -> 合成 rows（10 seeds）"""
    out = []
    import random as _r
    for rho, (g, es, spread) in rows_spec.items():
        rr = _r.Random(int(rho * 1000) + 13)
        for s in range(10):
            jitter = (s - 4.5) / 4.5 * spread + rr.gauss(0.0, spread / 4.0)
            out.append({"rho": rho, "seed": s, "gain_E": g + jitter,
                        "E_single": es, "E_swarm": es + g + jitter,
                        "A_single": 0.3, "T_single": 0.2})
    return out


def self_test() -> int:
    fails = []

    def check(name, cond, detail=""):
        print(f"  [{'PASS' if cond else 'FAIL'}] {name} {detail}")
        if not cond:
            fails.append(name)

    # T1 收益恒定 -> proxy 恰为 N、无红利
    a = audit(_mk({0.0: (0.18, 0.07, 0.02), 0.5: (0.18, 0.07, 0.02),
                   1.0: (0.00, 0.30, 0.02)}))
    rec = [r for r in a["per_rho"] if r["rho"] == 0.5][0]
    check("T1 恒定收益 -> proxy==N 且无红利",
          abs(rec["proxy_N_eff"] - 16) < 0.6 and a["verdict"] == "BONUS_NOT_ESTABLISHED",
          f"proxy={rec['proxy_N_eff']:.3f} verdict={a['verdict']}")

    # T2 收益 1.5x -> proxy=24 > N，必须被标 PROXY_INVALID
    b = audit(_mk({0.0: (0.10, 0.07, 0.01), 0.75: (0.15, 0.07, 0.01)}))
    check("T2 收益 1.5x -> proxy 越界被抓",
          b["flags"]["PROXY_INVALID"] and abs(b["per_rho"][1]["proxy_N_eff"] - 24) < 0.9,
          f"proxy={b['per_rho'][1]['proxy_N_eff']:.2f}")

    # T3 收益不变但 E_single 翻倍 -> 必须标 LEVEL_CONFOUND
    c = audit(_mk({0.0: (0.18, 0.06, 0.01), 0.9: (0.18, 0.16, 0.01), 1.0: (0.0, 0.32, 0.01)}))
    check("T3 端点水平漂移 -> LEVEL_CONFOUND", c["flags"]["LEVEL_CONFOUND"],
          f"E_single 0.06->0.32")

    # T4 大而稳的正向配对差 -> 红利成立
    d = audit(_mk({0.0: (0.10, 0.07, 0.005), 0.25: (0.14, 0.07, 0.005)}))
    check("T4 稳定正差 -> BONUS_ESTABLISHED", d["verdict"] == "BONUS_ESTABLISHED",
          f"t={d['per_rho'][1]['t']:.1f}")

    # T5 小差多比较 -> Bonferroni 后不成立（防「挑一个显著」）
    e = audit(_mk({0.0: (0.100, 0.07, 0.06), 0.25: (0.108, 0.07, 0.06),
                   0.5: (0.110, 0.07, 0.06), 0.75: (0.112, 0.07, 0.06),
                   0.9: (0.109, 0.07, 0.06), 0.945: (0.101, 0.07, 0.06),
                   1.0: (0.0, 0.32, 0.06)}))
    check("T5 多比较下小差不成立", e["verdict"] == "BONUS_NOT_ESTABLISHED",
          f"alpha_bonf={e['alpha_bonferroni']:.4f}")

    if fails:
        print(f"\nSELF-TEST FAILED: {len(fails)} -> {fails}")
        return 1
    print("\nSELF-TEST ALL PASS")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--in", dest="inp", default="outputs/nesurf.json")
    ap.add_argument("--out", default="outputs/neff_audit.json")
    ap.add_argument("--scale", type=int, default=16)
    args = ap.parse_args()
    if args.self_test:
        return self_test()

    rows = json.loads((HERE / args.inp).read_text(encoding="utf-8"))
    res = audit(rows, n_scale=args.scale)
    (HERE / args.out).write_text(json.dumps(res, indent=2, ensure_ascii=False),
                                 encoding="utf-8")
    print(f"\n{'rho':>6}{'gain_E':>10}{'E_single':>10}{'proxy':>8}"
          f"{'diff':>9}{'t':>7}{'win':>6}  CI95")
    for r in res["per_rho"]:
        ci = r.get("ci95")
        citxt = f"[{ci[0]:+.4f},{ci[1]:+.4f}]" if ci else ""
        print(f"{r['rho']:>6}{r['gain_E']:>10.4f}{r['E_single']:>10.4f}"
              f"{r['proxy_N_eff']:>8.2f}"
              f"{(r.get('mean') or 0):>+9.4f}{(r.get('t') or 0):>+7.2f}"
              f"{(r.get('win_rate') or 0):>6.2f}  {citxt}")
    print(f"\nalpha_bonf={res['alpha_bonferroni']:.4f}  flags={res['flags']}"
          f"\nVERDICT = {res['verdict']}  max_positive_shift={res['max_positive_shift']:+.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
