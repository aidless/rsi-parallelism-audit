"""T7：答案端点 vs 生态端点的同因变量、同预算对撞。

用户要求（m00395「全做」）：上一轮提出「让 SwarmWorld 的生态端点与单体最强在
同一因变量、同 token 预算下对撞」——本脚本是它的本地可控版本，不依赖
SwarmWorld 源码（该论文未确认开源）。

底物模型
--------
k 个任务族，每个族有隐藏真值方向 w*_i ∈ R^dim（单位向量）：
    w*_i = sqrt(rho) * u  +  sqrt(1-rho) * v_i
其中 u 是全局共享分量（单位向量），v_i 是族私有分量（单位向量），
rho ∈ [0,1] 是「可迁移性」：rho=1 时所有族同一个真值（学一个通吃），
rho=0 时各族真值正交（学一族对别族无用）。

策略 p 也是单位向量；族 i 上的分数 = dot(p, w*_i) ∈ [-1, 1]。
（分数有上界，所以「预算集中」的边际收益天然递减——这正好检验
 T5 的饱和发现，而不是人为造出的饱和。）

预算与两种部署
--------------
总评估次数 B（= token 预算的代理）。两种部署：
- single（单体）：把 B 全部押在一个族上（oracle 知道押哪族；blind 随机押）
- swarm（群体）：把 B 平均分给 k 个族，每族 B/k

搜索器：锚点式局部高斯扰动（与 rsi-agent 的 InnerAgent 同构）：
    p0 = 随机单位向量；每步 q = normalize(p + step*gauss)，step 指数衰减；
    q 更好则锚点移到 q。

两个因变量（从同一批评估里同时算，这就是「同因变量对撞」的定义）
--------------------------------------------------------------
A_answer   = max_i score_i(best_i)           答案型端点，最强单件
E_portfolio= mean_j max_i score_j(best_i)    生态型端点，跨族组合
            （每个族用对它最好的那个策略；单体只有一个策略，所以它的
             portfolio 只能是 mean_j score_j(p_single)）
T_heldout  = max_i score_heldout(best_i)     迁移端点，未参与训练的族

协调税 = A_single − A_swarm（为生态端点付出的答案端点代价）。

自测（--self-test）注入两个方向相反的断言，判据可红可绿：
1. rho=1.0：A_single > A_swarm（纯预算集中效应，与多样性无关）；
2. rho=0.0：E_swarm > E_single（多样性在生态端点上真有用）；
3. 所有分数落在 [-1, 1]。

复现：
    python3 analyses/tracks/rsi-after/T7-collision/collision_endpoints.py \
        --families 8 --budget 32 --seeds 20 --rhos 0,0.25,0.5,0.75,1.0
"""
from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

OUT = Path(__file__).resolve().parent / "outputs"


def unit(rng: random.Random, dim: int) -> list[float]:
    v = [rng.gauss(0.0, 1.0) for _ in range(dim)]
    n = math.sqrt(sum(c * c for c in v)) or 1.0
    return [c / n for c in v]


def dot(a, b) -> float:
    return sum(x * y for x, y in zip(a, b))


def normalize(v):
    n = math.sqrt(sum(c * c for c in v)) or 1.0
    return [c / n for c in v]


def make_families(rng, k, dim, rho):
    """返回 [(w*_i, v_i)]；w*_i = sqrt(rho)u + sqrt(1-rho)v_i。"""
    u = unit(rng, dim)
    out = []
    for _ in range(k):
        v = unit(rng, dim)
        w = [math.sqrt(rho) * a + math.sqrt(1 - rho) * b for a, b in zip(u, v)]
        out.append((normalize(w), v, u))
    return out


def best_of(n, score, rng, dim, base=None):
    """锚点局部搜索：n 次评估，返回 (best_p, best_score)。"""
    p = base if base is not None else unit(rng, dim)
    best_p, best_s = p, score(p)
    for t in range(max(0, n - 1)):
        step = max(0.5 * (0.94 ** t), 0.04)
        q = normalize([c + step * rng.gauss(0.0, 1.0) for c in p])
        s = score(q)
        if s > best_s:
            best_p, best_s = q, s
            p = q
    return best_p, best_s


