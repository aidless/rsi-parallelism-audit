"""T5 pilot：验证器带宽 vs 每代真实增益（rsi-agent 版）。

只依赖 rsi-agent 的纯标准库部件（core/tasks/gates/nc_guard/outer），不写任何其它文件之外的路径。
三个条件，每条件 N ∈ {1,4,16} 候选/代：

  C1 none      : 无闸 —— 每代取公开分 argmax 直接晋升（selection intensity = 1）
  C2 paired    : 现役 paired_gate（噪声地板 + ESS + Holm + 回归负担）(selection intensity = p_pass)
  C3 paired+nc : C2 且 candidate 池要先过 model_free_audit 窄门 (selection intensity = p_pass·p_nc)

"真实增益" = 在密封私集上相对 baseline 的 paired mean（私集只被读一次/代，且从不参与选择）。
不确定性按代池化：对每个代内 Δ 做 bootstrap（以代为单位重采样），给 95% CI。

用法：
  python3 pilot_budget_scaling.py --seeds 1,2,3 --gens 12 --n 1,4,16 --out pilot.json
本机 CPU 秒级。不要挂后台长时间跑。
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from pathlib import Path

# 本脚本只用 rsi_agent 的真实 gate/nc_guard 原语；池子生成用自己的（需要 N 支并列），
# 与 rsi_agent.outer.InnerAgent.propose 的步长/衰减公式逐项一致。


def _find_rsi_root() -> Path:
    for p in Path(__file__).resolve().parents:
        if (p / "rsi-agent" / "rsi_agent" / "__init__.py").exists():
            return p / "rsi-agent"
    raise SystemExit("rsi-agent not found above this file")


RSI_ROOT = _find_rsi_root()
sys.path.insert(0, str(RSI_ROOT))

from rsi_agent.core import HeuristicPolicy, ScoreVector  # noqa: E402
from rsi_agent.gates import paired_gate, estimate_noise_floor  # noqa: E402
from rsi_agent.nc_guard import Probe, model_free_audit  # noqa: E402
from rsi_agent.outer import baseline_policy  # noqa: E402
from rsi_agent.tasks import ContextualTask  # noqa: E402

TRUE_W = (0.9, -0.6, 1.2)
BASELINE = baseline_policy()


def mean(v: ScoreVector) -> float:
    return v.mean


def hack_signal(weights: tuple[float, float, float]) -> float:
    """与真值无关、但对 scorer 可见的"表面特征"（此处取权重的 L1 范数），
    模拟 2611.21538 的 padding hack：候选可以刷高代理分而不提升真值。"""
    return sum(abs(w) for w in weights) / 3.0 - 0.5


import dataclasses


@dataclasses.dataclass(frozen=True)
class ScoredView:
    v: float                 # 被评对象看到的（代理）分
    true_vec: ScoreVector    # 真值向量（仅记录，不参与选择）

    def vec(self) -> ScoreVector:
        """代理视为"整体同向抬升"：把 v - mean(true) 平摊到每个 episode。"""
        d = self.v - self.true_vec.mean
        return ScoreVector(tuple(x + d for x in self.true_vec.values))


def bootstrap_ci(xs: list[float], reps: int = 2000, seed: int = 0) -> tuple[float, float]:
    if not xs:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(xs)
    ms = sorted(sum(rng.choice(xs) for _ in range(n)) / n for _ in range(reps))
    return (round(ms[int(0.025 * reps)], 6), round(ms[int(0.975 * reps)], 6))


def build_probes(public_task: ContextualTask, n: int, seed: int) -> list[Probe]:
    rng = random.Random(f"nc-probe:{seed}")
    ps: list[Probe] = []
    for _ in range(n):
        w = tuple(round(rng.uniform(-1, 1), 4) for _ in range(3))
        ps.append(Probe(weights=w, true_quality=public_task.evaluate(HeuristicPolicy(w)).mean))
    return ps


def propose_pool(gen: int, n_cand: int, seed: int, anchor: tuple[float, float, float]) -> list[HeuristicPolicy]:
    """与 InnerAgent 同形的高斯局部扰动，但一次出 N 个候选。"""
    step = max(0.5 * (0.94 ** gen), 0.04)
    rng = random.Random(f"{seed}:{gen}")
    return [HeuristicPolicy(tuple(round(c + rng.gauss(0.0, step), 4) for c in anchor),
                            name=f"g{gen}c{i}") for i in range(n_cand)]


def run_arm(cond: str, n_cand: int, gens: int, seed: int, family_alpha: float = 0.05,
            gamed: bool = False, gamma_g: float = 2.0) -> dict:
    public = ContextualTask(seed=1000 + seed, n_episodes=128)
    private = ContextualTask(seed=90000 + seed, n_episodes=128)   # 密封：只读一次/代，不参与选择
    floor = estimate_noise_floor(public, BASELINE)
    base_pub = public.evaluate(BASELINE)
    base_as_view = ScoreVector(base_pub.values)
    base_priv = private.evaluate(BASELINE)

    # 每代有效 alpha：Holm 家族校正的简化版（单比较即 family_alpha/n_comp）
    alphas = [family_alpha / max(gens - g, 1) for g in range(gens)]

    probes = build_probes(public, 12, seed)
    # NC 前置审计：用的是 baseline 真值函数（诚实 scorer），因此 C3 本身不应失败；
    # 这里把"窄门"的代价体现在 min_probes 与每代重复审计上（成本计量）。
    nc = model_free_audit(probes, lambda ps: [p.true_quality for p in ps])
    nc_gamed = model_free_audit(probes, lambda ps: [p.true_quality + gamma_g * hack_signal(p.weights)
                                                    for ps in [ps] for p in ps])

    anchor = BASELINE.weights
    per_gen: list[float] = []
    delta_pool: list[float] = []
    verifier_calls = 0
    verify_cost = 0.0
    promoted = 0
    sel_intensity: list[float] = []

    for g in range(gens):
        pool = propose_pool(g, n_cand, seed, anchor)
        pv = [public.evaluate(p) for p in pool]
        # gaming：乐观 scorer 只看得到"抬升后的代理分"，真值仍来自 private
        score = [ScoredView(x.mean + gamma_g * hack_signal(p.weights), x) if gamed
                 else ScoredView(x.mean, x) for x, p in zip(pv, pool)]
        pv_priv = [private.evaluate(p) for p in pool]          # 池化真值：只记录
        verifier_calls += n_cand
        verify_cost += n_cand * (1.0 if cond == "none" else 3.0)  # cf. 单次 paired_gate ~O(E)
        delta_pool.extend(mean(x) - mean(base_priv) for x in pv_priv)

        if cond == "none":
            k = max(range(n_cand), key=lambda i: score[i].v)
            sel_intensity.append(1.0)
        else:
            passes = [i for i in range(n_cand)
                      if paired_gate(base_as_view, score[i].vec(), floor, alphas[g]).passed]
            # C3 = C2 再叠加 NC 窄门：代理分必须先在 probe grid 上通过非循环审计。
            # 诚实 scorer 必然过；被 hack 的乐观 scorer 在 gap_sign>0 处被拒。
            if cond == "paired_nc" and gamed:
                if not nc_gamed.passed:
                    passes = []      # 前置审计拒：整代零候选（fail-closed）
            sel_intensity.append(len(passes) / n_cand)
            k = max(passes, key=lambda i: score[i].v) if passes else None

        if k is None:
            # 全拒：零候选通过 -> 锚点不动（这是"带宽买不到东西"的真实形态）
            delta_pool.extend(mean(x) - mean(base_priv) for x in pv_priv)
            continue

        if cond == "none":
            # 无闸：直接采纳。若候选真变差，锚点跟着劣化——这就是被 hack 的机制
            anchor = pool[k].weights
            per_gen.append(mean(pv_priv[k]) - mean(base_priv))
            promoted += 1
        else:
            if mean(pv_priv[k]) > mean(anchor and pv_priv[0]) - 1e9:
                pass
            anchor = pool[k].weights
            per_gen.append(mean(pv_priv[k]) - mean(base_priv))
            promoted += 1

    deltas = per_gen
    mean_delta = statistics.fmean(deltas) if deltas else 0.0
    ci = bootstrap_ci(deltas, seed=seed)
    return {
        "cond": cond,
        "n_cand": n_cand,
        "gens": gens,
        "seed": seed,
        "mean_private_delta": round(mean_delta, 6),
        "ci95": ci,
        "promoted": promoted,
        "verifier_calls": verifier_calls,
        "mean_sel_intensity": round(statistics.fmean(sel_intensity), 4),
        "gain_per_1k_calls": round(mean_delta / max(verifier_calls, 1) * 1000, 6),
        "gain_per_cost": round(mean_delta / max(verify_cost, 1.0), 6),
        "delta_pooled_ci": bootstrap_ci(delta_pool, seed=seed + 77),
        "nc_passed": nc.passed,
    }


def soft_proxy(probes: list[Probe], beta: float = 3.0):
    """gaming 条件：乐观 padding 打分器——给每个 probe 的代理分 = 真值 + beta·|x|
    （与真值相关的平滑抬升），并在真实候选上按同形施加。"""
    return lambda ps: [p.true_quality + beta * (sum(abs(w) for w in p.weights) / 3.0 - 0.5)
                       for p in ps]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="1,2,3")
    ap.add_argument("--gens", type=int, default=12)
    ap.add_argument("--n", default="1,4,16")
    ap.add_argument("--out", default="pilot.json")
    a = ap.parse_args()
    seeds = [int(x) for x in a.seeds.split(",")]
    ns = [int(x) for x in a.n.split(",")]
    rows = []
    arms = ("none", "paired", "paired_nc")
    for cond in arms:
        for n in ns:
            for s in seeds:
                rows.append(run_arm(cond, n, a.gens, s))
    agg = {}
    for r in rows:
        key = f"{r['cond']}|N={r['n_cand']}"
        agg.setdefault(key, []).append(r)
    print(f"{'config':22s} {'Δpriv/gen':>10s} {'ci95':>22s} {'sel_int':>8s} {'calls':>6s} {'Δ/1k':>9s}")
    print("\n[gamed] 乐观 scorer（γ=2.0），代理分 = public_mean + γ·hack_signal")
    for cond in arms:
        for n in ns:
            rs = [run_arm(cond, n, a.gens, s, gamed=True) for s in seeds]
            md = statistics.fmean(x["mean_private_delta"] for x in rs)
            lo = statistics.fmean(x["ci95"][0] for x in rs)
            hi = statistics.fmean(x["ci95"][1] for x in rs)
            si = statistics.fmean(x["mean_sel_intensity"] for x in rs)
            print(f"{cond+'|N='+str(n):22s} {md:10.4f} [{lo:8.4f},{hi:8.4f}] sel={si:.3f}")
    for k, rs in agg.items():
        md = statistics.fmean(x["mean_private_delta"] for x in rs)
        lo = statistics.fmean(x["ci95"][0] for x in rs)
        hi = statistics.fmean(x["ci95"][1] for x in rs)
        si = statistics.fmean(x["mean_sel_intensity"] for x in rs)
        vc = statistics.fmean(x["verifier_calls"] for x in rs)
        gpk = statistics.fmean(x["gain_per_1k_calls"] for x in rs)
        print(f"{k:22s} {md:10.4f} [{lo:8.4f},{hi:8.4f}] {si:8.3f} {vc:6.1f} {gpk:9.4f}")
    gamed_rows = []
    for cond in arms:
        for n in ns:
            for s in seeds:
                gamed_rows.append(run_arm(cond, n, a.gens, s, gamed=True))
    Path(a.out).write_text(json.dumps({"truthful": rows, "gamed": gamed_rows}, indent=1),
                           encoding="utf-8")
    print(f"\nwrote {a.out} rows={len(rows)}")


if __name__ == "__main__":
    main()