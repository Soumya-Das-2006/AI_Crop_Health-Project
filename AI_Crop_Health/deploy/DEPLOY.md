# Alternative: low-cost AWS EC2 deployment

This optional 2 GiB setup uses hosted AI only. For the selected 8 GiB
`m7i-flex.large` instance and optional offline model, use the detailed
[AWS EC2 deployment guide](./DEPLOY-AWS-EC2.md).

The app calls hosted AI providers for its main diagnosis and chatbot features.
Do **not** install `requirements-ml.txt` on the web server: TensorFlow is large
and the online diagnosis provider is the preferred production path.

AWS prices, Free Tier eligibility and service limits change. Review the current
EC2, EBS, Elastic IP/public IPv4, data transfer and backup charges in the AWS
Pricing Calculator before launching, and create an AWS Budget alert. Do not
assume that this configuration is free.

---

## Before you start

You need:

- A domain you control; production enforces HTTPS and must have a valid TLS
  certificate
- Your `.env` values: `GROQ_API_KEY`, `CROP_HEALTH_API_KEY`, `INSECT_ID_API_KEY`,
  `GEMINI_API_KEY`, `OPENWEATHER_API_KEY`, `EMAIL_HOST_PASSWORD`
- A fresh `SECRET_KEY` (generated in step 5 — do **not** reuse the local one)
- An AWS account with permission to create EC2, networking, IAM and backup
  resources

---

## 1. Create the EC2 instance

In the EC2 console, launch an instance with:

| Setting | Value |
|---|---|
| Region | **Mumbai (ap-south-1)** — closest to your users |
| AMI | Ubuntu Server 24.04 LTS, 64-bit x86 |
| Instance type | `t3.small` (2 vCPU, 2 GiB RAM) starting size |
| Storage | 30 GiB or larger encrypted gp3 EBS root volume |
| Key pair | Create/download a key pair and keep the private key secure, or use Session Manager |
| IAM | Attach an instance role with `AmazonSSMManagedInstanceCore` if using Session Manager |

Place the instance in a public subnet whose route table sends internet traffic
through an Internet Gateway. A private subnet needs a NAT gateway or suitable
VPC endpoints for package downloads and the external AI/email providers.

The instance runs one Gunicorn worker to limit memory use. Monitor RAM, swap,
CPU credits, disk and application latency; scale the instance before adding
workers. Do not install TensorFlow on this small web instance.

Create a security group with **inbound only**:

| Port | Source |
|---|---|
| 80 (HTTP) | `0.0.0.0/0` and `::/0` |
| 443 (HTTPS) | `0.0.0.0/0` and `::/0` |
| 22 (SSH) | Your current public IP `/32` only, or omit SSH and connect with Session Manager |

Never expose PostgreSQL (5432) or Gunicorn (8000/socket) to the internet. Keep
the default outbound access so the instance can install packages and reach the
configured external providers. Use an Elastic IP for stable DNS; public IPv4
and Elastic IP charges may apply. Create an AWS Budget alert before or just
after launch.

Allocate an Elastic IP, associate it with this instance, and point the
domain's DNS A record at it. Add a separate A record for `www` only if you
configure that hostname in Django and TLS below.

---

## 2. System packages

SSH in, then:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev \
                    build-essential postgresql postgresql-contrib \
                    nginx git libpq-dev
```

---

## 3. PostgreSQL

For a small single-instance launch, PostgreSQL can run on the EC2 instance.
This reduces service count but means the database and app share one failure
domain. Keep Postgres bound to localhost and never open port 5432 in the
security group. For workloads requiring independent backups, maintenance or
availability, use Amazon RDS for PostgreSQL and restrict its security group to
this EC2 instance's security group.

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
python3.11 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r AI_Crop_Health/requirements.txt
sudo mkdir -p /srv/crophealth/media AI_Crop_Health/logs AI_Crop_Health/staticfiles
sudo chown -R www-data:www-data /srv/crophealth/media AI_Crop_Health/logs AI_Crop_Health/staticfiles
```

**Install `requirements.txt` only — not `requirements-ml.txt`.** That is the
difference between a ~250 MB install and a ~2 GB one, and between a 1 GB
instance and a 4 GB one. The app detects TensorFlow is absent and routes
diagnosis to crop.health, which covers more crops anyway. See the comments at
the top of `requirements-ml.txt`.

## 5. Environment

```bash
cd /srv/crophealth/AI_Crop_Health
cp .env.example .env
.venv/bin/python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
nano .env
```

