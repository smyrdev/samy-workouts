---
name: plan
description: >
  Generate a weekly workout plan. Asks the per-cycle questions — goal, target volume, training
  days, session length, priority muscles, and recent training — then combines them with the
  stored profile, the exercise database, and weekly volume landmarks. Verifies the plan
  arithmetically before presenting it. Use when the user asks for a workout plan, a training
  program, a new split, or wants their current plan regenerated, varied, or adjusted.
allowed-tools: Read, Write, Bash, Task, AskUserQuestion
argument-hint: "[--days N] [--deload] [--seed N]"
---

**This skill never reads `data/exercises_with_volume.json` directly.** `scripts/planner.py` owns
the DB; this skill only ever sees the compact summary it prints. If you find yourself reaching
for `Read` on that file, stop — the answer is a new `planner.py` subcommand, not a context read.
See `references/algorithm.md` before extending this skill.

## Flow

1. Read `profile/profile.json`. If it doesn't exist, tell the user to run `/onboard` first.
2. Ask the per-cycle questions with `AskUserQuestion`, defaulting each to the previous plan in
   `profile/plans/` when one exists (so re-planning with no changes is a few clicks):

   | Question | Options |
   |---|---|
   | Primary goal | Hypertrophy · Strength · General fitness · Endurance |
   | Target volume | Low (MEV) · **Moderate (MAV) — recommended** · High (MRV) |
   | Days per week | 2 · 3 · **4** · 5 · 6 (or `--days`) |
   | Session length | 30min→cap 5 · 45min→6 · **60min→8** · 90min→10 |
   | Priority muscles | Optional, max 2, from the 22-muscle vocabulary in `data/volume_landmarks.json` |
   | Recent training | Defaults to the exercises in the previous plan, if any |

3. Write these answers plus `previous_split`/`previous_plan` (from the last plan file, if any)
   as the `--cycle` JSON and invoke:
   ```
   python3 .claude/skills/plan/scripts/planner.py plan \
     --profile profile/profile.json --cycle '<json>' \
     --out profile/plans/plan-<date>.json --seed <seed if --seed given>
   ```
   If Python 3 isn't available, say so explicitly and fall back to doing the arithmetic yourself
   over a filtered subset — and warn the user the numbers are estimates, not verified.
4. Read the stdout summary (split, days, per-day exercises, weekly volume, `unmet`) — this is the
   only DB-derived text that should enter context, well under 1k tokens.
5. Dispatch the `plan-auditor` subagent to verify the file. If it reports failures, surface them
   to the user rather than silently retrying.
6. Add rep ranges from goal (hypertrophy 8-12, strength 4-6, endurance 12-20, general 8-15) and
   write `profile/plans/plan-<date>.md`: plain markdown, day headings, a `Sets × Reps` table, a
   weekly volume table with plain-English status (not `at_mav`/`below_mev` jargon), and a footer
   with the date and seed. No wrapping tables, no raw JSON.
7. Present the markdown. If the user pushes back on one exercise ("swap the lunges"), resolve
   which day they mean (infer if it appears once; ask via `AskUserQuestion` with an "all of them"
   option if it appears on several days and they didn't say which), then run:
   ```
   python3 .claude/skills/plan/scripts/planner.py swap --plan <file> --exercise "<name>" --day <N|all>
   ```
   and re-run the auditor.

## Rules

- Never write to `data/` — it's shipped, read-only reference data.
- `--deload` forces the low volume band regardless of the user's answer.
- Volume arithmetic is never done by the model — if a number needs computing, it goes through
  `planner.py` or `verify.py`, never by hand in the response.
