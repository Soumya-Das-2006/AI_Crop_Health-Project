# Deploy on AWS EC2 — m7i-flex.large

Ubuntu 24.04, 2 vCPU, 8 GiB RAM, Mumbai (ap-south-1).

**Check the live AWS Pricing Calculator before launching.** Instance, public
IPv4, EBS, snapshots and data transfer charges vary; promotional credits are
account-specific and are not guaranteed.

**The upside of 8 GiB:** it is the one size where you can optionally install
TensorFlow and run the bundled offline disease model alongside crop.health.
Step 10 covers that choice.

---

## Step 1 — Launch the instance

EC2 console → **Launch instance**.

| Field | Value |
|---|---|
| Name | `crophealth` |
| AMI | **Ubuntu Server 24.04 LTS (64-bit x86)** |
| Instance type | **m7i-flex.large** |
| Key pair | **Create new key pair** → name `crophealth` → type **RSA** → format **.pem** → Download |
| Storage | Change 8 GiB → **30 GiB encrypted**, type **gp3** |

The `.pem` file downloads once. Lose it and you lose SSH access to this
instance permanently — keep it somewhere safe, not in Downloads.

Region selector (top right) should read **Asia Pacific (Mumbai) ap-south-1**.

---

## Step 2 — Security group (the firewall)

In the launch wizard, under **Network settings → Edit**, create a security
group with three inbound rules:

| Type | Port | Source | Why |
|---|---|---|---|
| SSH | 22 | **My IP** | Only you. Never `0.0.0.0/0` here. |
| HTTP | 80 | `0.0.0.0/0` | Public website — any visitor |
| HTTPS | 443 | `0.0.0.0/0` | Public website — any visitor |

AWS warns about `0.0.0.0/0`. For 80 and 443 that warning is expected and
correct: a public site must accept every IP. For SSH it is a real risk, which
is why that one is restricted to your own address.

Then **Launch instance**.

> If your home IP changes (most Indian broadband is dynamic) and SSH stops
> working, edit the rule and set **My IP** again.

---

## Step 3 — Elastic IP (do not skip)

Without this, the public IP changes every time the instance stops and starts,
silently breaking your DNS.

EC2 console → **Elastic IPs** → **Allocate Elastic IP address** → Allocate →
select it → **Actions → Associate** → choose your `crophealth` instance →
Associate.

Note the IP down. This is your server address.

> Elastic IPs are charged when they are **not** attached to a running
> instance. If you stop the instance to save money (step 14), the IP keeps
> billing at ~$3.65/month. That is the price of keeping the same address.

---

## Step 4 — Connect over SSH

Open **PowerShell** in the folder where the `.pem` landed.

Windows will refuse the key if its permissions are too open. Fix them once:

```powershell
icacls crophealth.pem /inheritance:r
icacls crophealth.pem /grant:r "$($env:USERNAME):(R)"
```

Then connect, using your Elastic IP:

```powershell
ssh -i crophealth.pem ubuntu@YOUR_ELASTIC_IP
```

Type `yes` at the fingerprint prompt. You are in when the prompt shows
`ubuntu@ip-...:~$`.

The username is **ubuntu**, not root or ec2-user — that is specific to the
Ubuntu AMI.

---

## Step 5 — System packages

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev build-essential \
                    postgresql postgresql-contrib \
                    nginx git libpq-dev
