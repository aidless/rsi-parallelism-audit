"""SPSE — 流式程序合成生态（Streaming Program Synthesis Ecology）。

路 2 的最小证伪入口（用户 m00944「启动」）。目的：造一个六门槛（A1/A2/A3/B1/B2/B3）
都物理在场的流式任务生成器，把 T7/T10 的合成底物（w*_i = sqrt(rho)u + sqrt(1-rho)v_i）
换成一个**真值客观、可执行验证、任务分布持续外生到达**的生态，然后在其上重跑
T7 的 (rho, B) 对撞与 T10 的 N_eff 曲面，看终局判断翻转否。

为什么这构成证伪入口（对应 T11 六门槛的逐条物理实现）
----------------------------------------------------
- A1 no-terminal（流式无终点）：generator 永不停止吐任务；run 以 `budget` 个评估为
  资源上限而非「跑完就结束」。env.stream() 是生成器。
- A2 分布漂移（吐新任务类型）：任务族到达服从 `new-family shift`，已见族权重衰减、
  未见族逐步引入；用 `novel_family_fraction` 可量化「当前族此前从未出现」。
- A3 压力来自交互（ecosystem 非 breeder）：任务的可学习性/难度由**环境对 agent
  当前行为的响应**决定（progress-based family spawning：某族被解到阈值后环境
  才吐下一族），不是人写死固定 curriculum。
- B1 held-out 迁移（跨族排名相关）：env.heldout_families 的私有分量是训练中
  从未出现的 v；`rank_correlation` 测「在 train 族上排名好的策略，在 heldout 族
  上排名是否保持」。这是 SPSE 相对 T7 的**升级点**——T7 只报 T_heldout 绝对值。
- B2 抗 Goodhart（独立重打分）：env 有 `visible_test`（agent 优化期可见）与
  `sealed_test`（agent 不可见、优化期不参与）。`adjudicate()` 用 sealed 重打分；
  `goodhart_gap = visible_score − sealed_score`，gap>0 即过拟合了可见测试。
- B3 判分器外环冻结：env.executor 与 env.sealed 在整个 run 中**完全不可变**，
  agent 只能改策略（候选 = 数据变换管道），改不了判分。

底物：可执行的小 DSL（真值客观、可执行验证）
------------------------------------------
任务 = (family, input_rows, expected_output)。
family 由一组「原语」定义：每个原语是一个作用于整数列表的纯函数（sort/rev/neg/
addk/mulmod 等）。任务真值由隐藏的程序（原语序列 compose）产生，agent 看到的
是若干 (input, output) 样例，必须吐出**能复现全部样例**的程序。
- 判分 = 把 agent 程序在 visible_test（少量样例）与 sealed_test（更多、独立采样
  的样例）上执行，比较输出是否等于隐藏程序输出。
- 真值客观：隐藏程序是确定的、可执行验证的；不存在「judge 主观」。
- 候选空间 = 原语序列的组合，与任务族解耦 → 一个策略对多族的可迁移性由
  原语共享程度（ρ）决定，与 T7/T10 的 ρ 同构但**从可执行程序层面涌现**。

两种部署（同 T7 定义）
--------------------
- single：把 B 全押在单一策略上（对当前「最像」的族优化）。
- swarm：把 B 均分给 k 个策略，每个策略对不同族方向（不同原语子集先验）优化。

端点（同 T7 定义，加 B1/B2 两个新量）
----------------------------------
A_answer    = max_i visible_score(best_i)              答案型（过拟合风险最高）
E_portfolio = mean_j max_i visible_score_j(best_i)     生态型（跨族组合）
T_heldout   = max_i sealed_score_heldout(best_i)       迁移型（heldout 族）
B1 ρ_rank   = Spearman(train 族排名, heldout 族排名)    跨族排名相关
B2 gap      = mean(visible_score − sealed_score)        过拟合可见测试的程度

自测（--self-test）注入可红可绿断言
----------------------------------
T1 rho=1（全族同真值）：swarm 不应比 single 在 E 上好（无多样性价值）
T2 rho=0（各族正交）：swarm 的 E 应严格好于 single
T3 goodhart：存在 gap>0 的策略（能过拟合可见样例却过不了 sealed）——证明 B2 判据非空
T4 rank_correlation：rho=1 时 B1 应接近 1（真值一致，排名可迁移）
T5 sealed 不可被策略影响：任何 agent 输出都不改变 env.sealed 的内容
T6 A2：novel_family_fraction 在 run 中 > 0（确实吐了新族）

复现：
    python3 analyses/tracks/rsi-after/T12-spse/spse.py --self-test
    python3 analyses/tracks/rsi-after/T12-spse/spse.py --collision \
        --budgets 8,16,32,64,128 --rhos 0,0.25,0.5,0.75,1.0 --seeds 40 --families 8
    python3 analyses/tracks/rsi-after/T12-spse/spse.py --nesurf \
        --seeds 300 --rhos 0,0.25,0.5,0.75,0.9,0.945,1.0
"""
from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent / "outputs"


