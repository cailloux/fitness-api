# Claude Integration Reference

This document contains everything Claude needs to work with the fitness-api and Intervals.icu in future sessions. Store in the project root and reference at the start of new sessions.

---

## API Access

| Field | Value |
|---|---|
| Base URL | `https://fitness-api.grommet.co` |
| Auth header | `X-API-Key: REDACTED_ROTATE_ME` |
| Health check | `GET /health` (no auth required) |
| Swagger docs | `GET /docs` |
| Athlete ID | `i313152` |

---

## Key Conventions

- **Weight:** always passed in lbs — the API converts to kg internally
- **Dates:** always passed explicitly as `YYYY-MM-DD` — nothing defaults to server-side "today"
- **Timestamps:** always in local Eastern time (ET, UTC-4) — never rely on server UTC clock
- **Nutrition/macros:** Intervals.icu wellness only — Garmin nutrition write is not supported
- **Garmin weight:** always include `timestamp` in local time to avoid writing to the wrong day
- **Date resolution:** when the user says "yesterday" or "last Saturday", compute the explicit date and state it before making any API call so they can confirm

---

## Athlete Profile

Fetch current profile at any time: `GET /intervals/proxy/athlete`

Current values (as of April 2026 — fetch fresh if making zone-sensitive decisions):

### Run
| Setting | Value |
|---|---|
| Threshold pace | 7:29/mi |
| FTP (run power) | 432W |
| LTHR | 172 bpm |
| Max HR | 183 bpm |
| Pace units | min/mile |

Run pace zones (% of threshold pace):

| Zone | % of TP | Approx pace |
|---|---|---|
| Z1 | ~77.5% | ~9:40/mi |
| Z2 | ~87.7% | ~8:32/mi |
| Z3 | ~94.3% | ~7:56/mi |
| Z4 | ~100% | ~7:29/mi |
| Z5 | ~103.4% | ~7:14/mi |
| Z6 | ~111.5% | ~6:42/mi |

Run HR zones (bpm):
Z1 <126, Z2 126-140, Z3 140-154, Z4 154-166, Z5 166-176, Z6 >176

### Ride
| Setting | Value |
|---|---|
| FTP | 193W |
| LTHR | 169 bpm |
| Max HR | 186 bpm |

Ride HR zones (bpm):
Z1 <115, Z2 115-140, Z3 140-159, Z4 159-178, Z5 >178

### General
| Setting | Value |
|---|---|
| Resting HR | 41 bpm |
| Measurement | Imperial |
| Timezone | America/New_York |

**Athlete zones are read-only via API.** If asked to update FTP, LTHR, HR zones, or pace zones, instruct the user to do it manually: **Settings -> select the sport -> update the value** in the Intervals.icu UI. Always re-fetch the profile before making zone-sensitive workout decisions.

---

## Common Workflows

### Morning weight log
Logs to both Intervals.icu and Garmin simultaneously.

```
PUT /intervals/wellness/YYYY-MM-DD
{"weight_lbs": 189.6}

POST /garmin/weight
{"weight_lbs": 189.6, "timestamp": "YYYY-MM-DDTHH:MM:SS"}
```

### Nutrition / macros (Intervals.icu only)
```
PUT /intervals/wellness/YYYY-MM-DD
{"calories": 2400, "protein_g": 180, "carbs_g": 220, "fat_g": 80}
```

### Combined weight + nutrition
```
PUT /intervals/wellness/YYYY-MM-DD
{"weight_lbs": 189.6, "calories": 2400, "protein_g": 180, "carbs_g": 220, "fat_g": 80, "comments": "Optional free text"}
```

### Read any Intervals.icu data
```
GET /intervals/proxy/activities?oldest=2026-04-01&newest=2026-04-20
GET /intervals/proxy/activities/i123456789
GET /intervals/proxy/wellness?oldest=2026-04-01
GET /intervals/proxy/events?oldest=2026-04-20&newest=2026-04-27
GET /intervals/proxy/sport-settings/Ride
GET /intervals/proxy/athlete
```

### Create or update a planned workout
```
POST /intervals/proxy/events
PUT  /intervals/proxy/events/{event_id}
```

---

## Intervals.icu Domain Knowledge

### Subjective Score Scales

| Field | Scale | Notes |
|---|---|---|
| `fatigue` | 1-5 | 1=fresh, 5=exhausted |
| `soreness` | 1-5 | 1=none, 5=severe |
| `mood` | 1-5 | 1=poor, 5=great |
| `motivation` | 1-5 | 1=none, 5=high |
| `stress` | 1-5 | 1=none, 5=extreme |
| `sleep_quality` | 1-4 | 1=poor, 4=excellent |
| `readiness` | 0-100 | Higher = more ready to train |

### Planned Workout Description Format

The `description` field in event create/update payloads uses a structured plain-text format. Intervals.icu parses it automatically for duration, training load, and visualisation.

#### Duration vs Distance

Steps can be time-based or distance-based:

