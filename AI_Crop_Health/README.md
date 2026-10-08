# AI Crop Health

Django platform combining crop-disease diagnosis, land leasing, IoT field
monitoring and agronomic recommendations.

## What's in here

| App | Purpose |
|---|---|
| `detection` | Leaf-disease CNN diagnosis, crop & fertilizer recommendation, chatbot, advisory |
| `iot_sensor` | Fields, sensor nodes, readings, irrigation commands, alerts, zone optimisation |
| `agrolease` | Land listings, lease requests, agreements, KYC verification |
| `accounts` | Global OTP login (phone/email) and the global user profile |
| `features` | Weather, market prices, crop info, government schemes |
| `marketplace` | Product catalogue, cart, orders |
| `blog`, `contact` | Content pages, author profiles, enquiries |
| `core` | Audit logging, notifications, request-context middleware |

---

## Quickstart

Requires **Python 3.11**.

```bash
# 1. Virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

# 2. Dependencies
pip install -r requirements.txt

# 3. Configuration
cp .env.example .env
```

Now generate a secret key and paste it into `.env` as `SECRET_KEY`:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

```bash
# 4. Database
python manage.py migrate

# 5. Admin user
python manage.py createsuperuser

# 6. Run
python manage.py runserver
```

Open http://127.0.0.1:8000/ — admin is at `/admin/`.

Django will refuse to start if `SECRET_KEY` is missing. Every other variable in
`.env.example` is optional; the app degrades gracefully without the API keys
(Gemini cross-validation and weather simply switch off).

### Checking the project is healthy

This repository deliberately contains no test files. Verify a change by hand:

```bash
python manage.py check            # configuration and model problems
python manage.py makemigrations --check --dry-run   # nothing unmigrated
python manage.py runserver        # then click through the pages you changed
```

Before deploying, also run the production checklist:

```bash
DJANGO_DEBUG=False python manage.py check --deploy
```

---

## IoT devices

Field hardware (ESP32 / Raspberry Pi) posts readings to
`POST /iot/api/ingest/`.

**Every request must carry the device's own key** in the `X-Device-Key` header.
`device_id` identifies a device; it does not authenticate it. Without the header
the endpoint returns `401` and stores nothing.

```http
POST /iot/api/ingest/
Content-Type: application/json
X-Device-Key: <the key shown when you registered the device>

{
  "device_id": "ESP32-001",
  "soil_moisture_pct": 32.4,
  "nitrogen_ppm": 140,
  "phosphorus_ppm": 58,
  "potassium_ppm": 201,
  "soil_ph": 6.8,
  "temperature_c": 28.3,
  "humidity_pct": 72.1,
  "packet_id": "PKT-20240115-001"
}
```

Responses: `201` stored, `200 {"status":"duplicate"}` for a repeated
`packet_id`, `401` authentication failed, `413` body over 16 KB,
`429` rate limit (240 readings per device per hour).

Send a unique `packet_id` per reading. If the device retries after a lost
response the server recognises the duplicate and does not store it twice.

### Registering a device

1. Sign in and go to **My Farm → My Hardware** (`/iot/hardware/`).
2. Add a field, then register the device against it.
3. **The device key is displayed once.** Copy it into your firmware. If you lose
   it, rotate the key from Django admin (*Sensor nodes → Rotate device API key*)
   and reflash — the old key stops working immediately.

### Who can register hardware

Either path unlocks it:

- the account is **verified** by an admin, or
- the user is a **farmer with an approved lease** on land.

Required documents differ by role, because a farmer who leases land cannot
produce ownership proof:

| Role | Documents |
|---|---|
| Land owner | government ID, ownership proof, address proof |
| Farmer | government ID, address proof, selfie photo |

Admins review and approve or reject in Django admin under
**Agrolease → Agro profiles**. A rejection reason is shown back to the user so
they can re-upload.

---

## Admin panel

Everything is managed at `/admin/`.

### Customising the site without a deploy

**Core -> Site settings** is a single page holding what used to live in `.env`:

| Group | What you can change |
|---|---|
| Identity | Site name, tagline, logo |
| Link preview | The image shown when a link is shared on WhatsApp/Facebook/X |
| Contact | Email, phone, WhatsApp number, address |
| Social profiles | Facebook, X, Instagram, LinkedIn, YouTube |
| Analytics | Script URL and site ID |
| Features on/off | Marketplace, IoT, chatbot, land leasing, new sign-ups |
| Crop diagnosis | Confidence threshold and the disclaimer shown to farmers |
| Maintenance | Maintenance mode, its message, and a site-wide announcement banner |

A blank social field **hides** that icon rather than rendering a dead link.
Changes appear within 5 minutes (the settings row is cached), or immediately on
the next page load after saving.