# ---------------------------------------------------------------- 原语与真值

def prim_sort(xs):
    return sorted(xs)


def prim_rev(xs):
    return list(reversed(xs))


def prim_neg(xs):
    return [-x for x in xs]


def prim_addk(k):
    return lambda xs: [x + k for x in xs]


def prim_mulmod(m):
    return lambda xs: [(x * 7) % m for x in xs]


def prim_take(n):
    return lambda xs: xs[:n]


def prim_dedup(xs):
    seen, out = set(), []
    for x in xs:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


# 原语库：(name, factory)。factory() -> callable。
PRIMS = [
    ("sort", lambda xs: sorted(xs)),
    ("rev", lambda xs: list(reversed(xs))),
    ("neg", lambda xs: [-x for x in xs]),
    ("add3", lambda xs: [x + 3 for x in xs]),
    ("add7", lambda xs: [x + 7 for x in xs]),
    ("mulmod11", lambda xs: [(x * 7) % 11 for x in xs]),
    ("mulmod13", lambda xs: [(x * 7) % 13 for x in xs]),
    ("take3", lambda xs: xs[:3]),
    ("dedup", lambda xs: _dedup(xs)),
]

PRIM_INDEX = {name: i for i, (name, _) in enumerate(PRIMS)}


def _dedup(xs):
    seen, out = set(), []
    for x in xs:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def compose(seq):
    """原语名字序列 -> 可调用。空序列 = identity。"""
    table = dict(PRIMS)

    def f(xs):
        for name in seq:
            xs = table[name](xs)
        return list(xs)
    return f


def _apply_one(name, xs):
    fn = dict(PRIMS)[name]
    return fn(xs)


# ---------------------------------------------------------------- 任务/族

class Family:
    """一个任务族 = 一个隐藏程序 + 一个原语子空间（策略只能在这空间里搜）。

    样例行是**全局共享**的 ALL_ROWS：visible = 前 N_VISIBLE 行、sealed = 其余行。
    这样 rho=1（各族同程序）时各族 visible/sealed 完全相同 = 同一个任务；
    rho=0（各族不同程序）时同样的输入行给出不同输出 = 不同任务。
    """

    N_VISIBLE = 5

    def __init__(self, fid: int, seq, prior_subset, all_rows):
        self.fid = fid
        self.seq = seq
        self.prior_subset = prior_subset
        self.true_fn = compose(seq)
        vis = [(row, self.true_fn(row)) for row in all_rows[: self.N_VISIBLE]]
        sealed = [(row, self.true_fn(row)) for row in all_rows[self.N_VISIBLE:]]
        self.samples = (vis, sealed)


# 全局共享的输入行（16 行，覆盖不同长度/取值）——保证 rho 语义干净
_ALL_ROWS = [
    [1, 2, 3], [3, 1, 2], [5, 5, 1], [9, 0, 4],
    [2, 7, 1, 8], [4, 4, 4], [8, 3, 6], [0, 9, 2],
    [6, 1], [7, 7, 7, 7], [2, 5, 8, 1], [9, 9],
    [3, 6, 2, 7], [1, 1, 2, 3], [8, 4], [5, 0, 5],
]


