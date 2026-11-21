"""T14-deep: 冻结 anchor + 可学习内层目标 —— 让 rho 成为外生旋钮。

承接 T14-neff-real/T14.md §5 的开放问题：真实 outer loop 里 rho 是 anchor 漂移的
因变量。本脚本把外层 anchor 冻死在 BASELINE 上，只让内层目标方向 z_t 从 public 反馈
学习；于是实测 rho_bar 只由 rho_param 决定（外生），可直接检验 T10 的凸塌缩形态。

判据见 PRE_REGISTRATION_DEEP.md（执行前定死，禁止事后挑数）。

用法:
  python3 frozen_anchor.py --self-test
  python3 frozen_anchor.py --seeds 1,2,3 --gens 12 --n 1,4,16 --out frozen_anchor.json
"""
from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
from pathlib import Path

T13_DIR = Path(__file__).resolve().parents[1] / "T13-proposer-diversity"
sys.path.insert(0, str(T13_DIR))
import proposer_diversity as P  # noqa: E402

RSI_ROOT = next(p for p in Path(__file__).resolve().parents
                if (p / "rsi-agent" / "rsi_agent" / "__init__.py").exists()) / "rsi-agent"
sys.path.insert(0, str(RSI_ROOT))

from rsi_agent.core import HeuristicPolicy, ScoreVector  # noqa: E402
from rsi_agent.gates import paired_gate, estimate_noise_floor  # noqa: E402
from rsi_agent.tasks import ContextualTask, TRUE_W  # noqa: E402

BASELINE = P.BASELINE
ANCHOR = BASELINE.weights                      # (1,0,0) —— 外层冻结锚点
# z_0 必须与 anchor 不平行：否则 rho=1 时候选与 anchor 同方向，per-episode delta
# 恒为 0，Pearson 分母为 0 返回 0（T14 的常量向量陷阱），把 rho_bar(1) 拉成 11/12。
Z0 = tuple(1.0 / math.sqrt(3.0) for _ in range(3))   # 中性对称方向，不含 TRUE_W 知识
RHO_GRID = tuple(round(i / 10.0, 2) for i in range(11))   # 0,0.1,...,1.0
INNER_PROBES = 2
INNER_STEP = 0.12
INNER_LR = 0.15
PROBE_SCALE = 0.5


# ---------------- 缓存评测（S10 对表：必须与原 evaluate 逐值相等） ----------------
_EP_CACHE: dict = {}


def _episodes(task: ContextualTask):
    key = (task.seed, task.n_episodes, task.n_actions, tuple(task.true_w))
    if key not in _EP_CACHE:
        rng = random.Random(task.seed)
        eps, noise = [], []
        for ep in range(task.n_episodes):
            acts = tuple(tuple(round(rng.uniform(-1, 1), 4) for _ in range(3))
                         for _ in range(task.n_actions))
            eps.append(acts)
            noise.append(random.Random(f"{task.seed}:{ep}").uniform(-0.05, 0.05))
        _EP_CACHE[key] = (tuple(eps), tuple(noise), tuple(task.true_w))
    return _EP_CACHE[key]


def evaluate_cached(task: ContextualTask, policy: HeuristicPolicy) -> ScoreVector:
    eps, noise, tw = _episodes(task)
    w = policy.weights
    out = []
    for ep, acts in enumerate(eps):
        best = acts[0]
        bs = w[0] * best[0] + w[1] * best[1] + w[2] * best[2]
        for a in acts[1:]:
            s = w[0] * a[0] + w[1] * a[1] + w[2] * a[2]
            if s > bs:                      # 严格大于：与 max() 的首个最大项一致
                bs, best = s, a
        out.append(round(best[0] * tw[0] + best[1] * tw[1] + best[2] * tw[2] + noise[ep], 6))
    return ScoreVector(tuple(out))


# ---------------- 提案器 ----------------
def step_of(gen: int) -> float:
    return max(0.5 * (0.94 ** gen), 0.04)


