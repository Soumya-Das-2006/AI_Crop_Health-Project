# Deploy on Oracle Cloud — Always Free

Free **forever**, not a trial: 2 OCPU ARM, 12 GB RAM, 200 GB disk. That is far
more than this app needs.

Follow the steps in order. Each one is self-contained; don't skip ahead.

> **Read step 7 before you panic.** Oracle blocks ports in *two* places. Almost
> everyone opens the firewall in the console, sees the site still not load, and
> assumes the deploy failed. It hasn't — there is a second firewall inside the
> VM.
>
> Before starting, create an **A record** for `agricultureai.online` pointing
> to the VM's reserved public IP. Do not add `www` unless you also configure
> its DNS record and want that hostname to serve the site.

---

## Step 1 — Create the Oracle account

1. Go to <https://signup.oracle.com/>
2. Pick **Home Region: India South (Hyderabad)** or **India West (Mumbai)**.
   **This cannot be changed later**, so choose the one near your users.
3. A credit/debit card is required for identity verification. Always Free
   resources are not charged; a small temporary hold may appear and reverses.

Signups are sometimes rejected for no clear reason. If that happens, try a
different card or wait a day. If it keeps failing, use the AWS EC2 deployment
guide (`DEPLOY-AWS-EC2.md`) instead — don't lose days to this.

---

## Step 2 — Create an SSH key (on your Windows machine)

In PowerShell:

```powershell
ssh-keygen -t ed25519 -C "crophealth"
```

Press Enter at each prompt. This writes two files:

- `C:\Users\<you>\.ssh\id_ed25519` — **private**, never share or upload
- `C:\Users\<you>\.ssh\id_ed25519.pub` — **public**, this is what Oracle wants

Show the public key so you can copy it:

```powershell
type $env:USERPROFILE\.ssh\id_ed25519.pub
```

---

## Step 3 — Create the VM

Oracle console → **Compute → Instances → Create instance**.

| Field | Value |
|---|---|
| Name | `crophealth` |
| Image | **Ubuntu 24.04** (click *Change image*) |
| Shape | **Ampere → VM.Standard.A1.Flex** |
| OCPUs | **2** |
| Memory | **12 GB** |
| SSH key | **Paste public key** — the text from step 2 |

Make sure it says **"Always Free eligible"** before you create it.

**If you get "Out of host capacity":** that's Oracle being full, not your
mistake. Try a different Availability Domain in the dropdown, or retry in a few
hours. ARM capacity in Indian regions is often tight. If it persists after a
few tries, switch to Lightsail.

Once it's running, copy the **Public IP address** from the instance page.

---

## Step 4 — Make the IP permanent

Ephemeral IPs change when the VM restarts, which silently breaks your DNS.

Instance page → **Resources → Attached VNICs** → click the VNIC →
**IPv4 Addresses** → the ⋮ menu → **Edit** → Public IP → **Reserved IP** →
*Create new reserved IP* → Update.

---

## Step 5 — Connect

In PowerShell (replace with your IP):

```powershell
ssh ubuntu@YOUR_PUBLIC_IP
```

Type `yes` at the fingerprint prompt. You're in when the prompt reads
`ubuntu@crophealth:~$`.

---

## Step 6 — Open ports in the Oracle console (firewall 1 of 2)

Instance page → click the **Subnet** link → click the **Security List** →
**Add Ingress Rules**. Add two:

| Source CIDR | IP Protocol | Destination Port |
|---|---|---|
| `0.0.0.0/0` | TCP | `80` |
| `0.0.0.0/0` | TCP | `443` |

---

## Step 7 — Open ports inside the VM (firewall 2 of 2)

**This is the step everyone misses.** Oracle's Ubuntu image ships iptables
rules that reject everything except SSH, regardless of what the console says.
Run this on the server:

```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

Without this, nginx runs perfectly and the site is unreachable from the
internet, with nothing in any log to explain why.

---

## Step 8 — Install system packages

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-venv python3-dev build-essential \
                    postgresql postgresql-contrib \
                    nginx git libpq-dev
```

Everything here has ARM builds; nothing extra is needed for Ampere.

---

## Step 9 — Set up PostgreSQL

```bash
sudo -u postgres psql
```

At the `postgres=#` prompt, paste these one at a time. **Change the password.**

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

## Step 10 — Get the code

```bash
sudo mkdir -p /srv/crophealth && sudo chown $USER:$USER /srv/crophealth
git clone https://github.com/Soumya-Das-2006/AI_Crop_Health-Project.git /srv/crophealth
cd /srv/crophealth
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r AI_Crop_Health/requirements.txt
mkdir -p /srv/crophealth/media
```

**Install `requirements.txt` only — never `requirements-ml.txt`.** That skips
TensorFlow (1.5 GB) which the server does not need: the local model is the
*offline* tier and covers no Indian staple crops, while crop.health covers them
all. The app detects it's absent and routes accordingly.

On ARM this install takes a few minutes while numpy and scikit-learn resolve
their aarch64 wheels. That's normal.

---

