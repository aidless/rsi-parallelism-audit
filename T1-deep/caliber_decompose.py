#!/usr/bin/env python3
"""T1 §5.1 六因子口径闸：任一对齐失败即输出「不可分解·禁相减」。

只读 T1.md 的 §5.1；§5.2 之后的内容（含需 GPU 的重叠遗留）不进入判定。
退出码：0=六因子全对齐；1=口径闸红（不可分解·禁相减）；2=用法错；3=闸没执行（不等于通过）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

FACTORS = ("benchmark", "hardware", "code_version", "seed_count", "max_token", "implementation")
ALIGNED = "ALIGNED"
MISALIGNED = "MISALIGNED"
UNKNOWN = "UNKNOWN"
FAIL_VERDICT = "不可分解·禁相减"
PASS_VERDICT = "可对齐·仅允许跨系统描述差"
OUT_OF_SCOPE_MARKER = "6/1904"
DEFAULT_T1 = "analyses/tracks/rsi-after/T1-parallel-conv/T1.md"

NAME_MAP = {
    "代码版本": "code_version",
    "实现": "implementation",
    "硬件": "hardware",
    "seed 数": "seed_count",
    "max token": "max_token",
}


class ParseError(Exception):
    """闸没执行：输入结构不符合 §5.1 契约。"""


@dataclass(frozen=True)
class Factor:
    factor: str
    status: str
    evidence: str
    source_line: int


def _section_51(text: str) -> tuple[list[tuple[int, str]], str]:
    lines = text.splitlines()
    try:
        start = next(i for i, ln in enumerate(lines) if ln.strip().startswith("### 5.1"))
    except StopIteration as exc:
        raise ParseError("缺少 ### 5.1 标题") from exc
    try:
        end = next(i for i in range(start + 1, len(lines)) if lines[i].strip().startswith("### 5.2"))
    except StopIteration as exc:
        raise ParseError("缺少 ### 5.2 边界标题") from exc
    sec = [(start + i + 1, ln) for i, ln in enumerate(lines[start:end])]
    return sec, "\n".join(ln for _, ln in sec)


def _find(sec: list[tuple[int, str]], needle: str) -> tuple[int, str] | None:
    return next(((no, ln) for no, ln in sec if needle in ln), None)


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _first_number(cell: str) -> float | None:
    m = re.search(r"(\d+(?:\.\d+)?)", cell.replace(",", ""))
    return float(m.group(1)) if m else None


def parse_t1_text(text: str) -> dict:
    """从 §5.1 原文复算数字并抽取六因子状态；不做任何外部查数。"""
    sec, sec_text = _section_51(text)
    if OUT_OF_SCOPE_MARKER in sec_text:
        raise ParseError("§5.1 越界读到非本闸输入")

    acc = _find(sec, "精度（r=3）")
    tim = _find(sec, "时间（r=3）")
    tok = _find(sec, "生成 token（r=3）")
    con = _find(sec, "**分解结论**")
    if not (acc and tim and tok and con):
        raise ParseError("§5.1 缺少精度/时间/token/分解结论中的一行")

    a, b = _cells(acc[1])[1:3]
    ta, tb = _cells(tim[1])[1:3]
    ka, kb = _cells(tok[1])[1:3]
    a_pct, b_pct = _first_number(a), _first_number(b)
    t_a, t_b = _first_number(ta), _first_number(tb)
    k_a, k_b = _first_number(ka), _first_number(kb)
    if None in (a_pct, b_pct, t_a, t_b, k_a, k_b) or not t_a or not k_a:
        raise ParseError("§5.1 数字行无法复算")

    m = re.search(r"其余（([^）]+)）全不对齐", con[1])
    if not m:
        raise ParseError("分解结论缺少「其余（...）全不对齐」判据")
    misaligned = {NAME_MAP[x.strip()] for x in m.group(1).split("、") if x.strip() in NAME_MAP}
    if misaligned != {"code_version", "implementation", "hardware", "seed_count", "max_token"}:
        raise ParseError("§5.1 的六因子清单与契约不一致")

    test_row = _find(sec, "| 测试集 ")
    benchmark_ok = bool(test_row and "✅" in test_row[1]) or ("「测试集」一项对齐" in con[1])
    hw_row = _find(sec, "| 硬件 ")
    seed_row = _find(sec, "| 随机 seed ")
    token_row = _find(sec, "| 生成 token")

    def factor(name: str, status: str, hit: tuple[int, str] | None) -> Factor:
        if hit:
            return Factor(name, status, hit[1][:180], hit[0])
        return Factor(name, status, "由分解结论行判定；表中无独立行", con[0])

    factors = [
        factor("benchmark", ALIGNED if benchmark_ok else UNKNOWN, test_row),
        factor("hardware", MISALIGNED if "hardware" in misaligned else UNKNOWN, hw_row),
        factor("code_version", MISALIGNED if "code_version" in misaligned else UNKNOWN, None),
        factor("seed_count", MISALIGNED if "seed_count" in misaligned else UNKNOWN, seed_row),
        factor("max_token", MISALIGNED if "max_token" in misaligned else UNKNOWN, token_row),
        factor("implementation", MISALIGNED if "implementation" in misaligned else UNKNOWN, None),
    ]
    for f in factors:
        if f.status == UNKNOWN:
            raise ParseError("因子 " + f.factor + " 未落盘判定")

    numbers = {
        "accuracy_a_pct": a_pct,
        "accuracy_b_pct": b_pct,
        "descriptive_delta_pp": round(a_pct - b_pct, 1),
        "time_a_s": t_a,
        "time_b_s": t_b,
        "time_ratio_b_over_a": round(t_b / t_a, 2),
        "tokens_a": int(k_a),
        "tokens_b": int(k_b),
        "token_delta_pct": round((k_b - k_a) / k_a * 100, 1),
    }
    return {"numbers": numbers, "factors": factors, "section_51_sha256_12": hashlib.sha256(sec_text.encode("utf-8")).hexdigest()[:12]}


def decide(factors: list[Factor], rule: str = "all") -> dict:
    """生产 rule=all：六格全 ALIGNED 才绿；rule=any 仅用于自测反证。"""
    by = {f.factor: f.status for f in factors}
    if rule == "all":
        ok = all(by.get(k) == ALIGNED for k in FACTORS)
    elif rule == "any":
        ok = any(by.get(k) == ALIGNED for k in FACTORS)
    else:
        raise ValueError("rule must be all or any")
    blocked = [k for k in FACTORS if by.get(k) != ALIGNED]
    return {
        "verdict": PASS_VERDICT if ok else FAIL_VERDICT,
        "rc": 0 if ok else 1,
        "aligned_count": len(FACTORS) - len(blocked),
        "failed_count": len(blocked),
        "blocked_factors": blocked,
    }


def build_report(t1_path: Path) -> dict:
    text = t1_path.read_text(encoding="utf-8")
    parsed = parse_t1_text(text)
    decision = decide(parsed["factors"])
    n = parsed["numbers"]
    return {
        "schema": "t1-caliber-decompose/v1",
        "source": {"t1": str(t1_path), "section": "5.1", "sha256_12_full": hashlib.sha256(text.encode("utf-8")).hexdigest()[:12], "sha256_12_section": parsed["section_51_sha256_12"]},
        "read_only": True,
        "network_calls": 0,
        "ran_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "numbers": n,
        "factors": [{"factor": f.factor, "status": f.status, "evidence": f.evidence, "source_line": f.source_line} for f in parsed["factors"]],
        "decision": decision,
        "allowed_claim": "仅可作为跨系统描述差：两者相差 " + str(n["descriptive_delta_pp"]) + "pp；不可作同口径 A/B 比较或因子归因。",
        "verdict": decision["verdict"],
        "exit_code": decision["rc"],
    }


SYNTHETIC_T1 = """### 5.1 同一 benchmark 两套读数的混淆因子分解