Set at minimum (retain the other `.env.example` defaults):

```bash
SECRET_KEY=<the 50-char value you just generated>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=yourdomain.com
CSRF_TRUSTED_ORIGINS=https://yourdomain.com
DATABASE_URL=postgres://crophealth:YOUR_DB_PASSWORD@localhost:5432/crophealth

MEDIA_ROOT=/srv/crophealth/media
# Local PostgreSQL uses no TLS; for Amazon RDS keep DB_REQUIRE_SSL=True.
DB_REQUIRE_SSL=False

# Fills itself into the privacy policy - this is the DPDP hosting disclosure.
COMPANY_HOSTING_PROVIDER=Amazon Web Services EC2 (Mumbai, India)

GROQ_API_KEY=...
CROP_HEALTH_API_KEY=...
INSECT_ID_API_KEY=...
GEMINI_API_KEY=...
OPENWEATHER_API_KEY=...
EMAIL_HOST_USER=...
EMAIL_HOST_PASSWORD=...
DEFAULT_FROM_EMAIL=verified-sender@example.com
```

`MEDIA_ROOT` above points at `/srv/crophealth/media`, outside the repository.
For the local database, `DATABASE_URL` must use this format:
`postgresql://crophealth:URL_ENCODED_PASSWORD@127.0.0.1:5432/crophealth`.

Set every hostname you will serve in `DJANGO_ALLOWED_HOSTS` and in
`CSRF_TRUSTED_ORIGINS` with its `https://` scheme. Percent-encode special
characters in the database password before putting it in `DATABASE_URL`.
Set `DB_REQUIRE_SSL=False` only for PostgreSQL on the same machine; leave it
`True` for Amazon RDS.
If you want `www.yourdomain.com` too, create its DNS record and add it to both
environment variables before running Certbot.

With `DJANGO_DEBUG=False`, startup validation requires a 50-character
`SECRET_KEY`, real allowed hosts, PostgreSQL, and a configured production email
backend. Email is required because login codes must not be printed to logs.
Configure all integration keys that you need; missing AI/weather keys disable
those integrations or make the related features unavailable.

Keep secrets out of shell history, chat, and Git. Restrict the file to the
service account and root:

```bash
sudo chown www-data:www-data .env
sudo chmod 600 .env
```

---

## 6. Migrate and collect static

```bash
cd /srv/crophealth/AI_Crop_Health
sudo -u www-data ../.venv/bin/python manage.py check --deploy
sudo -u www-data ../.venv/bin/python manage.py migrate --noinput
sudo -u www-data ../.venv/bin/python manage.py collectstatic --noinput
sudo -u www-data ../.venv/bin/python manage.py setup_admin_roles
sudo -u www-data ../.venv/bin/python manage.py createsuperuser
```

---

## 7. gunicorn

```bash
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

After the domain's A record points to the Elastic IP and DNS has propagated,
install and configure HTTPS:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
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
sudo -u www-data ../.venv/bin/python manage.py check --deploy
sudo -u www-data ../.venv/bin/python manage.py migrate --noinput
sudo -u www-data ../.venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart crophealth
```

**Always restart after changing `.env`.** `python-dotenv` reads it once at
startup, so a running process never sees a new key — this is exactly why Ask AI
returned "unavailable" after the Groq key was first added locally.

---

## Backups and operations

- The database, public uploads and private verification documents are on the
  instance's EBS volume. Direct requests to `/media/verification/` are blocked;
  staff reviewers download those files through the Django admin.
  Configure scheduled encrypted EBS snapshots with an AWS Backup plan or
  Data Lifecycle Manager, and retain copies according to your recovery needs.
  Snapshots are crash-consistent; for stronger database recovery, schedule
  `pg_dump` backups and copy them to a private, versioned S3 bucket.
- Test restoring both the database and uploaded media to a separate instance.
  A backup that has never been restored is unverified.
- Use an instance role for AWS access; do not put long-lived AWS access keys
  in `.env`.
- Check `sudo journalctl -u crophealth -n 100`, `/var/log/nginx/`, disk usage,
  and EC2 status checks when diagnosing a failed deploy.
- Gmail SMTP caps at approximately 500 messages/day. Move to a transactional
  email provider as OTP volume grows.
- AWS charges vary by region and account. Review EC2 instance hours, EBS,
  public IPv4/Elastic IP, snapshots, S3 storage and data transfer in Cost
  Explorer and configure billing alerts.
