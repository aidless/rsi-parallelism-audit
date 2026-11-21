"""T3 遗留 1 推进：把 T7 的协调税从「评估次数」口径转成 token 计价模型。

背景：T3 遗留 1 =「SwarmWorld 未报两边 token 消耗」，这是外部数据缺口，本脚本不造数。
它做的是纯推导：用 T7 已实测的 collision.json（A/E/T 端点 vs 预算 B），叠加一个
显式的 token 价格模型，算出「token 计价下协调税被放大多少、答案端点交叉点右移多少」。

token 模型（参数外生，非实验测量）：
  单次候选评估 = t_eval tokens（默认 1 单位，作分母）
  每个 agent 的固定上下文开销 = t_fixed tokens（系统 prompt + 历史）
  单体 token = t_fixed + B_single · t_eval
  群体 token = k · t_fixed + B_swarm · t_eval        （k 个 agent 各付一次固定开销）
  → 群体比单体多付 (k−1)·t_fixed 的固定税，这部分在「评估次数」口径里看不见。

判定问题：给定同一 token 预算 T，答案端点 A 上单体 vs 群体谁赢？
  B_single = (T − t_fixed)/t_eval                      全押一族
  B_swarm  = (T − k·t_fixed)/t_eval                    k 族均分
  token 协调税倍数 = T_swarm(B) / T_single(B) = [k·t_fixed + B] / [t_fixed + B]
  t_fixed=0 时退化为 1（即 T7 评估次数口径）；t_fixed↑ 时 →k（8×）。

读数来自 T7 outputs/collision.json 的 agg（40 seeds，k=8）。
用法：python3 token_cost_model.py
输出：outputs/token_cost.json + 屏幕表
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
COLLISION = HERE.parent / "T7-collision" / "outputs" / "collision.json"
OUT = HERE / "outputs"
OUT.mkdir(exist_ok=True)

K = 8  # T7 主跑的族数


def load_agg() -> dict:
    d = json.loads(COLLISION.read_text())
    out = {}
    for r in d["agg"]:
        out[(r["rho"], r["budget"])] = r
    return out


def interp_a(agg: dict, rho: float, budget: float, key: str = "A_single") -> float:
    """在 T7 已测的 budget 网格上线性插值 A 端点；网格外钳到端点。"""
    pts = sorted((b, agg[(rho, b)][key]) for (r, b) in agg if r == rho)
    if budget <= pts[0][0]:
        return pts[0][1]
    if budget >= pts[-1][0]:
        return pts[-1][1]
    for (b0, v0), (b1, v1) in zip(pts, pts[1:]):
        if b0 <= budget <= b1:
            t = (budget - b0) / (b1 - b0)
            return v0 + t * (v1 - v0)
    raise RuntimeError("interp failed")


def main() -> None:
    agg = load_agg()
    budgets = sorted({b for (_, b) in agg})
    rhos = sorted({r for (r, _) in agg})
    t_eval = 1.0
    t_fixed_grid = [0.0, 2.0, 5.0, 20.0, 50.0]  # 以 t_eval 为单位

    print("=== 表 1：token 协调税倍数 = T_swarm(B)/T_single(B)，k=8 ===")
    print(f"{'t_fixed':>8s} " + "  ".join(f"B={b}" for b in [8, 32, 128]))
    tax_rows = {}
    for tf in t_fixed_grid:
        vals = {}
        for b in [8, 32, 128]:
            mult = (K * tf + b) / (tf + b) if b > 0 else float("inf")
            vals[b] = round(mult, 3)
        tax_rows[str(tf)] = vals
        print(f"{tf:8.1f} " + "  ".join(f"{vals[b]:6.3f}" for b in [8, 32, 128]))

    print("\n=== 表 2：同一 token 预算 T 下，答案端点 A 的胜者（swarm vs single）===")
    print("（B 由 token 预算反解；t_fixed>0 时群体有效评估预算缩水更快）")
    result = {}
    for rho in rhos:
        row = {}
        for tf in t_fixed_grid:
            wins = []
            # T 网格覆盖 T7 的答案端点交叉区（B=8..64），才能看到 t_fixed 把交叉点左移
            for T in [8, 16, 32, 64]:  # token 预算；t_eval=1 时 ≈ T7 的 B 网格
                b_single = (T - tf) / t_eval
                b_swarm = (T - K * tf) / t_eval
                # 跳过群体连一族都评估不起的预算（钳位伪影）
                if b_swarm < 1 or b_single < 1:
                    wins.append("-")
                    continue
                a_single = interp_a(agg, rho, b_single, "A_single")
                a_swarm = interp_a(agg, rho, b_swarm, "A_swarm")
                wins.append("S" if a_single > a_swarm else "W")
            row[str(tf)] = "".join(wins)  # 4 字符：T=8/16/32/64 的胜者
        result[str(rho)] = row
        print(f"rho={rho:<5} " + " ".join(f"tf={tf}:{row[str(tf)]}" for tf in t_fixed_grid))

    print("\n=== 表 3：生态端点 E 的净 token 效率（群体 E 增益 / token 溢价）===")
    print("（B_swarm=128 vs B_single=32，这是 T7 里群体 A 追平单体的预算对）")
    eff = {}
    for rho in rhos:
        r128 = agg[(rho, 128)]
        gain_e = r128["E_swarm"] - agg[(rho, 32)]["E_single"]
        for tf in t_fixed_grid:
            t_swarm = K * tf + 128
            t_single = tf + 32
            premium = t_swarm / t_single
            net = gain_e / premium if premium > 0 else 0.0
            eff.setdefault(str(rho), {})[str(tf)] = round(net, 4)
        print(f"rho={rho:<5} gain_E={gain_e:+.3f}  " +
              " ".join(f"tf={tf}:net={eff[str(rho)][str(tf)]:.3f}" for tf in t_fixed_grid))

    payload = {
        "source": str(COLLISION.relative_to(HERE.parent)),
        "k": K, "t_eval": t_eval, "t_fixed_grid": t_fixed_grid,
        "table1_token_tax_multiplier": tax_rows,
        "table2_answer_winner_by_token_budget": result,
        "table3_eco_net_efficiency": eff,
        "note": "token 模型参数外生，非实验测量；只做 T7 评估次数口径→token 口径的解析换算。SwarmWorld 真实 token 数仍缺。",
    }
    (OUT / "token_cost.json").write_text(json.dumps(payload, indent=1, ensure_ascii=False))
    print(f"\nwrote {OUT / 'token_cost.json'}")


if __name__ == "__main__":
    main()