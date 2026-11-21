#!/usr/bin/env python3
"""T5 §7 遗留 5：CPU-ms → token 的显式外生计价仪器（亚分钟、零 GPU）。

模型（B 级解析换算，外生参数，非本机实测；真实 2611.13524 token 数未核）：
  c_cpu_ms   = 2.55 ms/次验证   （T5.md:78，A 级实测）
  kappa      = 3                 （T5.md:118，闸固定开销倍率）
  rate r     = ms/token          （外生汇率：1 token 折合多少 CPU-ms）
  t_eval     = token/次验证      （外生：LLM judge 单次耗 token；本机 heuristic judge 为 0）
  cpu 折算 token 数 = c_cpu_ms / r
  token 附加倍率 M(r,t) = 1 + t_eval*r/c_cpu_ms      -> t_eval=0 时恰为 1
  C2 右式(归一) RHS = 1 + kappa*M                    -> t_eval=0 时回到 CPU 口径 1+kappa=4
  净差 net = LHS - RHS；flipped = LHS > RHS
  C2 左式(归一) LHS = s*(Δ_sel(N')-Δ_sel(N))/(N'-N)；另报 paired 诚实 Δ 版本

旧尺不可能产生的形状差：CPU-ms 口径 C2 只有一个点（RHS=4）；本尺给出 RHS 对 r 的
单调上升曲线及其翻正阈值，此形状是 token 计价独有的，不冒充旧尺复现。

用法:
  python3 token_pricing.py --self-test   # 反证门（注入违规必须被抓住）
  python3 token_pricing.py               # 正式扫描并落 token_pricing.json
"""
from __future__ import annotations
import json, math, sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent          # analyses/tracks/rsi-after/
OUT = Path(__file__).resolve().parent
C_CPU_MS = 2.55
KAPPA = 3.0
N_LO, N_HI = 4, 16
DSEL_LO, DSEL_HI = 0.542, 0.549
S_LO = 0.825
CEIL = 0.5496
T5_RHO_BAR = 0.945
T5_NEFF_PUB = 1.05
T10_NEFF_PUB = 1.4207


# ------------------------------------------------------------------ pure core

def token_multiplier(rate_ms_per_token: float, t_eval_tokens: float,
                     c_cpu_ms: float = C_CPU_MS) -> float:
    """token 附加倍率；t_eval=0 -> 1；rate=0（token 无限贵）-> inf。"""
    if rate_ms_per_token < 0 or t_eval_tokens < 0:
        return math.nan
    if rate_ms_per_token == 0:
        return math.inf if t_eval_tokens > 0 else 1.0
    return 1.0 + t_eval_tokens * rate_ms_per_token / c_cpu_ms


def c2_terms(sel_lo: float, sel_hi: float, s: float,
             n_lo: int = N_LO, n_hi: int = N_HI) -> dict:
    lhs = s * (sel_hi - sel_lo) / (n_hi - n_lo)
    return {"lhs_norm": lhs, "delta_sel_lo": sel_lo, "delta_sel_hi": sel_hi,
            "delta_sel_gap": sel_hi - sel_lo, "s": s,
            "denom_n": n_hi - n_lo}


def token_priced_c2(lhs_norm: float, rate_ms_per_token: float,
                    t_eval_tokens: float, kappa: float = KAPPA,
                    c_cpu_ms: float = C_CPU_MS) -> dict:
    m = token_multiplier(rate_ms_per_token, t_eval_tokens, c_cpu_ms)
    rhs = 1.0 + kappa * m
    rhs_cpu = 1.0 + kappa
    net = lhs_norm - rhs
    repl = 1.0 + t_eval_tokens * rate_ms_per_token / c_cpu_ms   # 替代口径：κ 被 token 全替换
    return {"rate_ms_per_token": rate_ms_per_token,
            "token_per_ms": (1.0 / rate_ms_per_token) if rate_ms_per_token > 0 else math.inf,
            "t_eval_tokens": t_eval_tokens,
            "cpu_equiv_tokens": c_cpu_ms / rate_ms_per_token if rate_ms_per_token > 0 else 0.0,
            "multiplier": m,
            "rhs_norm": rhs,
            "rhs_cpu_norm": rhs_cpu,
            "rhs_over_cpu": rhs / rhs_cpu if math.isfinite(rhs) else math.inf,
            "rhs_ms": c_cpu_ms * rhs,
            "rhs_replacement_norm": repl,
            "net_norm": net,
            "benefit_cost_ratio": lhs_norm / rhs if rhs else math.inf,
            "flipped": bool(lhs_norm > rhs)}


