#!/usr/bin/env python3
"""T3-deep：同底物上的「单体 portfolio（多策略）vs 采样群体」等预算对撞。

闭合 T3.md §5 遗留 2：把 T7-collision 的底物原样搬来（直接 import，不改 T7 文件），
对照从「1 支单策略拿全 B」扩展为「1 支单体持 m 个策略、总预算仍为 B」：
  - 单体 portfolio：m 个策略全部押在 oracle 族 0，每策略 B/m 次评估；
    答案端点 A_mono = max_p dot(p,w_0)，生态端点 E_mono = mean_j max_p dot(p,w_j)。
  - 采样群体：k 个 agent 各押一族、每族 B/k 次评估；
    A_swarm = max_i dot(p_i,w_i)，E_swarm = mean_j max_p dot(p,w_j)。
两个端点从同一批评估里同时算出；m=1 时本仪器逐 seed 退化为 T7 的 single 臂。

token 口径（沿用 T3 §6）：单体 token = t_fixed + B*t_eval，
群体 token = k*t_fixed + B*t_eval；同 token 预算 T 反解 B_mono/B_swarm 后比较。

用法：
  python3 analyses/tracks/rsi-after/T3-deep/budget_matched_swarm.py --self-test
  python3 analyses/tracks/rsi-after/T3-deep/budget_matched_swarm.py --prove-red
  python3 analyses/tracks/rsi-after/T3-deep/budget_matched_swarm.py
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
T7_DIR = HERE.parent / "T7-collision"
T3_DIR = HERE.parent / "T3-collective"
sys.path.insert(0, str(T7_DIR))
import collision_endpoints as ce  # noqa: E402  —— 只读底物，不改

T7_JSON = T7_DIR / "outputs" / "collision.json"
TOKEN_JSON = T3_DIR / "outputs" / "token_cost.json"
OUT = HERE / "outputs"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mean(xs):
    xs = list(xs)
    if not xs:
        raise ValueError("empty mean")
    return sum(xs) / len(xs)


def parse_floats(s: str):
    return [float(x) for x in s.split(",") if x.strip()]


def parse_ints(s: str):
    return [int(x) for x in s.split(",") if x.strip()]


def alloc_counts(budget: int, m: int):
    """总预算 B 分给 m 个策略；余数给前几个策略。"""
    if m < 1 or budget < 1:
        raise ValueError("budget/m must be positive")
    base, rem = divmod(budget, m)
    return [base + (1 if i < rem else 0) for i in range(m)]


def run_one(k, dim, rho, budget, seed, m, t_fixed=0.0, t_eval=1.0):
    """一粒种子：同底物、同预算，同时算 A/E/T 两端。"""
    rng = random.Random(seed)
    fams = ce.make_families(rng, k, dim, rho)
    ws = [f[0] for f in fams]
    u = fams[0][2]
    v_new = ce.unit(rng, dim)
    w_held = ce.normalize([math_sqrt(rho) * a + math_sqrt(1.0 - rho) * b
                           for a, b in zip(u, v_new)])

    # 群体先跑：保持与 T7 run_one 的 RNG 消耗顺序一致（m=1 才能逐位复现）。
    per = max(1, budget // k)
    swarm = []
    for w in ws:
        p, _ = ce.best_of(per, lambda q, w=w: ce.dot(q, w), rng, dim)
        swarm.append(p)
    A_swarm = max(ce.dot(p, w) for p, w in zip(swarm, ws))
    E_swarm = mean(max(ce.dot(p, wj) for p in swarm) for wj in ws)
    T_swarm = max(ce.dot(p, w_held) for p in swarm)

    # 单体 portfolio：m 个策略，全部押 oracle 族 0。
    mono = []
    for n in alloc_counts(budget, m):
        p, _ = ce.best_of(n, lambda q: ce.dot(q, ws[0]), rng, dim)
        mono.append(p)
    A_mono = max(ce.dot(p, ws[0]) for p in mono)
    E_mono = mean(max(ce.dot(p, wj) for p in mono) for wj in ws)
    T_mono = max(ce.dot(p, w_held) for p in mono)

    tax_A = A_mono - A_swarm   # >0：单体/集中赢答案端点
    gain_E = E_swarm - E_mono  # >0：群体赢生态端点
    gain_T = T_swarm - T_mono
    return {
        "rho": rho, "budget": budget, "seed": seed, "m": m,
        "A_mono": A_mono, "A_swarm": A_swarm,
        "E_mono": E_mono, "E_swarm": E_swarm,
        "T_mono": T_mono, "T_swarm": T_swarm,
        "tax_A": tax_A, "gain_E": gain_E, "gain_T": gain_T,
        "token_mono": t_fixed + budget * t_eval,
        "token_swarm": k * t_fixed + budget * t_eval,
        "win_A": "mono" if tax_A > 0 else ("swarm" if tax_A < 0 else "tie"),
        "win_E": "swarm" if gain_E > 0 else ("mono" if gain_E < 0 else "tie"),
        "win_T": "swarm" if gain_T > 0 else ("mono" if gain_T < 0 else "tie"),
    }


def math_sqrt(x):
    import math
    return math.sqrt(x)


def aggregate(rows):
    from collections import defaultdict
    g = defaultdict(list)
    for r in rows:
        g[(r["rho"], r["budget"], r["m"])].append(r)
    nums = ("A_mono", "A_swarm", "E_mono", "E_swarm", "T_mono", "T_swarm",
            "tax_A", "gain_E", "gain_T", "token_mono", "token_swarm")
    out = []
    for (rho, budget, m), rs in sorted(g.items()):
        d = {k: mean(r[k] for r in rs) for k in nums}
        d["mono_wins_A"] = mean(1.0 if r["tax_A"] > 0 else 0.0 for r in rs)
        d["swarm_wins_E"] = mean(1.0 if r["gain_E"] > 0 else 0.0 for r in rs)
        d["swarm_wins_T"] = mean(1.0 if r["gain_T"] > 0 else 0.0 for r in rs)
        d.update(rho=rho, budget=budget, m=m, n_seeds=len(rs),
                 winner_A="mono" if d["tax_A"] > 0 else ("swarm" if d["tax_A"] < 0 else "tie"),
                 winner_E="swarm" if d["gain_E"] > 0 else ("mono" if d["gain_E"] < 0 else "tie"))
        out.append(d)
    return out


def interp(agg, rho, m, budget, key):
    """在已落盘的 budget 网格上线性插值，网格外钳端点（与 T3 token 模型同口径）。"""
    pts = sorted((r["budget"], r[key]) for r in agg
                 if abs(r["rho"] - rho) < 1e-12 and r["m"] == m)
    if not pts:
        raise ValueError(f"no agg points for rho={rho} m={m} key={key}")
    if budget <= pts[0][0]:
        return pts[0][1]
    if budget >= pts[-1][0]:
        return pts[-1][1]
    for (b0, v0), (b1, v1) in zip(pts, pts[1:]):
        if b0 <= budget <= b1:
            return v0 + (v1 - v0) * (budget - b0) / (b1 - b0)
    raise RuntimeError("interp failed")


def verify_crossing(agg, rho, m, low, high, flip=False):
    """t_fixed=0 的 A 端点交叉点：low 处群体赢、high 处单体赢。"""
    sign = -1.0 if flip else 1.0
    swarm_bs = sorted(r["budget"] for r in agg
                      if abs(r["rho"] - rho) < 1e-12 and r["m"] == m and sign * r["tax_A"] < 0)
    mono_bs = sorted(r["budget"] for r in agg
                     if abs(r["rho"] - rho) < 1e-12 and r["m"] == m and sign * r["tax_A"] > 0)
    last_swarm = swarm_bs[-1] if swarm_bs else None
    first_mono = mono_bs[0] if mono_bs else None
    ok = (last_swarm == low and first_mono == high)
    return {"ok": ok, "last_swarm_budget": last_swarm, "first_mono_budget": first_mono,
            "target": [low, high], "rho": rho, "m": m, "flip": flip}


def verify_eco(gain_low, gain_high, net_low):
    """低 rho 生态端点仍正：gain>0、gain 高于高 rho、最重税下净效率>0。"""
    ok = gain_low > 0 and gain_low > gain_high and net_low > 0
    return {"ok": ok, "gain_low": gain_low, "gain_high": gain_high, "net_low_heavy_tax": net_low}


def crosscheck_t7(k, dim, rho, budgets, seeds):
    """与现役量具 T7 collision.json 逐实体对表；m=1 必须逐位相同。"""
    if not T7_JSON.exists():
        raise FileNotFoundError(T7_JSON)
    t7 = json.loads(T7_JSON.read_text(encoding="utf-8"))
    ref = {(r["rho"], r["budget"], r["seed"]): r for r in t7["rows"]}
    fields = {"A_mono": "A_single", "E_mono": "E_single", "T_mono": "T_single",
              "A_swarm": "A_swarm", "E_swarm": "E_swarm", "T_swarm": "T_swarm"}
    mismatches, checked = [], 0
    for b in budgets:
        for s in range(seeds):
            o = run_one(k, dim, rho, b, s, 1)
            r = ref.get((rho, b, s))
            if r is None:
                mismatches.append({"rho": rho, "budget": b, "seed": s, "field": "missing", "diff": None})
                continue
            for our, their in fields.items():
                checked += 1
                diff = o[our] - r[their]
                if abs(diff) > 1e-12:
                    mismatches.append({"rho": rho, "budget": b, "seed": s,
                                       "field": our + " vs " + their, "diff": diff})
    # 红反证：注入 +0.01 的已知偏移，检测器必须报 mismatch。
    injected = 0
    for b in budgets:
        for s in range(min(5, seeds)):
            o = run_one(k, dim, rho, b, s, 1)
            r = ref.get((rho, b, s))
            if r and abs(o["A_mono"] - (r["A_single"] + 0.01)) > 1e-12:
                injected += 1
    return {"against": "T7-collision/outputs/collision.json rows (single arm)",
            "checked_fields": checked, "mismatches": mismatches,
            "mismatch_count": len(mismatches),
            "red_control_injected_detections": injected,
            "note": "m=1 时本仪器 A_mono/E_mono/T_mono 必须逐 seed 等于 T7 A_single/E_single/T_single"}



def eco_gain(k, dim, rho, m, seeds, b_mono=32, b_swarm=128, t_fixed=50.0):
    rs_mono = [run_one(k, dim, rho, b_mono, s, m) for s in range(seeds)]
    rs_swarm = [run_one(k, dim, rho, b_swarm, s, m) for s in range(seeds)]
    gain = mean(r["E_swarm"] for r in rs_swarm) - mean(r["E_mono"] for r in rs_mono)
    premium = (k * t_fixed + b_swarm) / (t_fixed + b_mono)
    return {"rho": rho, "m": m, "b_mono": b_mono, "b_swarm": b_swarm,
            "gain_E": gain, "t_fixed_heavy": t_fixed, "premium": premium,
            "net_heavy": gain / premium}


def ecosystem_table(agg, rho_list, m, k, t_fixed_grid, b_mono=32, b_swarm=128):
    out = []
    for rho in rho_list:
        gain = (interp(agg, rho, m, b_swarm, "E_swarm") -
                interp(agg, rho, m, b_mono, "E_mono"))
        for tf in t_fixed_grid:
            premium = (k * tf + b_swarm) / (tf + b_mono)
            out.append({"rho": rho, "m": m, "t_fixed": tf, "gain_E": gain,
                        "token_premium": premium, "net_eco_efficiency": gain / premium})
    return out


def token_sweep(agg, rho_list, m, k, t_fixed_grid, t_eval, token_budgets):
    out = []
    for rho in rho_list:
        for tf in t_fixed_grid:
            for T in token_budgets:
                b_mono = (T - tf) / t_eval
                b_swarm = (T - k * tf) / t_eval
                if b_swarm < 1 or b_mono < 1:
                    out.append({"rho": rho, "m": m, "t_fixed": tf, "token_budget": T,
                                "b_mono": b_mono, "b_swarm": b_swarm,
                                "status": "swarm_unaffordable", "winner_A": "-"})
                    continue
                am = interp(agg, rho, m, b_mono, "A_mono")
                aw = interp(agg, rho, m, b_swarm, "A_swarm")
                em = interp(agg, rho, m, b_mono, "E_mono")
                ew = interp(agg, rho, m, b_swarm, "E_swarm")
                out.append({"rho": rho, "m": m, "t_fixed": tf, "token_budget": T,
                            "b_mono": b_mono, "b_swarm": b_swarm, "status": "ok",
                            "A_mono": am, "A_swarm": aw, "E_mono": em, "E_swarm": ew,
                            "winner_A": "mono" if am > aw else ("swarm" if am < aw else "tie"),
                            "winner_E": "swarm" if ew > em else ("mono" if ew < em else "tie")})
    return out


def provenance():
    p = {"generated_utc": datetime.now(timezone.utc).isoformat(),
         "python": sys.version.split()[0], "platform": platform.platform(),
         "script_sha256": sha256(Path(__file__).resolve()),
         "t7_script_sha256": sha256(T7_DIR / "collision_endpoints.py"),
         "t3_md_sha256": sha256(T3_DIR / "T3.md"),
         "collision_json_sha256": sha256(T7_JSON),
         "token_cost_json_sha256": sha256(TOKEN_JSON) if TOKEN_JSON.exists() else None}
    return p


def self_test(args, inject=False, write=True):
    budgets = parse_ints(args.budgets)
    rhos = parse_floats(args.rhos)
    rows_m1 = [run_one(args.families, args.dim, rho, b, s, 1)
               for rho in rhos for b in budgets for s in range(args.seeds)]
    agg_m1 = aggregate(rows_m1)
    cc = crosscheck_t7(args.families, args.dim, 0.0, budgets, args.seeds)

    cross_good = verify_crossing(agg_m1, 0.0, 1, 16, 32)
    cross_bad = verify_crossing(agg_m1, 0.0, 1, 16, 32, flip=True)

    eco_m = 4 if 4 in args.portfolio_ms else args.portfolio_ms[0]
    eco_low = eco_gain(args.families, args.dim, 0.0, eco_m, args.seeds)
    eco_high = eco_gain(args.families, args.dim, 1.0, eco_m, args.seeds)
    eco_good = verify_eco(eco_low["gain_E"], eco_high["gain_E"], eco_low["net_heavy"])
    eco_bad = verify_eco(-eco_low["gain_E"], -eco_high["gain_E"], -eco_low["net_heavy"])

    # 与 T3 §6 既有 token 表对表：m=1 必须复现（同一 collision.json）。
    legacy = json.loads(TOKEN_JSON.read_text(encoding="utf-8"))
    eco_m1 = ecosystem_table(agg_m1, rhos, 1, args.families, [0.0], 32, 128)
    legacy_mism = []
    for r in eco_m1:
        key = ("%g" % r["rho"]) if r["rho"] != int(r["rho"]) else ("%.1f" % r["rho"])
        want = legacy["table3_eco_net_efficiency"][key]["0.0"]
        if abs(r["net_eco_efficiency"] - want) > 1e-3:
            legacy_mism.append({"rho": r["rho"], "ours": r["net_eco_efficiency"], "legacy": want})

    range_bad = sum(1 for r in rows_m1 if not all(
        -1.0001 <= r[k] <= 1.0001 for k in ("A_mono", "A_swarm", "E_mono", "E_swarm", "T_mono", "T_swarm")))

    top_good = cross_good["ok"] and eco_good["ok"] and not cc["mismatches"]         and cc["red_control_injected_detections"] > 0 and not legacy_mism and range_bad == 0
    top_bad = cross_bad["ok"] and eco_bad["ok"] and cc["mismatch_count"] == 0

    payload = {
        "mode": "RED-INJECTED" if inject else "NORMAL",
        "cross_check_gate": cc,
        "st1_A_crossing_tfixed0_m1_rho0": cross_good,
        "st1_red_flipped_winner_gate": cross_bad,
        "st2_eco_low_rho": eco_low,
        "st2_eco_high_rho_control": eco_high,
        "st2_verdict": eco_good,
        "st2_red_sign_flip": eco_bad,
        "st3_legacy_token_table_crosscheck": {"mismatches": legacy_mism, "checked": len(eco_m1)},
        "st4_range_violations": range_bad,
        "gate_semantics": "good must pass; each injected fault must be detected (bad gate must fail)",
        "verdict": "PASS" if (top_good and not top_bad) else "FAIL",
    }
    if inject:
        # --prove-red：把注入后的坏断言当主判据，必须 FAIL 并以退出码 1 结束。
        print("RED PROOF: injected winner-flip + sign-flip; corrupted gate says",
              "PASS (decorative)" if top_bad else "FAIL (correctly fired)")
        if write is False:
            raise SystemExit(0 if top_bad else 1)
        raise SystemExit(0 if top_bad else 1)
    print(f"[st0] T7 逐 seed 对表: checked={cc['checked_fields']} mismatches={cc['mismatch_count']} "
          f"红控检出={cc['red_control_injected_detections']}")
    print(f"[st1] t_fixed=0, m=1, rho=0: last swarm B={cross_good['last_swarm_budget']}, "
          f"first mono B={cross_good['first_mono_budget']} -> {cross_good['ok']} "
          f"(反转判据 {cross_bad['ok']}，必须 False)")
    print(f"[st2] rho=0 eco gain={eco_low['gain_E']:+.4f}, rho=1 gain={eco_high['gain_E']:+.4f}, "
          f"net(tf={eco_low['t_fixed_heavy']:g})={eco_low['net_heavy']:+.4f} -> {eco_good['ok']} "
          f"(符号反转 {eco_bad['ok']}，必须 False)")
    print(f"[st3] T3 §6 token 表 m=1 复算 mismatches={len(legacy_mism)}/{len(eco_m1)}; "
          f"[st4] 越界分数={range_bad}")
    print("SELF-TEST", payload["verdict"])
    if write:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "self_test.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                                            encoding="utf-8")
    if payload["verdict"] != "PASS":
        raise SystemExit(1)
    return payload


def main_experiment(args):
    st = self_test(args, write=True)
    budgets, rhos, ms = parse_ints(args.budgets), parse_floats(args.rhos), args.portfolio_ms
    rows = [run_one(args.families, args.dim, rho, b, s, m)
            for m in ms for b in budgets for rho in rhos for s in range(args.seeds)]
    agg = aggregate(rows)
    eco = ecosystem_table(agg, rhos, ms[0] if len(ms) == 1 else 4,
                          args.families, parse_floats(args.t_fixed_grid))
    toks = token_sweep(agg, rhos, 4 if 4 in ms else ms[0], args.families,
                       parse_floats(args.t_fixed_grid), args.t_eval,
                       parse_ints(args.token_budgets))
    payload = {
        "design": {
            "question": "T3 §5 遗留 2: budget-concentrated monolithic portfolio vs sampled swarm",
            "substrate": "import collision_endpoints.py from T7-collision (unmodified)",
            "mono": "m strategies, all on oracle family 0, total B split B/m",
            "swarm": "k agents, one family each, B/k evaluations each",
            "endpoints": {"A_mono": "max_p dot(p,w_0)", "A_swarm": "max_i dot(p_i,w_i)",
                          "E_mono": "mean_j max_p dot(p,w_j)", "E_swarm": "mean_j max_p dot(p,w_j)"},
            "token_model": "mono=t_fixed+B*t_eval; swarm=k*t_fixed+B*t_eval",
            "k": args.families, "dim": args.dim, "seeds": args.seeds,
            "budgets": budgets, "rhos": rhos, "portfolio_ms": ms,
            "t_eval": args.t_eval, "t_fixed_grid": parse_floats(args.t_fixed_grid),
            "token_budgets": parse_ints(args.token_budgets),
        },
        "provenance": provenance(),
        "self_test": {"verdict": st["verdict"], "cross_check_mismatches": st["cross_check_gate"]["mismatch_count"]},
        "cross_check_gate": st["cross_check_gate"],
        "rows": rows, "agg": agg,
        "ecosystem_table": eco, "token_sweep": toks,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    jp = OUT / "budget_matched.json"
    jp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    cp = OUT / "budget_matched.csv"
    with cp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(agg[0].keys()))
        w.writeheader()
        w.writerows(agg)
    print(f"wrote {jp} ({len(rows)} rows) + {cp}")
    print("rho  B   m  A_mono A_swarm  E_mono E_swarm  tax_A  gain_E  winA  winE")
    for r in agg:
        if abs(r["rho"]) < 1e-12 and r["m"] in (1, 4):
            print(f"{r['rho']:>4.2f} {r['budget']:>3d} {r['m']:>2d} "
                  f"{r['A_mono']:>7.3f} {r['A_swarm']:>7.3f} {r['E_mono']:>7.3f} {r['E_swarm']:>7.3f} "
                  f"{r['tax_A']:>+6.3f} {r['gain_E']:>+7.3f} {r['winner_A']:>5s} {r['winner_E']:>5s}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--families", type=int, default=8)
    ap.add_argument("--dim", type=int, default=3)
    ap.add_argument("--seeds", type=int, default=40)
    ap.add_argument("--budgets", type=str, default="8,16,32,64,128")
    ap.add_argument("--rhos", type=str, default="0,0.25,0.5,0.75,1.0")
    ap.add_argument("--portfolio-ms", type=str, default="1,2,4,8")
    ap.add_argument("--t-eval", type=float, default=1.0)
    ap.add_argument("--t-fixed-grid", type=str, default="0,2,5,20,50")
    ap.add_argument("--token-budgets", type=str, default="8,16,32,64,128")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--prove-red", action="store_true")
    args = ap.parse_args()
    args.portfolio_ms = parse_ints(args.portfolio_ms)
    if args.prove_red:
        self_test(args, inject=True, write=False)
    elif args.self_test:
        self_test(args, write=True)
    else:
        main_experiment(args)


if __name__ == "__main__":
    main()