```

---

## Step 6 — PostgreSQL

Running Postgres on this instance rather than RDS saves roughly $15/month of
credits, which matters a lot on this instance size.

```bash
sudo -u postgres psql
```

Paste these one at a time. **Change the password.**

```sql
CREATE DATABASE crophealth;
CREATE USER crophealth WITH PASSWORD 'PUT_A_LONG_PASSWORD_HERE';
ALTER ROLE crophealth SET client_encoding TO 'utf8';
ALTER ROLE crophealth SET default_transaction_isolation TO 'read committed';
ALTER ROLE crophealth SET timezone TO 'Asia/Kolkata';
GRANT ALL PRIVILEGES ON DATABASE crophealth TO crophealth;
\c crophealth
GRANT ALL ON SCHEMA public TO crophealth;
\q
```

---

## Step 7 — Get the code

```bash
sudo mkdir -p /srv/crophealth && sudo chown $USER:$USER /srv/crophealth
git clone https://github.com/Soumya-Das-2006/AI_Crop_Health-Project.git /srv/crophealth
cd /srv/crophealth
python3.11 -m venv .venv
.venv/bin/pip install --upgrade pip
```

Media lives outside the checkout so `git pull` can never touch it:

```bash
mkdir -p /srv/crophealth/media
sudo mkdir -p AI_Crop_Health/logs AI_Crop_Health/staticfiles
sudo chown -R www-data:www-data /srv/crophealth/media AI_Crop_Health/logs AI_Crop_Health/staticfiles
```

---

## Step 8 — Install dependencies

```bash
.venv/bin/pip install -r AI_Crop_Health/requirements.txt
```

That is the lean server set: 14 packages, ~250 MB, no TensorFlow.

### Optional: add the offline disease model

8 GiB is enough to also run the bundled `.h5` model. Only worth it if you want
a fallback for when crop.health is unreachable or out of credits:

```bash
.venv/bin/pip install -r AI_Crop_Health/requirements-ml.txt
```

This adds ~1.5 GB of install and ~700 MB of RAM **per gunicorn worker**. If you
do this, keep `--workers 1` in step 11. Remember the offline model covers only
38 PlantVillage classes — apple, grape, tomato, potato, maize — and no rice,
wheat, cotton or sugarcane, so crop.health stays the primary either way.

---

## Step 9 — Configure

```bash
cd /srv/crophealth/AI_Crop_Health
cp .env.example .env
.venv/bin/python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
nano .env
```

Copy the long key it printed, then set at minimum:

```bash
SECRET_KEY=<paste the 50-character key>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=YOUR_ELASTIC_IP,yourdomain.com,www.yourdomain.com
CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
DATABASE_URL=postgres://crophealth:YOUR_DB_PASSWORD@localhost:5432/crophealth
MEDIA_ROOT=/srv/crophealth/media
DB_REQUIRE_SSL=False
COMPANY_HOSTING_PROVIDER=AWS EC2 (Mumbai, India)

GROQ_API_KEY=...
CROP_HEALTH_API_KEY=...
INSECT_ID_API_KEY=...
GEMINI_API_KEY=...
OPENWEATHER_API_KEY=...
EMAIL_HOST_USER=...
EMAIL_HOST_PASSWORD=...
DEFAULT_FROM_EMAIL=verified-sender@example.com
```

Save: `Ctrl+O`, Enter, `Ctrl+X`. Then:

```bash
sudo chown www-data:www-data .env
sudo chmod 600 .env
```

`COMPANY_HOSTING_PROVIDER` is rendered into your privacy policy — that is the
DPDP hosting disclosure, so do not leave it blank.

The app refuses to start in production if `SECRET_KEY` is under 50 characters,
real hosts are missing, it is still on SQLite, or production email is not
configured. Use `DB_REQUIRE_SSL=False` only for this local PostgreSQL setup;
leave it `True` for Amazon RDS. Percent-encode special characters in the
database password inside `DATABASE_URL`.

---

## Step 10 — Migrate

```bash
cd /srv/crophealth/AI_Crop_Health
sudo -u www-data ../.venv/bin/python manage.py check --deploy
sudo -u www-data ../.venv/bin/python manage.py migrate --noinput
sudo -u www-data ../.venv/bin/python manage.py collectstatic --noinput
sudo -u www-data ../.venv/bin/python manage.py setup_admin_roles
sudo -u www-data ../.venv/bin/python manage.py createsuperuser
```

---

## Step 11 — Run with gunicorn

```bash
sudo chown -R www-data:www-data /srv/crophealth/media
sudo cp deploy/gunicorn.service /etc/systemd/system/crophealth.service
```

The unit ships with `--workers 1`, sized for a 1–2 GB box. You have 8 GiB, so
if you did **not** install TensorFlow, raise it:

```bash
sudo sed -i 's/--workers 1/--workers 3/' /etc/systemd/system/crophealth.service
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now crophealth
sudo systemctl status crophealth
```

Look for **active (running)** in green. If not:

```bash
sudo journalctl -u crophealth -n 50
```

---

## Step 12 — nginx

```bash
sudo cp deploy/nginx.conf /etc/nginx/sites-available/crophealth
sudo sed -i 's/YOUR_DOMAIN/YOUR_ELASTIC_IP/g' /etc/nginx/sites-available/crophealth
sudo ln -sf /etc/nginx/sites-available/crophealth /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

`DJANGO_DEBUG=False` redirects HTTP to HTTPS, so the site will not be usable
over plain HTTP before the TLS certificate is installed in step 13. Verify it
after completing that step.

---

## Step 13 — Domain and HTTPS

Point A records for `yourdomain.com` and `www.yourdomain.com` at your Elastic
IP, and wait for both names to resolve before requesting the certificate. If
you will not use `www`, remove it from the command and Django settings:

