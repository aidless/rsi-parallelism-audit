#!/usr/bin/env python3
"""T11-deep evidence verifier: id/title/quote consistency against saved arXiv abs snapshots.
Usage: python3 verify_deep.py [--selftest]
Exit 0 = all checks pass (or selftest demonstrated both red and green); nonzero = failure.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))

def norm(s):
    return re.sub(r"\s+", " ", s or "").strip()

def load():
    claims = json.load(open(os.path.join(HERE, "claims_raw.json"), encoding="utf-8"))
    quotes = json.load(open(os.path.join(HERE, "quotes.json"), encoding="utf-8"))
    return claims, quotes

def check(claims, quotes):
    errs = []
    if len(claims) < 5:
        errs.append("too few verified claims: %d" % len(claims))
    ids = [c["id"] for c in claims]
    if len(ids) != len(set(ids)):
        errs.append("duplicate arXiv ids")
    for c in claims:
        cid = c["id"]
        if not re.fullmatch(r"\d{4}\.\d{4,5}", cid):
            errs.append("bad id format: " + cid)
        title = norm(c["title"])
        if not title.startswith("[" + cid + "]"):
            errs.append("id-title mismatch: " + cid + " -> " + title[:80])
        snap = os.path.join(HERE, c["snapshot"])
        if not os.path.isfile(snap):
            errs.append("missing snapshot: " + c["snapshot"])
            continue
        raw = open(snap, encoding="utf-8", errors="replace").read()
        if "[" + cid + "]" not in raw:
            errs.append("id absent in saved snapshot: " + cid)
        abstract = norm(c["abstract"])
        if len(abstract) < 100:
            errs.append("empty abstract: " + cid)
        qs = quotes.get(cid, [])
        if not qs:
            errs.append("no quotes registered: " + cid)
        for q in qs:
            if not norm(q):
                errs.append("empty quote: " + cid)
            elif norm(q) not in abstract:
                errs.append("quote absent from abstract: " + cid + " :: " + q[:70])
    return errs

def selftest():
    claims, quotes = json.loads(json.dumps(load()[0])), json.loads(json.dumps(load()[1]))
    bad_q = json.loads(json.dumps(quotes))
    cid = claims[0]["id"]
    bad_q[cid] = ["THIS SENTENCE DOES NOT EXIST IN ANY ABSTRACT"]
    err_q = check(claims, bad_q)
    bad_c = json.loads(json.dumps(claims))
    bad_c[1]["title"] = "[9999.99999] Deliberately wrong title"
    err_t = check(bad_c, quotes)
    clean = check(claims, quotes)
    ok = bool(err_q) and bool(err_t) and not clean
    print("selftest: injected_bad_quote_red=%s injected_bad_title_red=%s clean_green=%s" %
          (bool(err_q), bool(err_t), not clean))
    print("SELFTEST_OK" if ok else "SELFTEST_FAIL")
    return 0 if ok else 1

def main():
    if "--selftest" in sys.argv:
        return selftest()
    claims, quotes = load()
    errs = check(claims, quotes)
    if errs:
        for e in errs:
            print("FAIL:", e)
        return 1
    report = {
        "claims": len(claims),
        "id_title_verified": len(claims),
        "quotes_checked": sum(len(quotes.get(c["id"], [])) for c in claims),
        "all_quotes_in_abstract": True,
        "ids": [c["id"] for c in claims],
        "result": "PASS",
    }
    json.dump(report, open(os.path.join(HERE, "verify_report.json"), "w"), indent=2)
    print(json.dumps(report, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    sys.exit(main())
