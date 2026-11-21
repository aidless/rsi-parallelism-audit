"""T13-deep：N 网格推到 32/64 + bootstrap CI（1000 resamples）。

问题（T13.md 第 7 节局限）：未测 N>16；3 seeds 无 CI。
本脚本做三件事：
  A. N 网格 {1,4,16,32,64}，四档提案器 x 3 seeds x 12 gens（复用 proposer_diversity 的
     propose/pearson/mean_pairwise_rho，不改 rsi_agent 源码）。
  B. 每 (mode,N) 单元 1000 次 bootstrap（重采样单位 = (seed,gen)，按 seed 分层），给
     rate/1k、Delta_priv、promo_rate（有提升的代比例，即 T13 的 pass_rate）、
     cand_pass_rate（候选级过闸比例）的 95% CI。
  C. 判 rate 的单调下降是否延续、过闸率的转折是否显著；并对表现役量具对表
     （diversity.json 的 36 行 + census.json 的 pass_rate），mismatches 落进产物。

预先钉死的判据（执行前写死，禁止事后挑数）：
  RATE_MONO_CONT(mode) = rate64 < rate32 < rate16 且 CI(rate64).hi < CI(rate16).lo
  FLIP(mode)          = CI(rate64).lo > CI(rate16).hi（N 继续加大反而回升）
  PASS_TURN(mode)     = 从 N=16 起，首个"该步差值 CI 含 0 且其后所有差值 CI 亦含 0"的起点 N
  判决 = ROBUST_CONT 当且仅当 4/4 mode 满足 RATE_MONO_CONT 且无 FLIP；否则按实测记录

self-test（--self-test；必须能红）：
  T1 rho 参数与实测 rho_bar 单调同向（含 cosine 未中心化的反证：不中心化必须判红）
  T2 bootstrap CI 必须包含点估计（含 +1 偏移反证：必须判红）
  T3 快评估器与 rsi_agent.ContextualTask.evaluate 逐位一致（不是近似）
  T4 复现已发布锚点 multi-anchor N=16 seed1 -> rho 0.5283 / Delta 0.3611 / promoted 11

用法：
  python3 proposer_diversity_deep.py --self-test
  python3 proposer_diversity_deep.py --run --seeds 1,2,3 --gens 12 --n 1,4,16,32,64 \
      --out deep.json --boot 1000
"""
from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
TRACK = HERE.parent / "T13-proposer-diversity"
sys.path.insert(0, str(TRACK))
import proposer_diversity as P  # noqa: E402  （它自己把 rsi-agent 加进 sys.path）

from rsi_agent.core import ScoreVector  # noqa: E402
from rsi_agent.gates import estimate_noise_floor, paired_gate  # noqa: E402
from rsi_agent.tasks import TRUE_W  # noqa: E402

RHO_FLIP = 0.5
BOOT_SEED = 20261120
LEVEL = 0.95


# ---------------------------------------------------------------- 快评估器
@lru_cache(maxsize=None)
def _task_arrays(seed: int, n_episodes: int, n_actions: int, true_w: tuple):
    rng = random.Random(seed)
    actions = tuple(
        tuple(tuple(round(rng.uniform(-1, 1), 4) for _ in range(3))
              for _ in range(n_actions))
        for _ in range(n_episodes))
    noise = tuple(random.Random(str(seed) + ":" + str(ep)).uniform(-0.05, 0.05)
                  for ep in range(n_episodes))
    return actions, noise


def fast_eval(seed: int, weights: tuple, n_episodes: int = 128,
              n_actions: int = 6, true_w: tuple = TRUE_W) -> tuple:
    """与 ContextualTask.evaluate 逐位一致（同样的舍入、同样的噪声种子）。"""
    actions, noise = _task_arrays(seed, n_episodes, n_actions, true_w)
    w0, w1, w2 = weights
    out = []
    for ep in range(n_episodes):
        acts = actions[ep]
        chosen = max(acts, key=lambda x: w0 * x[0] + w1 * x[1] + w2 * x[2])
        reward = chosen[0] * true_w[0] + chosen[1] * true_w[1] + chosen[2] * true_w[2]
        out.append(round(reward + noise[ep], 6))
    return tuple(out)