def flip_rate_upper_bound(lhs_norm: float, t_eval_tokens: float,
                          kappa: float = KAPPA, c_cpu_ms: float = C_CPU_MS):
    """解 LHS > 1+κ(1+t·r/c)；返回使翻正成立的 r 上界（<0 => 物理域 r>0 无解）。"""
    if t_eval_tokens == 0:
        return {"feasible": False, "upper_bound": None,
                "reason": "t_eval=0 时 RHS 恒为 1+κ，与 rate 无关；LHS>1+κ 才翻正"}
    ub = c_cpu_ms * (lhs_norm - 1.0 - kappa) / (kappa * t_eval_tokens)
    return {"feasible": ub > 0, "upper_bound": ub,
            "reason": "r<ub 才翻正；ub<=0 表示正汇率域内翻正集为空"}


def kish_neff(n: int, rho_bar: float) -> float:
    return n / (1.0 + (n - 1) * rho_bar)


def crosswalk_neff(t5_rho: float, t5_n: int, t5_neff_pub: float,
                   t10_rho: float, t10_n: int, t10_neff_inv: float) -> dict:
    """T5 Kish N_eff 与 T10 曲线反解 n_eff 的点对表：只判方向，不判同量复现。"""
    kish = kish_neff(t5_n, t5_rho)
    mismatches = []
    if abs(kish - t5_neff_pub) > 0.01:
        mismatches.append("t5_kish_vs_pub")
    if abs(t10_rho - t5_rho) > 1e-9 or t10_n != t5_n:
        mismatches.append("rho_n_point_mismatch")
    gap = t10_neff_inv - kish
    ratio = t10_neff_inv / kish if kish else math.inf
    direction_consistent = (kish < 2.0 and t10_neff_inv < 2.0)
    return {"point": {"rho": t5_rho, "n": t5_n},
            "t5_kish_recomputed": round(kish, 6), "t5_published": t5_neff_pub,
            "t10_curve_inverse": t10_neff_inv, "t10_published": T10_NEFF_PUB,
            "gap_t10_minus_t5": round(gap, 6), "ratio_t10_over_t5": round(ratio, 6),
            "direction_consistent": bool(direction_consistent),
            "same_quantity": False,
            "verdict": ("DIRECTION_CONSISTENT_NOT_SAME_QUANTITY" if direction_consistent
                        else "DIRECTION_INCONSISTENT"),
            "mismatches": mismatches,
            "note": "T5 N_eff=Kish 公式 N/(1+(N-1)ρ̄)；T10 n_eff=δ(ρ=0,N) 曲线反解；"
                    "两者定义不同，仅塌缩端方向一致，不得当作同量复现。"}


# ------------------------------------------------------------------ disk inputs

def load_inputs() -> dict:
    t5 = (BASE / "T5-verifier-econ/T5.md").read_text(encoding="utf-8")
    assert "2.55 ms/次" in t5 and "κ=3" in t5 and "0.945" in t5
    assert "0.542" in t5 and "0.549" in t5 and "0.825" in t5   # C2 左式三常量逐字锚定
    def paired_mean(path, n):
        d = json.load(open(BASE / path, encoding="utf-8"))
        rows = [r for r in d["truthful"] if r["n_cand"] == n and r["cond"] == "paired"]
        if not rows:
            return None
        return {"n": n, "rows": len(rows),
                "delta": sum(r["mean_private_delta"] for r in rows)/len(rows),
                "rate_1k": sum(r["gain_per_1k_calls"] for r in rows)/len(rows),
                "verifier_calls": sum(r["verifier_calls"] for r in rows)/len(rows),
                "s": sum(r["mean_sel_intensity"] for r in rows)/len(rows)}
    pilot = {n: paired_mean("T5-verifier-econ/pilot.json", n) for n in (1,4,16)}
    sweep = {n: paired_mean("T5-verifier-econ/pilot-n-sweep.json", n)
             for n in (1,2,3,4,6,8,12,16)}
    t10 = json.load(open(BASE / "T10-independence/independence.json", encoding="utf-8"))
    row = [r for r in t10["summary"] if abs(r.get("rho",0)-T5_RHO_BAR)<1e-9]
    if not row:
        raise ValueError("T10 summary 缺 rho=0.945 行")
    return {"pilot": pilot, "sweep": sweep,
            "t10_neff_at_16": row[0]["n_eff_at_16"],
            "t10_delta_n16": row[0]["delta_n16"]}


