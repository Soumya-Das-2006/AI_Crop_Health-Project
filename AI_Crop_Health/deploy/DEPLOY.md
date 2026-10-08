# Deploying AI Crop Health

Target: **AWS Lightsail, Mumbai (ap-south-1)**, Ubuntu 24.04, 2 GB plan.
Free for the first 3 months on a new Lightsail account, then ~$12/month, which
your AWS free-tier credits cover comfortably for the full 6 months.

Everything here also works unchanged on any Ubuntu VPS (DigitalOcean, Hetzner,
Lightsail, EC2) — only step 1 is AWS-specific.

---

## Before you start

You need:

- The domain you will point at the server (or skip TLS and use the raw IP for now)
- Your `.env` values: `GROQ_API_KEY`, `CROP_HEALTH_API_KEY`, `INSECT_ID_API_KEY`,
  `GEMINI_API_KEY`, `OPENWEATHER_API_KEY`, `EMAIL_HOST_PASSWORD`
- A fresh `SECRET_KEY` (generated in step 5 — do **not** reuse the local one)

---

## 1. Create the instance

Lightsail console → Create instance:

| Setting | Value |
|---|---|
| Region | **Mumbai (ap-south-1)** — closest to your users |
| Platform | Linux/Unix |
| Blueprint | **OS Only → Ubuntu 24.04 LTS** (not the Django blueprint; it is outdated) |
| Plan | **2 GB RAM / 2 vCPU / 60 GB SSD** |

Then:

- **Networking → attach a static IP.** Without this the IP changes on every
  stop/start and your DNS silently breaks.
- **Networking → firewall:** allow HTTP (80) and HTTPS (443). SSH (22) is open
  by default.
- **Snapshots → enable automatic snapshots.** This is your only backup. The
  database and every farmer photo live on this one disk.

Set a billing alarm now, in the AWS Budgets console. It is free, it is one of
the five activities that earn the extra $100 of credits, and it is the only
thing that will tell you if something starts quietly consuming them.

---

## 2. System packages

SSH in, then:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-venv python3-dev build-essential \
                    postgresql postgresql-contrib \
                    nginx git libpq-dev
```

---

## 3. PostgreSQL

Running Postgres on the same box rather than Lightsail's managed database saves
$15/month — a third of your credit budget — for a workload this size.

```bash
sudo -u postgres psql
```

```sql
CREATE DATABASE crophealth;
CREATE USER crophealth WITH PASSWORD 'CHANGE_ME_TO_SOMETHING_LONG';
ALTER ROLE crophealth SET client_encoding TO 'utf8';
ALTER ROLE crophealth SET default_transaction_isolation TO 'read committed';
ALTER ROLE crophealth SET timezone TO 'Asia/Kolkata';
GRANT ALL PRIVILEGES ON DATABASE crophealth TO crophealth;
\c crophealth
GRANT ALL ON SCHEMA public TO crophealth;
\q
```

---

## 4. Code and virtualenv

```bash
sudo mkdir -p /srv/crophealth && sudo chown $USER:$USER /srv/crophealth
git clone https://github.com/Soumya-Das-2006/AI_Crop_Health-Project.git /srv/crophealth
cd /srv/crophealth
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r AI_Crop_Health/requirements.txt
```

**Install `requirements.txt` only — not `requirements-ml.txt`.** That is the
difference between a ~250 MB install and a ~2 GB one, and between a 1 GB
instance and a 4 GB one. The app detects TensorFlow is absent and routes
diagnosis to crop.health, which covers more crops anyway. See the comments at
the top of `requirements-ml.txt`.

Media lives outside the repo so a `git pull` can never touch it:

```bash
mkdir -p /srv/crophealth/media
```

---

## 5. Environment

```bash
cd /srv/crophealth/AI_Crop_Health
cp .env.example .env
.venv/bin/python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
nano .env
```

Set at minimum:

```bash
SECRET_KEY=<the 50-char value you just generated>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
DATABASE_URL=postgres://crophealth:YOUR_DB_PASSWORD@localhost:5432/crophealth

MEDIA_ROOT=/srv/crophealth/media

# Fills itself into the privacy policy - this is the DPDP hosting disclosure.
COMPANY_HOSTING_PROVIDER=AWS Lightsail (Mumbai, India)

GROQ_API_KEY=...
CROP_HEALTH_API_KEY=...
INSECT_ID_API_KEY=...
GEMINI_API_KEY=...
OPENWEATHER_API_KEY=...
EMAIL_HOST_USER=...
EMAIL_HOST_PASSWORD=...
```

The app **refuses to start** with `DEBUG=False` if `SECRET_KEY` is under 50
characters, `ALLOWED_HOSTS` is unset, or `DATABASE_URL` is missing. That is
deliberate: each of those fails silently otherwise.

```bash
chmod 600 .env
```

---

## 6. Migrate and collect static

```bash
cd /srv/crophealth/AI_Crop_Health
../.venv/bin/python manage.py migrate
../.venv/bin/python manage.py collectstatic --noinput
../.venv/bin/python manage.py createsuperuser
```

---

## 7. gunicorn

```bash
sudo chown -R www-data:www-data /srv/crophealth/media
sudo cp deploy/gunicorn.service /etc/systemd/system/crophealth.service
sudo systemctl daemon-reload
sudo systemctl enable --now crophealth
sudo systemctl status crophealth
```

If it fails: `sudo journalctl -u crophealth -n 50`.

---

## 8. nginx

```bash
sudo cp deploy/nginx.conf /etc/nginx/sites-available/crophealth
sudo sed -i 's/YOUR_DOMAIN/yourdomain.com/g' /etc/nginx/sites-available/crophealth
sudo ln -sf /etc/nginx/sites-available/crophealth /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

Point your domain's A record at the static IP, wait for it to resolve, then:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

Certbot rewrites the nginx file to add TLS and sets up auto-renewal.

---

## 9. Check it

```bash
curl -I https://yourdomain.com/
```

Then in a browser:

- `/` — language picker in the topbar, switch to हिंदी and confirm the page translates
- `/detection/diagnosis/` — upload a leaf photo, confirm a diagnosis and the
  top-3 list, then ask an Ask AI question
- `/detection/insect/` — needs insect.id credits topped up
- `/detection/chatbot/` — ask something in Bengali, confirm the reply is Bengali
- `/admin/` — Chat Sessions and Diagnosis logs should show your test traffic

---

## Updating later

```bash
cd /srv/crophealth && git pull
.venv/bin/pip install -r AI_Crop_Health/requirements.txt
cd AI_Crop_Health
../.venv/bin/python manage.py migrate
../.venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart crophealth
```

**Always restart after changing `.env`.** `python-dotenv` reads it once at
startup, so a running process never sees a new key — this is exactly why Ask AI
returned "unavailable" after the Groq key was first added locally.

---

## Things that will bite you

- **Month 5**: set a calendar reminder. AWS credits last 6 months; after that
  this instance bills at ~$12/month.
- **Media is on the instance disk.** Automatic snapshots are the backup. If you
  ever move to a host with an ephemeral filesystem, every photo is lost on the
  next deploy — and Ask AI re-reads stored photos, so old diagnoses break too.
- **Gmail SMTP caps at ~500 messages/day.** Fine now; move to a transactional
  provider when OTP volume grows.
- **Mumbai gets half the standard Lightsail data transfer allowance.** Not an
  issue at MVP traffic, worth knowing before you serve video or large images.