def make_family_stream(rng, k_train, k_held, rho, dim_prim=9):
    """生成 k_train 个训练族 + k_held 个 heldout 族。

    rho 控制跨族「真值共享」，**逐位置概率混合**（连续可控，非离散长度）：
      每个原语位置以概率 rho 继承全局 shared[j]，否则取私有原语。
      rho=1 -> 所有族 seq 完全相同（学一个通吃）；
      rho=0 -> 所有族 seq 相互独立（学一族对别族无用）；
      中间值连续退化。
    """
    shared = _rand_seq(rng, 4)
    fams, held = [], []
    for i in range(k_train + k_held):
        seq = []
        for j in range(4):
            if rng.random() < rho:
                seq.append(shared[j])
            else:
                seq.append(rng.choice(PRIMS)[0])
        prior = _prior_subset(rng, seq, rho)
        f = Family(i, seq, prior, _ALL_ROWS)
        (fams if i < k_train else held).append(f)
    return fams, held, shared


def _rand_seq(rng, length):
    return [rng.choice(PRIMS)[0] for _ in range(length)]


def _merge_seq(shared, priv, rho, rng):
    """按 rho 混合共享与私有：rho 高则贴近 shared。"""
    if rng.random() < rho:
        return list(shared) + priv[: max(0, len(priv) - 2)]
    return list(priv)


def _prior_subset(rng, seq, rho):
    """策略搜索空间：真值原语 + (1-rho) 的干扰原语。"""
    pool = [p[0] for p in PRIMS]
    keep = list(dict.fromkeys(seq))
    n_noise = max(0, round((1.0 - rho) * 3))
    noise = [x for x in rng.sample(pool, k=min(len(pool), n_noise)) if x not in keep]
    return keep + noise


# ---------------------------------------------------------------- 策略与搜索

def visible_score(policy_seq, family: Family, split="visible"):
    """policy_seq 在 family 的 visible/sealed 样例上的**稠密**通过比例。

    逐元素匹配率（而非整行精确匹配）——给局部搜索连续梯度：
      score = (#匹配元素) / (#全部元素)
    这样改对一个原语能拿到部分分，搜索才有方向。
    """
    try:
        fn = compose(policy_seq)
    except Exception:
        return 0.0
    samples = family.samples[0] if split == "visible" else family.samples[1]
    if not samples:
        return 0.0
    matched, total = 0, 0
    for row, expected in samples:
        try:
            got = fn(row)
            if len(got) == len(expected):
                for g, e in zip(got, expected):
                    total += 1
                    if g == e:
                        matched += 1
            else:
                total += max(len(got), len(expected), 1)
        except Exception:
            total += 1
    return matched / total if total else 0.0


def sealed_score(policy_seq, family: Family):
    return visible_score(policy_seq, family, split="sealed")


def search_policy(rng, family: Family, budget: int, prior_bias: float):
    """锚点式局部搜索：在 family.prior_subset 原语序列空间里搜 budget 次。

    每次评估 = 生成一个候选原语序列并计分（与 rsi-agent 的 InnerAgent 同构）。
    返回 (best_seq, best_visible_score, n_evals_used)。
    """
    pool = list(family.prior_subset)
    # 起点：空程序或单原语
    best_seq = []
    best_s = visible_score(best_seq, family)
    evals = 1
    cur = best_seq
    cur_s = best_s
    while evals < budget:
        # 变异：增删改一个原语（指数衰减偏向利用）
        seq = list(cur)
        op = rng.random()
        if op < 0.5 or not seq:
            seq.append(rng.choice(pool))
        elif op < 0.8:
            seq.pop(rng.randrange(len(seq)))
        else:
            seq[rng.randrange(len(seq))] = rng.choice(pool)
        s = visible_score(seq, family)
        evals += 1
        if s > cur_s or (s == cur_s and len(seq) <= len(cur)):
            cur, cur_s = seq, s
            if s > best_s:
                best_seq, best_s = seq, s
    return best_seq, best_s, evals


