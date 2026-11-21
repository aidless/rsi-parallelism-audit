#!/usr/bin/env python3
"""T10 - 独立性与带宽的联合曲面（把 T5 的 rho_bar 与 T7 的 (rho,B) 焊到同一底物上）。

问题
----
T5 实测 ρ̄=0.945 只是一个单点读数；T7 的 (ρ,B) 分区建在合成底物上。
两者从未在同一底物上扫过 ρ。这里把「候选间相关 ρ」做成自变量，量三件事：

  1. **有效独立样本数 N_eff(ρ,N)**：操作化定义为
     N_eff = Δ₀⁻¹( Δ(ρ,N) )，其中 Δ₀ 是 ρ=0 时同一 N 的增益曲线（单调，可插值反解）。
     这个定义不依赖任何公式假设，只凭「同增益 ⇒ 等效独立度」。
  2. **每预算效率** Δ/(c·N)：回答「加宽候选值不值」。
  3. **净赚临界 rho_star**：给定协调税 κ（T7 实测 ≈4× 预算），解
     Δ(ρ,N) − Δ(ρ,1) > κ·c·(N−1) 的 ρ 上界。

底物（与 T7 同族，可解析）
--------------------------
  u ~ N(0,1)^k                      共享方向（环境的「真信号」）
  v_i ~ N(0,1)^k                    个体方向
  w*_i = sqrt(ρ)·u + sqrt(1−ρ)·v_i  候选 i 的真参数
  q_i  = <w*_i, u>/||u||            候选 i 的真实质量（只由共享分量决定）
  ŝ_i  = q_i + ε_i,  ε ~ N(0, σ²)   验证器带噪观测
  选择 i* = argmax ŝ_i，增益 Δ = q_{i*} − E[q_1]（相对单候选基线）

ρ=0 时候选质量独立 ⇒ best-of-N 有经典增益；ρ→1 时所有 q_i 相同 ⇒ 选谁都没用，
Δ→0、N_eff→1。这正是 T5 里 ρ̄=0.945 的含义。

用法
----
  python3 independence_surface.py --self-test
  python3 independence_surface.py --seeds 200 --out .            # 默认网格
  python3 independence_surface.py --seeds 200 --rhos 0,0.5,0.9,0.95,1.0 --ns 1,2,4,8,16,32,64
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np


# ---------------------------------------------------------------- 底物

def true_quality(rng: np.random.Generator, k: int, rho: float, n: int) -> np.ndarray:
    """返回 n 个候选的真实质量 q_i = <w*_i, u>/||u||。

    w*_i = sqrt(ρ)u + sqrt(1−ρ)v_i  ⇒  q_i = sqrt(ρ)||u|| + sqrt(1−ρ)<v_i,u>/||u||
    取 ||u||=sqrt(k) 归一无损（常数平移不影响增益），于是
      q_i = sqrt(ρ·k) + sqrt(1−ρ)·<v_i, u>/sqrt(k)
    """
    u = rng.standard_normal(k)
    u = u / np.linalg.norm(u) * math.sqrt(k)
    v = rng.standard_normal((n, k))
    return math.sqrt(rho) * (u @ u) / np.linalg.norm(u) + math.sqrt(1.0 - rho) * (v @ u) / np.linalg.norm(u)


def arm_delta(rng: np.random.Generator, k: int, rho: float, n: int, sigma: float) -> float:
    """一次「抽 n 个候选、带噪选最大」的真实增益（相对单候选期望）。"""
    q = true_quality(rng, k, rho, n)
    s_hat = q + rng.standard_normal(n) * sigma
    i_star = int(np.argmax(s_hat))
    # 基线 = 单候选的期望质量（解析：sqrt(ρ)·sqrt(k)）
    baseline = math.sqrt(rho) * math.sqrt(k)
    return float(q[i_star] - baseline)


def mean_delta(rho: float, n: int, seeds: int, sigma: float, k: int, rng_seed: int) -> float:
    rng = np.random.default_rng(rng_seed)
    return float(np.mean([arm_delta(rng, k, rho, n, sigma) for _ in range(seeds)]))


# ---------------------------------------------------------------- N_eff 反解

def invert_neff(delta: float, curve_rho0: dict[int, float], n_cap: int | None = None) -> float:
    """给定 Δ(ρ,N)，在 ρ=0 的曲线 Δ₀(N_eff) 上反解等效独立样本数。

    curve_rho0 必须按 N 升序且 Δ 单调不减。
    **硬上界 n_cap**：给定 N 个候选，等效独立度不可能超过 N（σ=0 时取等）。
    反解只在 {n in curve: n <= n_cap} 上插值，越界截断到 [1, n_cap]。
    没有这条上界，蒙特卡洛噪声会让 N_eff 冒过 N（实测 8 候选算出 9.37）。
    """
    ns = [n for n in sorted(curve_rho0) if n_cap is None or n <= n_cap]
    if not ns:
        ns = sorted(curve_rho0)
    ds = [curve_rho0[n] for n in ns]
    if delta <= ds[0]:
        return 1.0
    if delta >= ds[-1]:
        return float(ns[-1])
    for i in range(1, len(ns)):
        if delta <= ds[i]:
            lo, hi = ds[i - 1], ds[i]
            frac = 0.0 if hi == lo else (delta - lo) / (hi - lo)
            return float(ns[i - 1] + frac * (ns[i] - ns[i - 1]))
    return float(ns[-1])


# ---------------------------------------------------------------- 主网格

def build_surface(rhos: list[float], ns: list[int], seeds: int, sigma: float,
                  k: int, seed0: int) -> dict:
    rho0_curve = {n: mean_delta(0.0, n, seeds, sigma, k, seed0 + n) for n in ns}
    rows = []
    for rho in rhos:
        for n in ns:
            d = mean_delta(rho, n, seeds, sigma, k, seed0 + n + int(rho * 1000))
            rows.append({
                "rho": rho,
                "n": n,
                "delta": round(d, 6),
                "delta_per_1k_budget": round(1000.0 * d / n, 4),
                "n_eff": round(invert_neff(d, rho0_curve, n_cap=n), 4),
                "n_eff_over_n": round(invert_neff(d, rho0_curve, n_cap=n) / n, 4),
            })
    return {"rho0_curve": {str(k_): round(v, 6) for k_, v in rho0_curve.items()}, "rows": rows}


def critical_rho(rows: list[dict], n: int, a: float) -> float | None:
    """解 Δ(ρ,n) − Δ(ρ,1) > a·(n−1) 的最大 ρ；无解返回 None。

    单位说明（必须连这句一起读）：
      Δ 是**质量单位**（真实得分的期望提升），成本是**判分次数**。
      两者不可直接比较，故引入外部换算系数 a = 「多验一个候选所值的质量」。
      a 不是本实验测出来的量，它是使用者的成本模型；本量表只给 (ρ, a) 分区，
      不给「该不该并行」的绝对结论。a 小 = 判分便宜（该加宽），
      a 大 = 判分昂贵或协调开销高（该收窄）。
    """
    by_rho = {}
    for r in rows:
        by_rho.setdefault(r["rho"], {})[r["n"]] = r["delta"]
    ok = []
    for rho, dmap in by_rho.items():
        if 1 not in dmap or n not in dmap:
            continue
        if dmap[n] - dmap[1] > a * (n - 1):
            ok.append(rho)
    return max(ok) if ok else None


# ---------------------------------------------------------------- self-test

def self_test() -> int:
    """四断言：能红能绿。任一失败 → exit 2。"""
    fails = []
    ns = [1, 2, 4, 8, 16, 32]
    seed0 = 7000

    # A1: ρ=1 ⇒ 所有候选同质 ⇒ Δ≈0 且 N_eff≈1
    d1 = mean_delta(1.0, 16, 400, 0.3, 8, seed0)
    if abs(d1) > 0.05:
        fails.append(f"A1 rho=1 delta={d1:.4f} 应≈0")
    # A2: ρ=0 ⇒ N_eff 应接近 N（±35%）
    curve0 = {n: mean_delta(0.0, n, 400, 0.3, 8, seed0 + n) for n in ns}
    neff0 = invert_neff(curve0[16], curve0, n_cap=16)
    if not (16 * 0.65 <= neff0 <= 16 * 1.35):
        fails.append(f"A2 rho=0 N_eff={neff0:.2f} 应≈16")
    # A3: N_eff 随 ρ 单调不增
    seq = [invert_neff(mean_delta(r, 16, 200, 0.3, 8, seed0 + 11), curve0, n_cap=16)
           for r in (0.0, 0.5, 0.9, 0.99)]
    for a, b in zip(seq, seq[1:]):
        if b > a + 0.05:
            fails.append(f"A3 N_eff 非单调: {seq}")
            break
    # A4: 1 ≤ N_eff ≤ N 恒成立
    for r in (0.0, 0.5, 0.95):
        v = invert_neff(mean_delta(r, 8, 100, 0.3, 8, seed0 + 3), curve0, n_cap=8)
        if not (1.0 - 1e-9 <= v <= 8 + 1e-9):
            fails.append(f"A4 N_eff={v:.3f} 越界 rho={r}")

    # A5: critical_rho 的判据逻辑本身要对——a 越大 rho* 越小，a 超阈值时无解
    fake = []
    for rho, d16 in ((0.0, 1.5), (0.5, 1.0), (0.9, 0.3)):
        fake += [{"rho": rho, "n": 1, "delta": 0.0}, {"rho": rho, "n": 16, "delta": d16}]
    r_lo = critical_rho(fake, 16, 0.01)   # 阈值 0.15 → 0.9 仍过（0.3>0.15）
    r_hi = critical_rho(fake, 16, 0.05)   # 阈值 0.75 → 0.5 过（1.0>0.75）、0.9 不过
    r_no = critical_rho(fake, 16, 10.0)   # 阈值 150 → 无解
    if r_lo != 0.9 or r_hi != 0.5 or r_no is not None:
        fails.append(f"A5 critical_rho 逻辑错: lo={r_lo} hi={r_hi} no={r_no}")

    if fails:
        for f in fails:
            print("SELFTEST FAIL:", f)
        return 2
    print("self-test OK: 5/5")
    print(f"  rho=0  N_eff(N=16) = {neff0:.2f}")
    print(f"  rho=1  delta(N=16) = {d1:.4f}")
    print(f"  N_eff 序列 rho=0/.5/.9/.99 = {[round(x,2) for x in seq]}")
    return 0


# ---------------------------------------------------------------- CLI

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rhos", default="0,0.25,0.5,0.75,0.9,0.945,0.99,1.0")
    ap.add_argument("--ns", default="1,2,4,8,16,32,64")
    ap.add_argument("--seeds", type=int, default=400)
    ap.add_argument("--sigma", type=float, default=0.5, help="验证器观测噪声")
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--seed", type=int, default=7000)
    ap.add_argument("--as_", default="0.005,0.01,0.02,0.05", help="每候选机会成本 a 的扫描格（质量单位）")
    ap.add_argument("--nstar", type=int, default=16, help="临界 rho 在哪个 N 上解")
    ap.add_argument("--out", default=".")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()

    if a.self_test:
        return self_test()

    rhos = [float(x) for x in a.rhos.split(",")]
    ns = [int(x) for x in a.ns.split(",")]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    surf = build_surface(rhos, ns, a.seeds, a.sigma, a.k, a.seed)
    rows = surf["rows"]

    # 汇总表：每个 ρ 一行，报 N_eff/N 与效率比
    summary = []
    for rho in rhos:
        sub = [r for r in rows if r["rho"] == rho]
        neff16 = next((r["n_eff"] for r in sub if r["n"] == 16), None)
        eff_n16 = next((r["n_eff_over_n"] for r in sub if r["n"] == 16), None)
        d1 = next((r["delta"] for r in sub if r["n"] == 1), None)
        d16 = next((r["delta"] for r in sub if r["n"] == 16), None)
        summary.append({
            "rho": rho, "n_eff_at_16": neff16, "n_eff_over_n_at_16": eff_n16,
            "delta_n1": d1, "delta_n16": d16,
        })

    payload = {
        "config": {"rhos": rhos, "ns": ns, "seeds": a.seeds, "sigma": a.sigma,
                   "k": a.k, "seed": a.seed, "a_grid": [float(x) for x in a.as_.split(",")],
                   "nstar": a.nstar},
        "rho0_curve": surf["rho0_curve"],
        "rows": rows,
        "summary": summary,
        "a_grid": [float(x) for x in a.as_.split(",")],
        "critical_rho": {str(a_): critical_rho(rows, a.nstar, a_) for a_ in
                         [float(x) for x in a.as_.split(",")]},
    }
    (out / "independence.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # CSV
    lines = ["rho,n,delta,delta_per_1k_budget,n_eff,n_eff_over_n"]
    for r in rows:
        lines.append(f'{r["rho"]},{r["n"]},{r["delta"]},{r["delta_per_1k_budget"]},{r["n_eff"]},{r["n_eff_over_n"]}')
    (out / "independence.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"{'rho':>6} {'N_eff@16':>9} {'N_eff/N':>8} {'Delta@1':>9} {'Delta@16':>9}")
    for s in summary:
        print(f'{s["rho"]:>6.3f} {s["n_eff_at_16"]:>9.2f} {s["n_eff_over_n_at_16"]:>8.3f} '
              f'{s["delta_n1"]:>9.4f} {s["delta_n16"]:>9.4f}')
    print(f"\n每候选机会成本 a → 加宽到 N={a.nstar} 仍净赚的最大 rho：")
    for a_, r_ in payload["critical_rho"].items():
        print(f"  a={a_:<7} rho* = {r_ if r_ is not None else '无解（任何 rho 都不净赚）'}")
    print(f"落盘: {out/'independence.json'}, {out/'independence.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())