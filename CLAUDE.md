# samy-workouts

A clone-and-use Claude Code skill pack that generates weekly workout plans from a 145-exercise
volume-credit database. No accounts, no server — the repo is the app. Not medical advice.

## Rules for working in this repo

- The exercise DB is `data/exercises_with_volume.json`. Its `volume` maps are **fractional set
  credits**, not importance weights — `Σ(sets × credit)` per muscle is exact arithmetic, not a
  judgement call.
- **Never read the full DB into context.** Every skill goes through
  `.claude/skills/plan/scripts/planner.py`, which loads the DB from disk and returns a compact
  summary (well under 1k tokens). If a task seems to need the raw DB in context, the fix is a
  new `planner.py` subcommand, not a `Read` call.
- **Never write to `data/`.** It's shipped, read-only reference data that cloners edit by hand,
  not through the skills.
- User state lives in `profile/` (gitignored). `profile/profile.example.json` is the only
  committed file there — it documents the schema for a fresh clone.
- Volume arithmetic is never done by the model. It goes through `planner.py` (selection/repair)
  or `verify.py` (independent audit), never computed by hand in a response.
- `verify.py` duplicates `planner.py`'s summing loop **on purpose** — see the comment at the top
  of each file. Do not refactor them to share a helper; a shared bug would pass both the
  planner's own repair loop and the audit, defeating the point of an independent check.
- `profile/profile.json` holds only stable facts (age, body stats, experience, equipment,
  injuries). Per-cycle answers (goal, volume band, days, priority muscles) belong in the plan
  file's `inputs_used`, not the profile — re-planning always re-asks them.
- Scripts are Python 3 **stdlib only** — no pip, no dependencies. If Python is unavailable, say
  so explicitly rather than silently estimating.
