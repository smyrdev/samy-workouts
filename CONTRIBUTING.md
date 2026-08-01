# Contributing

This repo is deliberately small: `data/`, two scripts, two skills, one subagent. Keep additions
in that spirit — see the "keep v1 simple" philosophy in the skill design if you're adding
behaviour, not just data.

## Adding an exercise to the DB

Edit `data/exercises_with_volume.json` directly. Each entry:

```json
{
  "exercise_name": "Cable lateral raise",
  "category": "Upper Body",
  "sub_category": "Lateral raises",
  "volume": { "Front Delt": 1.0, "Lateral Delt": 1.0, "Upper Pecs": 0.25 }
}
```

- `exercise_name` must be unique across the file — it's the only identifier a plan file stores.
- `category` is `"Upper Body"` or `"Lower Body"`.
- `sub_category` groups exercises for injury exclusion (`data/injury_exclusions.json` matches on
  it) — reuse an existing one from the file where the exercise genuinely fits; only add a new one
  if nothing fits.
- `volume` is **sparse** — omit a muscle entirely rather than writing `0.0`. Credits are
  fractional set counts, not importance weights: `1.0` means one set of this exercise counts as a
  full set for that muscle; `0.25` means a quarter. Base the number on how much of the working set
  is actually driven by that muscle, not on how "important" it feels.
- An exercise with no meaningfully-tracked muscle (pure mobility work, wrist/neck isolation) gets
  `"volume": {}` — it's excluded from all volume math and treated as an untracked accessory.
- Muscle names must exactly match a key in `data/volume_landmarks.json`. Run
  `python3 .claude/skills/plan/scripts/planner.py stats` after editing — it flags any muscle key
  used in the DB that's missing from the landmarks file.

## Changing landmarks, injury exclusions, or equipment keywords

All three files under `data/` are plain JSON with `note`/`source_note` fields explaining the
reasoning — edit them directly, no code change needed.

- **`volume_landmarks.json`** (MEV/MAV/MRV per muscle per experience level): these are an
  authored starting point, not settled science. If you're proposing a change, say where the
  number comes from (a program, a study, your own logged data) in the muscle's `note` field so
  the next person can judge it, rather than silently overwriting someone else's opinion.
- **`injury_exclusions.json`**: keyword-and-category matching only — there's no injury field in
  the DB. If you add a complaint or tighten an existing one, sanity-check the exclusion count
  (see *Verification* below) so it isn't accidentally excluding half the database.
- **`equipment_keywords.json`**: substring matching on exercise names, case-insensitive. Same
  caution — check what actually gets included/excluded before committing.

## Verification

There's no test framework — the checks below are the test suite, meant to be run by hand:

```bash
# 1. DB integrity: exercise count, empty-volume count, any muscle missing from landmarks
python3 .claude/skills/plan/scripts/planner.py stats

# 2. Generate a plan against the example profile (or your own profile/profile.json)
python3 .claude/skills/plan/scripts/planner.py plan \
  --profile profile/profile.example.json --cycle '{"primary_goal":"hypertrophy","volume_band":"moderate","training_days_per_week":4,"max_exercises_per_day":8,"priority_muscles":[],"recent_training":[]}' \
  --out /tmp/plan.json --seed 42

# 3. Independent arithmetic check — should print PASS
python3 .claude/skills/plan/scripts/verify.py --plan /tmp/plan.json --profile profile/profile.example.json
```

If you changed `planner.py` or `verify.py`, also run the same `plan` command twice with the same
`--seed` and confirm the output files are byte-identical apart from `created_at` — reproducibility
is what makes a reported bug investigable. Full verification steps (constrained profiles,
auditor-catches-a-planted-bug, swap edge cases) are documented in the project's design notes; the
three commands above cover the everyday case for a data-only contribution.

## Pull requests

Small, focused changes. If you're adding a new muscle, sub-category, or a structural change to
the schemas, open an issue first — those ripple through all four `data/` files and both scripts.
