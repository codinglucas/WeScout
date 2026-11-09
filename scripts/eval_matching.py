"""Precision/recall of the ID matcher on the hand-labelled pairs in eval/match_labels.csv.

    uv run python scripts/eval_matching.py [--labels eval/match_labels.csv]

A pair counts as predicted-match when its score reaches the AUTO threshold (what the
pipeline would link without a human). Pairs in the REVIEW band are reported separately.
"""

from __future__ import annotations

import argparse
import csv
from datetime import date
from pathlib import Path

from wescout.matching import AUTO, REVIEW, MatchSubject, score_pair


def _dob(text: str) -> date | None:
    return date.fromisoformat(text) if text.strip() else None


def _clubs(text: str) -> list[str]:
    return [c for c in text.split("|") if c.strip()]


def load(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as fh:
        lines = [line for line in fh if not line.startswith("#")]
    return list(csv.DictReader(lines))


def evaluate(rows: list[dict[str, str]]) -> dict[str, object]:
    tp = fp = fn = tn = review = 0
    errors: list[str] = []
    for r in rows:
        left = MatchSubject.build(
            "l", r["left_name"], r["left_first"] or None, r["left_last"] or None,
            _dob(r["left_dob"]), _clubs(r["left_clubs"]),
        )  # fmt: skip
        right = MatchSubject.build(
            "r", r["right_name"], date_of_birth=_dob(r["right_dob"]), clubs=_clubs(r["right_clubs"])
        )
        score, reason = score_pair(left, right)
        truth = r["is_match"].strip() == "1"
        predicted = score >= AUTO
        if REVIEW <= score < AUTO:
            review += 1
        if predicted and truth:
            tp += 1
        elif predicted and not truth:
            fp += 1
            errors.append(f"FALSE MATCH  {r['left_name']} ~ {r['right_name']} ({score}, {reason})")
        elif truth:
            fn += 1
            band = "review" if score >= REVIEW else "missed"
            errors.append(
                f"{band.upper():12} {r['left_name']} ~ {r['right_name']} ({score}, {reason})"
            )
        else:
            tn += 1
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    return {
        "pairs": len(rows), "tp": tp, "fp": fp, "fn": fn, "tn": tn, "review_band": review,
        "precision": round(precision, 3), "recall": round(recall, 3), "errors": errors,
    }  # fmt: skip


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", type=Path, default=Path("eval/match_labels.csv"))
    args = parser.parse_args()
    result = evaluate(load(args.labels))
    errors = result.pop("errors")
    print(" ".join(f"{k}={v}" for k, v in result.items()))
    for e in errors:  # type: ignore[attr-defined]
        print(" ", e)


if __name__ == "__main__":
    main()
