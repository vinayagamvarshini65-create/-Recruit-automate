# Recruit Automate

A small, self-contained recruitment email automation system: import candidates,
auto-generate personalized offer letters (PDF), and send them by email with
one click — with full status tracking.

Built as a working MVP of the solution proposal: candidate data → document
generation → email composition → send & track, all in one dashboard instead
of juggling spreadsheets, Word, and a mail client.

# LIVE APP : https://recruit-automate.onrender.com/

## Features

- **Candidate management** — add candidates manually or bulk-import via CSV
- **Editable templates** — one document template (offer letter) and one email
  template, both using `{{merge_field}}` placeholders
- **PDF generation** — merges candidate data into the template and renders a
  formatted PDF automatically (no manual copy-paste)
- **Live preview** — see the exact merged document and email before sending
- **Bulk send** — select any number of pending candidates and process them
  all in one action
- **Status tracking** — every candidate shows pending / sent / failed, with
  a full activity log of every generate/send event
- **Safe by default** — if no email server is configured, the app runs in
  demo mode: it composes real emails and saves them to `data/outbox/`
  instead of sending, so you can try the whole workflow with zero setup

## Quick start

```bash
cd recruit-automate
pip install -r requirements.txt
python app.py
```

Then open **http://localhost:5000** in your browser.

On first run the app creates a local SQLite database (`data/app.db`) with
default offer-letter and email templates already loaded, so you can try the
whole flow immediately:

1. Go to **Import CSV** and upload `sample_data/candidates_sample.csv`
   (or click "Download a sample CSV" on that page).
2. Go to **Generate & Send**, select the candidates, and click
   **Generate documents & send emails**.
3. Check **Candidates** to see status change to "sent" and download the
   generated PDF, or check **Activity Log** for the full audit trail.
4. Since no email server is configured by default, the composed emails are
   saved as text files under `data/outbox/` — open one to see exactly what
   would have been sent.

## Enabling real email sending

By default the app runs in **demo/dry-run mode** (no emails actually leave
your machine). To send real emails, set these environment variables before
running the app:

```bash
export SMTP_HOST=smtp.gmail.com
export SMTP_PORT=587
export SMTP_USER=your_email@gmail.com
export SMTP_PASSWORD=your_app_password      # use an app password, not your real password
export FROM_EMAIL=your_email@gmail.com
python app.py
```

Any standard SMTP provider works (Gmail, Outlook, SendGrid SMTP relay,
Amazon SES SMTP, etc.) — just point `SMTP_HOST`/`SMTP_PORT` at it.

## Project structure

```
recruit-automate/
  app.py              Flask routes / application logic
  database.py          SQLite data layer (candidates, templates, log)
  documents.py          Merge-field engine + PDF generation (reportlab)
  emailer.py            SMTP sending with a safe dry-run fallback
  templates/           Jinja2 HTML pages (dashboard, candidates, etc.)
  static/style.css      App styling
  sample_data/           Example CSV for import
  data/                 Created at runtime: SQLite DB, generated PDFs, outbox
```

## Customizing templates

Go to the **Templates** page in the app to edit:

- **Standard Offer Letter** (document) — the text that gets rendered to PDF
- **Standard Offer Email** (email) — subject line and email body

Both support these merge fields: `{{name}}`, `{{email}}`, `{{role}}`,
`{{department}}`, `{{salary}}`, `{{joining_date}}`, `{{today}}`.

## Deploying to Render.com (free tier)

1. **Push this project to a GitHub repository.**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/recruit-automate.git
   git push -u origin main
   ```
2. Go to [render.com](https://render.com), sign up (free), and click **New +** → **Web Service**.
3. Connect your GitHub account and select this repository.
4. Render auto-detects Python. Set (or confirm) these values:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app --bind 0.0.0.0:$PORT` (already in the included `Procfile`, Render will pick it up automatically)
5. Click **Create Web Service**. Render builds and deploys automatically — you'll get a live URL like `https://recruit-automate.onrender.com`.
6. To enable real email sending in production, go to your service's **Environment** tab on Render and add `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `FROM_EMAIL` as environment variables (same ones described above).

**Important — data persistence:** Render's free tier uses an ephemeral filesystem, so the SQLite database (`data/app.db`) and generated PDFs are wiped on every restart/redeploy. This is fine for a demo/portfolio deployment. For anything real, either:
- Add a **Render Persistent Disk** (paid, a few dollars/month) mounted at `/opt/render/project/src/data`, or
- Swap SQLite for a managed database — Render offers a free PostgreSQL tier, which would need small changes to `database.py`.

## Notes on extending this MVP

- Add authentication (e.g. Flask-Login) before deploying beyond local use
- Swap SQLite for PostgreSQL for multi-user / production use
- Add more document templates (rejection letters, certificates) by inserting
  additional rows into the `templates` table with `kind='document'`
- Hook up a transactional email API (SendGrid, SES) instead of raw SMTP for
  better deliverability and bounce tracking at scale