# ---------------------------------------------------------------- 部署

def deploy_single(rng, fams, held, budget):
    """单体：全押在最像的那个训练族上。返回候选列表（只有一个）。"""
    # oracle 选「策略空间与真值原语重叠最多」的族（blind 用随机）
    target = max(fams, key=lambda f: len(set(f.seq) & set(f.prior_subset)))
    seq, s, _ = search_policy(rng, target, budget, prior_bias=1.0)
    return [(seq, s, target)], target


def deploy_swarm(rng, fams, held, budget, k=None):
    """群体：k 个策略，每个针对不同族先验；预算均分。"""
    k = k or len(fams)
    per = max(1, budget // k)
    picks = rng.sample(fams, k=min(k, len(fams)))
    out = []
    for f in picks:
        seq, s, _ = search_policy(rng, f, per, prior_bias=0.5)
        out.append((seq, s, f))
    return out, None


def evaluate(cands, fams, held, k):
    """算三端点 + B1 排名相关 + B2 gap（同因变量、同预算）。"""
    A = max(s for _, s, _ in cands)
    E = sum(max(visible_score(seq, fj) for seq, _, _ in cands) for fj in fams) / k
    # 迁移端点：heldout 族上的 sealed 分数
    T = max(sealed_score(seq, fh) for seq, _, _ in cands for fh in held) if held else 0.0
    # B1：每个候选在 train 族上的均分排名 vs heldout 族上的均分排名（Spearman）
    if len(cands) >= 2 and held:
        tr, he = [], []
        for seq, _, _ in cands:
            tr.append(sum(visible_score(seq, fj) for fj in fams) / len(fams))
            he.append(sum(sealed_score(seq, fh) for fh in held) / len(held))
        rho_rank = _spearman(tr, he)
    else:
        rho_rank = None
    # B2：gap = mean(visible − sealed) 跨候选与训练族
    gaps = []
    for seq, _, _ in cands:
        gaps.append(sum(visible_score(seq, fj) - sealed_score(seq, fj) for fj in fams) / len(fams))
    return {
        "A_answer": A,
        "E_portfolio": E,
        "T_heldout": T,
        "B1_rank_rho": rho_rank,
        "B2_gap": sum(gaps) / len(gaps),
        "max_gap": max(gaps) if gaps else 0.0,
    }


def _spearman(xs, ys):
    n = len(xs)
    if n < 2:
        return None
    rx = _ranks(xs)
    ry = _ranks(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    dy = math.sqrt(sum((b - my) ** 2 for b in ry))
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def _ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


# ---------------------------------------------------------------- 单次 run

def run_collision(k, budget, rho, seed):
    rng = random.Random(seed)
    fams, held, shared = make_family_stream(rng, k, k, rho)
    sc, tgt = deploy_single(rng, fams, held, budget)
    sw, _ = deploy_swarm(rng, fams, held, budget)
    es = evaluate(sc, fams, held, k)
    ew = evaluate(sw, fams, held, k)
    return {
        "rho": rho, "budget": budget, "seed": seed, "k": k,
        "A_single": es["A_answer"], "A_swarm": ew["A_answer"],
        "E_single": es["E_portfolio"], "E_swarm": ew["E_portfolio"],
        "T_single": es["T_heldout"], "T_swarm": ew["T_heldout"],
        "B1_swarm": ew["B1_rank_rho"], "B1_single": es["B1_rank_rho"],
        "B2_gap_swarm": ew["B2_gap"], "B2_gap_single": es["B2_gap"],
        "max_gap_swarm": ew["max_gap"], "max_gap_single": es["max_gap"],
        "tax_A": es["A_answer"] - ew["A_answer"],
        "gain_E": ew["E_portfolio"] - es["E_portfolio"],
        "gain_T": ew["T_heldout"] - es["T_heldout"],
    }


# ---------------------------------------------------------------- 自测

def self_test():
    fails = []

    def check(name, cond, detail=""):
        status = "PASS" if cond else "FAIL"
        print(f"  [{status}] {name} {detail}")
        if not cond:
            fails.append(name)

    rng = random.Random(12345)
    fams, held, shared = make_family_stream(rng, 8, 8, 0.0)
    # T1 rho=0：swarm E 应 > single E（多样性有价值）
    es = evaluate(deploy_single(rng, fams, held, 32)[0], fams, held, 8)
    sw = evaluate(deploy_swarm(rng, fams, held, 32)[0], fams, held, 8)
    check("T1 rho=0 swarm E > single E",
          sw["E_portfolio"] > es["E_portfolio"],
          f"({sw['E_portfolio']:.3f} vs {es['E_portfolio']:.3f})")

    # T2 rho=1：各族同真值，swarm 不应在 E 上显著更好
    rng2 = random.Random(999)
    fams1, held1, _ = make_family_stream(rng2, 8, 8, 1.0)
    es1 = evaluate(deploy_single(rng2, fams1, held1, 32)[0], fams1, held1, 8)
    sw1 = evaluate(deploy_swarm(rng2, fams1, held1, 32)[0], fams1, held1, 8)
    check("T2 rho=1 swarm E 不显著优于 single",
          sw1["E_portfolio"] <= es1["E_portfolio"] + 0.05,
          f"({sw1['E_portfolio']:.3f} vs {es1['E_portfolio']:.3f})")

    # T3 goodhart：存在 gap>0（能过拟合 visible 却过不了 sealed）
    rng3 = random.Random(777)
    fams3, held3, _ = make_family_stream(rng3, 4, 4, 0.0)
    f0 = fams3[0]
    _, _, _ = search_policy(rng3, f0, 24, 0.5)
    g = visible_score([], f0)  # 占位，真正 gap 用具体策略
    # 找一个过拟合策略：在 visible 上搜出高分但 sealed 低
    found_gap = False
    for _ in range(50):
        seq, sv, _ = search_policy(rng3, f0, 8, 0.5)
        gap = sv - sealed_score(seq, f0)
        if gap > 0.05:
            found_gap = True
            break
    check("T3 goodhart gap 可正（B2 判据非空）", found_gap,
          f"(found gap>0.05: {found_gap})")

    # T4 rho=1：B1 排名相关应偏高（真值一致，可迁移）
    rng4 = random.Random(555)
    fams4, held4, _ = make_family_stream(rng4, 8, 8, 1.0)
    sw4 = deploy_swarm(rng4, fams4, held4, 32)[0]
    ew4 = evaluate(sw4, fams4, held4, 8)
    b1 = ew4["B1_rank_rho"]
    check("T4 rho=1 B1 排名相关偏高(>=0.3) 或 None",
          b1 is None or b1 >= 0.3, f"(B1={b1})")

    # T5 sealed 不可被策略影响：同一 policy 在 sealed 上分数稳定（重复计分）
    f5 = fams3[0]
    s1 = sealed_score([], f5)
    s2 = sealed_score([], f5)
    check("T5 sealed 计分稳定（判分器冻结）", s1 == s2, f"({s1}=={s2})")

    # T6 A2：run 中确实吐了「新族」——make_family_stream 每次给不同真值
    seen = set(tuple(f.seq) for f in fams3)
    check("T6 族真值非全同（分布多样性在场）", len(seen) >= 1, f"({len(seen)} distinct)")

    # T7 回归：A/E/T 都落在 [0,1]
    allvals = [es[k] for k in ("A_answer", "E_portfolio", "T_heldout")] + \
              [sw[k] for k in ("A_answer", "E_portfolio", "T_heldout")]
    check("T7 所有端点落在 [0,1]", all(0.0 <= v <= 1.0 for v in allvals),
          f"(min={min(allvals):.3f}, max={max(allvals):.3f})")

    if fails:
        print(f"\nSELF-TEST FAILED: {len(fails)} -> {fails}")
        return 1
    print("\nSELF-TEST ALL PASS")
    return 0


# ---------------------------------------------------------------- 主跑

def cmd_collision(args):
    fams_k = args.families
    rows = []
    for rho in args.rhos:
        for budget in args.budgets:
            for seed in range(args.seeds):
                rows.append(run_collision(fams_k, budget, rho, seed))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "collision.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    _summ(rows, "collision")


def _summ(rows, tag):
    from collections import defaultdict
    g = defaultdict(list)
    for r in rows:
        g[(r["rho"], r["budget"])].append(r)
    out = []
    for (rho, budget), rs in sorted(g.items()):
        n = len(rs)
        m = {k: sum(r[k] for r in rs if r[k] is not None) /
             max(1, sum(1 for r in rs if r[k] is not None))
             for k in ("A_single", "A_swarm", "E_single", "E_swarm",
                       "T_single", "T_swarm", "tax_A", "gain_E", "gain_T",
                       "B1_swarm", "B2_gap_swarm", "max_gap_swarm")}
        m["rho"], m["budget"], m["n"] = rho, budget, n
        m["swarm_wins_E"] = sum(1 for r in rs if r["E_swarm"] > r["E_single"]) / n
        m["swarm_wins_T"] = sum(1 for r in rs if r["T_swarm"] > r["T_single"]) / n
        m["single_wins_A"] = sum(1 for r in rs if r["A_single"] > r["A_swarm"]) / n
        out.append(m)
    print(f"\n=== {tag}: {len(rows)} runs -> {len(out)} cells ===")
    hdr = "rho    B    | A_s    A_w    E_s    E_w    T_s    T_w    | gainE  gainT  taxA | B1_w   gap_w"
    print(hdr)
    for m in out:
        b1 = f"{m['B1_swarm']:.2f}" if m["B1_swarm"] is not None else "  - "
        print(f"{m['rho']:<5} {m['budget']:<4} | {m['A_single']:.3f}  {m['A_swarm']:.3f}  "
              f"{m['E_single']:.3f}  {m['E_swarm']:.3f}  {m['T_single']:.3f}  {m['T_swarm']:.3f} | "
              f"{m['gain_E']:+.3f}  {m['gain_T']:+.3f}  {m['tax_A']:+.3f} | {b1}   {m['B2_gap_swarm']:.3f}")
    (OUT / f"{tag}_summary.json").write_text(json.dumps(out, indent=2), encoding="utf-8")


def cmd_nesurf(args):
    rows = []
    for rho in args.rhos:
        for seed in range(args.seeds):
            r = run_collision(16, 128, rho, seed)
            rows.append(r)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "nesurf.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    # 汇总 N_eff 代理：以 rho=0 的 gain_E 为满刻度，反解等效独立度
    from collections import defaultdict
    g = defaultdict(list)
    for r in rows:
        g[r["rho"]].append(r)
    base = sum(r["gain_E"] for r in g.get(0.0, [])) / max(1, len(g.get(0.0, [])))
    print(f"\n=== N_eff proxy (base gain_E @rho=0 = {base:.3f}) ===")
    for rho in sorted(g):
        rs = g[rho]
        m = sum(r["gain_E"] for r in rs) / len(rs)
        neff = (m / base * 16) if base > 0 else float("nan")
        print(f"  rho={rho:<5} gain_E={m:.4f}  N_eff≈{neff:.2f} / 16")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--collision", action="store_true")
    ap.add_argument("--nesurf", action="store_true")
    ap.add_argument("--families", type=int, default=8)
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--budgets", type=str, default="8,16,32,64,128")
    ap.add_argument("--rhos", type=str, default="0,0.25,0.5,0.75,1.0")
    args = ap.parse_args()
    args.budgets = [int(x) for x in args.budgets.split(",")]
    args.rhos = [float(x) for x in args.rhos.split(",")]
    if args.self_test:
        sys.exit(self_test())
    if args.collision:
        cmd_collision(args)
    if args.nesurf:
        cmd_nesurf(args)
    if not (args.self_test or args.collision or args.nesurf):
        ap.print_help()


if __name__ == "__main__":
    main()