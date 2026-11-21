#!/usr/bin/env python3
"""T2-deep 证据门：号-题验号 + 引文逐字存在性 + 摘要级/正文级分级。
用法:
  python3 evidence_gate.py --self-test   # 非空性反证：注入违规必须 exit!=0
  python3 evidence_gate.py               # 对 evidence/ 与 claims.json 实跑
判据:
  G1 号-题一致: abs-<id>.html 的 <title> 与 claims.json 期望标题一致（去空白比较）
  G2 引文存在: 每条 quote 必须在指定 source 文件文本中逐字命中（空白归一后）
  G3 分级合法: level=body 的 quote 不得只命中 abs 页；必须命中 PDF 提取文本或全文 HTML
退出码: 0=全过, 2=有违规, 3=self-test 未按预期变红
"""
import json, re, sys, html as htmlmod
from pathlib import Path

HERE = Path(__file__).parent
EV = HERE / "evidence"

def norm(s: str) -> str:
    s = htmlmod.unescape(s)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def load_text(name: str) -> str:
    p = EV / name
    if not p.exists():
        return ""
    return norm(p.read_text(errors="replace"))

def check(claims_path: Path):
    data = json.loads(claims_path.read_text())
    violations = []
    for c in data["checks"]:
        cid = c["id"]
        if c["kind"] == "title":
            txt = load_text(c["source"])
            if not txt:
                violations.append(f"{cid}: source missing {c['source']}"); continue
            if norm(c["expect_title"]) not in txt:
                violations.append(f"{cid}: title mismatch in {c['source']}")
        elif c["kind"] == "quote":
            src_txt = load_text(c["source"])
            q = norm(c["quote"])
            if not src_txt:
                violations.append(f"{cid}: source missing {c['source']}"); continue
            if q not in src_txt:
                violations.append(f"{cid}: quote NOT FOUND in {c['source']}: {q[:80]}...")
            if c.get("level") == "body":
                if c["source"].startswith("abs-"):
                    violations.append(f"{cid}: body-level claim sourced from abs page (forbidden)")
    return violations

def self_test():
    import tempfile, shutil
    ok = True
    base = json.loads((HERE / "claims.json").read_text())
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        # mutation 1: wrong title must go red
        m1 = json.loads(json.dumps(base))
        for c in m1["checks"]:
            if c["kind"] == "title":
                c["expect_title"] = "TOTALLY WRONG TITLE XYZ"; break
        p1 = td / "m1.json"; p1.write_text(json.dumps(m1))
        v1 = check(p1)
        print("self-test M1 (wrong title):", "RED as expected" if v1 else "FAILED-TO-GO-RED")
        ok &= bool(v1)
        # mutation 2: fabricated quote must go red
        m2 = json.loads(json.dumps(base))
        added = False
        for c in m2["checks"]:
            if c["kind"] == "quote":
                c["quote"] = "this sentence was never written by any author zzz"; added = True; break
        p2 = td / "m2.json"; p2.write_text(json.dumps(m2))
        v2 = check(p2)
        print("self-test M2 (fabricated quote):", "RED as expected" if v2 else "FAILED-TO-GO-RED")
        ok &= bool(v2)
        # mutation 3: body-level claim pointing at abs page must go red
        m3 = json.loads(json.dumps(base))
        for c in m3["checks"]:
            if c["kind"] == "quote":
                c["level"] = "body"; c["source"] = "abs-2603.19461.html"; break
        p3 = td / "m3.json"; p3.write_text(json.dumps(m3))
        v3 = check(p3)
        print("self-test M3 (abs-as-body):", "RED as expected" if v3 else "FAILED-TO-GO-RED")
        ok &= bool(v3)
    sys.exit(0 if ok else 3)

if __name__ == "__main__":
    if "--self-test" in sys.argv:
        self_test()
    v = check(HERE / "claims.json")
    if v:
        print("VIOLATIONS:")
        for x in v: print(" -", x)
        sys.exit(2)
    n = len(json.loads((HERE / "claims.json").read_text())["checks"])
    print(f"PASS: {n} checks (titles + quotes, level discipline enforced)")
    sys.exit(0)