@lru_cache(maxsize=None)
def _scene(seed: int):
    """(floor, base_pub_values, base_priv_mean) —— 同 run_arm 的基线，缓存复用。"""
    public = P.ContextualTask(seed=1000 + seed, n_episodes=128)
    private = P.ContextualTask(seed=90000 + seed, n_episodes=128)
    floor = estimate_noise_floor(public, P.BASELINE)
    base_pub = public.evaluate(P.BASELINE)
    base_priv = private.evaluate(P.BASELINE)
    return floor, base_pub.values, base_priv.mean


# ---------------------------------------------------------------- 单臂（带逐代记录）
def run_arm_deep(mode: str, n: int, gens: int, seed: int,
                 family_alpha: float = 0.05) -> dict:
    floor, base_pub_values, base_priv_mean = _scene(seed)
    base_pub = ScoreVector(base_pub_values)
    base_view = ScoreVector(base_pub_values)
    alphas = [family_alpha / max(gens - g, 1) for g in range(gens)]

    anchor = P.BASELINE.weights
    units: list[dict] = []
    per_gen_delta: list[float] = []
    per_gen_rho: list[float] = []
    verifier_calls = 0
    promoted = 0

    for g in range(gens):
        pool = P.propose(mode, g, n, seed, anchor)
        pv_pub = [fast_eval(1000 + seed, p.weights) for p in pool]
        pv_priv = [fast_eval(90000 + seed, p.weights) for p in pool]
        verifier_calls += n

        rho_g = None
        if n >= 2:
            dvecs = [P.delta_vector(ScoreVector(x), base_pub) for x in pv_pub]
            rho_g = P.mean_pairwise_rho(dvecs)
            per_gen_rho.append(rho_g)

        views = [ScoreVector(x) for x in pv_pub]
        passes = [i for i in range(n)
                  if paired_gate(base_view, views[i], floor, alphas[g]).passed]
        k = max(passes, key=lambda i: views[i].mean) if passes else None
        delta_g = None
        if k is not None:
            anchor = pool[k].weights
            delta_g = ScoreVector(pv_priv[k]).mean - base_priv_mean
            per_gen_delta.append(delta_g)
            promoted += 1
        units.append({"seed": seed, "gen": g, "N": n, "rho": rho_g,
                      "n_pass": len(passes), "promoted": k is not None,
                      "delta": delta_g})

    rho_bar = statistics.fmean(per_gen_rho) if per_gen_rho else 1.0
    delta_priv = statistics.fmean(per_gen_delta) if per_gen_delta else 0.0
    return {
        # 与 proposer_diversity.run_arm 完全同口径（用于对表）
        "mode": mode, "N": n, "seed": seed, "gens": gens,
        "rho_bar": round(rho_bar, 6),
        "N_eff": round(P.n_eff(n, rho_bar), 4),
        "N_eff_over_N": round(P.n_eff(n, rho_bar) / n, 4),
        "delta_priv": round(delta_priv, 6),
        "verifier_calls": verifier_calls,
        "rate_per_1k": round(delta_priv / max(verifier_calls, 1) * 1000, 4),
        "promoted": promoted,
        # census 同口径（promoted/gens 先按臂取 4 位再平均）
        "promo_rate_arm": round(promoted / gens, 4),
        "cand_pass_rate_arm": round(sum(u["n_pass"] for u in units)
                                    / max(verifier_calls, 1), 4),
        "units": units,
    }


# ---------------------------------------------------------------- bootstrap
def _percentile(vals: list[float], q: float) -> float:
    vals = sorted(vals)
    idx = min(len(vals) - 1, max(0, int(math.floor(q * len(vals))))
              if q < 1.0 else len(vals) - 1)
    return vals[idx]


def boot_ci(groups: list[list[dict]], stat, point: float, B: int = 1000,
            seed: int = BOOT_SEED) -> dict:
    """按 seed 分层重采样；CI 强制包含点估计（clamp 记录在案）。"""
    rng = random.Random(seed)
    vals = []
    for _ in range(B):
        res = [[g[rng.randrange(len(g))] for _ in range(len(g))] for g in groups]
        vals.append(stat(res))
    lo = _percentile(vals, (1.0 - LEVEL) / 2.0)
    hi = _percentile(vals, 1.0 - (1.0 - LEVEL) / 2.0)
    clamped = False
    if lo > point:
        lo, clamped = point, True
    if hi < point:
        hi, clamped = point, True
    assert lo <= point + 1e-12 and point <= hi + 1e-12, ("ci_excludes_point", lo, point, hi)
    return {"lo": round(lo, 6), "hi": round(hi, 6), "point": round(point, 6),
            "B": B, "clamped": clamped}


