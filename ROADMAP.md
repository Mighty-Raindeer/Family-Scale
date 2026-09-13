# Family Scale — future development

Local household health tool. Family-first, tracking-first.
Advice only after there is enough personal data to say something specific.

**Now:** people, weigh-ins, progress graph, fasting-interval metabolism estimate.

The rest of this file is the intended order of work. Do not skip ahead to
recommendations or plans until the matching tracker has been used for a while.

---

## Principles

1. **Capture stays faster than the habit.** A weigh-in is ten seconds. A run
   log should be “distance, time, how hard,” not a full training diary on day
   one. If logging is heavier than doing the thing, it will die.
2. **One person, many streams.** Weight, runs, lifts, food, and sleep all hang
   off the existing `people` row. Never fork a second “user” model.
3. **Store facts, derive opinions.** Raw entries are sacred. kcal/day, TDEE,
   “you’re under-recovered,” and next week’s plan are computed views and can
   be wrong. They must be labeled as estimates.
4. **Family, not a social network.** Per-person pages, no leaderboards, no
   public sharing. Optional household dashboard later (who hasn’t logged this
   week) is enough.
5. **Keep it small.** Prefer SQLite, server-rendered pages, and no local LLM.
   Phone use is LAN or a personal VPN, so mobile-first forms matter more
   than native apps.
6. **No advice without a goal and a baseline.** Recommendations need a stated
   goal (lose / maintain / gain / race / get stronger) plus enough history to
   beat a generic internet calculator.

---

## Stage 0 — Finish the body-weight core

Do this before adding other sports. It is the spine everything else reads.

| Item | Why |
|------|-----|
| Optional timestamp edit | Fix a missed morning weigh-in without lying about “now.” |
| Waist (and maybe chest/hip) | Weight alone hides recomposition. Tape is cheap and local. |
| Weigh-in protocol presets | “Morning fasted” vs “random.” Makes metabolism pairs easier. |
| Moving average on the graph | 7-day average so one salty dinner doesn’t look like failure. |
| Export / backup | SQLite copy + CSV. Same idea as Homeowner’s Journal. |
| Per-person goals | Target weight or “maintain.” Needed before any recommendation. |
| Auth or at least a PIN | Health data on the LAN. Fine for now; not fine once food photos exist. |

Keep the fasting metabolism check. Later it becomes one input to TDEE, not
the only calorie number in the app.

---

## Stage 1 — Tracking: movement

**Goal:** know what the household actually did this week.

### 1a. Runs and walks (first activity)

One `Activity` table, type = run | walk | hike | bike | other.

Minimum fields:

- person, when, duration
- distance (miles, matching the lb household)
- how hard (1–10 RPE or easy / steady / hard)
- optional note

Later, not now: GPS files, maps, shoe mileage, heart-rate import, races as
events. A phone can type 3.2 miles and 28:00 after a jog. That is the product.

Progress view: weekly mileage, easiest pace trend, last 8 weeks. No
“recommended long run” until Stage 3.

### 1b. Strength (second activity)

Model it as **sessions**, not a giant spreadsheet on day one.

- `Workout` — person, date, title (“Tuesday push”), duration, note
- `Set` — workout, exercise name, reps, weight, optional RPE
- `Exercise` — small household library (squat, bench, hinge, pull, carry)

Start with a short default list plus “add exercise.” Do not build a 400-move
catalog.

Progress view: last weight × reps per exercise, simple estimated 1RM later
(Epley is enough). Body-weight exercises store reps only.

### 1c. Daily check-in (the glue)

A one-screen evening log, optional per person:

- steps or “moved / didn’t” if no watch
- sleep hours + quality
- energy / soreness (1–5)
- mood (optional)

This is what lets later recommendations say “mileage is up and sleep is
down,” instead of inventing recovery from mileage alone.

---

## Stage 2 — Tracking: food and energy in

**Goal:** know intake well enough to explain the weight graph. Not to become
MyFitnessPal.

Build this in three rungs. Stop at the first rung that the household will
actually use.

| Rung | What you log | Good enough for |
|------|----------------|-----------------|
| **A. Meals as events** | Breakfast / lunch / dinner / snack, plus “light / normal / heavy” | Spotting “weekends are the surplus” |
| **B. Rough plate** | Protein-ish / carb-ish / veg, or a photo + a typed estimate | Better than nothing for TDEE |
| **C. Quantified food** | Grams + a small household food list (oatmeal, milk, chicken…) | Real calorie math |

Do **not** start at C. A USDA-scale database on this machine is a maintenance
trap, and full calorie logging has the worst dropout rate of anything in this
plan.

Household recipe box (spaghetti, tacos, school lunches) is more valuable than
a million branded barcodes. If a barcode lookup is ever added, cache it
locally and treat it as optional.

Protein deserves its own simple target earlier than full macros. Strength
progress without protein context is a common miss.

---

## Stage 3 — Recommendations (read-only advice)

Only after Stage 0 goals exist and there is **several weeks** of the relevant
tracker. Each recommendation names the data it used.

### 3a. Energy balance (weight + optional food)

- Trend weight (7-day average) → weekly rate of change
- If food is only rung A/B: “weight implies ~X kcal/day surplus/deficit”
- If food is rung C: compare logged intake vs implied TDEE
- Fasting RMR from the scale is a **check**, not the daily budget
- Mifflin–St Jeor stays the fallback when there is no trend yet

Output should sound like: “Last 21 days, this person is losing ~0.4 lb/week,
which is roughly a 200 kcal/day deficit at this weight. Overnight fasting
pairs have been ~1700–1900 kcal/day.”