## Step 11 — Configure

```bash
cd /srv/crophealth/AI_Crop_Health
cp .env.example .env
.venv/bin/python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
nano .env
```

Copy the long key it printed. In nano, set at minimum:

```bash
SECRET_KEY=<paste the 50-character key>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=agricultureai.online
CSRF_TRUSTED_ORIGINS=https://agricultureai.online
DATABASE_URL=postgres://crophealth:YOUR_DB_PASSWORD@localhost:5432/crophealth
DB_REQUIRE_SSL=False
MEDIA_ROOT=/srv/crophealth/media
COMPANY_HOSTING_PROVIDER=Oracle Cloud (Hyderabad, India)

GROQ_API_KEY=...
CROP_HEALTH_API_KEY=...
OPENWEATHER_API_KEY=...
EMAIL_HOST_USER=...
EMAIL_HOST_PASSWORD=...
DEFAULT_FROM_EMAIL=<verified sender address>
```

Save with `Ctrl+O`, Enter, then `Ctrl+X`. Then lock the file down:

```bash
sudo chown root:www-data .env
sudo chmod 640 .env
```

`COMPANY_HOSTING_PROVIDER` fills itself into your privacy policy — that is the
DPDP hosting disclosure, so don't leave it blank.

Use an SMTP app password and a sender address verified by that email provider.
The app refuses to start with the console email backend or incomplete SMTP
credentials, because email login codes must not be exposed in production logs.
Login OTP is email-only; phone OTP remains disabled until an SMS provider is
selected and configured.
For PostgreSQL on this same VM, set `DB_REQUIRE_SSL=False` unless you configure
PostgreSQL TLS.

The app refuses to start if `SECRET_KEY` is short, `ALLOWED_HOSTS` is unset,
the database is SQLite, or production email is incomplete. That's deliberate;
each otherwise makes the deployment insecure or silently broken.

---

## Step 12 — Migrate

```bash
cd /srv/crophealth/AI_Crop_Health
../.venv/bin/python manage.py migrate
../.venv/bin/python manage.py collectstatic --noinput
../.venv/bin/python manage.py createsuperuser
```

---

Before starting the service, verify the production configuration:

```bash
../.venv/bin/python manage.py check --deploy
```

Review all reported warnings before accepting real users. With the safe
defaults, Django may report `security.W005` and `security.W021`: subdomains and
browser preload are deliberately not forced on until every subdomain is known
to support HTTPS. Only enable them if you have verified that requirement.

---

## Step 13 — Run it with gunicorn

```bash
sudo chown -R www-data:www-data /srv/crophealth/media
sudo cp deploy/gunicorn.service /etc/systemd/system/crophealth.service
sudo systemctl daemon-reload
sudo systemctl enable --now crophealth
sudo systemctl status crophealth
```

Look for **active (running)** in green. If not:

```bash
sudo journalctl -u crophealth -n 50
```

With 12 GB of RAM you can raise `--workers 1` to `3` in the service file later.

---

## Step 14 — Put nginx in front

```bash
sudo cp deploy/nginx.conf /etc/nginx/sites-available/crophealth
sudo sed -i 's/YOUR_DOMAIN/agricultureai.online/g' /etc/nginx/sites-available/crophealth
sudo ln -sf /etc/nginx/sites-available/crophealth /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d agricultureai.online
```

Do not test or share the site until Certbot has issued the certificate.
Production Django redirects HTTP to HTTPS, so opening the public IP over HTTP
before TLS is configured will not work. Certbot sets up TLS and auto-renewal.
Check that `https://agricultureai.online` loads, then confirm renewal with:

```bash
sudo certbot renew --dry-run
```

---

## Step 15 — Check everything works

- `/` — switch the topbar language to हिंदी, page should translate
- `/detection/diagnosis/` — upload a leaf photo, check the top-3 list, ask an
  Ask AI question
- `/detection/chatbot/` — ask in Bengali, the reply should be Bengali
- `/detection/insect/` — needs insect.id credits topped up
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

**Always restart after editing `.env`.** It is read once at startup — this is
exactly why Ask AI said "unavailable" after the Groq key was first added.

---

## Backups — do this, Oracle will not

Free tier has no automatic backups and your database and every farmer photo are
on this one disk.

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

Copy those off the server periodically — a backup on the same disk is not a
backup.

---

## When things go wrong

| Symptom | Cause |
|---|---|
| Site unreachable, nginx fine | Step 7 (the VM's own iptables) |
| `502 Bad Gateway` | gunicorn down — `sudo journalctl -u crophealth -n 50` |
| `400 Bad Request` | Your IP/domain missing from `DJANGO_ALLOWED_HOSTS` |
| `Refusing to start in production` | Read it — it names the exact problem |
| Ask AI "not set up on this server" | `GROQ_API_KEY` missing, or no restart after editing `.env` |
| Site works, images 404 | `MEDIA_ROOT` and the nginx `/media/` alias disagree |
| "Out of host capacity" | Oracle is full — different AD, retry later, or use AWS EC2 |
