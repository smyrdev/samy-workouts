#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Independent recompute of a generated plan's arithmetic and constraints.
Deliberately shares no code with planner.py — see references/algorithm.md
for why duplicating the summing loop here is intentional, not an oversight.
Python 3 stdlib only.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def load(path):
    with open(path) as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--profile")
    args = ap.parse_args()

    plan = load(args.plan)
    db = load(ROOT / "data" / "exercises_with_volume.json")
    db_by_name = {e["exercise_name"]: e for e in db}

    ok = True

    def fail(msg):
        nonlocal ok
        ok = False
        print(f"FAIL: {msg}")

    # A: every plan exercise exists exactly in the DB
    for day in plan["workout_plan"]:
        for item in day["exercises"]:
            if item["name"] not in db_by_name:
                fail(f"day {day['day']}: '{item['name']}' is not in the DB")

    # B: recomputed Σ(sets × credit) matches the plan's own statistics
    totals = {}
    for day in plan["workout_plan"]:
        for item in day["exercises"]:
            ex = db_by_name.get(item["name"])
            if not ex:
                continue
            for muscle, credit in ex["volume"].items():
                totals[muscle] = totals.get(muscle, 0.0) + item["sets"] * credit
    stated = plan["statistics"]["weekly_volume_per_muscle"]
    for muscle, recomputed in totals.items():
        if abs(recomputed - stated.get(muscle, 0.0)) > 0.01:
            fail(f"{muscle}: recomputed {recomputed:g} != stated {stated.get(muscle, 0):g}")
    for muscle in stated:
        if muscle not in totals and stated[muscle] > 0.01:
            fail(f"{muscle}: stated {stated[muscle]:g} but no exercise contributes to it")

    # C: per-day cap and within-day duplicates
    cap = plan["inputs_used"]["max_exercises_per_day"]
    for day in plan["workout_plan"]:
        names = [item["name"] for item in day["exercises"]]
        if len(names) > cap:
            fail(f"day {day['day']}: {len(names)} exercises exceeds cap of {cap}")
        if len(names) != len(set(names)):
            fail(f"day {day['day']}: duplicate exercise within the same day")

    # D: ordering is compound-first
    for day in plan["workout_plan"]:
        scores = []
        for item in day["exercises"]:
            ex = db_by_name.get(item["name"])
            actual = sum(1 for c in ex["volume"].values() if c >= 0.5) if ex else None
            if ex and item.get("compound_score") != actual:
                fail(f"day {day['day']}: '{item['name']}' compound_score {item.get('compound_score')} != actual {actual}")
            scores.append(item.get("compound_score", 0))
        if any(scores[i] < scores[i + 1] for i in range(len(scores) - 1)):
            fail(f"day {day['day']}: exercises not ordered compound-first")

    # E: injury exclusions survived, and volume stays in-band (needs a profile)
    if args.profile:
        profile = load(args.profile)
        injury_exclusions = load(ROOT / "data" / "injury_exclusions.json")["complaints"]
        excl_subcats, excl_keywords = set(), []
        for inj in profile.get("injuries", []):
            spec = injury_exclusions.get(inj.get("key"))
            if spec:
                excl_subcats |= set(spec["exclude_sub_categories"])
                excl_keywords += spec["exclude_name_keywords"]
        for day in plan["workout_plan"]:
            for item in day["exercises"]:
                ex = db_by_name.get(item["name"])
                if not ex:
                    continue
                name_l = ex["exercise_name"].lower()
                if ex["sub_category"] in excl_subcats or any(k.lower() in name_l for k in excl_keywords):
                    fail(f"day {day['day']}: '{item['name']}' should have been excluded by injury filter")

        landmarks = load(ROOT / "data" / "volume_landmarks.json")["muscles"]
        level = profile["experience_level"]
        unmet_text = " ".join(plan.get("unmet", []))
        for muscle, row in landmarks.items():
            band = row[level]
            val = totals.get(muscle, 0.0)
            if val > band["mrv"] + 0.01:
                fail(f"{muscle}: {val:g} sets exceeds MRV {band['mrv']:g}")
            elif val < band["mev"] and muscle not in unmet_text and not row.get("optional"):
                fail(f"{muscle}: {val:g} sets below MEV {band['mev']:g} and not flagged in unmet[]")

    print("PASS" if ok else "VERIFY FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