- Time: `30s`, `10m`, `1m30`, `1h`, `1h30m`
- Distance: `1km`, `1mi`, `1mile`, `400mtr`, `400meters`, `400yrd`, `400yards`, `400y`
- Space between number and unit is fine: `1 km`, `400 mtr`
- Note: `m` means **minutes**, not metres. Use `mtr` for metres.

#### Target Types

Every step MUST include one target. Options:

| Target | Example | Notes |
|---|---|---|
| Absolute watts | `242w` | Power meter only |
| % of FTP | `80%`, `80-90%` | Range auto-normalized to midpoint |
| Power zone | `Z2` | Bare zone = power zone (cycling) |
| HR zone | `Z2 HR` | Must end with `HR` |
| % max HR | `75% HR`, `75-80% HR` | Must end with `HR` |
| % LTHR | `90% LTHR` | Must end with `LTHR` |
| Pace zone | `Z2 Pace` | Must end with `Pace` |
| Absolute pace | `5:00 Pace`, `7:29 Pace` | Must end with `Pace`; min/mile for Tim |
| % threshold pace | `90% Pace` | Must end with `Pace` |
| Swim pace | `1:45/100m` | Combined with distance step |
| Cadence | `90rpm`, `90-100rpm` | Can be added alongside any target |
| Ramp | `Ramp 100-200w`, `Ramp 60-80%` | Progressive power step |

#### Target Selection by Sport

- **Run:** watts if power meter; else pace zone (`Z2 Pace`) or absolute pace (`7:30 Pace`) for pace athletes; else HR zone (`Z2 HR`)
- **Ride:** watts if power meter; else HR zone (`Z2 HR`). Pace syntax NOT supported for cycling.
- **Swim:** distance + pace (e.g. `400mtr 1:45/100m`); or HR zone if no pace preference

#### Step Text Prompts

Any text before the duration/target becomes a label on the step:
```
- Recovery 30s 50%
- Easy spin 5m Z1 HR
```

#### Full Format Examples

**Easy run (distance-based):**
```
Main Set 1x
- 6mi Z2 Pace intensity=warmup
```

**Easy run (time-based):**
```
Main Set 1x
- 60m Z2 Pace intensity=warmup
```

**Tempo run (distance-based):**
```
Warmup
- 1mi Z1 Pace intensity=warmup

Main Set 1x
- 6mi Z4 Pace intensity=interval

Cooldown
- 1mi Z1 Pace intensity=cooldown
```

**Interval run:**
```
Warmup
- 10m Z1 Pace intensity=warmup

Main Set 6x
- 800mtr Z5 Pace intensity=interval
- 400mtr Z1 Pace intensity=recovery

Cooldown
- 10m Z1 Pace intensity=cooldown
```

**Power-based ride:**
```
Warmup
- 20m 60% 90-100rpm intensity=warmup

Main Set 6x
- 4m 100% 40-50rpm intensity=interval
- 5m 40% intensity=recovery

Cooldown
- 20m 60% 90-100rpm intensity=cooldown
```

**Ramp ride:**
```
Warmup
- 10m Z1 HR intensity=warmup

Main Set 1x
- Ramp 20m 60-100% intensity=interval

Cooldown
- 10m Z1 HR intensity=cooldown
```

**Swim:**
```
Main Set 4x
- 200mtr 1:45/100m intensity=interval
- 30s Z1 HR intensity=recovery
```

#### General Rules

- Bullets are always `-`
- `intensity=` flags always present: `warmup`, `cooldown`, `interval`, `recovery`
- Recovery/easy runs: single `Main Set 1x` only — no Warmup/Cooldown sections
- Structured workouts with intensity changes: Warmup + Main Set(s) + Cooldown
- Each distinct effort block is its own `Main Set 1x` with empty lines before and after
- Repeat intervals use `Main Set Nx` with `intensity=interval` / `intensity=recovery` pairs
- Pace ranges normalized to midpoint: `4:55-5:10 Pace` -> `5:02 Pace`
- Swim workouts render as structured text without coloured zone charts (expected)
- `Press lap ..` can be added to a step for Garmin lap-button workouts

### Editing Workouts — Confirmation Required

Before calling `PUT /intervals/proxy/events/{id}` to edit a workout, always summarise the changes (including workout name and date) and ask the user to explicitly confirm before proceeding.

### Best Efforts — Available Data by Sport

| Sport | Available |
|---|---|
| Run | Fastest time/pace for 400m, 1km, 5km, 10km, half, marathon. Best power by duration if running power meter present. |
| Ride | Best mean-maximal power (watts + W/kg) for key durations. |
| Swim | Fastest time/pace per 100m for 100m, 200m, 400m, 800m, 1500m. |

Fetch via proxy: `GET /intervals/proxy/athlete/best-efforts` or query training history.

---

## API Reference

### Intervals.icu — Wellness (typed, with unit conversion)

| Method | Path | Description |
|---|---|---|
| `PUT` | `/intervals/wellness/{date}` | Create or update wellness record |
| `GET` | `/intervals/wellness/{date}` | Get single day |
| `GET` | `/intervals/wellness?oldest=&newest=` | Get date range |

All fields optional. Only provided fields are written (PUT is non-destructive).

