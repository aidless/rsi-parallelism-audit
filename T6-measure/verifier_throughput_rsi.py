#!/usr/bin/env python3
"""吞吐-速率最小实验：验证器带宽（每代可判分的候选数）与改进速率的关系。

挂在本仓库 rsi-agent 上，不改其源码：用 MeteredTask 给所有公开集 evaluate 计数，
用 BatchInnerAgent 让每代生成 N 个候选并用公开分取最优（付费 N 次判分）。
密封集仍由 runner 在过公开闸后才触碰，evaluation_count 作为独立读数。

协议：3 条件 N=1/4/16 × 3 inner_seeds × 固定代数 G；读 rate = Δbest / 验证调用数。
负对照 --random-select：候选判分成本相同（每代对 width 个候选全部 evaluate、按构造恒等），但随机挑候选、不按分选优 → 若 rate 不塌，说明本协议测的不是"选择"。注意总 verifier_calls 随机侧更少（过闸少→密封确认少），故"成本相同"仅指候选判分、不含密封确认。

用法（工作区根目录）：
  python3 analyses/tracks/rsi-after/T6-measure/verifier_throughput_rsi.py --rsi-root rsi-agent --out analyses/tracks/rsi-after/T6-measure/outputs
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
from pathlib import Path


class MeteredTask:
    """包装 public task：每次判分计数 + 可选模拟耗时；其余属性委托原对象。"""

    def __init__(self, inner, counter: list[int], cost: float = 0.0):
        self.inner = inner
        self.counter = counter
        self.cost = cost

    def evaluate(self, policy):
        self.counter[0] += 1
        if self.cost:
            time.sleep(self.cost)
        return self.inner.evaluate(policy)

    def episodes(self):
        return self.inner.episodes()

    def __getattr__(self, name):
        return getattr(self.inner, name)


class BatchInnerAgent:
    """原 InnerAgent 的分布族：锚点 + 步长衰减高斯扰动；每代抽 N 个，按公开分选最好。"""

    def __init__(self, base, width: int, task, counter: list[int], random_select: bool = False):
        self.base = base            # 原 InnerAgent 实例
        self.width = width
        self.task = task
        self.counter = counter
        self.random_select = random_select

    def propose(self, history):
        original_seed = self.base.seed
        cands = []
        for i in range(self.width):
            self.base.seed = f"{original_seed}:{i}" if i else original_seed
            policy = self.base.propose(history)   # 只生成，不判分
            score = self.task.evaluate(policy).mean  # 判分（MeteredTask 计数）
            cands.append((score, i, policy))
        self.base.seed = original_seed
        if self.random_select:
            return random.Random(f"pick:{original_seed}:{len(history.entries)}").choice(cands)[2]
        return max(cands, key=lambda x: (x[0], -x[1]))[2]


def run_one(rsi_root: Path, width: int, inner_seed: int, generations: int,
            cost: float, random_select: bool, public_seed: int = 100,
            private_seed: int = 99991) -> dict:
    sys.path.insert(0, str(rsi_root))
    from rsi_agent.runner import RSIRunner  # noqa: PLC0415

    counter = [0]
    runner = RSIRunner(public_seed=public_seed, private_seed=private_seed,
                       generations=generations, inner_seed=inner_seed)
    metered = MeteredTask(runner.public_task, counter, cost)
    runner.public_task = metered
    runner.inner = BatchInnerAgent(runner.inner, width, metered, counter, random_select)
    t0 = time.perf_counter()
    result = runner.run()
    wall = time.perf_counter() - t0
    delta = result.best_public_mean - result.baseline_public_mean
    return {
        "N": width, "inner_seed": inner_seed, "generations": generations,
        "verifier_calls": counter[0], "sealed_evaluations": result.sealed_evaluations,
        "baseline_public_mean": round(result.baseline_public_mean, 6),
        "best_public_mean": round(result.best_public_mean, 6),
        "delta": round(delta, 6),
        "rate_per_1k_verifications": round(1000 * delta / counter[0], 6) if counter[0] else None,
        "promoted": sum(1 for g in result.generations if g.promoted),
        "verdict": result.verdict, "wall_s": round(wall, 4),
        "random_select": random_select,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rsi-root", default="rsi-agent", help="rsi-agent 仓库根目录")
    ap.add_argument("--out", default="analyses/tracks/rsi-after/T6-measure/outputs")
    ap.add_argument("--Ns", nargs="+", type=int, default=[1, 4, 16])
    ap.add_argument("--seeds", nargs="+", type=int, default=[7, 17, 27])
    ap.add_argument("--generations", type=int, default=16)
    ap.add_argument("--cost", type=float, default=0.0, help="每次判分的模拟耗时秒")
    ap.add_argument("--random-select", action="store_true", help="负对照：付判分费但不按分选优")
    args = ap.parse_args()

    rsi_root = Path(args.rsi_root).expanduser().resolve()
    if not (rsi_root / "rsi_agent" / "runner.py").exists():
        print(f"ERR rsi-agent not found at {rsi_root}", file=sys.stderr)
        return 2

    rows = []
    for n in args.Ns:
        for seed in args.seeds:
            r = run_one(rsi_root, n, seed, args.generations, args.cost, args.random_select)
            rows.append(r)
            print(f"N={n:2} seed={seed:3} calls={r['verifier_calls']:4} "
                  f"Δ={r['delta']:+.4f} rate/1k={r['rate_per_1k_verifications']:+.3f} "
                  f"promoted={r['promoted']} {r['verdict']}")

    summary = []
    for n in args.Ns:
        subset = [r for r in rows if r["N"] == n]
        rates = [r["rate_per_1k_verifications"] for r in subset]
        deltas = [r["delta"] for r in subset]
        summary.append({
            "N": n, "trials": len(subset),
            "mean_calls": round(statistics.mean(r["verifier_calls"] for r in subset), 1),
            "mean_delta": round(statistics.mean(deltas), 6),
            "mean_rate_per_1k": round(statistics.mean(rates), 6),
            "rate_range": [min(rates), max(rates)],
            "mean_promoted": round(statistics.mean(r["promoted"] for r in subset), 2),
        })

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    suffix = "-random" if args.random_select else ""
    (out / f"throughput{suffix}.json").write_text(
        json.dumps({"protocol": {"Ns": args.Ns, "seeds": args.seeds,
                                "generations": args.generations, "cost_s": args.cost,
                                "random_select": args.random_select},
                    "per_trial": rows, "summary": summary},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    print("SUMMARY")
    for s in summary:
        print(f"  N={s['N']:2} calls={s['mean_calls']:7.1f} Δ={s['mean_delta']:+.4f} "
              f"rate/1k={s['mean_rate_per_1k']:+.3f} promoted={s['mean_promoted']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