def run_one(k, dim, rho, budget, seed):
    rng = random.Random(seed)
    fams = make_families(rng, k, dim, rho)
    ws = [f[0] for f in fams]
    # held-out 族：私有分量新的 v_new
    v_new = unit(rng, dim)
    u = fams[0][2]
    w_held = normalize([math.sqrt(rho) * a + math.sqrt(1 - rho) * b
                        for a, b in zip(u, v_new)])

    # --- swarm：预算均分 ---
    per = max(1, budget // k)
    swarm = []
    for i, w in enumerate(ws):
        p, s = best_of(per, lambda q, w=w: dot(q, w), rng, dim)
        swarm.append((p, s))
    A_swarm = max(s for _, s in swarm)
    E_swarm = sum(max(dot(p, wj) for p, _ in swarm) for wj in ws) / k
    T_swarm = max(dot(p, w_held) for p, _ in swarm)

    # --- single（oracle 押族 0）：预算全押一族 ---
    p_s, s_s = best_of(budget, lambda q: dot(q, ws[0]), rng, dim)
    A_single = s_s
    E_single = sum(dot(p_s, wj) for wj in ws) / k
    T_single = dot(p_s, w_held)

    # --- single（blind：随机押一族）的期望 ---
    blind_idx = rng.randrange(k)
    p_b, s_b = best_of(budget, lambda q, w=ws[blind_idx]: dot(q, w), rng, dim)
    A_blind = s_b
    E_blind = sum(dot(p_b, wj) for wj in ws) / k
    T_blind = dot(p_b, w_held)

    return {
        "rho": rho, "budget": budget, "seed": seed,
        "A_single": A_single, "A_swarm": A_swarm, "A_blind": A_blind,
        "E_single": E_single, "E_swarm": E_swarm, "E_blind": E_blind,
        "T_single": T_single, "T_swarm": T_swarm, "T_blind": T_blind,
        "tax_A": A_single - A_swarm,
        "gain_E": E_swarm - E_single,
        "gain_T": T_swarm - T_single,
    }


def summarize(rows):
    """按 rho/budget 聚合均值。"""
    from collections import defaultdict
    g = defaultdict(list)
    for r in rows:
        g[(r["rho"], r["budget"])].append(r)
    out = []
    for (rho, budget), rs in sorted(g.items()):
        n = len(rs)
        m = {k: sum(r[k] for r in rs) / n for k in
             ("A_single", "A_swarm", "A_blind", "E_single", "E_swarm",
              "E_blind", "T_single", "T_swarm", "T_blind", "tax_A", "gain_E", "gain_T")}
        # 逐 seed 符号一致性：swarm 胜的 seed 比例
        m["swarm_wins_E"] = sum(1 for r in rs if r["E_swarm"] > r["E_single"]) / n
        m["swarm_wins_T"] = sum(1 for r in rs if r["T_swarm"] > r["T_single"]) / n
        m["single_wins_A"] = sum(1 for r in rs if r["A_single"] > r["A_swarm"]) / n
        m["rho"] = rho
        m["budget"] = budget
        m["n_seeds"] = n
        out.append(m)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--families", type=int, default=8)
    ap.add_argument("--dim", type=int, default=3)
    ap.add_argument("--budget", type=int, default=32)
    ap.add_argument("--budgets", type=str, default="", help="逗号分隔，覆盖 --budget")
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--rhos", type=str, default="0,0.25,0.5,0.75,1.0")
    ap.add_argument("--out", type=str, default=str(OUT / "collision.json"))
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    rhos = [float(x) for x in args.rhos.split(",") if x]
    budgets = [int(x) for x in args.budgets.split(",") if x] or [args.budget]

    if args.self_test:
        rows = []
        for rho in (0.0, 1.0):
            for seed in range(args.seeds):
                rows.append(run_one(args.families, args.dim, rho, args.budget, seed))
        agg = {r["rho"]: r for r in summarize(rows)}
        ok = True
        a_loss, e_gain = agg[1.0]["tax_A"], agg[0.0]["gain_E"]
        print(f"[st1] rho=1.0 tax_A = {a_loss:+.4f} (要求 >0，纯预算集中应让单体赢 A)")
        ok &= a_loss > 0
        print(f"[st2] rho=0.0 gain_E = {e_gain:+.4f} (要求 >0，多样性在生态端点应有用)")
        ok &= e_gain > 0
        bad = [r for r in rows if not all(-1.0001 <= r[k] <= 1.0001 for k in
                                          ("A_single", "A_swarm", "E_single", "E_swarm",
                                           "T_single", "T_swarm"))]
        print(f"[st3] 越界分数 {len(bad)} 条（要求 0）")
        ok &= not bad
        # 方向对比：rho=0 的 E 增益应大于 rho=1 的 E 增益
        print(f"[st4] rho=0 gain_E {agg[0.0]['gain_E']:+.4f} > rho=1 "
              f"{agg[1.0]['gain_E']:+.4f} ? "
              f"{agg[0.0]['gain_E'] > agg[1.0]['gain_E']}")
        ok &= agg[0.0]["gain_E"] > agg[1.0]["gain_E"]
        print("SELF-TEST", "PASS" if ok else "FAIL")
        raise SystemExit(0 if ok else 1)

    rows = []
    for budget in budgets:
        for rho in rhos:
            for seed in range(args.seeds):
                rows.append(run_one(args.families, args.dim, rho, budget, seed))
    agg = summarize(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps({"rows": rows, "agg": agg}, ensure_ascii=False, indent=1),
                              encoding="utf-8")
    # CSV
    import csv
    csvp = Path(args.out).with_suffix(".csv")
    with csvp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(agg[0].keys()))
        w.writeheader()
        w.writerows(agg)
    print(f"wrote {args.out} ({len(rows)} rows) + {csvp}")
    hdr = ("rho  budget  n  A_single A_swarm A_blind  E_single E_swarm  "
           "T_single T_swarm  tax_A  gain_E  gain_T  singleW_A swarmW_E swarmW_T")
    print(hdr)
    for r in agg:
        print(f"{r['rho']:>4.2f} {r['budget']:>5d} {r['n_seeds']:>3d} "
              f"{r['A_single']:>8.3f} {r['A_swarm']:>7.3f} {r['A_blind']:>7.3f}  "
              f"{r['E_single']:>8.3f} {r['E_swarm']:>7.3f}  "
              f"{r['T_single']:>8.3f} {r['T_swarm']:>7.3f}  "
              f"{r['tax_A']:>+6.3f} {r['gain_E']:>+7.3f} {r['gain_T']:>+7.3f}  "
              f"{r['single_wins_A']:>8.2f} {r['swarm_wins_E']:>7.2f} {r['swarm_wins_T']:>7.2f}")


if __name__ == "__main__":
    main()
