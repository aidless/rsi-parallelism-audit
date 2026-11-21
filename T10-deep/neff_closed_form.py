#!/usr/bin/env python3
"""T10-deep — 闭合 N_eff–ρ 的函数形式问题（解析底物，不外推真实系统）。

问题
----
T10 §7 审计判定 SYMBOL_SEMANTIC_COLLISION：Kish 公式 N/(1+(N-1)ρ)（方差膨胀口径）
与曲线反解 Δ₀⁻¹(Δ(ρ,N))（增益等值口径）共用符号 N_eff，中段 ρ=0.5 差 2.83×。
本仪器把两条曲线都写成闭式并量化差距来源：

  1. Kish：给定闭式，端点/单调性直接钉死。
  2. 反解：T10 底物 q_i = √(ρk) + √(1−ρ)·z_i，z_i iid N(0,1)，ŝ_i = q_i + ε_i，ε~N(0,σ²)。
     令 W_i = √(1−ρ)z_i + ε_i ~ N(0,1−ρ+σ²)，argmax 由 W 决定；
     Cov(√(1−ρ)z_i, W_i)=1−ρ，故对高斯共同选择最大值有
       Δ_exact(ρ,N) = (1−ρ)/√(1−ρ+σ²) · a_N，  a_N = E[max of N iid N(0,1)]。
     无噪 σ→0：Δ = √(1−ρ)·a_N；反解闭式 N_eff_inv = A⁻¹(a_N·√(1−ρ))，
     A(m)=a_m 在 log m 上插值并钳位 [1,N]。
     ⇒ 反解口径由「极值统计 × 幅度收缩」决定；Kish 由「1/(1+(N−1)ρ) 有理衰减」决定。
  2b. 带噪精确增益还有更简洁的闭式：Δ(ρ,N;σ) = (1−ρ)/√(1−ρ+σ²) · a_N。
     推导：W_i=√(1−ρ)z_i+ε_i ~ N(0,1−ρ+σ²)，Cov(√(1−ρ)z_i,W_i)=1−ρ，
     故 E[√(1−ρ)z_{argmax W}] = Cov/√(Var(W))·a_N。
  3. 差距分解（乘法、精确到浮点）：
       ratio = inv/Kish = [inv/A_inv] · [A_inv/Kish]
     第一项 = MC+分段线性插值伪影（应≈1）；第二项 = 纯泛函形状差（2.8× 的来源）。
     另报「有效相关映射」ρ_kish = (N/N_eff − 1)/(N−1)：两口径要对上数，
     Kish 必须喂一个远大于生成 ρ 的相关（ρ=0.5 → ≈0.925）。

self-test 断言（--self-test，任一失败 exit 2；--prove-red 注入违规证明能红）
  A1 Kish(ρ=0)=N；A2 Kish(ρ=1)=1；A3 Kish 对 ρ 严格递减
  A4 无噪闭式反解 ρ=0 ⇒ N_eff=N（±2%，log 插值曲率残差）
  A5 无噪闭式反解 ρ=1 ⇒ N_eff=1（精确）
  A6 无噪闭式反解对 ρ 单调不增（细网格）
  A7 求积 Δ_exact vs MC（同底物公式重采样）相对误差 <2%
  A8 落盘 independence.json 复算：Δ_exact vs 存储 delta 差 <0.05（400 seeds SE≈0.03）
  A9 中点比值复现审计：|ratio(ρ=0.5) − 2.829| < 0.02
  A10 分解闭合：factor_artifact × factor_shape == ratio（1e-9）

用法
----
  python3 neff_closed_form.py --self-test
  python3 neff_closed_form.py --prove-red     # 每断言注入一个违规，全部必须被抓（exit 0）
  python3 neff_closed_form.py --out .         # 产出 closed_form.json / closed_form.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
DEFAULT_INPUT = HERE.parent / "T10-independence" / "independence.json"


# ---------------------------------------------------------------- 闭式构件

def kish(n: float, rho: float) -> float:
    """Kish 有效样本量（方差膨胀口径）：N/(1+(N−1)ρ)。"""
    return n / (1.0 + (n - 1.0) * rho)


_GL_CACHE: dict[int, tuple[np.ndarray, np.ndarray]] = {}


def gh_max_mean(n: int, tau: float, nodes: int = 256) -> float:
    """a_N=E[max of N iid N(0,1)] = N∫ x·φ(x)·Φ(x)^{N−1} dx。

    参数 tau 仅为兼容旧签名而保留，求的是无噪极值期望，不使用它。
    probabilists' Gauss–Hermite：roots_hermitenorm 权重和=√(2π)，须除。
    关键坑：被积函数必须带 x 因子；只写 Φ^{N−1} 的积分恒为 1/N，
    乘 N 后永远得 1（本轮 A7/A8 假红的根因）。
    """
    from scipy.special import ndtr, roots_hermitenorm
    if nodes not in _GL_CACHE:
        x, w = roots_hermitenorm(nodes)
        _GL_CACHE[nodes] = (x, w / math.sqrt(2.0 * math.pi))
    x, w = _GL_CACHE[nodes]
    return float(n * np.sum(w * x * ndtr(x) ** (n - 1)))


def build_a_table(ns: list[int], nodes: int = 256) -> dict[int, float]:
    """a_N=E[max of N iid N(0,1)]，N=1 时解析为 0。

    教训③：不能对 N=1 走通用求积——Φ^{0}=1 时积分为 E[X]=0，浮点尾项
    会给出 ~1e-16 噪声；a_inverse 拿它作分母会把整个表污染成 0（实测 A4=1）。
    """
    return {n: (0.0 if n <= 1 else gh_max_mean(n, 0.0, nodes)) for n in ns}


def a_interp(m: float, a_tab: dict[int, float]) -> float:
    """A(m)=a_m，在 log m 上线性插值（m≥1）；m≤1 → 0。"""
    ms = sorted(a_tab)
    if m <= 1.0:
        return 0.0
    if m >= ms[-1]:
        # 超出表格范围用最后一段斜率外推（仅诊断用，主流程 m≤N≤64 在表内）
        lo, hi = ms[-2], ms[-1]
        slope = (a_tab[hi] - a_tab[lo]) / (math.log(hi) - math.log(lo))
        return a_tab[hi] + slope * (math.log(m) - math.log(hi))
    for lo, hi in zip(ms, ms[1:]):
        if m <= hi:
            f = (math.log(m) - math.log(lo)) / (math.log(hi) - math.log(lo))
            return a_tab[lo] + f * (a_tab[hi] - a_tab[lo])
    raise AssertionError("unreachable")


def a_inverse(y: float, a_tab: dict[int, float], cap: float) -> float:
    """A⁻¹(y)：在 log m 上反插值，钳位到 [1, cap]。y≤0 → 1。"""
    ms = sorted(a_tab)
    if y <= 0.0:
        return 1.0
    if y >= a_tab[ms[-1]]:
        return float(min(cap, ms[-1]))
    for lo, hi in zip(ms, ms[1:]):
        if y <= a_tab[hi]:
            f = (y - a_tab[lo]) / (a_tab[hi] - a_tab[lo])
            m = math.exp(math.log(lo) + f * (math.log(hi) - math.log(lo)))
            return float(max(1.0, min(cap, m)))
    return float(cap)


def delta_exact(rho: float, n: int, sigma: float, nodes: int = 256) -> float:
    """T10 底物的精确期望增益（解析，无需数值积分）：

      q_i = √(ρk) + √(1−ρ)z_i;  s_i = q_i + ε_i, ε~N(0,σ²)
      W_i := √(1−ρ)z_i + ε_i ~ N(0, v), v = 1−ρ+σ²
      Cov(√(1−ρ)z_i, W_i) = 1−ρ  ⇒  E[增益] = (1−ρ)/√(1−ρ+σ²) · a_N
    无噪 σ→0 极限 = √(1−ρ)·a_N（反解闭式用的就是这个极限）。
    """
    if rho >= 1.0:
        return 0.0
    return (1.0 - rho) / math.sqrt(1.0 - rho + sigma * sigma) * gh_max_mean(n, 0.0, nodes)


def neff_inv_closed(rho: float, n: int, a_tab: dict[int, float]) -> float:
    """无噪闭式反解：A⁻¹(a_N·√(1−ρ))，钳位 [1,n]。"""
    return a_inverse(a_tab[n] * math.sqrt(max(0.0, 1.0 - rho)), a_tab, cap=n)


def neff_inv_closed_noise_cancel(rho: float, n: int, sigma: float,
                                 a_tab: dict[int, float]) -> float:
    """T10 反解的实际口径：ρ=0 基线曲线是带噪的 Δ₀(N)=a_N/√(1+σ²)。

    故 N_eff 满足 a_{N_eff}/√(1+σ²) = Δ(ρ,N;σ)，即
      A⁻¹( a_N · √(1+σ²)·(1−ρ)/√(1−ρ+σ²) )，再钳位 [1,n]。
    噪声在同一 Δ 曲线里被抵消，只剩 σ 对选择幅度的压缩。
    """
    if rho >= 1.0:
        return 1.0
    y = a_tab[n] * math.sqrt(1.0 + sigma * sigma) * (1.0 - rho) / math.sqrt(1.0 - rho + sigma * sigma)
    return a_inverse(y, a_tab, cap=n)


def invert_neff_piecewise(delta: float, curve: dict[int, float], cap: int) -> float:
    """复刻 T10 independence_surface.py:77 invert_neff（N 轴分段线性 + n_cap）。"""
    ns = [n for n in sorted(curve) if n <= cap]
    ds = [curve[n] for n in ns]
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


def mc_delta(rho: float, n: int, sigma: float, seeds: int, seed: int) -> tuple[float, float]:
    """按 T10 底物的等价标量形式重采样：q_i=√(ρk)+√(1−ρ)z_i（k 只做平移，取 k=8）。

    返回 (mean, se)。这是独立于求积的第二条测量路径（对表用）。
    """
    rng = np.random.default_rng(seed)
    k = 8
    base = math.sqrt(rho * k)
    s = math.sqrt(max(0.0, 1.0 - rho))
    z = rng.standard_normal((seeds, n))
    eps = rng.standard_normal((seeds, n)) * sigma
    q = base + s * z
    idx = np.argmax(q + eps, axis=1)
    gains = q[np.arange(seeds), idx] - base
    return float(gains.mean()), float(gains.std(ddof=1) / math.sqrt(seeds))


# ---------------------------------------------------------------- 断言（可注入）

def check_assertions(inp: dict, a_tab: dict[int, float], nodes: int,
                     mc_seeds: int, inject: str | None = None) -> list[tuple[str, bool, str]]:
    """返回 [(id, ok, detail)]。inject ∈ {A1..A12} 时对该断言的输入注入一个违规。"""
    cfg = inp["config"]
    sigma, nstar = cfg["sigma"], cfg["nstar"]
    curve = {int(k): v for k, v in inp["rho0_curve"].items()}
    rows = {(r["rho"], r["n"]): r for r in inp["rows"]}
    out = []

    # A1/A2/A3 Kish 端点与单调
    v = kish(16, 0.0)
    if inject == "A1":
        v = kish(16, 0.0) + 0.5  # 注入：端点偏移
    out.append(("A1", abs(v - 16.0) < 1e-12, f"Kish(16,0)={v:.6f} 应=16"))
    v = kish(16, 1.0)
    if inject == "A2":
        v = 1.2
    out.append(("A2", abs(v - 1.0) < 1e-12, f"Kish(16,1)={v:.6f} 应=1"))
    grid = np.linspace(0, 1, 201)
    seq = [kish(16, float(r)) for r in grid]
    mono = all(b < a for a, b in zip(seq, seq[1:]))
    if inject == "A3":
        mono = False
    out.append(("A3", mono, "Kish 对 ρ 严格递减（201 点）"))

    # A4/A5/A6 无噪闭式反解端点与单调
    v = neff_inv_closed(0.0, 16, a_tab)
    if inject == "A4":
        v *= 0.8
    out.append(("A4", abs(v - 16.0) / 16.0 < 0.02, f"闭式反解(ρ=0,N=16)={v:.4f} 应≈16(±2%)"))
    v = neff_inv_closed(1.0, 16, a_tab)
    if inject == "A5":
        v = 1.5
    out.append(("A5", abs(v - 1.0) < 1e-12, f"闭式反解(ρ=1,N=16)={v:.6f} 应=1"))
    fine = [neff_inv_closed(float(r), 16, a_tab) for r in np.linspace(0, 1, 401)]
    mono = all(b <= a + 1e-12 for a, b in zip(fine, fine[1:]))
    if inject == "A6":
        mono = False
    out.append(("A6", mono, "闭式反解对 ρ 单调不增（401 点）"))

    # A7 求积 vs MC（第二条独立测量路径）
    probes = [(0.0, 16), (0.5, 16), (0.945, 16), (0.5, 4)]
    worst = 0.0
    det = []
    for rho, n in probes:
        de = delta_exact(rho, n, sigma, nodes)
        dm, se = mc_delta(rho, n, sigma, mc_seeds, 9100 + n + int(rho * 1000))
        rel = abs(de - dm) / max(abs(dm), 1e-9)
        worst = max(worst, rel)
        det.append(f"({rho},{n}): exact={de:.4f} mc={dm:.4f}±{se:.4f}")
    ok = worst < 0.02
    if inject == "A7":
        ok = False  # 注入：假装超差
    out.append(("A7", ok, f"求积vsMC最大相对差={worst:.4f} (<2%); " + "; ".join(det)))

    # A8 落盘 delta 复算（400 seeds，单格 SE≈0.03；56 格取最大 → 阈 0.10）
    worst = 0.0
    worst_at = ""
    for (rho, n), r in rows.items():
        de = delta_exact(rho, n, sigma, nodes)
        d = abs(de - r["delta"])
        if d > worst:
            worst, worst_at = d, f"(rho={rho},n={n}) stored={r['delta']} exact={de:.4f}"
    ok = worst < 0.10
    if inject == "A8":
        ok = False
    out.append(("A8", ok, f"|Δ_exact−Δ_stored| max={worst:.4f} @ {worst_at} (<0.10; 400 seeds×56 格)"))

    # A9 中点比值复现审计 JSON 的 2.829
    r05 = rows[(0.5, nstar)]
    kv = kish(nstar, 0.5)
    iv = invert_neff_piecewise(r05["delta"], curve, nstar)
    ratio = iv / kv
    if inject == "A9":
        ratio += 0.5
    out.append(("A9", abs(ratio - 2.829) < 0.02,
                f"ρ=0.5: Kish={kv:.4f} 反解(复刻)={iv:.4f} ratio={ratio:.4f} 应≈2.829"))

    # A10 分解闭合
    ac = neff_inv_closed(0.5, nstar, a_tab)
    f_art, f_shape = iv / ac, ac / kv
    closed_ok = abs(f_art * f_shape - ratio) < 1e-9
    if inject == "A10":
        closed_ok = False
    out.append(("A10", closed_ok, f"artifact({f_art:.4f})×shape({f_shape:.4f})={f_art*f_shape:.6f} == ratio({ratio:.6f})"))

    # A11 噪声抵消闭式：落入存储反解的 ±12%（N 轴分段线性 + 400 seeds 残差）
    nc = neff_inv_closed_noise_cancel(0.5, nstar, sigma, a_tab)
    nc_rel = iv / nc
    nc_ok = abs(nc_rel - 1.0) < 0.12
    if inject == "A11":
        nc_ok = False
    out.append(("A11", nc_ok,
                f"噪声抵消闭式(ρ=0.5)={nc:.4f}，存储反解={iv:.4f}，伪影={nc_rel:.3f} (<12%)"))

    # A12 三因子分解闭合
    f_noise = nc / ac
    tri_ok = abs((iv / nc) * f_noise * (ac / kv) - ratio) < 1e-9
    if inject == "A12":
        tri_ok = False
    out.append(("A12", tri_ok,
                f"interp({iv/nc:.4f})×noise_baseline({f_noise:.4f})×shape({ac/kv:.4f}) == ratio({ratio:.6f})"))
    return out


# ---------------------------------------------------------------- 主分析

def analyze(inp: dict, a_tab: dict[int, float], nodes: int, mc_seeds: int) -> dict:
    cfg = inp["config"]
    sigma, nstar = cfg["sigma"], cfg["nstar"]
    rhos, ns = cfg["rhos"], cfg["ns"]
    curve = {int(k): v for k, v in inp["rho0_curve"].items()}
    rows = {(r["rho"], r["n"]): r for r in inp["rows"]}

    per_rho = []
    for rho in rhos:
        r = rows[(rho, nstar)]
        kv = kish(nstar, rho)
        iv_stored = r["n_eff"]
        iv_rep = invert_neff_piecewise(r["delta"], curve, nstar)
        ac = neff_inv_closed(rho, nstar, a_tab)
        nc = neff_inv_closed_noise_cancel(rho, nstar, sigma, a_tab)
        de = delta_exact(rho, nstar, sigma, nodes)
        dn0 = a_tab[nstar] * math.sqrt(max(0.0, 1.0 - rho))
        ratio = iv_stored / kv
        per_rho.append({
            "rho": rho,
            "kish": round(kv, 4),
            "inverse_stored": iv_stored,
            "inverse_replicated": round(iv_rep, 4),
            "inverse_closed_noiseless": round(ac, 4),
            "inverse_closed_noise_cancel": round(nc, 4),
            "delta_stored": r["delta"],
            "delta_exact_noisy": round(de, 6),
            "delta_closed_noiseless": round(dn0, 6),
            "ratio_stored_over_kish": round(ratio, 4),
            "factor_interp_mc": round(iv_stored / nc, 4),
            "factor_noise_baseline": round(nc / ac, 4),
            "factor_shape_functional": round(ac / kv, 4),
            "rho_kish_equivalent": round((nstar / iv_stored - 1.0) / (nstar - 1.0), 4),
        })

    # 全网格单调性核查（固定 N，沿 ρ；容差 = 400 seeds 噪声量级）
    viol = []
    for n in ns:
        seq = [(rho, rows[(rho, n)]["n_eff"]) for rho in rhos]
        for (r1, v1), (r2, v2) in zip(seq, seq[1:]):
            if v2 > v1 + 0.05:
                viol.append({"n": n, "rho_from": r1, "rho_to": r2,
                             "neff_from": v1, "neff_to": v2})

    # 无噪闭式在全 ρ 细网格上的界与单调（解析层保证）
    fine = np.linspace(0, 1, 401)
    closed_mono = True
    closed_bounds = True
    for n in ns:
        seq = [neff_inv_closed(float(r), n, a_tab) for r in fine]
        closed_mono &= all(b <= a + 1e-12 for a, b in zip(seq, seq[1:]))
        closed_bounds &= all(1.0 - 1e-12 <= v <= n + 1e-12 for v in seq)

    mid = next(p for p in per_rho if p["rho"] == 0.5)
    collapse = next(p for p in per_rho if p["rho"] == 0.945)
    return {
        "config": {"sigma": sigma, "k": cfg["k"], "nstar": nstar, "nodes": nodes,
                   "mc_seeds_check": mc_seeds, "input": str(DEFAULT_INPUT)},
        "a_table_noiseless": {str(n): round(a_tab[n], 6) for n in sorted(a_tab)},
        "closed_forms": {
            "kish": "N/(1+(N-1)*rho)",
            "delta_exact": "sqrt(1-rho)*N*Integral phi(x)*Phi(x*sqrt(1-rho)/sigma)^(N-1) dx; rho=1 -> 0",
            "delta_noiseless": "sqrt(1-rho)*a_N, a_N=E[max of N iid N(0,1)]",
            "inverse_noiseless": "A^{-1}(a_N*sqrt(1-rho)), A(m)=a_m interpolated in log m, clamped [1,N]",
        },
        "per_rho_at_nstar": per_rho,
        "mid_gap_decomposition": {
            "rho": 0.5, "ratio": mid["ratio_stored_over_kish"],
            "factor_interp_mc": mid["factor_interp_mc"],
            "factor_noise_baseline": mid["factor_noise_baseline"],
            "factor_shape_functional": mid["factor_shape_functional"],
            "reading": "ratio = interp × noise_baseline × shape；2.8x 主因是 shape（极值统计与有理衰减是不同泛函），另两因子是口径/数值伪影",
        },
        "collapse_end": {"rho": 0.945, "kish": collapse["kish"],
                         "inverse": collapse["inverse_stored"],
                         "ratio": collapse["ratio_stored_over_kish"]},
        "monotonicity": {
            "stored_grid_violations_gt_0.05": viol,
            "closed_form_monotone_all_n": bool(closed_mono),
            "closed_form_bounds_1_to_n_all_n": bool(closed_bounds),
        },
        "scope": "解析底物（合成 best-of-N），rho 为人为自变量；一切数字不外推真实系统。",
    }


# ---------------------------------------------------------------- CLI

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", default=str(DEFAULT_INPUT))
    ap.add_argument("--out", default=".")
    ap.add_argument("--nodes", type=int, default=256, help="Gauss-Hermite 节点数（a_N 求积；a_N 公式带 x 因子）")
    ap.add_argument("--mc-seeds", type=int, default=20000, help="A7 对表 MC 样本数")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--prove-red", action="store_true", help="逐断言注入违规，全部必须被抓")
    a = ap.parse_args()

    inp = json.loads(Path(a.input).read_text(encoding="utf-8"))
    ns = inp["config"]["ns"]
    a_tab = build_a_table(ns, a.nodes)

    if a.self_test or a.prove_red:
        base = check_assertions(inp, a_tab, a.nodes, a.mc_seeds)
        if a.self_test:
            fails = [t for t in base if not t[1]]
            for aid, ok, det in base:
                print(f"{'OK ' if ok else 'FAIL'} {aid}: {det}")
            if fails:
                print(f"self-test FAIL: {len(fails)}/{len(base)}")
                return 2
            print(f"self-test OK: {len(base)}/{len(base)}")
            return 0
        # prove-red：干净跑必须全绿；每个注入必须恰好点亮对应断言
        if any(not ok for _, ok, _ in base):
            print("PROVE-RED FAIL: 基线本身有红，先修仪器")
            return 2
        bad = []
        for aid, _, _ in base:
            mutated = check_assertions(inp, a_tab, a.nodes, a.mc_seeds, inject=aid)
            hit = [m for m in mutated if m[0] == aid and not m[1]]
            if not hit:
                bad.append(aid)
            else:
                print(f"RED-CAUGHT {aid}: {hit[0][2]}")
        if bad:
            print(f"PROVE-RED FAIL: 注入未被抓: {bad}")
            return 2
        print(f"prove-red OK: {len(base)}/{len(base)} 注入全部被抓，门能红")
        return 0

    res = analyze(inp, a_tab, a.nodes, a.mc_seeds)
    checks = check_assertions(inp, a_tab, a.nodes, a.mc_seeds)
    res["selfcheck"] = [{"id": i, "ok": ok, "detail": d} for i, ok, d in checks]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "closed_form.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    with (out / "closed_form.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(res["per_rho_at_nstar"][0].keys()))
        w.writeheader()
        w.writerows(res["per_rho_at_nstar"])

    print(f"{'rho':>6} {'Kish':>7} {'反解(存)':>9} {'闭式(无噪)':>10} {'闭式(同噪)':>10} {'ratio':>7} {'插值':>7} {'基线噪':>7} {'形状':>7} {'ρ_kish等效':>10}")
    for p in res["per_rho_at_nstar"]:
        print(f"{p['rho']:>6.3f} {p['kish']:>7.3f} {p['inverse_stored']:>9.4f} "
              f"{p['inverse_closed_noiseless']:>10.4f} {p['inverse_closed_noise_cancel']:>10.4f} "
              f"{p['ratio_stored_over_kish']:>7.3f} {p['factor_interp_mc']:>7.3f} "
              f"{p['factor_noise_baseline']:>7.3f} {p['factor_shape_functional']:>7.3f} "
              f"{p['rho_kish_equivalent']:>10.4f}")
    nred = sum(1 for c in res["selfcheck"] if not c["ok"])
    print(f"\nselfcheck 内嵌: {len(checks)-nred}/{len(checks)} 绿")
    print(f"落盘: {out/'closed_form.json'}, {out/'closed_form.csv'}")
    return 0 if nred == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
