#!/usr/bin/env python3
"""第九法：同符号不同语义审计——N_eff 在 T5(Kish) 与 T10(曲线反解) 的定义碰撞。

T5 定义：N_eff = N/(1+(N-1)*rho_bar)，rho_bar 是真实 rsi_agent.gates.paired_gate
  底物上实测的「候选 per-episode Δ 向量的平均两两 Pearson 相关」(T5.md:77,182)。
T10 定义：N_eff = Delta_0^{-1}(Delta(rho,N))，Delta_0 是 rho=0 的 best-of-N 增益曲线，
  rho 是人为自变量，底物是解析带噪 best-of-N (independence_surface.py:7-13,77)。

两者共用符号 N_eff，但定义、底物、rho 来源全不同。SUMMARY L35 / T10.md L24
声称「交叉验证吻合」。本审计问：同一 rho 数值下两者读数是否可比？

用法: python3 neff_semantics_audit.py --self-test && python3 neff_semantics_audit.py
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
N = 16  # 两轨共同比较的候选数


def kish_neff(rho: float, n: int = N) -> float:
    """T5 的 Kish 有效样本量公式：n/(1+(n-1)*rho)。"""
    return n / (1.0 + (n - 1) * rho)


def load_inverse_neff() -> dict[float, float]:
    """从 T10 independence.json 读 N=16 各 rho 的曲线反解 N_eff。"""
    d = json.loads((BASE / "independence.json").read_text(encoding="utf-8"))
    return {r["rho"]: float(r["n_eff"]) for r in d["rows"] if r["n"] == N}


def compute(inv: dict[float, float]) -> dict:
    """给定反解读数，逐 rho 对比 Kish 与反解，判是否发生符号语义碰撞。"""
    rows = []
    for rho in sorted(inv):
        k = kish_neff(rho)
        i = inv[rho]
        rows.append({
            "rho": rho,
            "kish_neff": round(k, 4),
            "inverse_neff": round(i, 4),
            "diff_inverse_minus_kish": round(i - k, 4),
            "ratio_inverse_over_kish": round(i / k, 3) if k else None,
        })
    diffs = [abs(r["diff_inverse_minus_kish"]) for r in rows]
    max_diff = max(diffs)

    def at(rho_target: float) -> dict:
        return min(rows, key=lambda r: abs(r["rho"] - rho_target))

    cross = at(0.945)   # 交叉验证声称成立的 rho 点
    mid = at(0.5)       # 中段，检验「吻合」是否只在高 rho 端点偶然成立

    # 判据：除塌缩端外若两定义差异 > 0.5，则是同符号不同量的语义碰撞
    collision = max_diff > 0.5
    return {
        "rows": rows,
        "max_abs_diff": round(max_diff, 4),
        "crossval_rho_0945": cross,
        "mid_rho_05": mid,
        "collision_only_at_collapse_end": abs(mid["diff_inverse_minus_kish"]) > abs(cross["diff_inverse_minus_kish"]),
        "verdict": "SYMBOL_SEMANTIC_COLLISION" if collision else "NO_COLLISION",
    }


def audit() -> dict:
    inv = load_inverse_neff()
    result = compute(inv)
    result["source"] = "T10-independence/independence.json (inverse) + T5.md:77 Kish formula"
    result["definitions"] = {
        "T5_kish": "N/(1+(N-1)*rho_bar), rho_bar 实测 Pearson 相关 (paired_gate 底物)",
        "T10_inverse": "Delta_0^{-1}(Delta(rho,N)), rho 人为自变量 (解析 best-of-N 底物)",
    }
    return result


def self_test() -> int:
    checks = 0
    # T1: Kish 边界正确（rho=0→N, rho=1→1, N=1→1）
    assert abs(kish_neff(0.0, 16) - 16.0) < 1e-9, "Kish rho=0 应=N"
    assert abs(kish_neff(1.0, 16) - 1.0) < 1e-9, "Kish rho=1 应=1"
    assert abs(kish_neff(0.5, 1) - 1.0) < 1e-9, "Kish N=1 应=1"
    checks += 1
    # T2: 反解 rho=0 触顶 N（七法 #1 已证）
    inv = load_inverse_neff()
    assert abs(inv[0.0] - 16.0) < 0.01, "反解 rho=0 应触顶 16"
    checks += 1
    # T3: 真实数据必须判红（碰撞）
    assert audit()["verdict"] == "SYMBOL_SEMANTIC_COLLISION", "真实数据应判 SYMBOL_SEMANTIC_COLLISION"
    checks += 1
    # T4: 注入两定义处处相等的假反解 → 必须判绿（证明门能绿，非装饰）
    fake_inv = {rho: kish_neff(rho) for rho in inv}
    assert compute(fake_inv)["verdict"] == "NO_COLLISION", "注入相等应判 NO_COLLISION"
    checks += 1
    # T5: 「吻合」只在高 rho 端点偶然成立——中段差异必须大于交叉验证点差异
    a = audit()
    assert a["collision_only_at_collapse_end"], "中段 rho=0.5 差异应大于 rho=0.945"
    checks += 1
    return checks


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        n = self_test()
        print(f"self-test {n}/{n} PASS")
    else:
        r = audit()
        print(f"VERDICT = {r['verdict']}")
        print(f"max_abs_diff = {r['max_abs_diff']}")
        print(f"{'rho':>6} {'Kish':>8} {'inverse':>8} {'diff':>8} {'ratio':>8}")
        for row in r["rows"]:
            print(f"{row['rho']:>6} {row['kish_neff']:>8} {row['inverse_neff']:>8} "
                  f"{row['diff_inverse_minus_kish']:>8} {str(row['ratio_inverse_over_kish']):>8}")
        c = r["crossval_rho_0945"]
        m = r["mid_rho_05"]
        print("crossval rho=0.945: Kish={} inverse={}".format(c["kish_neff"], c["inverse_neff"]))
        print("mid rho=0.5:        Kish={} inverse={}".format(m["kish_neff"], m["inverse_neff"]))
        print(f"collision_only_at_collapse_end = {r['collision_only_at_collapse_end']}")
        out = BASE / "neff_semantics_audit.json"
        out.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"written -> {out.name}")
