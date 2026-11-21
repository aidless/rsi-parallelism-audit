"""SPSE-deep — T12（路 2 最小证伪基准）的参数化深挖变体。

闭的是 T12.md 局限第一条：
  「DSL 原语是 toy（9 个），程序长度 <= 4；真值客观但任务难度远低于 SWE-bench/湿实验。
    『迁移红利』是否在真实程序合成/定理证明中成立未核。」

做法（唯一改动轴：任务难度）
---------------------------
1. 原语库 9 -> 16（前 9 个与 T12-spse/spse.py 逐字同序，新增 7 个纯函数原语）。
   --dim 9 时 PRIMS[:9] 与原版完全一致，RNG 消耗序列不变 -> 可与原版做逐值对照。
2. 真值程序长度 4 -> 6（--depth）。--depth 4 时与原版一致。
3. 候选程序长度上限 --max-len（默认 = depth）。--max-len 0 表示不设上限 =
   原版行为（原版搜索可无限增长）。这一轴是为「长度 <= L」这句局限做的物理约束。

不变的部分（保证对照干净）：rho 逐位置概率混合、prior 子空间构造（noise = round((1-rho)*3)）、
稠密逐元素评分、visible/sealed 切分、single/swarm 部署、A/E/T/B1/B2 定义、_spearman。

新增读数（都可从落盘 JSON 复算，不改 RNG）：
  E_identity  空程序（identity）在 train 族上的 visible 均分 = 任务地板
  solve_rate_*  端点 >= 0.95 的 run 比例 = 预算是否够用（地板/天花板效应诊断）
  len_max_*   实际提交程序的最大长度 = 长度上限是否真的生效

用法
----
  python3 spse_deep.py --self-test          # 自测（含「能红」电池）
  python3 spse_deep.py --prove-red          # 只跑注入违规电池，必须全部被抓
  python3 spse_deep.py --parity             # 与原版 spse.py 逐值对照（重构等价性）
  python3 spse_deep.py --collision --dim 16 --depth 6 --tag c2_d16_l6 \
      --families 8 --budgets 8,16,32,64 --rhos 0,0.25,0.5,0.75,0.9,0.945,1.0 --seeds 40
  python3 spse_deep.py --nesurf --dim 16 --depth 6 --tag n2_d16_l6 --seeds 300 \
      --rhos 0,0.25,0.5,0.75,0.9,0.945,1.0 --budget 128
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import random
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"
ORIG_PATH = HERE.parent / "T12-spse" / "spse.py"

# ---------------------------------------------------------------- 原语库（16）

def _dedup(xs):
    seen, out = set(), []
    for x in xs:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


PRIMS = [
    # --- 前 9 个：与 T12-spse/spse.py 的 PRIMS 逐字同序（dim=9 时必须完全一致）
    ("sort", lambda xs: sorted(xs)),
    ("rev", lambda xs: list(reversed(xs))),
    ("neg", lambda xs: [-x for x in xs]),
    ("add3", lambda xs: [x + 3 for x in xs]),
    ("add7", lambda xs: [x + 7 for x in xs]),
    ("mulmod11", lambda xs: [(x * 7) % 11 for x in xs]),
    ("mulmod13", lambda xs: [(x * 7) % 13 for x in xs]),
    ("take3", lambda xs: xs[:3]),
    ("dedup", lambda xs: _dedup(xs)),
    # --- 新增 7 个（dim>9 才启用）：保持同一族「整数列表 -> 整数列表」纯函数
    ("abs", lambda xs: [abs(x) for x in xs]),
    ("add5", lambda xs: [x + 5 for x in xs]),
    ("mulmod17", lambda xs: [(x * 7) % 17 for x in xs]),
    ("mod3", lambda xs: [x % 3 for x in xs]),
    ("take2", lambda xs: xs[:2]),
    ("drop1", lambda xs: xs[1:]),
    ("sortdesc", lambda xs: sorted(xs, reverse=True)),
]

PRIM_INDEX = {name: i for i, (name, _) in enumerate(PRIMS)}

_ALL_ROWS = [
    [1, 2, 3], [3, 1, 2], [5, 5, 1], [9, 0, 4],
    [2, 7, 1, 8], [4, 4, 4], [8, 3, 6], [0, 9, 2],
    [6, 1], [7, 7, 7, 7], [2, 5, 8, 1], [9, 9],
    [3, 6, 2, 7], [1, 1, 2, 3], [8, 4], [5, 0, 5],
]


def active_prims(dim: int):
    if not (2 <= dim <= len(PRIMS)):
        raise ValueError(f"dim must be 2..{len(PRIMS)}, got {dim}")
    return PRIMS[:dim]


def compose(seq):
    """原语名字序列 -> 可调用。空序列 = identity。"""
    table = dict(PRIMS)

    def f(xs):
        for name in seq:
            xs = table[name](xs)
        return list(xs)
    return f


# ---------------------------------------------------------------- 任务/族

class Family:
    N_VISIBLE = 5

    def __init__(self, fid: int, seq, prior_subset, all_rows):
        self.fid = fid
        self.seq = list(seq)
        self.prior_subset = prior_subset
        self.true_fn = compose(seq)
        vis = [(row, self.true_fn(row)) for row in all_rows[: self.N_VISIBLE]]
        sealed = [(row, self.true_fn(row)) for row in all_rows[self.N_VISIBLE:]]
        self.samples = (vis, sealed)


def make_family_stream(rng, k_train, k_held, rho, dim=9, depth=4):
    """k_train 训练族 + k_held heldout 族。rho 逐位置概率混合（连续可控）。"""
    pool = active_prims(dim)
    shared = _rand_seq(rng, depth, pool)
    fams, held = [], []
    for i in range(k_train + k_held):
        seq = []
        for j in range(depth):
            if rng.random() < rho:
                seq.append(shared[j])
            else:
                seq.append(rng.choice(pool)[0])
        prior = _prior_subset(rng, seq, rho, pool)
        f = Family(i, seq, prior, _ALL_ROWS)
        (fams if i < k_train else held).append(f)
    return fams, held, shared


def _rand_seq(rng, length, pool):
    return [rng.choice(pool)[0] for _ in range(length)]


def _prior_subset(rng, seq, rho, pool):
    """策略搜索空间：真值原语 + round((1-rho)*3) 个干扰原语（取自当前 dim 的原语库）。"""
    pool_names = [p[0] for p in pool]
    keep = list(dict.fromkeys(seq))
    n_noise = max(0, round((1.0 - rho) * 3))
    noise = [x for x in rng.sample(pool_names, k=min(len(pool_names), n_noise)) if x not in keep]
    return keep + noise


# ---------------------------------------------------------------- 评分

def visible_score(policy_seq, family: Family, split="visible"):
    """逐元素匹配率（稠密梯度）。"""
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


def search_policy(rng, family: Family, budget: int, prior_bias: float, max_len=0):
    """锚点式局部搜索。max_len=0 表示不设上限（= 原版行为）；否则候选长度 <= max_len。"""
    pool = list(family.prior_subset)
    best_seq = []
    best_s = visible_score(best_seq, family)
    evals = 1
    cur, cur_s = best_seq, best_s
    while evals < budget:
        seq = list(cur)
        op = rng.random()
        at_cap = bool(max_len) and len(seq) >= max_len
        if (op < 0.5 or not seq) and not at_cap:
            seq.append(rng.choice(pool))
        elif op < 0.8 or (at_cap and op < 0.5):
            if seq:
                seq.pop(rng.randrange(len(seq)))
            else:
                seq.append(rng.choice(pool))
        else:
            if seq:
                seq[rng.randrange(len(seq))] = rng.choice(pool)
            else:
                seq.append(rng.choice(pool))
        s = visible_score(seq, family)
        evals += 1
        if s > cur_s or (s == cur_s and len(seq) <= len(cur)):
            cur, cur_s = seq, s
            if s > best_s:
                best_seq, best_s = seq, s
    return best_seq, best_s, evals


# ---------------------------------------------------------------- 部署

def deploy_single(rng, fams, held, budget, max_len=0):
    target = max(fams, key=lambda f: len(set(f.seq) & set(f.prior_subset)))
    seq, s, _ = search_policy(rng, target, budget, prior_bias=1.0, max_len=max_len)
    return [(seq, s, target)], target


def deploy_swarm(rng, fams, held, budget, k=None, max_len=0):
    k = k or len(fams)
    per = max(1, budget // k)
    picks = rng.sample(fams, k=min(k, len(fams)))
    out = []
    for f in picks:
        seq, s, _ = search_policy(rng, f, per, prior_bias=0.5, max_len=max_len)
        out.append((seq, s, f))
    return out, None


def evaluate(cands, fams, held, k):
    A = max(s for _, s, _ in cands)
    E = sum(max(visible_score(seq, fj) for seq, _, _ in cands) for fj in fams) / k
    T = max(sealed_score(seq, fh) for seq, _, _ in cands for fh in held) if held else 0.0
    if len(cands) >= 2 and held:
        tr, he = [], []
        for seq, _, _ in cands:
            tr.append(sum(visible_score(seq, fj) for fj in fams) / len(fams))
            he.append(sum(sealed_score(seq, fh) for fh in held) / len(held))
        rho_rank = _spearman(tr, he)
    else:
        rho_rank = None
    gaps = []
    for seq, _, _ in cands:
        gaps.append(sum(visible_score(seq, fj) - sealed_score(seq, fj) for fj in fams) / len(fams))
    ident = sum(visible_score([], fj) for fj in fams) / len(fams)
    return {
        "A_answer": A,
        "E_portfolio": E,
        "T_heldout": T,
        "B1_rank_rho": rho_rank,
        "B2_gap": sum(gaps) / len(gaps),
        "max_gap": max(gaps) if gaps else 0.0,
        "E_identity": ident,
        "len_max": max(len(seq) for seq, _, _ in cands),
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
        for kk in range(i, j + 1):
            r[order[kk]] = avg
        i = j + 1
    return r


# ---------------------------------------------------------------- 单次 run

def run_collision(k, budget, rho, seed, dim=9, depth=4, max_len=0):
    rng = random.Random(seed)
    fams, held, shared = make_family_stream(rng, k, k, rho, dim=dim, depth=depth)
    sc, tgt = deploy_single(rng, fams, held, budget, max_len=max_len)
    sw, _ = deploy_swarm(rng, fams, held, budget, max_len=max_len)
    es = evaluate(sc, fams, held, k)
    ew = evaluate(sw, fams, held, k)
    return {
        "rho": rho, "budget": budget, "seed": seed, "k": k,
        "dim": dim, "depth": depth, "max_len": max_len,
        "A_single": es["A_answer"], "A_swarm": ew["A_answer"],
        "E_single": es["E_portfolio"], "E_swarm": ew["E_portfolio"],
        "T_single": es["T_heldout"], "T_swarm": ew["T_heldout"],
        "B1_swarm": ew["B1_rank_rho"], "B1_single": es["B1_rank_rho"],
        "B2_gap_swarm": ew["B2_gap"], "B2_gap_single": es["B2_gap"],
        "max_gap_swarm": ew["max_gap"], "max_gap_single": es["max_gap"],
        "E_identity": es["E_identity"],
        "len_max_single": es["len_max"], "len_max_swarm": ew["len_max"],
        "tax_A": es["A_answer"] - ew["A_answer"],
        "gain_E": ew["E_portfolio"] - es["E_portfolio"],
        "gain_T": ew["T_heldout"] - es["T_heldout"],
    }


# ---------------------------------------------------------------- 可违反的不变量（自测/红电池共用）

def prims_collisions(prims, rows=None):
    """返回在 rows 上完全无法区分的原语对（同一输入 -> 同一输出）。"""
    rows = rows or _ALL_ROWS
    table = dict(prims)
    bad = []
    names = [p[0] for p in prims]
    for a in range(len(names)):
        for b in range(a + 1, len(names)):
            fa, fb = table[names[a]], table[names[b]]
            same = all(fa(r) == fb(r) for r in rows)
            if same:
                bad.append((names[a], names[b]))
    return bad


def depth_violations(cands, depth):
    return [len(seq) for seq, _, _ in cands if len(seq) > depth]


def rho1_seq_identical(fams):
    return len({tuple(f.seq) for f in fams}) == 1


def gap_nonempty_exists(rng, fam, trials=60, budget=10, thresh=0.05):
    for _ in range(trials):
        seq, sv, _ = search_policy(rng, fam, budget, 0.5)
        if sv - sealed_score(seq, fam) > thresh:
            return True
    return False


# ---------------------------------------------------------------- 自测

def self_test() -> int:
    fails = []

    def check(name, cond, detail=""):
        print(f"  [{'PASS' if cond else 'FAIL'}] {name} {detail}")
        if not cond:
            fails.append(name)

    # --- 正向：原版语义在 dim=9/depth=4 下复现（原 self-test 的 T1/T2/T3/T4/T5/T6 对应断言）
    rng = random.Random(12345)
    fams, held, _ = make_family_stream(rng, 8, 8, 0.0, dim=9, depth=4)
    es = evaluate(deploy_single(rng, fams, held, 32, 4)[0], fams, held, 8)
    sw = evaluate(deploy_swarm(rng, fams, held, 32, 4)[0], fams, held, 8)
    check("T1 rho=0 swarm E > single E",
          sw["E_portfolio"] > es["E_portfolio"],
          f"({sw['E_portfolio']:.3f} vs {es['E_portfolio']:.3f})")

    rng2 = random.Random(999)
    fams1, held1, _ = make_family_stream(rng2, 8, 8, 1.0, dim=9, depth=4)
    es1 = evaluate(deploy_single(rng2, fams1, held1, 32, 4)[0], fams1, held1, 8)
    sw1 = evaluate(deploy_swarm(rng2, fams1, held1, 32, 4)[0], fams1, held1, 8)
    check("T2 rho=1 swarm E 不显著优于 single",
          sw1["E_portfolio"] <= es1["E_portfolio"] + 0.05,
          f"({sw1['E_portfolio']:.3f} vs {es1['E_portfolio']:.3f})")

    rng3 = random.Random(777)
    fams3, held3, _ = make_family_stream(rng3, 4, 4, 0.0, dim=9, depth=4)
    check("T3 goodhart gap 可正（B2 判据非空）",
          gap_nonempty_exists(rng3, fams3[0]),
          "(searched 60 policies for gap>0.05)")

    rng4 = random.Random(555)
    fams4, held4, _ = make_family_stream(rng4, 8, 8, 1.0, dim=9, depth=4)
    b1 = evaluate(deploy_swarm(rng4, fams4, held4, 32, 4)[0], fams4, held4, 8)["B1_rank_rho"]
    check("T4 rho=1 B1 排名相关偏高(>=0.3) 或 None", b1 is None or b1 >= 0.3, f"(B1={b1})")

    f5 = fams3[0]
    check("T5 sealed 计分稳定（判分器冻结）",
          sealed_score([], f5) == sealed_score([], f5))

    check("T6 族真值多样（分布非单点）",
          len({tuple(f.seq) for f in fams3}) >= 2,
          f"({len({tuple(f.seq) for f in fams3})} distinct)")

    allvals = [es[k] for k in ("A_answer", "E_portfolio", "T_heldout")] + \
              [sw[k] for k in ("A_answer", "E_portfolio", "T_heldout")]
    check("T7 所有端点落在 [0,1]", all(0.0 <= v <= 1.0 for v in allvals),
          f"(min={min(allvals):.3f}, max={max(allvals):.3f})")

    # --- 新轴：dim=16 / depth=6
    prims16 = active_prims(16)
    check("T8 dim=16 原语两两可区分（无同函数重名）",
          prims_collisions(prims16) == [], f"(collisions={prims_collisions(prims16)})")
    check("T9 dim=16 启用后的原语数与名称表自洽",
          len(prims16) == 16 and len(dict(prims16)) == 16)

    rng6 = random.Random(2026)
    fams6, held6, _ = make_family_stream(rng6, 8, 8, 0.25, dim=16, depth=6)
    check("T10 depth=6 真值程序长度=6（长度上限真的生效）",
          all(len(f.seq) == 6 for f in fams6 + held6),
          f"(lens={sorted({len(f.seq) for f in fams6 + held6})})")
    sw6 = deploy_swarm(rng6, fams6, held6, 64, max_len=6)[0]
    check("T11 搜索候选长度 <= max_len",
          depth_violations(sw6, 6) == [], f"(viol={depth_violations(sw6, 6)})")

    # depth 轴确实改变了任务：dim 相同、depth 4 vs 6，同一 seed 的真值序列不同
    r_a = random.Random(4242)
    fa, _, _ = make_family_stream(r_a, 4, 4, 0.5, dim=16, depth=4)
    r_b = random.Random(4242)
    fb, _, _ = make_family_stream(r_b, 4, 4, 0.5, dim=16, depth=6)
    check("T12 depth 轴非空（同 seed 下 4/6 产生的真值不同）",
          [tuple(f.seq) for f in fa] != [tuple(f.seq) for f in fb])

    # 端点随难度真实变化：同一 (seed, rho, B) 下 dim16/l6 的 E_identity / 端点不应与 dim9/l4 完全相同
    p9 = run_collision(8, 32, 0.0, 11, dim=9, depth=4, max_len=4)
    p16 = run_collision(8, 32, 0.0, 11, dim=16, depth=6, max_len=6)
    check("T13 难度轴非空（dim/depth 改变读数）",
          p9["E_single"] != p16["E_single"] or p9["A_single"] != p16["A_single"],
          f"(E_s {p9['E_single']:.4f} vs {p16['E_single']:.4f})")

    # --- 「能红」电池：注入 4 类违规，每条必须被抓到
    red = red_battery()
    for name, det in red.items():
        check(f"RED {name}", det, "(违规已注入，断言被触发)")

    if fails:
        print(f"\nSELF-TEST FAILED: {len(fails)} -> {fails}")
        return 1
    print("\nSELF-TEST ALL PASS")
    return 0


def red_battery():
    """每条返回 True = 注入的违规被对应断言抓到（仪器能红）。"""
    out = {}
    # M1 重名原语（同函数不同名）：两两可区分断言必须失败
    dup = list(active_prims(16)) + [("sort_dup", lambda xs: sorted(xs))]
    out["M1 duplicate-primitive"] = prims_collisions(dup) != []

    # M2 长度越界候选：长度上限断言必须失败
    out["M2 depth-violation"] = depth_violations([(["sort"] * 7, 1.0, None)], 6) != []

    # M3 rho=1 语义被破坏（族不共享真值）：rho=1 同真值断言必须失败
    rng = random.Random(31337)
    broken, _, _ = make_family_stream(rng, 8, 8, 0.0, dim=16, depth=6)  # 本该 rho=1
    out["M3 rho1-broken"] = not rho1_seq_identical(broken)

    # M4 sealed 被污染成 visible（gap 恒 0）：gap 非空断言必须失败
    class _Poisoned:
        pass
    f = make_family_stream(random.Random(5), 2, 2, 0.0, dim=9, depth=4)[0][0]
    f.samples = (f.samples[0], list(f.samples[0]))  # sealed := visible
    out["M4 sealed-poisoned"] = not gap_nonempty_exists(random.Random(5), f, trials=20)
    return out


# ---------------------------------------------------------------- 与原版对照

def _load_orig():
    spec = importlib.util.spec_from_file_location("spse_orig", ORIG_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def cmd_parity() -> int:
    print(f"orig = {ORIG_PATH}")
    if not ORIG_PATH.exists():
        print("PARITY FAILED: original spse.py not found")
        return 1
    orig = _load_orig()
    fails = []

    def check(name, cond, detail=""):
        print(f"  [{'PASS' if cond else 'FAIL'}] {name} {detail}")
        if not cond:
            fails.append(name)

    # P1 任务生成逐值一致（dim=9, depth=4）
    for rho, seed in ((0.0, 0), (0.35, 3), (0.9, 7), (1.0, 11)):
        r = random.Random(seed)
        of, oh, osh = orig.make_family_stream(r, 8, 8, rho)
        r2 = random.Random(seed)
        df, dh, dsh = make_family_stream(r2, 8, 8, rho, dim=9, depth=4)
        check(f"P1 families seqs identical rho={rho} seed={seed}",
              [f.seq for f in of] == [f.seq for f in df]
              and [f.seq for f in oh] == [f.seq for f in dh]
              and osh == dsh)
        check(f"P1b prior subsets identical rho={rho} seed={seed}",
              [f.prior_subset for f in of] == [f.prior_subset for f in df])

    # P2 单 run 逐值一致（max_len=0 = 原版无长度上限；dim=9/depth=4）
    for rho, B, seed in ((0.0, 32, 0), (1.0, 8, 0), (0.5, 64, 7)):
        a = orig.run_collision(8, B, rho, seed)
        b = run_collision(8, B, rho, seed, dim=9, depth=4, max_len=0)
        keys = ("A_single", "A_swarm", "E_single", "E_swarm", "T_single", "T_swarm",
                "B2_gap_swarm", "gain_E", "gain_T", "tax_A")
        same = all(abs(a[k] - b[k]) < 1e-12 for k in keys)
        check(f"P2 run values identical rho={rho} B={B} seed={seed}", same,
              "" if same else f"(orig {a['E_single']:.6f} vs deep {b['E_single']:.6f})")

    # P3 候选长度上限在 B<=128 的实际搜索里从未触发（实测最大候选长度 3/4），
    # 因此 capped 与 uncapped 必须逐值相等——这是一个约束「没偷改机制」的断言，
    # 不是「长度轴非空」的断言。长度轴只在真值程序侧生效（见 T10/T12）。
    keys = ("A_single", "A_swarm", "E_single", "E_swarm", "T_single", "T_swarm", "gain_E")
    p3_same = True
    for rho, B, seed in ((0.0, 32, 5), (0.25, 64, 5), (0.5, 128, 11), (1.0, 64, 3)):
        a = orig.run_collision(8, B, rho, seed)
        b = run_collision(8, B, rho, seed, dim=9, depth=4, max_len=4)
        p3_same &= all(abs(a[k] - b[k]) < 1e-12 for k in keys)
    check("P3 候选长度上限在 B<=128 惰性（capped==uncapped）", p3_same,
          "(4 cells checked)")

    if fails:
        print(f"\nPARITY FAILED: {len(fails)} -> {fails}")
        return 1
    print("\nPARITY ALL PASS")
    return 0


# ---------------------------------------------------------------- 主跑

def cmd_collision(args):
    rows = []
    for rho in args.rhos:
        for budget in args.budgets:
            for seed in range(args.seeds):
                rows.append(run_collision(args.families, budget, rho, seed,
                                          dim=args.dim, depth=args.depth,
                                          max_len=args.max_len or args.depth))
    tag = args.tag or f"d{args.dim}_l{args.depth}"
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"collision_{tag}.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    _summ(rows, f"collision_{tag}", tag)


def _summ(rows, tag, tag_short=""):
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
                       "B1_swarm", "B2_gap_swarm", "max_gap_swarm", "E_identity",
                       "len_max_single", "len_max_swarm")}
        m["rho"], m["budget"], m["n"] = rho, budget, n
        m["swarm_wins_E"] = sum(1 for r in rs if r["E_swarm"] > r["E_single"]) / n
        m["swarm_wins_T"] = sum(1 for r in rs if r["T_swarm"] > r["T_single"]) / n
        m["single_wins_A"] = sum(1 for r in rs if r["A_single"] > r["A_swarm"]) / n
        m["solve_rate_single"] = sum(1 for r in rs if r["A_single"] >= 0.95) / n
        m["solve_rate_swarm"] = sum(1 for r in rs if r["A_swarm"] >= 0.95) / n
        m["b1_none_rate"] = sum(1 for r in rs if r["B1_swarm"] is None) / n
        out.append(m)
    print(f"\n=== {tag}: {len(rows)} runs -> {len(out)} cells ===")
    print("rho    B    | A_s    A_w    E_s    E_w    T_s    T_w    | gainE  gainT  taxA | B1_w  gap_w  idE   sr_s sr_w")
    for m in out:
        b1 = f"{m['B1_swarm']:5.2f}" if m["B1_swarm"] is not None else "  -  "
        print(f"{m['rho']:<5} {m['budget']:<4} | {m['A_single']:.3f}  {m['A_swarm']:.3f}  "
              f"{m['E_single']:.3f}  {m['E_swarm']:.3f}  {m['T_single']:.3f}  {m['T_swarm']:.3f} | "
              f"{m['gain_E']:+.3f}  {m['gain_T']:+.3f}  {m['tax_A']:+.3f} | {b1}  {m['B2_gap_swarm']:.3f} "
              f"{m['E_identity']:.3f}  {m['solve_rate_single']:.2f} {m['solve_rate_swarm']:.2f}")
    (OUT / f"{tag}_summary.json").write_text(json.dumps(out, indent=2), encoding="utf-8")


def cmd_nesurf(args):
    rows = []
    for rho in args.rhos:
        for seed in range(args.seeds):
            rows.append(run_collision(16, args.budget, rho, seed,
                                      dim=args.dim, depth=args.depth,
                                      max_len=args.max_len or args.depth))
    tag = args.tag or f"n_d{args.dim}_l{args.depth}"
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"nesurf_{tag}.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    from collections import defaultdict
    g = defaultdict(list)
    for r in rows:
        g[r["rho"]].append(r)
    base = sum(r["gain_E"] for r in g.get(0.0, [])) / max(1, len(g.get(0.0, [])))
    print(f"\n=== {tag}: N_eff proxy (base gain_E @rho=0 = {base:.4f}, B={args.budget}) ===")
    print("rho     gain_E   E_single  proxy   solve_s")
    for rho in sorted(g):
        rs = g[rho]
        mg = sum(r["gain_E"] for r in rs) / len(rs)
        me = sum(r["E_single"] for r in rs) / len(rs)
        ms = sum(1 for r in rs if r["A_single"] >= 0.95) / len(rs)
        neff = (mg / base * 16) if base > 0 else float("nan")
        print(f"{rho:<7} {mg:+.4f}  {me:.4f}   {neff:6.2f}  {ms:.2f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--prove-red", action="store_true")
    ap.add_argument("--parity", action="store_true")
    ap.add_argument("--collision", action="store_true")
    ap.add_argument("--nesurf", action="store_true")
    ap.add_argument("--dim", type=int, default=16)
    ap.add_argument("--depth", type=int, default=6)
    ap.add_argument("--max-len", dest="max_len", type=int, default=0,
                    help="候选程序长度上限；0 = 与上限同 depth（--depth 传 0 时表示无上限）")
    ap.add_argument("--families", type=int, default=8)
    ap.add_argument("--seeds", type=int, default=40)
    ap.add_argument("--budgets", type=str, default="8,16,32,64")
    ap.add_argument("--budget", type=int, default=128)
    ap.add_argument("--rhos", type=str, default="0,0.25,0.5,0.75,0.9,0.945,1.0")
    ap.add_argument("--tag", type=str, default="")
    args = ap.parse_args()
    args.budgets = [int(x) for x in args.budgets.split(",")]
    args.rhos = [float(x) for x in args.rhos.split(",")]

    if args.self_test:
        sys.exit(self_test())
    if args.prove_red:
        red = red_battery()
        ok = all(red.values())
        for k, v in red.items():
            print(f"  [{'CAUGHT' if v else 'MISSED'}] {k}")
        print("\nRED BATTERY " + ("ALL CAUGHT" if ok else "HAS MISSES"))
        sys.exit(0 if ok else 1)
    if args.parity:
        sys.exit(cmd_parity())
    if args.collision:
        cmd_collision(args)
    if args.nesurf:
        cmd_nesurf(args)
    if not (args.self_test or args.prove_red or args.parity or args.collision or args.nesurf):
        ap.print_help()


if __name__ == "__main__":
    main()