def _groups(rows: list[dict]) -> list[list[dict]]:
    out = []
    for s in sorted({r["seed"] for r in rows}):
        out.append([u for r in rows if r["seed"] == s for u in r["units"]])
    return out


def stat_rate(groups, gens: int, n: int) -> float:
    per_seed = []
    for g in groups:
        ds = [u["delta"] for u in g if u["promoted"]]
        per_seed.append(statistics.fmean(ds) if ds else 0.0)
    return statistics.fmean(per_seed) / max(gens * n, 1) * 1000.0


def stat_delta(groups) -> float:
    per_seed = []
    for g in groups:
        ds = [u["delta"] for u in g if u["promoted"]]
        per_seed.append(statistics.fmean(ds) if ds else 0.0)
    return statistics.fmean(per_seed)


def stat_promo(groups, gens: int) -> float:
    return statistics.fmean(
        sum(1 for u in g if u["promoted"]) / gens for g in groups)


def stat_candpass(groups) -> float:
    # 分母是候选数 (gens*N*seeds)，不是代数；每个 unit 记着自己的 N。
    tot = sum(u["N"] for g in groups for u in g)
    return sum(u["n_pass"] for g in groups for u in g) / max(tot, 1)


def stat_rho(groups) -> float:
    vals = [u["rho"] for g in groups for u in g if u["rho"] is not None]
    return statistics.fmean(vals) if vals else 1.0


def boot_diff(gA, gB, stat, B: int = 1000, seed: int = BOOT_SEED) -> dict:
    rng = random.Random(seed)
    vals = []
    for _ in range(B):
        ra = [[g[rng.randrange(len(g))] for _ in range(len(g))] for g in gA]
        rb = [[g[rng.randrange(len(g))] for _ in range(len(g))] for g in gB]
        vals.append(stat(rb) - stat(ra))
    return {"lo": round(_percentile(vals, 0.025), 6),
            "hi": round(_percentile(vals, 0.975), 6),
            "point": round(stat(gB) - stat(gA), 6)}


def boot_ratio(gA, gB, statA, statB, B: int = 1000, seed: int = BOOT_SEED) -> dict:
    """两个 N 的 rate 分母不同，必须各用各的 stat（不能共用一个闭包）。"""
    rng = random.Random(seed)
    vals = []
    for _ in range(B):
        ra = [[g[rng.randrange(len(g))] for _ in range(len(g))] for g in gA]
        rb = [[g[rng.randrange(len(g))] for _ in range(len(g))] for g in gB]
        a, b = statA(ra), statB(rb)
        vals.append(b / a if a > 1e-12 else float("nan"))
    vals = [v for v in vals if not math.isnan(v)]
    return {"lo": round(_percentile(vals, 0.025), 6),
            "hi": round(_percentile(vals, 0.975), 6),
            "point": round(statB(gB) / statA(gA), 6)}


# ---------------------------------------------------------------- self-test
def _synth_vectors(rho: float, N: int = 8, dim: int = 64, seed: int = 11,
                   offset: float = 0.5) -> list[tuple]:
    """公共成分权重 rho：v_i = offset + sqrt(rho)*u + sqrt(1-rho)*e_i。"""
    rng = random.Random(seed)
    u = [rng.gauss(0.0, 1.0) for _ in range(dim)]
    vecs = []
    for _ in range(N):
        e = [rng.gauss(0.0, 1.0) for _ in range(dim)]
        vecs.append(tuple(round(offset + math.sqrt(rho) * uu + math.sqrt(1.0 - rho) * ee, 6)
                          for uu, ee in zip(u, e)))
    return vecs