| Our field | Type | Intervals.icu field | Notes |
|---|---|---|---|
| `weight_lbs` | float | `weight` | Converted to kg |
| `calories` | int | `kcalConsumed` | kcal |
| `protein_g` | float | `protein` | grams |
| `carbs_g` | float | `carbohydrates` | grams |
| `fat_g` | float | `fatTotal` | grams |
| `sleep_hours` | float | `sleepSecs` | Converted to seconds |
| `sleep_score` | float | `sleepScore` | |
| `sleep_quality` | int | `sleepQuality` | 1-4 |
| `avg_sleeping_hr` | float | `avgSleepingHR` | bpm |
| `resting_hr` | int | `restingHR` | bpm |
| `hrv` | float | `hrv` | ms |
| `hrv_sdnn` | float | `hrvSDNN` | ms |
| `spO2` | float | `spO2` | % |
| `systolic` | int | `systolic` | mmHg |
| `diastolic` | int | `diastolic` | mmHg |
| `respiration` | float | `respiration` | |
| `baevsky_si` | float | `baevskySI` | |
| `body_fat` | float | `bodyFat` | % |
| `abdomen` | float | `abdomen` | |
| `blood_glucose` | float | `bloodGlucose` | |
| `lactate` | float | `lactate` | |
| `vo2max` | float | `vo2max` | |
| `fatigue` | int | `fatigue` | 1-5 |
| `soreness` | int | `soreness` | 1-5 |
| `mood` | int | `mood` | 1-5 |
| `motivation` | int | `motivation` | 1-5 |
| `stress` | int | `stress` | 1-5 |
| `injury` | int | `injury` | |
| `readiness` | float | `readiness` | 0-100 |
| `hydration` | int | `hydration` | |
| `hydration_volume` | float | `hydrationVolume` | |
| `steps` | int | `steps` | |
| `comments` | str | `comments` | Free text |

### Intervals.icu — Generic Proxy (full API surface)

```
GET|POST|PUT|DELETE /intervals/proxy/{path}
```

Athlete ID is prepended automatically. Pass the path after `/athlete/{id}/`.
Query parameters and request body forwarded as-is — use Intervals.icu native camelCase field names when writing via proxy directly.

Common paths:

```
GET  /intervals/proxy/athlete
GET  /intervals/proxy/activities?oldest=2026-04-01
GET  /intervals/proxy/activities/{id}?intervals=true
POST /intervals/proxy/activities/manual
GET  /intervals/proxy/events?oldest=2026-04-20&newest=2026-04-27
POST /intervals/proxy/events
PUT  /intervals/proxy/events/{id}
DELETE /intervals/proxy/events/{id}
GET  /intervals/proxy/sport-settings/Ride
GET  /intervals/proxy/wellness/2026-04-20
```

Sport settings are **read-only** — do not PUT on sport-settings.

### Garmin — Weight and Body Composition

| Method | Path | Description |
|---|---|---|
| `POST` | `/garmin/weight` | Log weigh-in |
| `GET` | `/garmin/weight?start_date=&end_date=` | Weigh-in history |
| `DELETE` | `/garmin/weight/{id}` | Delete weigh-in |
| `POST` | `/garmin/body-composition` | Upload body comp (.fit) |
| `GET` | `/garmin/body-composition?log_date=` | Get body comp |

### Garmin — Daily Health (read-only)

| Method | Path |
|---|---|
| `GET` | `/garmin/stats?log_date=` |
| `GET` | `/garmin/heart-rate?log_date=` |
| `GET` | `/garmin/sleep?log_date=` |
| `GET` | `/garmin/steps?log_date=` |
| `GET` | `/garmin/profile` |

### Garmin — Nutrition

Not supported — Garmin's API is food-database-based.
`POST /garmin/nutrition` returns 501. Use `PUT /intervals/wellness/{date}` for macros.

---

## Infrastructure

| Detail | Value |
|---|---|
| Host | Unraid server "kirk" |
| Project path | `/mnt/user/files/cailloux/Code/fitness-api` |
| Container name | `fitness-api` |
| Garmin token path | `/data/garmin_tokens` (inside container) |
| Host token path | `/mnt/user/appdata/fitness-api/data` |
| Tunnel | Cloudflare — no port forwarding required |

### Rebuild after code changes
```bash
cd /mnt/user/files/cailloux/Code/fitness-api
docker build --no-cache -t fitness-api:latest .
docker stop fitness-api && docker rm fitness-api
# Recreate via Unraid Docker UI -> Apply
```

### Re-authenticate Garmin (if session expires)
```bash
docker exec -it fitness-api python -m app.services.garmin --reauth
```

---

## Write Support Summary

| Data | Intervals.icu | Garmin |
|---|---|---|
| Weight | yes | yes |
| Calories | yes | no |
| Macros (protein/carbs/fat) | yes | no |
| Body composition | no | yes via .fit upload |
| HRV / sleep / subjective scores | yes | no |
| Planned workouts | yes | yes |
| Activity upload | yes | yes |
| Athlete zones / FTP | no — read-only | no |
