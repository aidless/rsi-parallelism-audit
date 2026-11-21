#!/usr/bin/env python3
"""新旧两次估计对比：逐季判定 95% CI 是否重叠，并汇总 P2 量级/趋势。

数据全部来自落盘的 outputs/verifier_share.csv 与 outputs_p2x/verifier_share.csv。
用法: python3 compare_p2x.py
"""
import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(p):
    return {r["quarter"]: r for r in csv.DictReader(p.open(encoding="utf-8"))}


old = read(HERE / "outputs" / "verifier_share.csv")
new = read(HERE / "outputs_p2x" / "verifier_share.csv")

print(f"{'季度':8} {'旧 P2/万':>9} {'旧 CI(est)':>14} {'新 P2/万':>9} {'新 CI(est)':>14} {'新 n':>5} {'CI 重叠':>8}")
overlaps = []
for q in sorted(new):
    o, n = old[q], new[q]
    olo, ohi = int(o["p2_lo"]), int(o["p2_hi"])
    nlo, nhi = int(n["p2_lo"]), int(n["p2_hi"])
    ov = max(olo, nlo) <= min(ohi, nhi)
    overlaps.append(ov)
    print(f"{q:8} {float(o['p2_per_10k']):9.2f} [{olo:3},{ohi:4}]{'':4} "
          f"{float(n['p2_per_10k']):9.2f} [{nlo:3},{nhi:3}]{'':4} {n['sample_n']:>5} {'是' if ov else '否':>8}")

rates = [float(new[q]["p2_per_10k"]) for q in ("2025Q4", "2026Q1", "2026Q2")]
print()
print(f"四季新旧 CI 全部重叠: {'是' if all(overlaps) else '否'}")
print(f"有命中的三季 P2/万: {rates}；范围 {min(rates):.2f}–{max(rates):.2f}，中位 {sorted(rates)[1]:.2f}")
print("2026Q3 本样本未捕获 P2（0/600），CI 上界 =", new["2026Q3"]["p2_hi"], "篇（≈",
      round(10000 * int(new['2026Q3']['p2_hi']) / int(new['2026Q3']['total']), 2), "/万），不可写成真实零")
