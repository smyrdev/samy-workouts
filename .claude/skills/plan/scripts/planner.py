#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Owns the exercise DB. Filters, selects, and emits a weekly plan; also
performs in-place swaps. Never share code with verify.py — see
references/algorithm.md for why. Python 3 stdlib only.
"""
import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DB_PATH = ROOT / "data" / "exercises_with_volume.json"
LANDMARKS_PATH = ROOT / "data" / "volume_landmarks.json"
INJURY_PATH = ROOT / "data" / "injury_exclusions.json"
EQUIPMENT_PATH = ROOT / "data" / "equipment_keywords.json"

REP_RANGES = {"hypertrophy": "8-12", "strength": "4-6", "endurance": "12-20", "general": "8-15"}
BAND_KEYS = {"low": "mev", "moderate": "mav", "high": "mrv"}
BAND_ORDER = ["low", "moderate", "high"]

PUSH = ["Upper Pecs", "Lower Pecs", "Front Delt", "Lateral Delt",
        "Triceps Medial & Lateral Heads", "Triceps Long Head"]
PULL = ["Lats", "Middle Traps", "Upper Traps", "Lower Traps", "Rear Delt", "Biceps"]
LEGS = ["Glute maximus", "Glute medius", "Vasti of the quads", "Rectus femoris",
        "Biceps femoris long head and semis", "Biceps femoris short head",
        "Gastrocnemius", "Soleus", "Erector Spinae", "Abs"]
UPPER = PUSH + PULL
CHEST_BACK = ["Upper Pecs", "Lower Pecs", "Lats", "Middle Traps", "Upper Traps", "Lower Traps"]
SHOULDERS_ARMS = ["Front Delt", "Lateral Delt", "Rear Delt", "Biceps",
                   "Triceps Medial & Lateral Heads", "Triceps Long Head"]

SPLITS = {
    2: [("full_body_2", [("Full Body A", None), ("Full Body B", None)])],
    3: [("full_body_3", [("Full Body A", None), ("Full Body B", None), ("Full Body C", None)])],
    4: [("upper_lower", [("Upper", UPPER), ("Lower", LEGS), ("Upper", UPPER), ("Lower", LEGS)]),
        ("full_body_4", [("Full Body A", None), ("Full Body B", None),
                          ("Full Body C", None), ("Full Body D", None)])],
    5: [("ul_ppl_5", [("Upper", UPPER), ("Lower", LEGS), ("Push", PUSH),
                       ("Pull", PULL), ("Legs", LEGS)])],
    6: [("ppl_2", [("Push", PUSH), ("Pull", PULL), ("Legs", LEGS),
                    ("Push", PUSH), ("Pull", PULL), ("Legs", LEGS)]),
        ("arnold", [("Chest & Back", CHEST_BACK), ("Shoulders & Arms", SHOULDERS_ARMS),
                     ("Legs", LEGS), ("Chest & Back", CHEST_BACK),
                     ("Shoulders & Arms", SHOULDERS_ARMS), ("Legs", LEGS)])],
}
FOCUS_TO_MUSCLES = {
    "Upper": UPPER, "Lower": LEGS, "Push": PUSH, "Pull": PULL, "Legs": LEGS,
    "Chest & Back": CHEST_BACK, "Shoulders & Arms": SHOULDERS_ARMS,
}

def load_json(path):
    with open(path) as f:
        return json.load(f)

def all_muscles(landmarks):
    return sorted(landmarks["muscles"].keys())

def focus_muscles(focus_name, landmarks):
    return FOCUS_TO_MUSCLES.get(focus_name) or all_muscles(landmarks)

def compound_score(exercise):
    return sum(1 for c in exercise["volume"].values() if c >= 0.5)

def filter_pool(db, equipment, injuries, equipment_keywords, injury_exclusions):
    tier = equipment_keywords["tiers"].get(equipment, {"allow_all": True})
    excl_subcats, excl_keywords = set(), []
    for inj in injuries:
        spec = injury_exclusions["complaints"].get(inj.get("key"))
        if not spec:
            continue
        excl_subcats |= set(spec["exclude_sub_categories"])
        excl_keywords += spec["exclude_name_keywords"]

    pool = []
    for ex in db:
        if not ex["volume"]:
            continue  # untracked accessory (Neck/Forearm/Adduction) — never fed to volume math
        name_l = ex["exercise_name"].lower()
        if not tier.get("allow_all"):
            allowed = any(kw.lower() in name_l for kw in tier.get("allow_keywords", []))
            denied = any(kw.lower() in name_l for kw in tier.get("deny_keywords", []))
            if not allowed or denied:
                continue
        if ex["sub_category"] in excl_subcats:
            continue
        if any(kw.lower() in name_l for kw in excl_keywords):
            continue
        pool.append(ex)
    return pool

def resolve_targets(landmarks, level, band, priority_muscles):
    targets, floors, ceilings, optional = {}, {}, {}, {}
    for muscle, rows in landmarks["muscles"].items():
        row = rows[level]
        use_band = band
        if muscle in priority_muscles:
            idx = min(BAND_ORDER.index(band) + 1, len(BAND_ORDER) - 1)
            use_band = BAND_ORDER[idx]
        targets[muscle] = row[BAND_KEYS[use_band]]
        floors[muscle] = row["mev"]
        ceilings[muscle] = row["mrv"]
        optional[muscle] = rows.get("optional", False)
    return targets, floors, ceilings, optional

def pick_split(days, seed_rng, previous_split):
    candidates = SPLITS[days]
    if len(candidates) == 1:
        return candidates[0]
    others = [c for c in candidates if c[0] != previous_split]
    pool = others or candidates
    return pool[seed_rng.randrange(len(pool))]

def score_exercise(ex, emphasis, running, targets):
    # No clamping to zero: an exercise that piles more onto an already-met
    # muscle must be penalized, not just under-rewarded, or greedy fill
    # keeps stacking it for its OTHER credits and blows past MRV unseen.
    return sum(credit * (targets[m] - running.get(m, 0.0))
               for m, credit in ex["volume"].items() if m in emphasis)

def fill_day(pool, emphasis, running, targets, cap, goal, recent, rng):
    day = []
    used_names, used_subcats = set(), set()
    sets_lo, sets_hi = (4, 5) if goal == "strength" else (3, 4)
    while len(day) < cap:
        candidates = [ex for ex in pool if ex["exercise_name"] not in used_names]
        if not candidates:
            break
        scored = [(score_exercise(ex, emphasis, running, targets), ex) for ex in candidates]
        best = max(s for s, _ in scored)
        if best <= 0 and day:
            break  # nothing left offers real benefit and the day already has a workout
        if best <= 0:
            # day is still empty — a session with zero exercises is worse than a
            # slightly-redundant one, so fall back to the highest compound score
            band = [max(scored, key=lambda t: compound_score(t[1]))]
        else:
            band = [(s, ex) for s, ex in scored if s >= best * 0.9]
        weights = []
        for s, ex in band:
            w = 1.0
            if ex["exercise_name"] in recent:
                w *= 0.3
            if ex["sub_category"] not in used_subcats:
                w *= 1.2
            weights.append(w)
        pick = rng.choices(band, weights=weights, k=1)[0][1]
        sets = rng.randrange(sets_lo, sets_hi + 1)
        day.append({"name": pick["exercise_name"], "sets": sets})
        used_names.add(pick["exercise_name"])
        used_subcats.add(pick["sub_category"])
        for m, credit in pick["volume"].items():
            running[m] = running.get(m, 0.0) + sets * credit
    return day

def recompute(days, by_name):
    running = {}
    for day in days:
        for item in day["exercises"]:
            for m, credit in by_name[item["name"]]["volume"].items():
                running[m] = running.get(m, 0.0) + item["sets"] * credit
    return running


def repair(days, pool, targets, floors, ceilings, optional, cap, goal, rng, by_name, landmarks):
    for _ in range(3):
        # Excess first: shrinking an over-target muscle can itself create a
        # new deficit, so deficient-fill must see the POST-shrink state, not
        # a stale snapshot — otherwise the two passes fight each other and
        # never converge (a muscle fixed by one undoes the other's fix).
        running = recompute(days, by_name)
        excess = [m for m in ceilings if running.get(m, 0.0) > ceilings[m]]
        changed = False
        for m in excess:
            over = running.get(m, 0.0) - ceilings[m]
            contributors = [(day, item) for day in days for item in day["exercises"]
                            if by_name[item["name"]]["volume"].get(m, 0) > 0]
            contributors.sort(key=lambda t: -by_name[t[1]["name"]]["volume"].get(m, 0) * t[1]["sets"])
            for day, item in contributors:
                if over <= 0:
                    break
                credit = by_name[item["name"]]["volume"].get(m, 0)
                while item["sets"] > 2 and over > 0:
                    item["sets"] -= 1
                    over -= credit
                    changed = True
                if over > 0 and item["sets"] <= 2 and len(day["exercises"]) > 1:
                    over -= item["sets"] * credit
                    day["exercises"].remove(item)
                    changed = True

        running = recompute(days, by_name)
        deficient = [m for m in floors if running.get(m, 0.0) < floors[m]]
        for m in deficient:
            target_day = next((d for d in days if m in focus_muscles(d["focus"], landmarks)
                                and len(d["exercises"]) < cap), None)
            if not target_day:
                continue
            used = {e["name"] for e in target_day["exercises"]}
            sets = rng.randrange(4, 6) if goal == "strength" else rng.randrange(3, 5)
            candidates = [ex for ex in pool if ex["exercise_name"] not in used and ex["volume"].get(m, 0) >= 0.5]
            # Never re-open a ceiling this same pass just closed elsewhere —
            # skip and let it surface honestly in unmet[] instead.
            safe = [ex for ex in candidates if all(
                running.get(m2, 0.0) + sets * c2 <= ceilings.get(m2, 1e9) + 0.01
                for m2, c2 in ex["volume"].items())]
            if not safe:
                continue
            best = max(safe, key=lambda ex: ex["volume"].get(m, 0))
            target_day["exercises"].append({"name": best["exercise_name"], "sets": sets})
            for m2, c2 in best["volume"].items():
                running[m2] = running.get(m2, 0.0) + sets * c2
            changed = True

        if not changed:
            break
    running = recompute(days, by_name)
    unmet = []
    for m in floors:
        val = running.get(m, 0.0)
        if val < floors[m]:
            unmet.append(f"{m}: {val:g} sets, below MEV {floors[m]:g}" + (" (optional)" if optional[m] else ""))
    return running, unmet

def order_day(day, by_name):
    def key(item):
        ex = by_name[item["name"]]
        return (-compound_score(ex), -sum(ex["volume"].values()), item["name"])
    day["exercises"].sort(key=key)
    for i, item in enumerate(day["exercises"], start=1):
        item["order"] = i

def status_label(sets, floor, mav, ceiling, optional):
    if sets < floor:
        return "below_mev_optional" if optional else "below_mev"
    if sets <= mav * 0.9:
        return "at_mev"
    if sets <= mav * 1.1:
        return "at_mav"
    if sets <= ceiling:
        return "above_mav"
    return "above_mrv"

def build_plan(profile, cycle, db, landmarks, injury_exclusions, equipment_keywords, seed, date_str):
    rng = random.Random(seed) if seed is not None else random.Random()
    level = profile["experience_level"]
    goal = cycle["primary_goal"]
    band = cycle["volume_band"]
    days = cycle["training_days_per_week"]
    cap = cycle["max_exercises_per_day"]
    priority = cycle.get("priority_muscles", [])[:2]
    recent = set(cycle.get("recent_training", []))
    previous_split = cycle.get("previous_split")

    pool = filter_pool(db, profile["equipment"], profile.get("injuries", []),
                        equipment_keywords, injury_exclusions)
    constrained = len(pool) < 40
    by_name = {ex["exercise_name"]: ex for ex in pool}

    targets, floors, ceilings, optional = resolve_targets(landmarks, level, band, priority)
    split_name, day_specs = pick_split(days, rng, previous_split)

    plan_days = []
    running = {}
    for i, (focus, emphasis) in enumerate(day_specs, start=1):
        muscles = emphasis or all_muscles(landmarks)
        exercises = fill_day(pool, set(muscles), running, targets, cap, goal, recent, rng)
        plan_days.append({"day": i, "focus": focus, "exercises": exercises})

    running, unmet = repair(plan_days, pool, targets, floors, ceilings, optional, cap, goal, rng, by_name, landmarks)

    for day in plan_days:
        order_day(day, by_name)
        day["total_sets"] = sum(e["sets"] for e in day["exercises"])

    landmark_status = {}
    for m in sorted(landmarks["muscles"].keys()):
        val = round(running.get(m, 0.0), 2)
        mav = landmarks["muscles"][m][level]["mav"]
        landmark_status[m] = status_label(val, floors[m], mav, ceilings[m], optional[m])

    plan = {
        "metadata": {
            "generator": "workout_planning_engine", "version": "1.0",
            "created_at": date_str, "split": split_name, "audited": False, "seed": seed if seed is not None else rng.getrandbits(32),
        },
        "inputs_used": {
            "primary_goal": goal, "volume_band": band,
            "training_days_per_week": days, "max_exercises_per_day": cap,
            "priority_muscles": priority,
            "target_weekly_volume": round(sum(targets.values()), 2),
            "previous_plan": cycle.get("previous_plan"),
        },
        "statistics": {
            "weekly_volume_per_muscle": {m: round(running.get(m, 0.0), 2) for m in sorted(landmarks["muscles"].keys())},
            "landmark_status": landmark_status,
        },
        "constrained": constrained,
        "pool_size": len(pool),
        "unmet": unmet,
        "workout_plan": [],
    }
    for day in plan_days:
        entry = {"day": day["day"], "focus": day["focus"], "total_sets": day["total_sets"], "exercises": []}
        for item in day["exercises"]:
            ex = by_name[item["name"]]
            entry["exercises"].append({
                "order": item["order"], "name": item["name"], "sets": item["sets"],
                "reps": REP_RANGES[goal], "compound_score": compound_score(ex),
                "primary_targets": [m for m, c in sorted(ex["volume"].items(), key=lambda kv: -kv[1]) if c >= 0.5],
                "logged_sets": [],
            })
        plan["workout_plan"].append(entry)
    return plan

def print_summary(plan):
    m = plan["metadata"]
    print(f"split: {m['split']}  days: {len(plan['workout_plan'])}  "
          f"pool: {plan['pool_size']}/145 exercises  constrained: {plan['constrained']}")
    for day in plan["workout_plan"]:
        items = " · ".join(f"{e['name']} {e['sets']}x" for e in day["exercises"])
        print(f"day {day['day']} {day['focus']} ({day['total_sets']} sets): {items}")
    vol_bits = " · ".join(f"{m} {v} {plan['statistics']['landmark_status'][m]}"
                           for m, v in plan["statistics"]["weekly_volume_per_muscle"].items())
    print(f"volume: {vol_bits}")
    print("unmet: " + ("none" if not plan["unmet"] else "; ".join(plan["unmet"])))

def cmd_stats(args):
    db = load_json(DB_PATH)
    landmarks = load_json(LANDMARKS_PATH)
    empty = [ex["exercise_name"] for ex in db if not ex["volume"]]
    db_muscles = set()
    for ex in db:
        db_muscles |= set(ex["volume"].keys())
    missing = db_muscles - set(landmarks["muscles"].keys())
    print(f"exercises: {len(db)}")
    print(f"empty volume: {len(empty)} ({', '.join(empty)})")
    print(f"muscle keys not in landmarks: {sorted(missing) if missing else 'none'}")
    return 1 if missing else 0

def cmd_plan(args):
    db = load_json(DB_PATH)
    landmarks = load_json(LANDMARKS_PATH)
    injury_exclusions = load_json(INJURY_PATH)
    equipment_keywords = load_json(EQUIPMENT_PATH)
    profile = load_json(args.profile)
    cycle = json.loads(args.cycle) if args.cycle.strip().startswith("{") else load_json(args.cycle)
    if args.days:
        cycle["training_days_per_week"] = args.days
    if args.deload:
        cycle["volume_band"] = "low"

    plan = build_plan(profile, cycle, db, landmarks, injury_exclusions, equipment_keywords,
                       args.seed, cycle.get("created_at", "unknown-date"))
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(plan, f, indent=2, sort_keys=False)
        f.write("\n")
    print_summary(plan)
    return 0

def cmd_swap(args):
    db = load_json(DB_PATH)
    landmarks = load_json(LANDMARKS_PATH)
    injury_exclusions = load_json(INJURY_PATH)
    equipment_keywords = load_json(EQUIPMENT_PATH)
    plan = load_json(args.plan)
    by_name = {ex["exercise_name"]: ex for ex in db}

    profile_path = Path(args.profile) if args.profile else ROOT / "profile" / "profile.json"
    ceilings = {}
    if profile_path.exists():
        profile = load_json(profile_path)
        pool = filter_pool(db, profile["equipment"], profile.get("injuries", []),
                            equipment_keywords, injury_exclusions)
        level = profile.get("experience_level")
        if level:
            ceilings = {m: rows[level]["mrv"] for m, rows in landmarks["muscles"].items()}
    else:
        pool = [ex for ex in db if ex["volume"]]

    occurrences = [d["day"] for d in plan["workout_plan"]
                   if any(e["name"] == args.exercise for e in d["exercises"])]
    if not occurrences:
        print(f"'{args.exercise}' not found in plan", file=sys.stderr)
        return 1
    if args.day == "all":
        target_days = occurrences
    elif args.day:
        target_days = [int(args.day)]
    elif len(occurrences) == 1:
        target_days = occurrences
    else:
        print(f"'{args.exercise}' appears on days {occurrences} — pass --day N or --day all", file=sys.stderr)
        return 1

    goal = plan["inputs_used"]["primary_goal"]
    for day in plan["workout_plan"]:
        if day["day"] not in target_days:
            continue
        removed = next(e for e in day["exercises"] if e["name"] == args.exercise)
        muscles = set(by_name[removed["name"]]["volume"].keys())
        used = {e["name"] for e in day["exercises"]} - {removed["name"]}
        candidates = [ex for ex in pool if ex["exercise_name"] not in used and ex["exercise_name"] != removed["name"]]
        candidates = [ex for ex in candidates if any(m in muscles for m in ex["volume"])]
        if not candidates:
            print(f"no replacement found for '{args.exercise}' on day {day['day']}", file=sys.stderr)
            continue
        without = recompute([{"exercises": [e for e in d["exercises"] if not (d is day and e is removed)]}
                              for d in plan["workout_plan"]], by_name)
        safe = [ex for ex in candidates if all(
            without.get(m2, 0.0) + removed["sets"] * c2 <= ceilings.get(m2, 1e9) + 0.01
            for m2, c2 in ex["volume"].items())]
        if not safe:
            print(f"  warning: no replacement for '{args.exercise}' on day {day['day']} keeps every muscle under MRV; picked the closest match", file=sys.stderr)
        best = max(safe or candidates, key=lambda ex: sum(c for m, c in ex["volume"].items() if m in muscles))
        day["exercises"] = [e for e in day["exercises"] if e["name"] != args.exercise]
        day["exercises"].append({
            "order": 0, "name": best["exercise_name"], "sets": removed["sets"],
            "reps": REP_RANGES[goal], "compound_score": compound_score(best),
            "primary_targets": [m for m, c in sorted(best["volume"].items(), key=lambda kv: -kv[1]) if c >= 0.5],
            "logged_sets": [],
        })
        day["exercises"].sort(key=lambda e: (-e["compound_score"], -sum(by_name[e["name"]]["volume"].values()), e["name"]))
        for i, e in enumerate(day["exercises"], start=1):
            e["order"] = i
        day["total_sets"] = sum(e["sets"] for e in day["exercises"])
        print(f"day {day['day']}: swapped '{args.exercise}' -> '{best['exercise_name']}'")

    running = {}
    for day in plan["workout_plan"]:
        for item in day["exercises"]:
            for m, credit in by_name[item["name"]]["volume"].items():
                running[m] = running.get(m, 0.0) + item["sets"] * credit
    plan["statistics"]["weekly_volume_per_muscle"] = {m: round(running.get(m, 0.0), 2)
                                                        for m in sorted(landmarks["muscles"].keys())}
    plan["metadata"]["audited"] = False
    with open(args.plan, "w") as f:
        json.dump(plan, f, indent=2, sort_keys=False)
        f.write("\n")
    return 0

def main():
    parser = argparse.ArgumentParser(description="samy-workouts planner — filters, selects, and verifies-internally a weekly plan")
    sub = parser.add_subparsers(dest="command", required=True)

    p_stats = sub.add_parser("stats", help="DB integrity report")
    p_stats.set_defaults(func=cmd_stats)

    p_plan = sub.add_parser("plan", help="generate a weekly plan")
    p_plan.add_argument("--profile", required=True)
    p_plan.add_argument("--cycle", required=True, help="JSON blob or path to a JSON file")
    p_plan.add_argument("--out", required=True)
    p_plan.add_argument("--days", type=int)
    p_plan.add_argument("--deload", action="store_true")
    p_plan.add_argument("--seed", type=int)
    p_plan.set_defaults(func=cmd_plan)

    p_swap = sub.add_parser("swap", help="swap one exercise instance in an existing plan")
    p_swap.add_argument("--plan", required=True)
    p_swap.add_argument("--exercise", required=True)
    p_swap.add_argument("--day")
    p_swap.add_argument("--profile")
    p_swap.set_defaults(func=cmd_swap)

    args = parser.parse_args()
    sys.exit(args.func(args))

if __name__ == "__main__":
    main()
