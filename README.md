# fitness-api

A self-hosted FastAPI service for logging fitness and nutrition data to Intervals.icu and Garmin Connect. Designed to run as a Docker container on Unraid, exposed via Cloudflare Tunnel, and called by Claude.

---

## Project Structure

```
fitness-api/
├── Dockerfile
├── requirements.txt
├── README.md
└── app/
    ├── __init__.py
    ├── main.py              # FastAPI app entrypoint
    ├── config.py            # Env var loading
    ├── auth.py              # X-API-Key middleware
    ├── routers/
    │   ├── __init__.py
    │   ├── intervals.py     # Intervals.icu endpoints
    │   └── garmin.py        # Garmin Connect endpoints
    └── services/
        ├── __init__.py
        ├── intervals.py     # Intervals.icu API client
        └── garmin.py        # Garmin Connect wrapper
```

---

## Environment Variables

Set these in Unraid's container UI (not in a file). The container will fail fast at startup if any are missing.

| Variable | Description |
|---|---|
| `INTERVALS_API_KEY` | From intervals.icu Settings → Developer Settings |
| `INTERVALS_ATHLETE_ID` | From your intervals.icu URL — e.g. `i12345` |
| `GARMIN_EMAIL` | Your Garmin Connect account email |
| `GARMIN_PASSWORD` | Your Garmin Connect password |
| `FITNESS_API_KEY` | A secret you invent — used to authenticate requests to this API |

---

## Building & Running on Unraid

### 1. Place project files

Copy the project to your Unraid server:

```
/mnt/user/appdata/fitness-api/
```

### 2. Build the Docker image

From the Unraid terminal:

```bash
cd /mnt/user/appdata/fitness-api
docker build -t fitness-api:latest .
```

### 3. Add container in Unraid UI

Docker → Add Container:

| Field | Value |
|---|---|
| Name | `fitness-api` |
| Repository | `fitness-api:latest` |
| Network Type | Bridge |
| Port | Host `8000` → Container `8000` |

**Add Path:**

| Host path | Container path | Access |
|---|---|---|
| `/mnt/user/appdata/fitness-api/data` | `/data` | Read/Write |

**Add each env var** from the table above.

Click Apply.

### 4. Garmin first-run MFA

The Garmin session requires one interactive login. Run from the Unraid terminal after the container starts:

```bash
docker exec -it fitness-api python -m app.services.garmin --reauth
```

Follow the prompts. The session token is saved to `/data/garmin_tokens.json` and persists across restarts. Re-run this command if Garmin ever invalidates the session (typically after a few months or a password change).

---

## Cloudflare Tunnel

In Cloudflare Zero Trust, point a tunnel to:

```
http://your-unraid-ip:8000
```

No port forwarding needed. The public URL is what Claude uses to call the API.

---

## Authentication

Every request (except `/health`) requires:

```
X-API-Key: <FITNESS_API_KEY>
```

---

## API Reference

### Health check

```
GET /health
```

No auth required. Returns `{"status": "ok"}`.

### Interactive docs

```
GET /docs
```

FastAPI's built-in Swagger UI. Useful for testing endpoints manually.

---

### Intervals.icu — Wellness

#### Log weight and/or nutrition for a day

```
PUT /intervals/wellness/{date}
```

Date format: `YYYY-MM-DD`. This is a **raw passthrough** — the body must match the
[Intervals.icu Wellness schema](https://intervals.icu/api/v1/docs) exactly. No field
renaming, no unit conversion, no validation on this API's side. All fields optional —
only provided fields are written. PUT is non-destructive; omitted fields are not
overwritten.

Weight is in **kg**. Sleep is in **seconds**.

```json
{
  "weight": 86.0,
  "kcalConsumed": 2400,
  "protein": 180,
  "carbohydrates": 220,
  "fatTotal": 80,
  "sleepSecs": 27000,
  "restingHR": 52,
  "hrv": 68.4,
  "fatigue": 2,
  "soreness": 1,
  "mood": 4,
  "motivation": 4,
  "stress": 2,
  "comments": "Felt good today"
}
```

#### Get wellness records

```
GET /intervals/wellness?oldest=YYYY-MM-DD&newest=YYYY-MM-DD
GET /intervals/wellness/{date}
```

---

### Intervals.icu — Activities

```
GET  /intervals/activities?oldest=YYYY-MM-DD
GET  /intervals/activities/{activity_id}
POST /intervals/activities
PUT  /intervals/activities/{activity_id}
DELETE /intervals/activities/{activity_id}
```

---

### Intervals.icu — Events (planned workouts)

```
GET    /intervals/events?oldest=YYYY-MM-DD
GET    /intervals/events/{event_id}
POST   /intervals/events
PUT    /intervals/events/{event_id}
DELETE /intervals/events/{event_id}
```

---

### Intervals.icu — Sport Settings

```
GET /intervals/sport-settings
GET /intervals/sport-settings/{sport}
PUT /intervals/sport-settings/{sport}
```

Sport values: `Ride`, `Run`, `Swim`.

---

### Garmin — Weight

#### Log a weigh-in

```
POST /garmin/weight
```

Always pass `timestamp` in local time to avoid the UTC/local date boundary issue.

```json
{
  "weight_kg": 86.0,
  "timestamp": "2026-04-19T07:00:00"
}
```

#### Get weigh-in history

```
GET /garmin/weight?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
```

#### Delete a weigh-in

```
DELETE /garmin/weight/{weigh_in_id}
```

---

### Garmin — Body Composition

```
POST /garmin/body-composition
GET  /garmin/body-composition?log_date=YYYY-MM-DD
```

Body composition is uploaded via `.fit` file. Weight is required; all other fields optional.

---

### Garmin — Daily Health (read-only)

```
GET /garmin/stats?log_date=YYYY-MM-DD
GET /garmin/heart-rate?log_date=YYYY-MM-DD
GET /garmin/sleep?log_date=YYYY-MM-DD
GET /garmin/steps?log_date=YYYY-MM-DD
GET /garmin/profile
```

---

### Garmin — Activities

```
GET  /garmin/activities?start=0&limit=20
GET  /garmin/activities/{activity_id}
```

---

## Timezone Notes

Dates and timestamps are always passed explicitly by the caller — nothing defaults to server-side "now". This avoids writing to the wrong day when the server clock (UTC) is ahead of Eastern time (UTC-4/5).

**Rule:** always pass the date or timestamp you intend, in local time.

---

## Write Support Summary

| Operation | Target | Status |
|---|---|---|
| Weight | Intervals.icu wellness | ✅ Reliable |
| Weight | Garmin Connect | ✅ Reliable |
| Macros / calories | Intervals.icu wellness | ✅ Reliable |
| Macros / calories | Garmin Connect | ❌ No endpoint — use Intervals.icu wellness |
| Body composition | Garmin Connect | ✅ Via .fit upload |
| Planned workouts | Intervals.icu events | ✅ Reliable |

---

## Updating the Container

After code changes, rebuild and restart:

```bash
cd /mnt/user/appdata/fitness-api
docker build -t fitness-api:latest .
docker restart fitness-api
```

The Garmin session token in `/data` persists — no need to re-auth unless the session has expired.

---

## Usage with Claude

Once the Cloudflare Tunnel is live, provide Claude with:
- The public tunnel URL
- The `FITNESS_API_KEY` value

Claude will store these in memory and can call the API directly in future sessions to log weight, macros, and other wellness data on your behalf.

Example: *"Log my morning weight as 189.6 lbs for today"* → Claude calls `PUT /intervals/wellness/YYYY-MM-DD` and `POST /garmin/weight` with the appropriate payloads.
