"""T13 提案器多样性消融：ρ̄=0.945 是不是局部扰动的产物？

核心问题（T5 遗留 1）：终局判断「加宽并行亏」目前只在**最坏情况提案器**
（单 anchor 高斯局部扰动）上验证过。换真正多样的提案器，ρ̄ 应显著下降，
C2 左式可能翻正 → 核心结论可能被实质翻转。本脚本用 CPU 秒级实验判定这一条。

设计：复用 rsi-agent 的 tasks/gates/core 原语（不改源码），只换 propose。
四档提案器（多样性梯度单调）：
  D0 single-small : 单 anchor，小步长高斯扰动（复现 T5 的 ρ̄≈0.945）
  D1 single-large : 单 anchor，步长×3（探索远，但仍单中心）
  D2 multi-anchor : 一组分散方向锚点，每个候选随机挑一个 + 小扰动（模拟不同 backbone）
  D3 structured   : 结构化稀疏/符号模式池（模拟不同提示策略/归纳偏置）

ρ̄ 定义（与 T5.md:182 一致）：每个候选在 public 集上相对 baseline 的 per-episode Δ
向量，N 个候选两两 Pearson 相关取平均。N_eff = N/(1+(N−1)ρ̄)。

预先钉死的判据（执行前定，禁止事后挑数）——写在 T13.md 与本报告：
  ρ_FLIP = 0.5
  RATE_NONMONO = rate(N=16) >= rate(N=4)（3 seeds 均值；rate=Δpriv/1k 验证调用）
  FLIP  = 存在 D2 或 D3 同时满足 ρ̄ < ρ_FLIP 且 RATE_NONMONO
  ROBUST= 否则（主轴结论从「局部扰动池里成立」升级为「跨提案器成立」）

用法：
  python3 proposer_diversity.py --self-test
  python3 proposer_diversity.py --seeds 1,2,3 --gens 12 --n 1,4,16 --out diversity.json
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

BASELINE = baseline_policy()
RHO_FLIP = 0.5

# D2 的分散锚点（不含 TRUE_W，不引入隐藏真值知识）
D2_ANCHORS = (
    (1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1),
    (0.7, 0.7, 0), (0.7, 0, 0.7), (0, 0.7, 0.7),
    (-0.7, 0.7, 0), (0.7, -0.7, 0), (0, -0.7, 0.7),
)


# ---------- ρ̄ 仪器 ----------
def delta_vector(pv: ScoreVector, base: ScoreVector) -> tuple[float, ...]:
    return tuple(a - b for a, b in zip(pv.values, base.values))


def pearson(xs: tuple[float, ...], ys: tuple[float, ...]) -> float:
    n = len(xs)
    if n != len(ys) or n < 2:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    dx = sum((x - mx) ** 2 for x in xs)
    dy = sum((y - my) ** 2 for y in ys)
    if dx <= 1e-15 or dy <= 1e-15:
        return 0.0
    return max(-1.0, min(1.0, num / (dx * dy) ** 0.5))


def mean_pairwise_rho(vecs: list[tuple[float, ...]]) -> float:
    m = len(vecs)
    if m < 2:
        return 1.0
    rs = [pearson(vecs[i], vecs[j]) for i in range(m) for j in range(i + 1, m)]
    return sum(rs) / len(rs)


def n_eff(n: int, rho: float) -> float:
    if n <= 1:
        return 1.0
    return n / (1.0 + (n - 1) * max(0.0, min(1.0, rho)))


# ---------- 四档提案器 ----------
def propose(mode: str, gen: int, n: int, seed: int,
            anchor: tuple[float, float, float]) -> list[HeuristicPolicy]:
    rng = random.Random(f"{mode}:{seed}:{gen}")
    step = max(0.5 * (0.94 ** gen), 0.04)
    out: list[HeuristicPolicy] = []

    if mode in ("single-small", "single-large"):
        s = step if mode == "single-small" else step * 3.0
        for i in range(n):
            w = tuple(round(c + rng.gauss(0.0, s), 4) for c in anchor)
            out.append(HeuristicPolicy(w, name=f"g{gen}c{i}"))

    elif mode == "multi-anchor":
        for i in range(n):
            a = rng.choice(D2_ANCHORS)
            w = tuple(round(c + rng.gauss(0.0, step), 4) for c in a)
            out.append(HeuristicPolicy(w, name=f"g{gen}c{i}"))

    elif mode == "structured":
        for i in range(n):
            m = rng.randint(0, 3)
            if m == 0:                      # 单维激活
                d = rng.randrange(3)
                v = [0.0, 0.0, 0.0]
                v[d] = rng.choice([-1.0, 1.0]) * rng.uniform(0.5, 1.5)
            elif m == 1:                    # 双维符号
                d1, d2 = rng.sample(range(3), 2)
                v = [0.0, 0.0, 0.0]
                v[d1] = rng.choice([-1.0, 1.0])
                v[d2] = rng.choice([-1.0, 1.0])
            elif m == 2:                    # 全维符号
                v = [float(rng.choice([-1, 1])) for _ in range(3)]
            else:                           # 随机尺度全向
                v = [rng.uniform(0.3, 1.5) * rng.choice([-1.0, 1.0]) for _ in range(3)]
            w = tuple(round(x + rng.gauss(0.0, 0.1), 4) for x in v)
            out.append(HeuristicPolicy(w, name=f"g{gen}c{i}"))
    else:
        raise ValueError(f"unknown mode {mode}")
    return out


# ---------- 单臂 ----------
def run_arm(mode: str, n: int, gens: int, seed: int,
            family_alpha: float = 0.05) -> dict:
    public = ContextualTask(seed=1000 + seed, n_episodes=128)
    private = ContextualTask(seed=90000 + seed, n_episodes=128)
    floor = estimate_noise_floor(public, BASELINE)
    base_pub = public.evaluate(BASELINE)
    base_priv = private.evaluate(BASELINE)
    base_view = ScoreVector(base_pub.values)
    alphas = [family_alpha / max(gens - g, 1) for g in range(gens)]

    anchor = BASELINE.weights
    per_gen_delta: list[float] = []
    per_gen_rho: list[float] = []
    verifier_calls = 0
    promoted = 0

    for g in range(gens):
        pool = propose(mode, g, n, seed, anchor)
        pv_pub = [public.evaluate(p) for p in pool]
        pv_priv = [private.evaluate(p) for p in pool]
        verifier_calls += n

        # ρ̄：public per-episode Δ 向量两两相关
        if n >= 2:
            dvecs = [delta_vector(x, base_pub) for x in pv_pub]
            per_gen_rho.append(mean_pairwise_rho(dvecs))

        views = [ScoreVector(x.values) for x in pv_pub]
        passes = [i for i in range(n)
                  if paired_gate(base_view, views[i], floor, alphas[g]).passed]
        k = max(passes, key=lambda i: views[i].mean) if passes else None
        if k is None:
            continue
        anchor = pool[k].weights
        per_gen_delta.append(pv_priv[k].mean - base_priv.mean)
        promoted += 1

    rho_bar = statistics.fmean(per_gen_rho) if per_gen_rho else 1.0
    delta_priv = statistics.fmean(per_gen_delta) if per_gen_delta else 0.0
    return {
        "mode": mode, "N": n, "seed": seed, "gens": gens,
        "rho_bar": round(rho_bar, 6),
        "N_eff": round(n_eff(n, rho_bar), 4),
        "N_eff_over_N": round(n_eff(n, rho_bar) / n, 4),
        "delta_priv": round(delta_priv, 6),
        "verifier_calls": verifier_calls,
        "rate_per_1k": round(delta_priv / max(verifier_calls, 1) * 1000, 4),
        "promoted": promoted,
    }


# ---------- self-test（门可红可绿）----------
def self_test() -> None:
    # T1 完全相同的 Δ 向量 → ρ=1
    v = (0.1, -0.2, 0.3, 0.0, 0.5, -0.1)
    assert abs(pearson(v, v) - 1.0) < 1e-9, "T1 fail: identical vectors rho != 1"
    # T2 构造低相关向量 → ρ < 0.5
    a = (1, 0, 1, 0, 1, 0)
    b = (0, 1, 0, 1, 0, 1)
    assert pearson(a, b) < 0.5, "T2 fail: orthogonal-like vectors rho >= 0.5"
    # T3 N_eff 端点
    assert abs(n_eff(16, 1.0) - 1.0) < 1e-9, "T3a fail: rho=1 should give N_eff=1"
    assert abs(n_eff(16, 0.0) - 16.0) < 1e-9, "T3b fail: rho=0 should give N_eff=N"
    # T4 mean_pairwise_rho 单向量返回 1
    assert mean_pairwise_rho([v]) == 1.0, "T4 fail: single vector rho != 1"
    # T5 注入一个"假多样"检测：把 4 个候选强制为全同的**非常量** Δ 向量 → ρ 必须=1
    # （常量向量 pearson 分母为 0，返回 0 是正确行为，不能拿来测"塌缩"）
    same = (1.0, -0.5, 0.3, 0.8, -0.2, 0.6, -0.9, 0.1)
    fake = [same for _ in range(4)]
    assert abs(mean_pairwise_rho(fake) - 1.0) < 1e-9, "T5 fail: identical deltas not detected"
    print("self-test 5/5 PASS")


# ---------- 汇总与判决 ----------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--seeds", default="1,2,3")
    ap.add_argument("--gens", type=int, default=12)
    ap.add_argument("--n", default="1,4,16")
    ap.add_argument("--out", default="diversity.json")
    a = ap.parse_args()
    if a.self_test:
        self_test()
        return

    seeds = [int(x) for x in a.seeds.split(",")]
    ns = [int(x) for x in a.n.split(",")]
    modes = ("single-small", "single-large", "multi-anchor", "structured")
    rows: list[dict] = []
    for mode in modes:
        for n in ns:
            for s in seeds:
                rows.append(run_arm(mode, n, a.gens, s))

    # 按 (mode,N) 聚合
    summary: dict[str, dict[int, dict[str, float]]] = {}
    for mode in modes:
        summary[mode] = {}
        for n in ns:
            sub = [r for r in rows if r["mode"] == mode and r["N"] == n]
            summary[mode][n] = {
                "rho_bar": statistics.fmean(r["rho_bar"] for r in sub),
                "N_eff": statistics.fmean(r["N_eff"] for r in sub),
                "N_eff_over_N": statistics.fmean(r["N_eff_over_N"] for r in sub),
                "delta_priv": statistics.fmean(r["delta_priv"] for r in sub),
                "rate_per_1k": statistics.fmean(r["rate_per_1k"] for r in sub),
            }

    # 预先钉死的判决
    flip_modes = []
    for mode in ("multi-anchor", "structured"):
        rho = summary[mode].get(16, {}).get("rho_bar", 1.0)
        rate4 = summary[mode].get(4, {}).get("rate_per_1k", 0.0)
        rate16 = summary[mode].get(16, {}).get("rate_per_1k", 0.0)
        if rho < RHO_FLIP and rate16 >= rate4:
            flip_modes.append({"mode": mode, "rho_bar": round(rho, 4),
                               "rate4": round(rate4, 3), "rate16": round(rate16, 3)})
    verdict = "FLIP" if flip_modes else "ROBUST"

    print(f"{'mode':16s} {'N':>3s} {'rho_bar':>8s} {'N_eff/N':>8s} {'Δpriv':>8s} {'rate/1k':>8s}")
    for mode in modes:
        for n in ns:
            d = summary[mode][n]
            print(f"{mode:16s} {n:3d} {d['rho_bar']:8.4f} {d['N_eff_over_N']:8.4f} "
                  f"{d['delta_priv']:8.4f} {d['rate_per_1k']:8.3f}")
        print()
    print(f"ρ_FLIP={RHO_FLIP}  RATE_NONMONO: rate(16)>=rate(4)")
    print(f"VERDICT = {verdict}")
    if flip_modes:
        for f in flip_modes:
            print(f"  FLIP via {f}")

    Path(a.out).write_text(json.dumps({
        "config": {"gens": a.gens, "seeds": seeds, "ns": ns,
                   "rho_flip": RHO_FLIP,
                   "rate_nonmono_def": "rate(N=16) >= rate(N=4)"},
        "rows": rows, "summary": summary,
        "verdict": verdict, "flip_modes": flip_modes,
    }, indent=1), encoding="utf-8")
    print(f"\nwrote {a.out} rows={len(rows)}")


if __name__ == "__main__":
    main()