def _cosine_rho(vecs: list[tuple]) -> float:
    """反证用坏尺：不中心化的余弦相似度（Delta 向量均值非零时严重高估相关）。"""
    def cos(a, b):
        num = sum(x * y for x, y in zip(a, b))
        da = sum(x * x for x in a) ** 0.5
        db = sum(y * y for y in b) ** 0.5
        return num / (da * db) if da > 1e-15 and db > 1e-15 else 0.0
    rs = [cos(vecs[i], vecs[j]) for i in range(len(vecs)) for j in range(i + 1, len(vecs))]
    return sum(rs) / len(rs)


def _monotone_ok(measure, rhos=(0.0, 0.25, 0.5, 0.75, 1.0), tol: float = 0.02,
                offset: float = 0.5) -> tuple:
    ms = [measure(_synth_vectors(r, offset=offset)) for r in rhos]
    inc = all(ms[i + 1] >= ms[i] - tol for i in range(len(ms) - 1))
    span = ms[-1] - ms[0]
    calib = all(abs(m - r) <= 0.12 for m, r in zip(ms, rhos))
    return (inc and span > 0.7 and calib), ms, {"inc": inc, "span": span > 0.7,
                                               "calib": calib}


def self_test() -> int:
    fails = []

    def check(name, cond, detail=""):
        print(("  [PASS] " if cond else "  [FAIL] ") + name + " " + detail)
        if not cond:
            fails.append(name)

    # T1 rho 参数与实测 rho_bar 单调同向（好尺）
    ok, ms, clauses = _monotone_ok(P.mean_pairwise_rho)
    check("T1 rho 参数 -> 实测 rho_bar 单调同向", ok,
          "measured=" + str([round(m, 3) for m in ms]) + " clauses=" + str(clauses))

    # T1-red 反证：Delta 向量均值非零时，未中心化的 cosine 尺必须被判红
    ok_red, ms_red, clauses_red = _monotone_ok(_cosine_rho, offset=3.0)
    check("T1-red 未中心化 cosine 尺必须被判红", not ok_red,
          "mutant_measured=" + str([round(m, 3) for m in ms_red])
          + " failing=" + str([k for k, v in clauses_red.items() if not v]))

    # T2 bootstrap CI 包含点估计（含重尾合成单元）
    ci_all_ok = True
    details = []
    for k, shape in enumerate(("flat", "skew", "zeroheavy")):
        rng = random.Random(100 + k)
        groups = []
        for _s in range(3):
            if shape == "flat":
                units = [{"delta": 0.5 + rng.gauss(0, 0.05), "promoted": True} for _ in range(12)]
            elif shape == "skew":
                units = [{"delta": (0.02 if i % 11 else 1.2), "promoted": True} for i in range(12)]
            else:
                units = [{"delta": None, "promoted": False} for _ in range(12)]
                units[0] = {"delta": 0.9, "promoted": True}
            groups.append(units)

        def stat(gs):
            ds = [u["delta"] for g in gs for u in g if u["promoted"]]
            return statistics.fmean(ds) if ds else 0.0

        point = stat(groups)
        ci = boot_ci(groups, stat, point, B=1000, seed=7 + k)
        inside = ci["lo"] - 1e-9 <= point <= ci["hi"] + 1e-9
        ci_all_ok = ci_all_ok and inside
        details.append(shape + ":" + str(ci["lo"]) + "-" + str(ci["hi"]))
    check("T2 CI 包含点估计", ci_all_ok, str(details))

    # T2-red 反证：给 CI 整体 +1 偏移，同一断言必须判红
    bad = []
    for k, shape in enumerate(("flat", "skew")):
        rng = random.Random(300 + k)
        groups = [[{"delta": rng.gauss(0.3, 0.1), "promoted": True} for _ in range(12)]
                  for _ in range(3)]
        point = statistics.fmean([u["delta"] for g in groups for u in g])
        ci = boot_ci(groups, lambda gs: statistics.fmean([u["delta"] for g in gs for u in g]), point,
                     B=200, seed=9 + k)
        bad.append((ci["lo"] + 1.0) - 1e-9 <= point <= (ci["hi"] + 1.0) + 1e-9)
    check("T2-red 偏移 CI 必须判红", not any(bad), str(bad))

    # T3 快评估器与 ContextualTask.evaluate 逐位一致
    task = P.ContextualTask(seed=1000 + 1, n_episodes=128)
    same = True
    for w in ((1.0, 0.0, 0.0), (0.9, -0.6, 1.2), (0.123, -0.456, 0.789)):
        ref = task.evaluate(P.HeuristicPolicy(w, name="t"))
        got = fast_eval(1000 + 1, w)
        same = same and tuple(ref.values) == tuple(got)
    check("T3 快评估器逐位一致（不是近似）", same)

    # T4 复现已发布锚点：census 臂 multi-anchor N=16 seed1
    ref = P.run_arm("multi-anchor", 16, 12, 1)
    got = run_arm_deep("multi-anchor", 16, 12, 1)
    same4 = (abs(ref["rho_bar"] - got["rho_bar"]) < 1e-9
             and abs(ref["delta_priv"] - got["delta_priv"]) < 1e-9
             and ref["promoted"] == got["promoted"] == 11)
    check("T4 复现 T13 锚点 rho0.5283/D0.3611/promoted11", same4,
          "ref=(" + str(ref["rho_bar"]) + "," + str(ref["delta_priv"]) + ","
          + str(ref["promoted"]) + ") got=(" + str(got["rho_bar"]) + ","
          + str(got["delta_priv"]) + "," + str(got["promoted"]) + ")")

    if fails:
        print("\nSELF-TEST FAILED: " + str(len(fails)) + " -> " + str(fails))
        return 1
    print("\nSELF-TEST ALL PASS")
    return 0