Not: “Eat 1,743 calories tomorrow.”

### 3b. Training load vs recovery

From runs + check-ins:

- Mileage or minutes up > ~20% week-over-week → “easy week” nudge
- Hard days stacked with poor sleep → “don’t add a fourth hard session”
- Long gap since last run → “start shorter than last peak”

From lifts:

- Same exercise, stalled 3+ sessions, sleep/soreness bad → deload suggestion
- Fast progress + low soreness → “add a set or 5 lb,” not a new program

### 3c. Guards (always on)

- Kids / teens: tracking only, no cut recommendations
- Pregnancy / injury flags if we ever add them
- Never recommend extreme deficits or “earn your food”
- Every advice card has a “this is not medical advice” line and a dismiss

Recommendations are a **feed of cards** on the person page, not pop-ups
during a weigh-in. Logging must stay calm.

---

## Stage 4 — Planning (write a week, then adjust)

Plans are drafts the person can edit. The app proposes; the household
decides.

### 4a. Weekly training plan

Inputs: goal (race / consistency / get stronger), available days, recent
load, sleep.

Outputs: a simple week — e.g. 3 runs (easy / easy / long) or 3 lift days
(push / pull / legs) with suggested exercises from **that person’s** library.

After the week, compare planned vs logged. The next proposal starts from
what they actually did, not from the fantasy calendar.

### 4b. Weight and calorie targets

Only with a goal and a trend:

- “To lose ~0.5 lb/week, aim near X kcal if you keep logging like this”
- Recalculate every 2 weeks from the graph, not from a one-time BMR
- Strength + deficit: remind that the scale may stall while waist drops

### 4c. Meals (last)

Meal planning only if food tracking is at least rung B and someone wants
it. Start with “repeat last week’s dinners” and a protein target, not
generated macros for every plate.

---

## Suggested build order

Concrete slices, each shippable on its own:

| Slice | Stage | Ships |
|-------|-------|--------|
| 0.1 | 0 | Edit weigh-in time, 7-day average, CSV export |
| 0.2 | 0 | Waist + per-person goal |
| 1.1 | 1 | Run/walk log + weekly mileage graph |
| 1.2 | 1 | Lift session + sets + last-time-you-did-this |
| 1.3 | 1 | Evening check-in (sleep, energy, soreness) |
| 2.1 | 2 | Meal events (light / normal / heavy) |
| 2.2 | 2 | Household food list + optional calories |
| 3.1 | 3 | Weight-trend TDEE card |
| 3.2 | 3 | Load/recovery cards from runs + sleep |
| 3.3 | 3 | Lift stall / add-weight cards |
| 4.1 | 4 | Editable weekly plan vs logged |
| 4.2 | 4 | Recalculating calorie target from trend |
| 4.3 | 4 | Dinner repeat / protein plan |

Skip a slice if the household is not using the slice under it. A lift planner
with no lift logs is theater.

---

## Data sketch

Keep SQLite. Add tables; do not rewrite the app.

```
people              (exists)
measurements        (exists: weight + fasting flags)
body_metrics        waist_cm, optional others, recorded_at
goals               person, type, target, start, active
activities          person, type, started_at, duration_s, distance_m, rpe, notes
workouts            person, started_at, title, notes
exercises           name, family (squat/hinge/push/pull/carry/other)
sets                workout, exercise, reps, weight_kg, rpe
checkins            person, date, sleep_h, energy, soreness, steps
food_entries        person, eaten_at, kind (meal|item), size, kcal?, notes
foods               household catalog: name, default_kcal, protein_g
advice_events       computed cards, dismissed_at (so we don't nag)
plans               week_start, person, payload json (sessions + targets)
plan_items          planned vs completed activity/workout ids
```

Estimates (RMR, TDEE, 1RM, weekly load) stay in Python modules, same as
`app/metabolism.py`. Do not persist them as if they were measurements.

---

## Product shape

- **Log** stays the home page. Tabs or a single “what happened” chooser:
  weight / run / lift / meal / check-in.
- **Progress** grows sections per stream, still one person at a time.
- **Person** holds profile, goals, and the advice feed.
- **Plan** appears only in Stage 4, as its own page, not stuffed into Log.

Phone on the LAN or a personal VPN is the real client. Big taps, few fields,
last-used person remembered (already started).

---

## Integrations (later, optional)

Useful only after the matching tracker exists:

| Source | Use |
|--------|-----|
| Phone share-sheet / PWA | “Add to Home Screen” so logging is one tap |
| GPX / Garmin / Strava export file | Fill Activity distance/time; never require the cloud |
| Home Assistant | Morning reminder, not auto-creating fake weigh-ins |
| Watch / Health Connect CSV | Steps and sleep into check-ins |

Do not make the app depend on an account at Garmin, Strava, or MyFitnessPal.

---

## Out of scope until much later

- Coaching chatbots or a local LLM
- Medical diagnosis, bloodwork, medication
- Social features, sharing, comparison between family members as scores
- Supplement stacks, grocery store APIs, restaurant menus
- Native iOS/Android apps (PWA first)
- Automatic calorie counts from photos

---

## How to know a stage is done

- **Tracking:** that stream has been logged on most active days for 3+ weeks
  without nagging.
- **Recommendations:** a person can point at a card and the numbers on it
  match their graph.
- **Planning:** at least half of last week’s plan items were completed or
  explicitly skipped — if everything is skipped, the planner is too ambitious.

When in doubt, add a better log screen, not a smarter opinion.