| 因子 | RecursiveMAS 自家读数 | ConvRSI 复跑读数 | 是否同口径 | 可复算的分解 |
|---|---|---|---|---|
| 精度（r=3） | 77.8% [H2 Table 2] | 71.4% [H1 Table 2] | ❌ 不同 | 差 6.4pp |
| 时间（r=3） | 1360s [H2 Table 2] | 2658s [H1 Table 2] | ❌ 不同 | 差 1.95× |
| 生成 token（r=3） | 519 [H2 Table 2] | 556 [H1 Table 2] | ❌ 不同 | 差 7.1% |
| 硬件 | 未逐条报 | RTX 4090D，四 seed | ❌ | 硬件差无法排除 |
| 随机 seed | 5 runs | 4 seeds | ❌ | 方差口径不同 |
| 测试集 | 全量 | 全量 500 题 | ✅ 同 | 唯一对齐的因子 |

**分解结论**：两套读数在「测试集」一项对齐，其余（代码版本、实现、硬件、seed 数、max token）全不对齐。

### 5.2 其他遗留

本段含有不在闸输入内的 6/1904 标记，解析器不得读到。
"""


def _fixture(overrides: dict[str, str] | None = None, omit: tuple[str, ...] = ()) -> list[Factor]:
    overrides = overrides or {}
    return [Factor(k, overrides.get(k, ALIGNED), "fixture " + k, 0) for k in FACTORS if k not in omit]


def run_selftest() -> int:
    cases: list[tuple[str, object]] = []

    def t(name: str, fn: object) -> None:
        cases.append((name, fn))

    def t_parse() -> None:
        parsed = parse_t1_text(SYNTHETIC_T1)
        st = {f.factor: f.status for f in parsed["factors"]}
        assert st["benchmark"] == ALIGNED, st
        assert all(st[k] == MISALIGNED for k in FACTORS if k != "benchmark"), st
        assert all(OUT_OF_SCOPE_MARKER not in f.evidence for f in parsed["factors"])

    def t_all_green() -> None:
        d = decide(_fixture())
        assert d["verdict"] == PASS_VERDICT and d["rc"] == 0 and d["blocked_factors"] == [], d

    def t_inject_single_alignment_green() -> None:
        red = decide(_fixture({"hardware": MISALIGNED}))
        assert red["rc"] == 1 and red["blocked_factors"] == ["hardware"], red
        green = decide(_fixture())
        assert green["rc"] == 0 and green["blocked_factors"] == [], green

    def t_each_single_failure_blocks() -> None:
        for k in FACTORS:
            d = decide(_fixture({k: MISALIGNED}))
            assert d["rc"] == 1 and d["blocked_factors"] == [k], (k, d)

    def t_unknown_blocks() -> None:
        d = decide(_fixture({"max_token": UNKNOWN}))
        assert d["rc"] == 1 and d["blocked_factors"] == ["max_token"], d

    def t_criterion_mutation() -> None:
        f = _fixture({"implementation": MISALIGNED})
        assert decide(f, rule="all")["rc"] == 1
        assert decide(f, rule="any")["rc"] == 0

    def t_coverage_guard() -> None:
        f = _fixture({"seed_count": MISALIGNED}, omit=("seed_count",))
        d = decide(f)
        assert d["rc"] == 1 and d["blocked_factors"] == ["seed_count"], d

    def t_numbers() -> None:
        n = parse_t1_text(SYNTHETIC_T1)["numbers"]
        assert n["descriptive_delta_pp"] == 6.4, n
        assert n["time_ratio_b_over_a"] == 1.95, n
        assert n["token_delta_pct"] == 7.1, n

    t("§5.1 解析器抽出 1 对齐/5 失败且不越界", t_parse)
    t("六因子全对齐必须翻绿", t_all_green)
    t("注入单因子对齐必须变绿（反证）", t_inject_single_alignment_green)
    t("逐因子单点击穿都必须翻红", t_each_single_failure_blocks)
    t("UNKNOWN 不得充当对齐", t_unknown_blocks)
    t("判据变异 all→any 必须翻绿（反证）", t_criterion_mutation)
    t("漏枚举 seed_count 不得翻绿（覆盖闸）", t_coverage_guard)
    t("6.4pp/1.95×/7.1% 可从表内复算", t_numbers)

    results = []
    for name, fn in cases:
        try:
            fn()
            results.append({"name": name, "status": "PASS"})
        except Exception as exc:
            results.append({"name": name, "status": "FAIL", "detail": type(exc).__name__ + ": " + str(exc)})
    passed = sum(r["status"] == "PASS" for r in results)
    rc = 0 if passed == len(results) else 1
    print(json.dumps({"self_test": "caliber_decompose", "passed": passed, "total": len(results), "rc": rc, "cases": results}, ensure_ascii=False, indent=2))
    return rc


def main() -> int:
    ap = argparse.ArgumentParser(description="T1 §5.1 六因子口径闸")
    ap.add_argument("--t1", default=DEFAULT_T1, help="T1.md 相对路径")
    ap.add_argument("--self-test", action="store_true", help="只跑内存夹具，不读盘")
    args = ap.parse_args()
    if args.self_test:
        return run_selftest()

    p = Path(args.t1)
    if not p.exists():
        p = Path(__file__).parent.parent / "T1-parallel-conv" / "T1.md"
    try:
        report = build_report(p)
    except (OSError, ParseError) as exc:
        print(json.dumps({"verdict": "GATE_NOT_EXECUTED", "rc": 3, "detail": type(exc).__name__ + ": " + str(exc), "note": "闸没执行不等于通过"}, ensure_ascii=False, indent=2))
        return 3
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