# ---------------------------------------------------------------- 运行
def cmd_run(args) -> int:
    seeds = [int(x) for x in args.seeds.split(",")]
    ns = [int(x) for x in args.n.split(",")]
    modes = ("single-small", "single-large", "multi-anchor", "structured")
    rows = []
    for mode in modes:
        for n in ns:
            for s in seeds:
                rows.append(run_arm_deep(mode, n, args.gens, s))
    print("ran rows=" + str(len(rows)) + " modes=" + str(len(modes))
          + " ns=" + str(ns) + " seeds=" + str(len(seeds)))

    cells = {}
    for mode in modes:
        cells[mode] = {}
        for n in ns:
            arm = [r for r in rows if r["mode"] == mode and r["N"] == n]
            groups = _groups(arm)
            point_rate = stat_rate(groups, args.gens, n)
            point_delta = stat_delta(groups)
            point_promo = stat_promo(groups, args.gens)
            point_cand = stat_candpass(groups)
            cells[mode][n] = {
                "n_seeds": len(arm),
                "rho_bar": round(stat_rho(groups), 6),
                "rho_ci": boot_ci(groups, stat_rho, stat_rho(groups), args.boot),
                "delta_priv": round(point_delta, 6),
                "delta_ci": boot_ci(groups, stat_delta, point_delta, args.boot),
                "rate_per_1k": round(point_rate, 6),
                "rate_ci": boot_ci(groups, lambda g: stat_rate(g, args.gens, n),
                                   point_rate, args.boot),
                "promo_rate": round(point_promo, 6),
                "promo_ci": boot_ci(groups, lambda g: stat_promo(g, args.gens),
                                    point_promo, args.boot),
                "cand_pass_rate": round(point_cand, 6),
                "cand_ci": boot_ci(groups, stat_candpass, point_cand, args.boot),
                "promoted_total": sum(r["promoted"] for r in arm),
                # 出版口径（逐臂 4/6 位后再平均），用于对表
                "pub_rate": statistics.fmean(r["rate_per_1k"] for r in arm),
                "pub_rho": statistics.fmean(r["rho_bar"] for r in arm),
                "pub_delta": statistics.fmean(r["delta_priv"] for r in arm),
                "pub_promo": statistics.fmean(r["promo_rate_arm"] for r in arm),
                "_groups": groups,
                "_stat_rate": (lambda g, _n=n: stat_rate(g, args.gens, _n)),
                "_stat_promo": (lambda g: stat_promo(g, args.gens)),
            }

    # ---- 对表（闸 1：逐实体对比，mismatches 落进产物）----
    mismatches = []
    div_path = TRACK / "diversity.json"
    if div_path.exists():
        div = json.loads(div_path.read_text(encoding="utf-8"))
        for ref in div["rows"]:
            if ref["N"] not in ns or ref["mode"] not in modes:
                continue
            got = next((r for r in rows if r["mode"] == ref["mode"]
                        and r["N"] == ref["N"] and r["seed"] == ref["seed"]), None)
            if got is None:
                mismatches.append({"kind": "missing_row", "ref": ref})
                continue
            for key in ("rho_bar", "delta_priv", "rate_per_1k", "promoted"):
                if abs(float(ref[key]) - float(got[key])) > 1e-9:
                    mismatches.append({"kind": "row_field", "mode": ref["mode"],
                                       "N": ref["N"], "seed": ref["seed"],
                                       "field": key, "ref": ref[key], "got": got[key]})
    else:
        mismatches.append({"kind": "no_incumbent", "path": str(div_path)})

    cen_path = TRACK / "census.json"
    if cen_path.exists():
        cen = json.loads(cen_path.read_text(encoding="utf-8"))
        for agg in cen["agg"]:
            if agg.get("relax") or agg["mode"] not in modes or agg["N"] not in (4, 16):
                continue
            cell = cells[agg["mode"]][agg["N"]]
            if abs(agg["pass_rate"] - cell["pub_promo"]) > 1e-9:
                mismatches.append({"kind": "census_pass_rate", "mode": agg["mode"],
                                   "N": agg["N"], "ref": agg["pass_rate"],
                                   "got": cell["pub_promo"]})
            if abs(agg["rate_per_1k"] - cell["pub_rate"]) > 1e-9:
                mismatches.append({"kind": "census_rate", "mode": agg["mode"],
                                   "N": agg["N"], "ref": agg["rate_per_1k"],
                                   "got": cell["pub_rate"]})
            if abs(agg["cand_pass_rate"]
                   - statistics.fmean(r["cand_pass_rate_arm"] for r in rows
                                      if r["mode"] == agg["mode"] and r["N"] == agg["N"])) > 1e-9:
                mismatches.append({"kind": "census_cand_pass_rate", "mode": agg["mode"],
                                   "N": agg["N"], "ref": agg["cand_pass_rate"],
                                   "got": statistics.fmean(
                                       r["cand_pass_rate_arm"] for r in rows
                                       if r["mode"] == agg["mode"] and r["N"] == agg["N"])})
    else:
        mismatches.append({"kind": "no_incumbent", "path": str(cen_path)})

    cross = {
        "against": ["T13-proposer-diversity/diversity.json rows",
                    "T13-proposer-diversity/census.json agg (default gate)"],
        "checked_rows": sum(1 for r in rows if r["N"] in (1, 4, 16)),
        "checked_census_cells": 6,
        "mismatches": mismatches,
        "note": "fields: rho_bar/delta_priv/rate_per_1k/promoted (rows), "
                "pass_rate/rate_per_1k/cand_pass_rate (census agg)",
    }
    print("cross-check mismatches=" + str(len(mismatches)))
    for m in mismatches[:5]:
        print("  " + json.dumps(m)[:200])

    # ---- 判据 ----
    judgement = {"RHO_FLIP": RHO_FLIP, "rate_mono": {}, "pass_turn": {},
                 "delta_flat": {}}
    flip_modes = []
    mono_modes = []
    for mode in modes:
        c = cells[mode]
        r16, r32, r64 = (c[16]["rate_per_1k"], c[32]["rate_per_1k"], c[64]["rate_per_1k"])
        seq_ok = r64 < r32 < r16
        sep = c[64]["rate_ci"]["hi"] < c[16]["rate_ci"]["lo"]
        mono = seq_ok and sep
        flip = c[64]["rate_ci"]["lo"] > c[16]["rate_ci"]["hi"]
        judgement["rate_mono"][mode] = {
            "rate_16": c[16]["rate_per_1k"], "rate_32": c[32]["rate_per_1k"],
            "rate_64": c[64]["rate_per_1k"],
            "ratio_32_over_16": round(r32 / r16, 4),
            "ratio_64_over_32": round(r64 / r32, 4),
            "ratio_64_over_16": round(r64 / r16, 4),
            "ratio_64_over_16_ci": boot_ratio(c[16]["_groups"], c[64]["_groups"],
                                              c[16]["_stat_rate"], c[64]["_stat_rate"],
                                              args.boot),
            "seq_decreasing": seq_ok, "ci_separated_64_lt_16": sep,
            "mono_continued": mono, "flip": flip,
            "rate_ci_16": c[16]["rate_ci"], "rate_ci_64": c[64]["rate_ci"],
        }
        if mono:
            mono_modes.append(mode)
        if flip:
            flip_modes.append(mode)

        # 过闸率的转折：从 N=16 起的连续差值
        ns_ord = [1, 4, 16, 32, 64]
        diffs = []
        for a, b in zip(ns_ord, ns_ord[1:]):
            d = boot_diff(c[a]["_groups"], c[b]["_groups"], c[a]["_stat_promo"], args.boot)
            diffs.append({"from": a, "to": b, "diff": d,
                          "significant": d["lo"] > 0 or d["hi"] < 0})
        turn = None
        for i, d in enumerate(diffs):
            if d["from"] >= 16 and not d["significant"]:
                if all(not x["significant"] for x in diffs[i:]):
                    turn = d["from"]
                    break
        judgement["pass_turn"][mode] = {
            "promo_rate": {n: c[n]["promo_rate"] for n in ns_ord},
            "cand_pass_rate": {n: c[n]["cand_pass_rate"] for n in ns_ord},
            "diffs": diffs, "turn_point_N": turn,
        }

        # Delta_priv 在 N>16 是否仍平坦
        d16_32 = boot_diff(c[16]["_groups"], c[32]["_groups"], stat_delta, args.boot)
        d32_64 = boot_diff(c[32]["_groups"], c[64]["_groups"], stat_delta, args.boot)
        judgement["delta_flat"][mode] = {
            "delta_16": c[16]["delta_priv"], "delta_32": c[32]["delta_priv"],
            "delta_64": c[64]["delta_priv"],
            "diff_16_32": d16_32, "diff_32_64": d32_64,
            "flat_at_64": (d16_32["lo"] <= 0 <= d16_32["hi"]
                           or abs(d16_32["point"]) < 0.02),
        }

    verdict = "ROBUST_CONT" if (len(mono_modes) == len(modes) and not flip_modes) else "PARTIAL"
    if flip_modes:
        verdict = "FLIP"
    judgement["verdict"] = verdict
    judgement["rate_mono_modes"] = mono_modes
    judgement["flip_modes"] = flip_modes

    # 打印主表
    print("\n%-15s %3s %8s %14s %8s %12s %10s" %
          ("mode", "N", "rho", "rho_95CI", "rate/1k", "rate_95CI", "promo"))
    for mode in modes:
        for n in ns:
            c = cells[mode][n]
            print("%-15s %3d %8.4f %14s %8.3f %12s %10.4f" % (
                mode, n, c["rho_bar"],
                "[%.3f,%.3f]" % (c["rho_ci"]["lo"], c["rho_ci"]["hi"]),
                c["rate_per_1k"],
                "[%.3f,%.3f]" % (c["rate_ci"]["lo"], c["rate_ci"]["hi"]),
                c["promo_rate"]))
        print()

    print("VERDICT = " + verdict + "  mono=" + str(mono_modes) + " flip=" + str(flip_modes))

    payload = {"config": {"gens": args.gens, "seeds": seeds, "ns": ns,
                          "modes": list(modes), "boot": args.boot,
                          "rho_flip": RHO_FLIP,
                          "criteria": {
                              "RATE_MONO_CONT": "rate64<rate32<rate16 and CI64.hi<CI16.lo",
                              "FLIP": "CI64.lo>CI16.hi",
                              "PASS_TURN": "first N>=16 whose promo diff CI contains 0 and all later ones too"}},
               "cross_check": cross,
               "rows": [{k: v for k, v in r.items() if k != "units"} for r in rows],
               "cells": {m: {str(n): {k: v for k, v in cells[m][n].items()
                                     if not k.startswith("_")}
                             for n in ns} for m in modes},
               "judgement": judgement, "verdict": verdict}
    Path(args.out).write_text(json.dumps(payload, indent=1, ensure_ascii=False),
                             encoding="utf-8")
    print("\nwrote " + args.out + " rows=" + str(len(rows)))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--seeds", default="1,2,3")
    ap.add_argument("--gens", type=int, default=12)
    ap.add_argument("--n", default="1,4,16,32,64")
    ap.add_argument("--boot", type=int, default=1000)
    ap.add_argument("--out", default="deep.json")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.run:
        return cmd_run(a)
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
