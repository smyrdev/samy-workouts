# samy-workouts

An open-source Claude Code skill pack that replaces a fitness app. Clone it, run Claude Code
inside it, answer an interview, and get a weekly training plan computed — not vibed — from a
145-exercise volume database. No accounts, no subscription, no server. The repo is the app.

> **Not medical advice.** This is a volume-arithmetic tool, not a coach or a clinician. Injury
> filtering is a coarse keyword-and-category heuristic — see *Honest limitations* below — and
> `/onboard` will echo back exactly what it excludes so you can veto a bad call. If you have a
> real injury, talk to a professional, not this repo.

## Quickstart

```bash
git clone <this-repo>
cd samy-workouts
claude
```

Then, inside Claude Code:

```
/onboard   # one-time: age, body stats, experience, equipment, injuries
/plan      # every cycle: goal, volume target, days/week, session length, priorities
```

That's it. No `pip install`, no `npm i`, no API key, no MCP server to register. The two skills
call `python3` scripts that ship with the repo (stdlib only); if Python 3 isn't on your machine,
the `/plan` skill says so explicitly and falls back to rougher, clearly-labelled estimates.

Your plan lands in `profile/plans/plan-<date>.md` — plain markdown, readable on your phone at the
gym — plus a `plan-<date>.json` for anyone who wants the machine-readable version.

## How the volume-credit model works

Every exercise in `data/exercises_with_volume.json` carries a `volume` map: fractional **set
credits** per muscle, not importance weights.

```json
{
  "exercise_name": "Barbell overhead press",
  "volume": { "Front Delt": 1.0, "Lateral Delt": 1.0, "Triceps Medial & Lateral Heads": 1.0, "Upper Traps": 0.25 }
}
```

One set of Barbell overhead press credits a *full* set (`1.0`) to Front Delt, Lateral Delt, and
Triceps, and a *quarter* set (`0.25`) to Upper Traps. Do 4 sets of it, and:

```
Front Delt      += 4 × 1.0  = 4.0 sets
Lateral Delt    += 4 × 1.0  = 4.0 sets
Triceps M&L     += 4 × 1.0  = 4.0 sets
Upper Traps     += 4 × 0.25 = 1.0 sets
```

Sum that across every exercise in the week and you get real weekly volume per muscle —
`Σ(sets × credit)` — which `planner.py` compares against `data/volume_landmarks.json` (your
weekly MEV/MAV/MRV target band) to select exercises, and `verify.py` independently recomputes
before any plan is presented to you. Two separately-written implementations of the same sum
agreeing is the evidence the numbers are right — see `CLAUDE.md` for why those two files
deliberately don't share code.

## Editing the data

Everything under `data/` is plain, hand-editable JSON with `note` / `source_note` fields
explaining the reasoning in-file. If you disagree with a number, edit the JSON — you never need
to touch a prompt or a script:

- **`data/exercises_with_volume.json`** — the 145-exercise database.
- **`data/volume_landmarks.json`** — weekly MEV/MAV/MRV per muscle per experience level. Our
  authored starting point, not settled science.
- **`data/injury_exclusions.json`** — which sub-categories / name keywords get excluded per
  complaint.
- **`data/equipment_keywords.json`** — which exercises count as home-gym or bodyweight, by name
  keyword.

See `CONTRIBUTING.md` for the schema details and how to run the verification steps after an edit.

## Honest limitations

These are properties of the dataset, not bugs to fix — you deserve to know them before trusting a
plan:

1. **Injury filtering is coarse.** There's no injury field in the DB. Exclusion works on
   `sub_category` and exercise-name keywords. It will over-exclude safe variants and can
   under-exclude unsafe ones — `/onboard` echoes the exclusion list back so you can catch it.
2. **Equipment inference is keyword matching on exercise names.** A name with no equipment word
   defaults to full-gym-only. Fragile, and honestly so.
3. **Rep ranges are goal-derived, not data-derived.** The DB has no rep data.
4. **Nine exercises carry zero volume data** (all Neck, all Forearm, and Hip adduction) and are
   excluded from volume math entirely.
5. **Some muscles are barely reachable.** `Rectus femoris` appears in only 3 exercises,
   `Glute medius` in 6 — a plan may legitimately fall short of their MAV. They're marked
   `optional` in the landmarks file rather than silently failing.
6. **Landmarks are a starting point**, meant to be edited. `/plan` lets you choose low/moderate/
   high within them, but the underlying numbers are our authored opinion.
7. **Plans vary between runs, on purpose**, so re-planning monthly gives you something new. Want
   a specific plan back? Regenerate with its `metadata.seed`.
8. **v1 prescribes straight sets only** — no supersets, no rest periods, no tempo, no
   week-to-week progression. It's a weekly template, not a periodised program. Exercise *order*
   is computed (compound movements first); how you run the session otherwise is yours.

## Roadmap (not in v1)

- **`/log`** — session logging against the `logged_sets[]` field already in the plan schema.
- **`/progress`** — volume/adherence trends once logs exist, likely a dataviz artifact.
- **`/explain <exercise>`** — why a given exercise is in your plan, from its volume map.
- **`/adjust`, `/deload`** — plan-level volume multipliers; single-exercise swaps already ship
  today via `planner.py swap`.
- **Plan tournament** — generate several candidate splits in parallel, audit each, present the
  winner. The first real use for multi-agent orchestration in this repo.

## License

MIT — see `LICENSE`.
