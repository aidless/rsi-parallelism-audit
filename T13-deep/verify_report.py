"""verify_report.py — T13-deep 报告的自检（格式 + 数字可复算）"""
import json

p = "T13-deep.md"
lines = open(p, encoding="utf-8").read().split("\n")
errs = []
for i, l in enumerate(lines):
    if l.startswith("|") and i > 0 and lines[i - 1].strip() and not lines[i - 1].startswith("|"):
        errs.append(("blank-before-table", i + 1, lines[i - 1][:40]))
fence = chr(96) * 3
fences = [i for i, l in enumerate(lines) if l.startswith(fence)]
if len(fences) % 2:
    errs.append(("unbalanced-fence", fences))

blocks, cur = [], []
for i, l in enumerate(lines):
    if l.startswith("|"):
        cur.append((i + 1, l))
    elif cur:
        blocks.append(cur)
        cur = []
if cur:
    blocks.append(cur)
for b in blocks:
    cnt = b[0][1].count("|")
    for ln, l in b:
        if l.count("|") != cnt:
            errs.append(("pipe-count", ln, l.count("|"), cnt))

d = json.load(open("deep.json", encoding="utf-8"))
checked = 0
for b in blocks:
    if "ρ̄" not in b[0][1]:
        continue
    for ln, l in b[1:]:
        if set(l.replace("|", "").replace(" ", "")) <= set("-:"):
            continue
        c = [x.strip() for x in l.strip("|").split("|")]
        m, n = c[0], int(c[1])
        cell = d["cells"][m][str(n)]
        num = lambda s: float(s.split("[")[0])
        vals = [num(c[2]), num(c[3]), num(c[4]), num(c[5]), num(c[6])]
        exp = [cell["rho_bar"], cell["rate_per_1k"], cell["promo_rate"],
               cell["cand_pass_rate"], cell["delta_priv"]]
        if max(abs(a - b) for a, b in zip(vals, exp)) > 0.00051:
            errs.append(("main-value", ln, vals, exp))
        checked += 1
print("format_errors", errs)
print("main_rows_checked", checked, "tables", len(blocks), "fences", len(fences))
print("verdict", d["verdict"], "cross_check_mismatches",
      len(d["cross_check"]["mismatches"]))
assert not errs and checked == 20