def frozen_propose(rho, gen, n, seed, anchor, z):
    """外层 anchor 冻结；共享项是被学习的目标方向 z（不是 anchor 本身）。"""
    rng = random.Random(f"t14d:{seed}:{gen}")
    s = step_of(gen)
    out = []
    for i in range(n):
        eps = tuple(rng.gauss(0.0, 1.0) for _ in range(3))
        w = tuple(round(anchor[j] + s * ((rho ** 0.5) * z[j]
                                        + ((1.0 - rho) ** 0.5) * eps[j]), 4)
                  for j in range(3))
        out.append(HeuristicPolicy(w, name=f"g{gen}c{i}"))
    return out


def drift_propose(rho, gen, n, seed, anchor):
    """T14 原构造（供 S6/S8 反证用；不是本轨提案器）。"""
    rng = random.Random(f"t14:{seed}:{gen}")
    s = step_of(gen)
    shared = tuple(rng.gauss(0.0, 1.0) for _ in range(3))
    out = []
    for i in range(n):
        ind = tuple(rng.gauss(0.0, 1.0) for _ in range(3))
        w = tuple(round(anchor[j] + s * ((rho ** 0.5) * shared[j]
                                        + ((1.0 - rho) ** 0.5) * ind[j]), 4)
                  for j in range(3))
        out.append(HeuristicPolicy(w, name=f"g{gen}c{i}"))
    return out


def inner_update(gen, seed, anchor, z, public, base_mean):
    """内层目标从 public 反馈学习。入参没有 rho —— 学习轨迹与 rho 无关（外生性）。"""
    rng = random.Random(f"t14d-inner:{seed}:{gen}")
    v = [0.0, 0.0, 0.0]
    for _ in range(INNER_PROBES):
        eps = tuple(rng.gauss(0.0, 1.0) for _ in range(3))
        w = tuple(round(anchor[k] + INNER_STEP * (z[k] + PROBE_SCALE * eps[k]), 4)
                  for k in range(3))
        g = evaluate_cached(public, HeuristicPolicy(w)).mean - base_mean
        for k in range(3):
            v[k] += g * eps[k]
    nv = math.sqrt(sum(x * x for x in v))
    if nv < 1e-12:
        return z
    zn = [z[k] + INNER_LR * (v[k] / nv) for k in range(3)]
    nn = math.sqrt(sum(x * x for x in zn))
    return tuple(zn[k] / nn for k in range(3))


# ---------------- 单臂 ----------------
def run_arm(rho, n, gens, seed, mode="frozen", learn=True, family_alpha=0.05):
    public = ContextualTask(seed=1000 + seed, n_episodes=128)
    private = ContextualTask(seed=90000 + seed, n_episodes=128)
    floor = estimate_noise_floor(public, BASELINE)
    base_pub = evaluate_cached(public, BASELINE)
    base_priv = evaluate_cached(private, BASELINE)
    base_view = ScoreVector(base_pub.values)
    base_pub_mean = base_pub.mean
    alphas = [family_alpha / max(gens - g, 1) for g in range(gens)]

    anchor = ANCHOR
    z = Z0
    anchor_trace = [anchor]
    z_trace = [z]
    per_gen_rho, deltas_inst, deltas_acc = [], [], []
    pass_tot = promoted = 0

    for g in range(gens):
        pool = (frozen_propose(rho, g, n, seed, anchor, z) if mode == "frozen"
                else drift_propose(rho, g, n, seed, anchor))
        pv_pub = [evaluate_cached(public, p) for p in pool]
        pv_priv = [evaluate_cached(private, p) for p in pool]

        if n >= 2:
            dvecs = [P.delta_vector(x, base_pub) for x in pv_pub]
            per_gen_rho.append(P.mean_pairwise_rho(dvecs))
        deltas_inst.append(max(x.mean for x in pv_pub) - base_pub_mean)

        views = [ScoreVector(x.values) for x in pv_pub]
        passes = [i for i in range(n)
                  if paired_gate(base_view, views[i], floor, alphas[g]).passed]
        pass_tot += len(passes)
        k = max(passes, key=lambda i: views[i].mean) if passes else None
        if k is not None:
            deltas_acc.append(pv_priv[k].mean - base_priv.mean)
            promoted += 1

        if mode == "frozen":
            if learn:
                z = inner_update(g, seed, ANCHOR, z, public, base_pub_mean)
            anchor = ANCHOR
        elif k is not None:
            anchor = pool[k].weights
        anchor_trace.append(anchor)
        z_trace.append(z)

    rho_bar = statistics.fmean(per_gen_rho) if per_gen_rho else 1.0
    delta_acc = statistics.fmean(deltas_acc) if deltas_acc else 0.0
    calls_cand = gens * n
    calls_total = gens * (n + (INNER_PROBES if (mode == "frozen" and learn) else 0))
    z_final = z_trace[-1]
    cos_true = (sum(z_final[k] * TRUE_W[k] for k in range(3))
                / max(math.sqrt(sum(x * x for x in z_final)), 1e-12)
                / math.sqrt(sum(x * x for x in TRUE_W)))   # 仅诊断，不进提案器
    return {
        "rho_param": rho, "N": n, "seed": seed, "gens": gens, "mode": mode,
        "rho_bar": round(rho_bar, 6),
        "N_eff": round(P.n_eff(n, rho_bar), 4),
        "N_eff_over_N": round(P.n_eff(n, rho_bar) / n, 4),
        "delta_inst": round(statistics.fmean(deltas_inst), 6),
        "delta_priv": round(delta_acc, 6),
        "rate_cand": round(delta_acc / max(calls_cand, 1) * 1000, 4),
        "rate_total": round(delta_acc / max(calls_total, 1) * 1000, 4),
        "pass_rate": round(pass_tot / max(gens * n, 1), 6),
        "promoted": promoted,
        "calls_cand": calls_cand, "calls_total": calls_total,
        "cos_z_truew": round(cos_true, 6),
        "anchor_distinct": len(set(anchor_trace)),
        "_trace": {"rho_gen": [round(x, 6) for x in per_gen_rho],
                   "delta_inst_gen": [round(x, 6) for x in deltas_inst],
                   "z": [[round(c, 6) for c in zz] for zz in z_trace]},
    }


