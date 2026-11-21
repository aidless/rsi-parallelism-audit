#!/usr/bin/env python3
"""T7-deep: k x rho budget-response sweep, coordination-tax multiple and verdict."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
COLLISION = HERE.parent / "T7-collision"
GEN = COLLISION / "collision_endpoints.py"
EXISTING = COLLISION / "outputs"
RAW = HERE / "raw"
KS = [2, 4, 8, 16, 32]
RHOS = [0.0, 0.5, 0.75, 1.0]
BUDGETS = [32, 64, 128, 256]
REF_B = 32


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def tag(k: int, rho: float) -> str:
    return f"k{k}_rho{rho:g}".replace(".", "p")


def run_generation(seeds: int):
    RAW.mkdir(parents=True, exist_ok=True)
    logs = []
    for rho in RHOS:
        for k in KS:
            out = RAW / f"{tag(k, rho)}.json"
            cmd = [
                sys.executable, str(GEN),
                "--families", str(k),
                "--budgets", ",".join(str(b) for b in BUDGETS),
                "--rhos", str(rho),
                "--seeds", str(seeds),
                "--out", str(out),
            ]
            cp = subprocess.run(cmd, capture_output=True, text=True)
            logs.append({
                "cmd": cmd,
                "returncode": cp.returncode,
                "stdout": cp.stdout.strip(),
                "stderr": cp.stderr.strip(),
            })
            if cp.returncode != 0:
                raise RuntimeError("generator failed: " + str(cmd) + chr(10) + cp.stderr)
    sep = chr(10) + chr(10)
    (HERE / "run.log").write_text(
        sep.join(
            ("$ " + " ".join(x["cmd"]) + chr(10) + "(exit " + str(x["returncode"]) + ")" + chr(10)
             + x["stdout"] + chr(10) + x["stderr"]).strip()
            for x in logs
        ),
        encoding="utf-8",
    )
    return logs


def rows_index(rows):
    return {(float(r["rho"]), int(r["budget"]), int(r["seed"])): r for r in rows}


def compare_rows(new_rows, old_rows):
    ni, oi = rows_index(new_rows), rows_index(old_rows)
    mism = []
    only_new = sorted(set(ni) - set(oi))
    only_old = sorted(set(oi) - set(ni))
    if only_new or only_old:
        mism.append({"type": "key_set", "only_new": only_new, "only_old": only_old})
    for kk in sorted(set(ni) & set(oi)):
        for field in sorted(set(oi[kk]) | set(ni[kk])):
            a, b = ni[kk].get(field), oi[kk].get(field)
            if a != b:
                mism.append({
                    "rho": kk[0], "budget": kk[1], "seed": kk[2],
                    "field": field, "new": a, "existing": b,
                })
    return mism


def cross_check_real():
    per_k = []
    for k in KS:
        oldp = EXISTING / f"k_sweep_{k}.json"
        old = load(oldp)
        oldrows = [
            r for r in old["rows"]
            if float(r["rho"]) in (0.0, 0.5) and int(r["budget"]) == REF_B
        ]
        new_files, newrows = [], []
        for rho in (0.0, 0.5):
            p = RAW / f"{tag(k, rho)}.json"
            new_files.append({"path": str(p), "sha256": sha256(p)})
            newrows.extend(
                r for r in load(p)["rows"] if int(r["budget"]) == REF_B
            )
        mism = compare_rows(newrows, oldrows)
        per_k.append({
            "k": k,
            "against": str(oldp),
            "against_sha256": sha256(oldp),
            "new_files": new_files,
            "new_rows": len(newrows),
            "existing_rows": len(oldrows),
            "mismatches": mism,
        })
    allm = [m for item in per_k for m in item["mismatches"]]
    return {
        "against": "T7-collision/outputs/k_sweep_{2,4,8,16,32}.json rows: budget=32, rho in {0,0.5}",
        "mismatches": allm,
        "per_k": per_k,
        "note": "same generator, same seeds; strict per-field float equality",
    }

def compute_multiple(ref: float, curve: dict, inject_bad: bool = False):
    """Minimum B reaching ref; inject_bad reverses comparison for red control."""
    for b, val in sorted(curve.items()):
        hit = (val <= ref) if inject_bad else (val >= ref - 1e-12)
        if hit:
            return b / REF_B
    return None


def shape_of(values):
    vals = [v for v in values if v is not None]
    if len(vals) < 2:
        return "insufficient"
    inc = sum(1 for a, b in zip(vals, vals[1:]) if b > a + 1e-9)
    dec = sum(1 for a, b in zip(vals, vals[1:]) if b < a - 1e-9)
    if inc == len(vals) - 1:
        return "increasing"
    if dec == len(vals) - 1:
        return "decreasing"
    if all(abs(v - vals[0]) <= 1e-9 for v in vals):
        return "flat"
    return "nonmonotone"


def aggregate_metrics():
    metrics, files = {}, {}
    for rho in RHOS:
        for k in KS:
            p = RAW / f"{tag(k, rho)}.json"
            data = load(p)
            by_b = {
                int(a["budget"]): a
                for a in data["agg"] if abs(float(a["rho"]) - rho) < 1e-12
            }
            base = by_b[REF_B]
            ref = base["A_single"]
            curve = {b: by_b[b]["A_swarm"] for b in BUDGETS}
            mult = compute_multiple(ref, curve)
            metrics[tag(k, rho)] = {
                "rho": rho, "k": k, "n_seeds": base["n_seeds"],
                "A_single_B32": ref,
                "A_swarm_B32": base["A_swarm"],
                "tax_A_B32": base["tax_A"],
                "gain_E_B32": base["gain_E"],
                "single_wins_A_B32": base["single_wins_A"],
                "swarm_wins_E_B32": base["swarm_wins_E"],
                "A_swarm_curve": {str(b): curve[b] for b in BUDGETS},
                "A_swarm_B128_minus_single_B32": by_b[128]["A_swarm"] - ref,
                "break_even_B": int(mult * REF_B) if mult is not None else None,
                "budget_multiple": mult,
            }
            files[str(p)] = {"sha256": sha256(p), "rows": len(data["rows"])}
    return metrics, files


def verdict(metrics):
    low_mult = [metrics[tag(8, r)]["budget_multiple"] for r in (0.0, 0.5)]
    high_mult = [
        metrics[tag(k, r)]["budget_multiple"] for r in (0.75, 1.0) for k in KS
    ]
    low4 = all(v == 4.0 for v in low_mult)
    high4 = any(v == 4.0 for v in high_mult)
    if high4:
        label = "NO: 4x holds at high rho too"
    elif low4:
        label = "YES: 4x only at low rho"
    else:
        label = "INCONCLUSIVE: low-rho k=8 did not reproduce 4x"
    return {
        "label": label,
        "low_k8_multiples": low_mult,
        "high_multiples": high_mult,
        "low4": low4,
        "high4": high4,
        "criterion": "high4 => NO; else low4 => YES; else INCONCLUSIVE",
    }

def selftest():
    ref, curve = 0.90, {32: 0.80, 64: 0.85, 128: 0.91, 256: 0.95}
    good = compute_multiple(ref, curve)
    assert good == 4.0, ("positive_fixture", good)
    assert 1.0 <= good <= 8.0, ("range_assert", good)
    red = compute_multiple(ref, curve, inject_bad=True)
    assert red != good, ("red_fixture_no_effect", red, good)

    rows_a = [{"rho": 0.0, "budget": 32, "seed": i, "v": float(i)} for i in range(3)]
    rows_b = [dict(r) for r in rows_a]
    assert compare_rows(rows_a, rows_b) == [], "cross_check_positive_failed"
    rows_b[1]["v"] = 9.9
    mm = compare_rows(rows_a, rows_b)
    assert any(m.get("field") == "v" for m in mm), ("cross_check_red_failed", mm)

    base = {tag(k, r): {"budget_multiple": None} for r in RHOS for k in KS}
    low = {key: dict(val) for key, val in base.items()}
    low[tag(8, 0.0)]["budget_multiple"] = 4.0
    low[tag(8, 0.5)]["budget_multiple"] = 4.0
    v_low = verdict(low)
    high = {key: dict(val) for key, val in low.items()}
    high[tag(8, 0.75)]["budget_multiple"] = 4.0
    v_high = verdict(high)
    assert v_low["label"] != v_high["label"], ("verdict_mutation_failed", v_low, v_high)
    print(
        "SELF-TEST PASS | multiple_good=4.0 multiple_red="
        + str(red) + " cross_check_red_hits=" + str(len(mm))
        + " verdict_low=" + v_low["label"] + " verdict_high=" + v_high["label"]
    )


def fmt(v, digits=4):
    return "None(>8x)" if v is None else f"{v:.{digits}f}"


def make_md(res):
    m = res["metrics"]
    lines = [
        "# T7-deep：k × ρ 的协调税倍数闭合",
        "",
        "结论：" + res["verdict"]["label"] + "。",
        "",
        "对表闸：" + str(len(res["cross_check_gate"]["mismatches"]))
        + " mismatches；逐 seed 重跑 ρ∈{0,0.5}、B=32 与 T7-collision/outputs/k_sweep_*.json 严格相等。",
        "",
        "| ρ | k | B/k@32 | A_single(32) | A_swarm(32) | tax_A(32) | 追平 B | 倍数 | A_swarm(128)−A_single(32) | gain_E(32) | 单体胜A(32) |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for rho in RHOS:
        for k in KS:
            r = m[tag(k, rho)]
            lines.append(
                "| " + f"{rho:g} | {k} | {REF_B // k} | {r['A_single_B32']:.4f} | "
                + f"{r['A_swarm_B32']:.4f} | {r['tax_A_B32']:+.4f} | "
                + str(r["break_even_B"] if r["break_even_B"] is not None else ">256")
                + " | " + fmt(r["budget_multiple"], 2) + " | "
                + f"{r['A_swarm_B128_minus_single_B32']:+.4f} | {r['gain_E_B32']:+.4f} | "
                + f"{r['single_wins_A_B32']:.3f} |"
            )
    lines += [
        "",
        "形状（按 k=2→32）：",
        "",
        "- tax_A(32)："
        + "；".join("ρ=" + f"{rho:g} " + res["shapes"]["tax_A"][f"rho_{rho:g}"] for rho in RHOS),
        "- 预算倍数："
        + "；".join(
            "ρ=" + f"{rho:g} " + res["shapes"]["budget_multiple"][f"rho_{rho:g}"]
            + " (None 数=" + str(res["shapes"]["unreached"][f"rho_{rho:g}"]) + ")"
            for rho in RHOS
        ),
        "",
        "判据与已有读数：倍数=最小追平 B/32；4×=追平 B=128。ρ=0/0.5 的 B=32 数值与 §5b 已有 JSON 逐字段相等（见 cross_check_gate），本表不覆盖旧数。",
        "",
        "复算：",
        "",
        "```bash",
        "python3 analyses/tracks/rsi-after/T7-deep/t7_deep.py --self-test",
        "python3 analyses/tracks/rsi-after/T7-deep/t7_deep.py --seeds 40",
        "python3 analyses/tracks/rsi-after/T7-deep/t7_deep.py --analyze-only",
        "```",
        "",
        "产物：t7_deep_results.json（全量指标、命令、SHA256）、raw/*.json（现役生成器原始 rows/agg）、run.log、selftest.log。",
        "",
    ]
    return "\n".join(lines)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=40)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--analyze-only", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        selftest()
        return

    logs = [] if args.analyze_only else run_generation(args.seeds)
    cc = cross_check_real()
    if cc["mismatches"]:
        (HERE / "cross_check_failed.json").write_text(
            json.dumps(cc, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        raise SystemExit("CROSS-CHECK FAILED: " + str(len(cc["mismatches"])) + " mismatches")
    metrics, files = aggregate_metrics()
    shapes = {"tax_A": {}, "budget_multiple": {}, "unreached": {}}
    for rho in RHOS:
        key = f"rho_{rho:g}"
        shapes["tax_A"][key] = shape_of([metrics[tag(k, rho)]["tax_A_B32"] for k in KS])
        shapes["budget_multiple"][key] = shape_of(
            [metrics[tag(k, rho)]["budget_multiple"] for k in KS]
        )
        shapes["unreached"][key] = sum(
            1 for k in KS if metrics[tag(k, rho)]["budget_multiple"] is None
        )
    res = {
        "schema_version": "t7-deep-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_generator": {"path": str(GEN), "sha256": sha256(GEN)},
        "design": {"path": str(HERE / "design.md"), "criterion": "see design.md"},
        "parameters": {
            "ks": KS, "rhos": RHOS, "budgets": BUDGETS,
            "seeds": args.seeds, "dim": 3, "ref_budget": REF_B,
        },
        "commands": logs,
        "raw_files": files,
        "cross_check_gate": cc,
        "metrics": metrics,
        "shapes": shapes,
        "verdict": verdict(metrics),
    }
    (HERE / "t7_deep_results.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (HERE / "T7-deep.md").write_text(make_md(res), encoding="utf-8")
    print("wrote t7_deep_results.json, T7-deep.md; " + res["verdict"]["label"])
    print("cross_check_mismatches =", len(cc["mismatches"]))


if __name__ == "__main__":
    main()