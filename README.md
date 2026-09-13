# Family Scale

A local-first household health tracker. Log only what you have: weight, waist,
runs, lifts, meals, or a day check-in. Gaps are fine.

## What it does

- Sparse logs: every field is optional except “at least one thing”
- Body: weight, waist, optional fasting interval for a rough resting-metabolism estimate
- Move: run / walk / hike / bike
- Lift: sessions and sets
- Day: sleep, energy, soreness, mood, steps (updates today’s card if you come back later)
- Eat: breakfast / lunch / dinner / snack, optional light / normal / heavy
- Progress graphs, 7-day weight average, weekly mileage, CSV export

The metabolism number is a household estimate (water vapor plus fasted fat
oxidation), not a lab RMR. Best with an evening + next-morning pair on the
same scale.

Future work is in [ROADMAP.md](ROADMAP.md).

## Run

```bash
python3 -m pip install -r requirements.txt
HT_HOST=127.0.0.1 HT_PORT=8088 python3 run.py
```

Open http://127.0.0.1:8088/

For LAN access, bind `HT_HOST=0.0.0.0` and put a real `HT_SECRET_KEY` in the
environment. Default bind is localhost only.

SQLite lives at `data/health.db` and is gitignored. Do not commit a live
database — it is personal health data.

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `HT_HOST` | `127.0.0.1` | Bind address |
| `HT_PORT` | `8088` | Port |
| `HT_SECRET_KEY` | placeholder | Set a long random string if you expose this beyond localhost |
| `HT_DATA_DIR` | `./data` | Database directory |
| `HT_TIMEZONE` | `America/New_York` | Display timezone |

User systemd is a fine way to keep it running on a home server; see your
own unit file, not this repo.