# ------------------------------------------------------------------ self-test

def self_test() -> bool:
    ok = True
    def chk(name, cond, detail=""):
        nonlocal ok
        print(("PASS " if cond else "FAIL ") + name + (" | "+detail if detail else ""))
        ok = ok and bool(cond)

    lhs = c2_terms(DSEL_LO, DSEL_HI, S_LO)["lhs_norm"]

    # 1) t_eval=0 退化为 1（倍率=1、RHS/RHS_cpu=1）
    z = token_priced_c2(lhs, 100.0, 0.0)
    chk("selftest:t_eval0_multiplier_is_1", abs(z["multiplier"]-1.0)<1e-12)
    chk("selftest:t_eval0_rhs_ratio_is_1", abs(z["rhs_over_cpu"]-1.0)<1e-12,
        f"rhs={z['rhs_norm']:.6f} rhs_cpu={z['rhs_cpu_norm']:.6f}")

    # 2) 高 rate 必翻负（净差仍<0、flipped=False，且随 rate 单调不增）
    hi = token_priced_c2(lhs, 1e6, 1000.0)
    lo = token_priced_c2(lhs, 1e-2, 1000.0)
    chk("selftest:high_rate_stays_negative", (not hi["flipped"]) and hi["net_norm"]<0,
        f"net={hi['net_norm']:.6f}")
    chk("selftest:net_monotone_in_rate", hi["net_norm"] <= lo["net_norm"],
        f"net(1e6)={hi['net_norm']:.3f} <= net(1e-2)={lo['net_norm']:.3f}")

    # 3) 反证注入：把 LHS 造到 >4，翻正探测器必须变红（证明不是硬编码常数）
    inj = token_priced_c2(5.0, 100.0, 0.0)
    chk("selftest:flip_detector_can_go_red", inj["flipped"] and inj["net_norm"]>0,
        f"injected LHS=5 -> net={inj['net_norm']:.3f}")
    inj_ub = flip_rate_upper_bound(5.0, 1000.0)
    chk("selftest:flip_threshold_sensitive", inj_ub["feasible"] and inj_ub["upper_bound"]>0,
        f"ub={inj_ub['upper_bound']}")

    # 4) 真实 LHS 的翻正集为空
    ub = flip_rate_upper_bound(lhs, 1000.0)
    chk("selftest:real_flip_set_empty", (not ub["feasible"]) and ub["upper_bound"]<0,
        f"ub={ub['upper_bound']:.6g}")

    # 5) 替代口径 t_eval=0 -> RHS=1，仍不翻正
    chk("selftest:replacement_degenerate", abs(z["rhs_replacement_norm"]-1.0)<1e-12 and lhs<1.0,
        f"lhs={lhs:.8f}")

    # 6) Kish 复算 + 对表能红
    cw = crosswalk_neff(T5_RHO_BAR, 16, T5_NEFF_PUB, T5_RHO_BAR, 16, T10_NEFF_PUB)
    chk("selftest:kish_reproduce_t5", cw["mismatches"]==[] and abs(cw["t5_kish_recomputed"]-1.054366)<1e-6,
        f"kish={cw['t5_kish_recomputed']}")
    chk("selftest:crosswalk_direction", cw["direction_consistent"] and (not cw["same_quantity"]),
        cw["verdict"])
    red = crosswalk_neff(T5_RHO_BAR, 16, T5_NEFF_PUB, T5_RHO_BAR, 16, 5.0)
    chk("selftest:crosswalk_can_go_red", (not red["direction_consistent"]),
        "inject T10 n_eff=5.0 -> direction inconsistent")
    red2 = crosswalk_neff(0.0, 16, T5_NEFF_PUB, 0.0, 16, T10_NEFF_PUB)
    chk("selftest:kish_point_mismatch_red", "t5_kish_vs_pub" in red2["mismatches"],
        "inject rho=0 -> Kish=16 vs published 1.05")
    return ok