Real secrets — `SECRET_KEY`, database credentials, API keys — stay in `.env` on
purpose. They do not belong in a database that staff can read.

Copy your existing `.env` branding into the editable row once:

```bash
python manage.py seed_site_settings --with-content
```

`--with-content` also creates starter hero slides and feature cards.

### Homepage content

**Core -> Homepage hero slides** and **Core -> Homepage feature cards** control
the carousel and the feature tiles. Drag the sort order, tick to show or hide,
and upload images (compressed automatically). If no slides exist the homepage
falls back to its built-in ones, so it is never empty.

### Staff roles

```bash
python manage.py setup_admin_roles          # create/update the roles
python manage.py setup_admin_roles --list   # show what each role can do
```

| Role | Can do | Deliberately cannot |
|---|---|---|
| Verification Reviewer | Approve farmer/owner KYC | Touch products or content |
| Content Editor | Blog, schemes, crop info, products, homepage | **See any identity document** |
| Support Agent | Enquiries, feedback, read diagnoses | Change a diagnosis |
| Field Operations | Devices, thresholds, irrigation | See personal data |
| Marketplace Manager | Products and orders | Everything else |

To assign one: **Users -> pick a user -> tick "Staff status" -> add to a group.**
Do **not** also tick "Superuser" — that overrides every restriction above.

> A broader legacy `Staff` group also exists (from `setup_staff_group`) and does
> grant KYC access. Use the scoped roles above for new staff.

### Exporting data

Most list pages have **Export selected to CSV**. Exports are capped at 50,000
rows, open correctly in Excel, and neutralise cells starting with `=`, `+`, `-`
or `@` so a malicious submission cannot run as a spreadsheet formula.

---

## Leaf-disease model

`detection/ml_engine/plant_disease/` holds a MobileNetV1 (224×224) classifier
over the 38-class PlantVillage label set.

**The model's accuracy has not been measured.** There is no held-out evaluation
and no labelled test split in this repository, so no accuracy figure is
published anywhere in the code or UI. `CONFIDENCE_THRESHOLD` gates an individual
prediction's confidence; it is not a statement about model accuracy.

Two things to know before relying on the confidence number:

- **It is uncalibrated by default.** Raw softmax over 38 classes is heavily
  overconfident. Set `PLANT_DISEASE_TEMPERATURE` once you have fitted a
  temperature on a labelled validation split; until then a warning is logged at
  startup. Predictions are additionally gated on top-2 margin and entropy, which
  need no fitting.
- **The label map must match the model head.** The predictor refuses to start if
  `class_indices.json` and the model's output size disagree. This guard exists
  because a 38-output model was once paired with a 35-entry label file, which
  silently mislabelled every prediction above index 3 — including reporting
  diseased leaves as healthy at 100% confidence. Always ship the
  `class_indices.json` produced by the same training run as the weights.

`AI_Crop_Health_Training.ipynb` (repo root) trains an EfficientNetV2B0 and is
the intended replacement backbone. It has no saved outputs and did not produce
the currently deployed `.h5`.

---

## Deployment notes

- `DJANGO_DEBUG=False` turns on SSL redirect, secure cookies, HSTS and
  nosniff. Set real hosts in `ALLOWED_HOSTS` in `AI_Crop_Health/settings.py`.
- **SQLite is the current database and will not survive concurrent sensor
  writes.** Switch to PostgreSQL (there is a commented block in `settings.py`
  and `DB_*` variables in `.env.example`) before connecting real field hardware.
- Run `python manage.py collectstatic` and serve `STATIC_ROOT` from the web
  server, and serve `MEDIA_ROOT` too — Django only serves media while `DEBUG`
  is on.
- Logs are written to `logs/django.log` as UTF-8.
- `python manage.py compute_daily_metrics` aggregates IoT metrics; schedule it
  daily. `python manage.py seed_demo_data` creates demo fields and readings.

---

## Troubleshooting

**"SECRET_KEY not set in .env file"** — you skipped step 3. Copy
`.env.example` to `.env` and generate a key.

**Leaf diagnosis unavailable / "Failed to load model"** — check
`logs/django.log`. The model is a Keras 2 H5 file and needs `tf_keras`
installed (it is in `requirements.txt`); loading it with Keras 3 directly
fails on `DepthwiseConv2D`.

**Device gets 401 from `/iot/api/ingest/`** — the `X-Device-Key` header is
missing or wrong, or the node is marked inactive. The same 401 is returned for
an unknown `device_id`, deliberately, so the endpoint cannot be used to discover
which devices exist.

**Farmer sees an empty field dashboard** — they can only see fields they own or
fields linked to land they hold an *approved* lease on. `owner_approved` is not
enough; it still awaits admin review.
