#!/usr/bin/env python3
"""从正文纯文本抽取关键词上下文（亚分钟级，零依赖）。
用法: python3 extract_context.py FILE [PATTERN ...]
      python3 extract_context.py --self-test
self-test 必须能红：对合成文本验证命中/未命中两条路径。
"""
import re, sys
from pathlib import Path

def contexts(txt, pats, before=200, after=260, cap=5):
    out = []
    for pat in pats:
        for m in list(re.finditer(re.escape(pat), txt, re.I))[:cap]:
            s = max(0, m.start() - before)
            e = min(len(txt), m.end() + after)
            out.append(f"[{pat} @{m.start()}] ...{txt[s:e]}...")
    return out

def self_test():
    txt = "We use equal compute baselines and report 80 iterations. No matched compute was used."
    hit = contexts(txt, ["equal compute"], cap=2)
    miss = contexts(txt, ["quantum teleportation"], cap=2)
    ok = bool(hit) and not miss and "equal compute" in hit[0]
    print("self-test:", "PASS" if ok else "FAILED-TO-GO-RED")
    sys.exit(0 if ok else 3)

if __name__ == "__main__":
    if "--self-test" in sys.argv:
        self_test()
    f = sys.argv[1]
    pats = sys.argv[2:] or ["compute", "iteration", "baseline", "budget"]
    txt = Path(f).read_text(errors="replace")
    for c in contexts(txt, pats):
        print(c + "\n")
