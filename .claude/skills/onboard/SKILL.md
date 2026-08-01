---
name: onboard
description: >
  Record the user's stable training facts — age, body stats, experience level, available
  equipment, injuries, and units — and write them to profile/profile.json. Use when the user is
  setting up for the first time, or asks to update their body stats, injuries, experience, or
  available equipment. Per-cycle choices like goal and volume are asked by /plan, not here.
allowed-tools: Read, Write, Bash, AskUserQuestion
argument-hint: "[--update]"
---

## What belongs here

Only things that stay true for months. The test: *would this answer still be true in three
months?* Yes → ask it here. No → it belongs to `/plan` instead (goal, volume band, days,
priority muscles — those are per-cycle).

## Flow

1. If `profile/profile.json` already exists and `--update` was not passed, tell the user their
   profile is already set up and ask if they want `--update` instead of a full re-interview.
2. Ask, via `AskUserQuestion` (so the user clicks, not types):
   - Age (number — context for recovery, not used in v1 math)
   - Height (number + unit)
   - Weight (number + unit)
   - Experience: Beginner (<1yr) · Intermediate (1-3yr) · Advanced (3yr+)
   - Equipment: Full gym · Home (dumbbells + bands) · Bodyweight only
   - Injuries/limitations: multi-select from the keys in `data/injury_exclusions.json`, plus free
     text, plus a "none" option
   - Units for future display: kg · lb
3. **After the injury question, echo the concrete consequence before writing anything.** Read
   the chosen injury's `exclude_sub_categories` / `exclude_name_keywords` from
   `data/injury_exclusions.json`, count how many of the 145 exercises that would remove, and say
   so in plain English: "Lower back — I'll exclude hip hinges and erector spinae work, about 15
   exercises. Sound right?" Let the user veto before it's written.
4. Write `profile/profile.json` matching the schema in `profile/profile.example.json`
   (`$schema_version`, timestamps, body stats, `experience_level`, `equipment`, `injuries: []`,
   `units`, plus the empty v2 hooks `training_history: []` and `current_plan: null`).
5. Tell the user to run `/plan` next.

## `--update`

Read the existing profile, ask only about the field(s) the user named (or ask which field if
they just said "update my profile"), rewrite those fields plus `updated_at`, and stop — this is
not a full re-interview.

## Rules

- Never read or write anything under `data/` — that's shipped, read-only reference data.
- Never invent defaults for injuries or equipment; if the user skips a question, ask again or
  leave it as an explicit "none"/"full_gym" rather than guessing.
- `profile/` is gitignored. This skill is the only writer of `profile/profile.json`.