# ------------------------------------------------------------------ main run

def main() -> int:
    inp = load_inputs()
    lhs = c2_terms(DSEL_LO, DSEL_HI, S_LO)
    p4, p16 = inp["pilot"][4], inp["pilot"][16]
    lhs_honest = (p16["delta"] - p4["delta"]) / (N_HI - N_LO)
    rates = [1e-4, 1e-3, 1e-2, 0.1, 1.0, 10.0, 100.0, 1e3, 1e4]
    t_eval_grid = [0.0, 100.0, 1000.0, 10000.0]
    sweep = []
    for t in t_eval_grid:
        for r in rates:
            row = token_priced_c2(lhs["lhs_norm"], r, t)
            row["net_honest_norm"] = lhs_honest - row["rhs_norm"]
            row["flipped_honest"] = bool(lhs_honest > row["rhs_norm"])
            sweep.append(row)
    thresholds = {str(int(t)): flip_rate_upper_bound(lhs["lhs_norm"], t) for t in t_eval_grid}
    thresholds_honest = {str(int(t)): flip_rate_upper_bound(lhs_honest, t) for t in t_eval_grid}
    cw = crosswalk_neff(T5_RHO_BAR, 16, T5_NEFF_PUB, T5_RHO_BAR, 16,
                        inp["t10_neff_at_16"])
    required_gap = (1.0 + KAPPA) * (N_HI - N_LO) / S_LO   # t_eval=0 翻正所需 Δsel gap
    payload = {
        "instrument": "T5-deep token_pricing.py",
        "model_grade": "B (explicit exogenous analytic conversion; not measured)",
        "constants": {"c_cpu_ms": C_CPU_MS, "kappa": KAPPA, "N": [N_LO, N_HI],
                      "delta_sel": [DSEL_LO, DSEL_HI], "s_lo": S_LO, "ceiling": CEIL,
                      "source": "T5.md:78,83,118,121-126"},
        "exogenous": {"token_rate_unit": "ms/token", "t_eval_unit": "token/verifier-call",
                      "real_token_counts_2611_13524": "UNKNOWN",
                      "note": "本机 judge 为 heuristic（0 token）；t_eval 与 rate 均为情景参数，非实测"},
        "c2_terms": lhs,
        "honest_pilot_marginal": {"delta4": round(p4["delta"],6), "delta16": round(p16["delta"],6),
                                  "lhs_norm": round(lhs_honest,8),
                                  "source": "pilot.json truthful paired n=4/16"},
        "sweep": sweep,
        "flip_thresholds_sel": thresholds,
        "flip_thresholds_honest": thresholds_honest,
        "required_delta_sel_gap_for_flip_t0": round(required_gap,4),
        "required_gap_vs_ceiling": {"gap": round(required_gap,4), "ceiling": CEIL,
                                    "impossible": required_gap > CEIL},
        "neff_crosswalk": cw,
        "t10_anchor": {"rho": T5_RHO_BAR, "n": 16, "n_eff": inp["t10_neff_at_16"],
                       "delta_n16": inp["t10_delta_n16"]},
        "n_sweep_rate_peak": {"n": 1, "rate_per_1k": round(inp["sweep"][1]["rate_1k"],4)},
        "verdict": {
            "c2_flips_positive_at_any_positive_rate": False,
            "high_rate_net": round(token_priced_c2(lhs["lhs_norm"], 1e6, 1000.0)["net_norm"],6),
            "t0_net": round(token_priced_c2(lhs["lhs_norm"], 100.0, 0.0)["net_norm"],6),
            "neff_crosswalk": cw["verdict"]}}
    out = OUT / "token_pricing.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(payload["verdict"], indent=2, ensure_ascii=False))
    print("wrote token_pricing.json")
    return 0

if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(0 if self_test() else 1)
    sys.exit(main())