# ---------------- 统计与判决 ----------------
def _ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(xs, ys):
    return P.pearson(tuple(_ranks(list(xs))), tuple(_ranks(list(ys))))


def summarize(rows):
    s = {}
    for r in RHO_GRID:
        for n in (1, 4, 16):
            sub = [x for x in rows if x["rho_param"] == r and x["N"] == n]
            if not sub:
                continue
            s[(r, n)] = {k: statistics.fmean(x[k] for x in sub)
                         for k in ("rho_bar", "N_eff", "N_eff_over_N", "delta_inst",
                                   "delta_priv", "rate_cand", "rate_total",
                                   "pass_rate", "cos_z_truew")}
    return s


def verdict(s):
    rho_bar16 = [s[(r, 16)]["rho_bar"] for r in RHO_GRID]
    mono = all(rho_bar16[i] <= rho_bar16[i + 1] + 1e-9 for i in range(len(RHO_GRID) - 1))
    v1_ok = (mono and rho_bar16[0] <= 0.40 and abs(rho_bar16[-1] - 1.0) <= 0.002
             and P.pearson(tuple(RHO_GRID), tuple(rho_bar16)) >= 0.95)
    span = s[(0.0, 16)]["N_eff"] / max(s[(1.0, 16)]["N_eff"], 1e-9)
    v2_ok = span >= 3.0
    d1 = "JUDGEABLE" if (v1_ok and v2_ok) else "DEGRADED_INSTRUMENT"

    d_inst16 = [s[(r, 16)]["delta_inst"] for r in RHO_GRID]
    gap = d_inst16[0] - d_inst16[-1]
    sp_rho = spearman(RHO_GRID, d_inst16)
    if sp_rho <= -0.8 and gap >= 0.05:
        shape = "COLLAPSE_REPRODUCED"
    elif sp_rho >= 0.8 and gap <= -0.05:
        shape = "REVERSED_SIGNAL_DOMINANT"
    else:
        shape = "MIXED_SHAPE"
    neff16 = [s[(r, 16)]["N_eff"] for r in RHO_GRID]
    cos16 = [s[(r, 16)]["cos_z_truew"] for r in RHO_GRID]
    attrib = {"spearman_dinst_rho": round(sp_rho, 4),
              "spearman_dinst_neff": round(spearman(neff16, d_inst16), 4),
              "spearman_dinst_cos": round(spearman(cos16, d_inst16), 4),
              "gap_dinst_0_minus_1": round(gap, 6)}

    flips_t, flips_c = [], []
    for r in RHO_GRID:
        if s[(r, 16)]["rate_total"] >= s[(r, 4)]["rate_total"]:
            flips_t.append(r)
        if s[(r, 16)]["rate_cand"] >= s[(r, 4)]["rate_cand"]:
            flips_c.append(r)
    taxes = [s[(r, 4)]["rate_total"] / max(s[(r, 16)]["rate_total"], 1e-9) for r in RHO_GRID]
    taxes_c = [s[(r, 4)]["rate_cand"] / max(s[(r, 16)]["rate_cand"], 1e-9) for r in RHO_GRID]
    d4 = ("TAX_ROBUST" if min(taxes) >= 3.0
          else ("TAX_RHO_SENSITIVE" if min(taxes) < 2.0 else "TAX_MIDDLE"))
    return {
        "V1_rho_bar16": [round(x, 4) for x in rho_bar16],
        "V1_monotone": mono,
        "V1_span_low": round(rho_bar16[0], 4),
        "V1_pearson": round(P.pearson(tuple(RHO_GRID), tuple(rho_bar16)), 4),
        "V1": "PASS" if v1_ok else "FAIL",
        "V2_neff_span": round(span, 4), "V2": "PASS" if v2_ok else "FAIL",
        "D1": d1, "D1_shape": shape,
        "attribution": attrib,
        "D2_flip_total": flips_t, "D2_flip_cand": flips_c,
        "D2": "RATE_FLIP_ANY" if flips_t else "RATE_ROBUST_ACROSS_RHO",
        "D4_tax_min": round(min(taxes), 4), "D4_tax_max": round(max(taxes), 4),
        "D4_tax_min_cand": round(min(taxes_c), 4), "D4_tax_max_cand": round(max(taxes_c), 4),
        "D4": d4,
    }