```bash
sudo sed -i 's/YOUR_ELASTIC_IP/yourdomain.com www.yourdomain.com/' /etc/nginx/sites-available/crophealth
sudo nginx -t && sudo systemctl reload nginx
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

Then update `DJANGO_ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` in `.env` to the
domain and `sudo systemctl restart crophealth`. Since `.env` is owned by
`www-data`, edit it with `sudoedit .env`. If serving `www`, its DNS A record
must also resolve to the Elastic IP before requesting the certificate.

---

## Step 14 — Control the cost (important on this instance)

### Set a budget alert first

Billing console → **Budgets** → Create a monthly cost budget and configure
email alerts at multiple thresholds. Use the current Pricing Calculator
estimate; do not assume this instance is covered by a trial or promotional
credits.

### Stop the instance when you are not using it

Stopping the instance stops its compute charges, but storage, snapshots and
public IPv4 charges continue. Calculate both running and stopped costs before
using stop/start to reduce the bill. Do not rely on promotional credits unless
they are confirmed in your AWS Billing console.

EC2 console → select instance → **Instance state → Stop instance**. Start it
again before a demo. The Elastic IP and all your data survive.

What continues to bill while stopped includes the public IPv4 address, the
30 GB EBS volume, and any retained snapshots. The rates change, so use the
Pricing Calculator for current amounts.

**Never "Terminate"** — that deletes the instance and its disk. Only "Stop".

### Or move down a size later

If the offline model turns out not to matter, compare a smaller instance type
in the Pricing Calculator. A 2 GiB type cannot run the optional TensorFlow
model reliably. Stop the instance → **Actions → Instance settings → Change
instance type** → choose the size → start.

---

## Step 15 — Backups

EC2 gives you none by default, and your database and every farmer photo are on
this one volume.

```bash
sudo tee /usr/local/bin/crophealth-backup.sh >/dev/null <<'SH'
#!/bin/bash
set -e
D=/srv/crophealth/backups
mkdir -p "$D"
sudo -u postgres pg_dump crophealth | gzip > "$D/db-$(date +%F).sql.gz"
tar czf "$D/media-$(date +%F).tar.gz" -C /srv/crophealth media
find "$D" -type f -mtime +14 -delete
SH
sudo chmod +x /usr/local/bin/crophealth-backup.sh
echo "0 3 * * * root /usr/local/bin/crophealth-backup.sh" | sudo tee /etc/cron.d/crophealth-backup
```

Also take an **EBS snapshot** before any risky change: EC2 console → Volumes →
select → Actions → Create snapshot.

Copy backups off the server periodically. A backup on the same disk is not a
backup.

---

## Step 16 — Verify every feature

- `/` — switch the topbar language to हिंदी, the page should translate
- `/detection/diagnosis/` — upload a leaf photo, check the top-3 list, then ask
  an Ask AI question
- `/detection/chatbot/` — ask something in Bengali, the reply should be Bengali
- `/detection/insect/` — needs insect.id credits topped up
- `/admin/` — Chat Sessions and Diagnosis logs should show your test traffic

---

## Updating later

```bash
cd /srv/crophealth && git pull
.venv/bin/pip install -r AI_Crop_Health/requirements.txt
cd AI_Crop_Health
sudo -u www-data ../.venv/bin/python manage.py check --deploy
sudo -u www-data ../.venv/bin/python manage.py migrate --noinput
sudo -u www-data ../.venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart crophealth
```

**Always restart after editing `.env`.** It is read once at startup — this is
exactly why Ask AI reported "unavailable" after the Groq key was first added.

---

## When things go wrong

| Symptom | Cause |
|---|---|
| SSH times out | Security group rule 22 is not your current IP |
| `Permission denied (publickey)` | Wrong `.pem`, or user is not `ubuntu` |
| `WARNING: UNPROTECTED PRIVATE KEY FILE` | Run the `icacls` commands in step 4 |
| Site unreachable, nginx running | Security group missing port 80/443 |
| `502 Bad Gateway` | gunicorn down — `sudo journalctl -u crophealth -n 50` |
| `400 Bad Request` | IP/domain missing from `DJANGO_ALLOWED_HOSTS` |
| `Refusing to start in production` | Read the message — it names the exact problem |
| Ask AI "not set up on this server" | `GROQ_API_KEY` missing, or no restart after `.env` edit |
| Images 404 | `MEDIA_ROOT` and the nginx `/media/` alias disagree |
| IP changed after restart | No Elastic IP — step 3 |
