#!/usr/bin/env python3
"""从 outputs_p2x/sample.jsonl 的 P2 命中里，按季确定性抽最多 10 条写 review_p2.jsonl。

抽样种子固定为 Random(f"p2x|{q}")，与抽样顺序绑定；不足 10 条则全取。
"""
import json
import random
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs_p2x"

pool = defaultdict(list)
for line in (OUT / "sample.jsonl").read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    r = json.loads(line)
    if r["tier"] == "P2":
        pool[r["quarter"]].append(r)

with (OUT / "review_p2.jsonl").open("w", encoding="utf-8") as f:
    total = 0
    for q in sorted(pool):
        recs = pool[q]
        rnd = random.Random(f"p2x|{q}")
        chosen = rnd.sample(recs, min(10, len(recs)))
        print(f"{q}: P2 hits={len(recs)} chosen={len(chosen)}")
        for r in chosen:
            f.write(json.dumps({
                "id": r["id"], "quarter": q, "tier_pred": "P2",
                "reason": r["reason"], "title": r["title"], "abstract": r["abstract"],
            }, ensure_ascii=False) + "\n")
            total += 1
    print("review_p2.jsonl rows:", total)