# ---------------- 自检 ----------------
def self_test():
    # S10 先跑：缓存评测仪器与原 evaluate 必须逐值相等，否则后面所有读数都不可信
    for seed in (1000 + 1, 90000 + 1):
        task = ContextualTask(seed=seed, n_episodes=128)
        for w in [(1.0, 0.0, 0.0), (0.9, -0.6, 1.2), (0.5, 0.5, 0.5), (-0.3, 0.8, 0.1), (1.2, 1.2, 1.2)]:
            p = HeuristicPolicy(w)
            assert evaluate_cached(task, p).values == task.evaluate(p).values, f"S10 fail {seed} {w}"

    v = (0.1, -0.2, 0.3, 0.0, 0.5, -0.1)
    assert abs(P.pearson(v, v) - 1.0) < 1e-9, "S1 fail"
    assert P.pearson((1, 0, 1, 0), (0, 1, 0, 1)) < 0.5, "S2 fail"
    assert abs(P.n_eff(16, 1.0) - 1.0) < 1e-9 and abs(P.n_eff(16, 0.0) - 16.0) < 1e-9, "S3 fail"
    assert P.mean_pairwise_rho([v]) == 1.0, "S4 fail"
    same = (1.0, -0.5, 0.3, 0.8, -0.2, 0.6)
    assert abs(P.mean_pairwise_rho([same for _ in range(4)]) - 1.0) < 1e-9, "S5 fail"

    # S6：完整 arm 上的 rho_param -> 实测 rho_bar 单调同向（T14 曾在此陷阱翻车）
    good = [run_arm(r, 16, 12, 1)["rho_bar"] for r in RHO_GRID]
    assert all(good[i] <= good[i + 1] + 1e-9 for i in range(len(good) - 1)), f"S6a fail {good}"
    assert good[0] <= 0.40 and abs(good[-1] - 1.0) <= 1e-6, f"S6b fail {good}"
    # S6d 常量向量陷阱守卫：rho=1 时每一代的 delta 向量必须非常量，逐代 rho 都是 1
    arm1 = run_arm(1.0, 16, 12, 1)
    assert all(abs(x - 1.0) <= 1e-9 for x in arm1["_trace"]["rho_gen"]), f"S6d fail {arm1['_trace']['rho_gen']}"
    drift = [run_arm(r, 16, 12, 1, mode="drift")["rho_bar"] for r in RHO_GRID]
    assert not all(drift[i] <= drift[i + 1] + 1e-9 for i in range(len(drift) - 1)), f"S6c fail {drift}"

    # S7 常量向量：pearson 分母为 0 必须返回 0，而不是 1
    assert P.pearson((2.0, 2.0, 2.0), (2.0, 2.0, 2.0)) == 0.0, "S7 fail"

    # S8 anchor 冻结不变式（反证：drift 模式必须动）
    frz = run_arm(0.5, 4, 6, 1)
    assert frz["anchor_distinct"] == 1, f"S8a fail distinct={frz['anchor_distinct']}"
    drf = run_arm(0.5, 4, 6, 1, mode="drift")
    assert drf["anchor_distinct"] > 1, f"S8b fail distinct={drf['anchor_distinct']}"

    # S9 内层学习活性（纯公开证据）+ 冻结内层复核必须红
    public = ContextualTask(seed=1001, n_episodes=128)
    base_mean = evaluate_cached(public, HeuristicPolicy(ANCHOR)).mean
    arm = run_arm(0.5, 4, 12, 1)
    z_fin = tuple(arm["_trace"]["z"][-1])
    probe = HeuristicPolicy(tuple(round(ANCHOR[k] + INNER_STEP * z_fin[k], 4) for k in range(3)))
    learned_mean = evaluate_cached(public, probe).mean
    assert learned_mean > base_mean, f"S9a fail learned={learned_mean:.4f} base={base_mean:.4f}"
    frozen_inner = run_arm(0.5, 4, 12, 1, learn=False)
    assert frozen_inner["_trace"]["z"][-1] == [round(x, 6) for x in Z0], "S9b fail frozen inner still moved"

    print("self-test 10/10 PASS; good_rho=" + ",".join(f"{x:.3f}" for x in good)
          + " | drift_rho=" + ",".join(f"{x:.3f}" for x in drift)
          + f" | learned_z_public={learned_mean:.4f} vs base={base_mean:.4f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--seeds", default="1,2,3")
    ap.add_argument("--gens", type=int, default=12)
    ap.add_argument("--n", default="1,4,16")
    ap.add_argument("--out", default="frozen_anchor.json")
    a = ap.parse_args()
    if a.self_test:
        self_test()
        return

    seeds = [int(x) for x in a.seeds.split(",")]
    ns = [int(x) for x in a.n.split(",")]
    rows = [run_arm(r, n, a.gens, s) for r in RHO_GRID for n in ns for s in seeds]
    s = summarize(rows)
    v = verdict(s)

    print(f"{'rho':>5s} {'N':>3s} {'rho_bar':>8s} {'N_eff':>7s} {'d_inst':>8s} "
          f"{'d_priv':>8s} {'rate_t':>8s} {'rate_c':>8s} {'pass':>7s} {'cosZ':>7s}")
    for r in RHO_GRID:
        for n in ns:
            d = s[(r, n)]
            print(f"{r:5.2f} {n:3d} {d['rho_bar']:8.4f} {d['N_eff']:7.3f} "
                  f"{d['delta_inst']:8.4f} {d['delta_priv']:8.4f} {d['rate_total']:8.3f} "
                  f"{d['rate_cand']:8.3f} {d['pass_rate']:7.4f} {d['cos_z_truew']:7.4f}")
        print()
    for k, val in v.items():
        print(f"  {k} = {val}")

    traces = {f"{r}|{n}": x["_trace"] for r in RHO_GRID for n in (16,)
              for x in rows if x["rho_param"] == r and x["N"] == 16 and x["seed"] == 1}
    Path(a.out).write_text(json.dumps({
        "config": {"rho_grid": RHO_GRID, "seeds": seeds, "ns": ns, "gens": a.gens,
                   "anchor": ANCHOR, "inner_probes": INNER_PROBES,
                   "inner_step": INNER_STEP, "inner_lr": INNER_LR,
                   "substrate": "T13 ContextualTask + paired_gate, frozen-anchor frozen_inner-target"},
        "rows": [{k: x for k, x in row.items() if k != "_trace"} for row in rows],
        "summary": [{"rho_param": r, "N": n, **s[(r, n)]} for r in RHO_GRID for n in ns],
        "traces_seed1_N16": traces,
        "verdict": v,
    }, indent=1), encoding="utf-8")
    print("\nwrote " + a.out + " rows=" + str(len(rows)))


if __name__ == "__main__":
    main()
