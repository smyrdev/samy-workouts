# The planning algorithm

`planner.py` owns the exercise DB. This skill never reads `data/exercises_with_volume.json`
directly — every step that touches the DB is deterministic (filtering, greedy selection,
`Σ(sets × credit)`), so a script does it and returns a compact summary instead of putting 13k
tokens of JSON in context on every run.

## Division of labour

- **User** (asked by `/plan` or `/onboard`): goal, volume band, days/week, session length →
  exercise cap, priority muscles, recent training, equipment, injuries.
- **`planner.py`**: everything derivable from data — filtering, target resolution, split choice,
  exercise selection, set counts, ordering, repair.
- **`verify.py`**: independent recompute of the one load-bearing claim, Σ(sets × credit). Shares
  no code with `planner.py` on purpose — see the comment at the top of each file.
- **Model**: interview, rep ranges (goal-derived lookup), prose, explaining `constrained`/`unmet`
  honestly, and judgement calls like resolving an ambiguous swap.

## CLI contract

```
planner.py stats
  DB integrity: exercise count, empty-volume count, muscle keys missing from landmarks.

planner.py plan --profile P --cycle C --out F [--days N] [--deload] [--seed N]
  C is a JSON blob or a path to one: {primary_goal, volume_band, training_days_per_week,
  max_exercises_per_day, priority_muscles, recent_training, previous_split, previous_plan}.
  Writes F (pretty JSON, schema in the skill's SKILL.md) and prints a compact stdout summary —
  that summary is the only DB-derived text that should ever enter your context.

planner.py swap --plan F --exercise "Name" [--day N | --day all] [--profile P]
  Replaces one instance with the best-fitting filler for the volume it carried. Omitting --day
  when the exercise appears on more than one day is an error that lists the days — ask the user
  via AskUserQuestion rather than guessing. Re-run verify.py after any swap.

verify.py --plan F [--profile P]
  Recomputes Σ(sets × credit) from the plan + DB independently, checks per-day cap, within-day
  duplicates, compound-first ordering, injury exclusions, and MEV/MRV bands. Exit 1 on any
  mismatch.
```

## Steps, in order

1. **Filter the pool.** Drop the 9 exercises with `volume: {}` (Neck, Forearm, Hip adduction —
   they carry no tracked credit). Apply the equipment tier from `data/equipment_keywords.json`,
   then injury exclusions from `data/injury_exclusions.json` for each of the user's injuries.
   Fewer than ~40 surviving exercises → `constrained: true` in the output.
2. **Resolve targets.** For the user's `experience_level`, look up each muscle's row in
   `data/volume_landmarks.json`. The target band comes from the user's chosen volume_band
   (low → MEV, moderate → MAV, high → MRV). Priority muscles (max 2) get pushed one band up,
   capped at MRV. The floor for repair is always MEV; the ceiling is always MRV, regardless of
   band, so a "low" plan can never quietly exceed MRV either.
3. **Choose the split** from `training_days_per_week` (2 → full body ×2, 3 → full body ×3,
   4 → upper/lower ×2 or full body ×4, 5 → upper/lower/push/pull/legs, 6 → PPL ×2 or an
   Arnold-style chest-back / shoulders-arms / legs ×2). Where more than one option exists, the
   run's RNG (seeded or not) picks, avoiding the previous plan's split when possible.
4. **Greedy-fill each day.** Score every remaining candidate by
   `Σ(credit × (target − running))` over the day's emphasis muscles — deliberately *not* clamped
   at zero, so an exercise that piles more onto an already-met muscle is penalized, not just
   under-rewarded. Take a weighted random pick from the near-best band (within ~10% of the top
   score), down-weighting exercises the user just ran. Never repeat an exercise within a day; a
   day that would otherwise end up empty falls back to the single highest-compound-score option
   rather than shipping a zero-exercise day.
5. **Repair.** Up to 3 passes, each fixing excess (over MRV) before deficits (under MEV) — fixing
   excess first matters, because shrinking an over-target muscle can itself create a new deficit,
   and a deficit-fix must never re-open a ceiling this same pass just closed. A deficit-fix that
   can't find a "safe" candidate (one that doesn't blow another muscle's MRV) skips rather than
   forcing it — the gap is reported honestly in `unmet[]` instead.
6. **Order each day compound-first.** Sort by count of muscles credited ≥0.5, descending; ties by
   total credit, then name. This is checked, not assumed — `compound_score` is written into the
   plan file so the auditor can verify the sort without recomputing it from the DB.
7. **Emit.** Write the full plan JSON and print the compact summary (split, per-day exercise
   list with set counts, weekly volume per muscle with a landmark-status word, and `unmet`).

## Why the score isn't clamped at zero, and why repair orders excess before deficit

Both fixes came from watching real runs overshoot Front Delt by 2-4× its landmark: an exercise
already past its target for muscle A still looked attractive because of muscles B and C, so
greedy kept stacking it. Removing the clamp lets an already-met muscle actively penalize further
selection. In repair, fixing a deficit before excess let the two passes fight each other — an
excess-fix would remove an exercise, and the very next deficit-fix (working from a stale
snapshot) would put a near-identical one right back. Excess-first, with a live running total and
a "never reopen what this pass just closed" rule on deficit-fills, converges instead of
oscillating.

## Model layer, after the script returns

Add rep ranges from goal (hypertrophy `8-12`, strength `4-6`, endurance `12-20`, general `8-15`
— the DB has no rep data, this is a plain lookup), write `plan-<date>.md` in plain markdown, and
surface `constrained` / `unmet` in honest English rather than status codes.
