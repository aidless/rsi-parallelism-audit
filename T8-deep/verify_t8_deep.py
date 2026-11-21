#!/usr/bin/env python3
"""Verifier for T8-deep report: tokens must exist in report and source evidence."""
import argparse
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FORMULA = r"I(LLM,q)=\frac{1}{m}\sum_{i=1}^{m}\frac{r_{\text{target}_{i}}|_{q}-1}{n}"
FILES = ["T8-deep.md", "fetch-0.txt", "fetch-3.txt", "fetch-html-1.txt"]

REPORT_TOKENS = [
    FORMULA,
    "**判定：A**",
    "published in 2024",
    "**Published**: 03 August 2025",
    "KDD '25: Proceedings of the 31st ACM SIGKDD Conference on Knowledge Discovery and Data Mining V.2",
    "https://ar5iv.labs.arxiv.org/html/2411.02429",
    "https://dl.acm.org/doi/10.1145/3711896.3737419",
    "https://arxiv.org/abs/2411.02429",
]

EVIDENCE_TOKENS = {
    "fetch-html-1.txt": [
        FORMULA,
        "published in 2024",
        r"I(LLM,q)\in[0,1]",
    ],
    "fetch-3.txt": [
        "**Published**: 03 August 2025",
        "KDD '25: Proceedings of the 31st ACM SIGKDD Conference on Knowledge Discovery and Data Mining V.2",
        "10.1145/3711896.3737419",
    ],
    "fetch-0.txt": [
        "[Submitted on 31 Oct 2024]",
        '<meta name="citation_date" content="2024/10/31" />',
    ],
}


def read(path):
    return path.read_text(encoding="utf-8")


def check(root):
    errors = []
    report = root / "T8-deep.md"
    if not report.is_file():
        return ["T8-deep.md missing"]
    report_text = read(report)
    for token in REPORT_TOKENS:
        if token not in report_text:
            errors.append(f"T8-deep.md missing token: {token[:90]}")
    if report_text.count("**判定：A**") < 3:
        errors.append("T8-deep.md verdict count below 3")
    for name, tokens in EVIDENCE_TOKENS.items():
        path = root / name
        if not path.is_file():
            errors.append(f"{name} missing")
            continue
        body = read(path)
        for token in tokens:
            if token not in body:
                errors.append(f"{name} missing token: {token[:90]}")
    return errors


def self_test():
    real_errors = check(ROOT)
    if real_errors:
        print("SELFTEST POSITIVE FAIL")
        for err in real_errors:
            print(" -", err)
        return 1
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        for name in FILES:
            if not (ROOT / name).is_file():
                print("SELFTEST SETUP FAIL: missing source", name)
                return 1
            shutil.copyfile(ROOT / name, tmp / name)
        bad_formula = "I(LLM,q)=WRONG"
        changed = []
        for name in ["T8-deep.md", "fetch-html-1.txt"]:
            path = tmp / name
            body = read(path)
            if FORMULA not in body:
                print("SELFTEST SETUP FAIL: formula absent in", name)
                return 1
            path.write_text(body.replace(FORMULA, bad_formula), encoding="utf-8")
            changed.append(name)
        fake_errors = check(tmp)
        if not fake_errors:
            print("SELFTEST NEGATIVE FAIL: injected wrong formula still passed")
            return 1
        if not any(e.startswith("T8-deep.md") for e in fake_errors):
            print("SELFTEST NEGATIVE FAIL: report did not detect injection")
            return 1
        if not any(e.startswith("fetch-html-1.txt") for e in fake_errors):
            print("SELFTEST NEGATIVE FAIL: evidence did not detect injection")
            return 1
        print("SELFTEST OK: injected wrong formula into " + ", ".join(changed))
        print("red observations:", len(fake_errors))
        for err in fake_errors:
            print(" -", err)
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        raise SystemExit(self_test())
    errors = check(ROOT)
    if errors:
        print("FAIL:", len(errors))
        for err in errors:
            print(" -", err)
        raise SystemExit(1)
    print("PASS: report and 3 evidence files contain all required tokens")


if __name__ == "__main__":
    main()
