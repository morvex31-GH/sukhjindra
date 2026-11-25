# Making Admin Portal edits permanent (PostgreSQL setup)

## Why your edits were resetting

Your app already saved edits to a database, but that database was a **SQLite file
(`sgi_admissions.db`) on the web server's own disk**, and PDFs/avatars were saved in
`uploads/` on that same disk. Most cloud hosts (Render, Railway, Heroku, Vercel, Fly,
Koyeb, free tiers generally) give your app a **temporary disk**. Every redeploy, restart
or wake-from-sleep replaces it with a fresh copy of your code. The database file is
then recreated empty and `init_db()` re-seeds the hardcoded defaults, so `25+` comes back.

The fix is to move all data to a database that lives **outside** the web server.
After this change:

| Data | Before | After |
|---|---|---|
| Site text, stats, contact info | SQLite file on server disk | PostgreSQL |
| Notices, programs, staff, leads | SQLite file on server disk | PostgreSQL |
| Notice PDFs, staff photos | `uploads/` folder on server disk | PostgreSQL (`files` table) |
| Admin logins | SQLite file | PostgreSQL |

---

## Step 1: Create a free PostgreSQL database (Neon, recommended)

1. Go to https://console.neon.tech and sign up (no credit card needed).
2. **Create project**, pick the region closest to your visitors (e.g. Singapore).
3. On the project dashboard click **Connect** and copy the connection string. It looks like:
   `postgresql://user:password@ep-xxxx.ap-southeast-1.aws.neon.tech/neondb?sslmode=require`
   Keep `?sslmode=require` at the end.

**Why Neon over Supabase for this site:** Neon's free compute sleeps after 5 minutes idle
but your data stays stored and wakes in about a second on the next request. Supabase
free projects are *paused* after about a week of low activity and must be manually
resumed (there is a limited restore window), which is risky for a site that could sit
untouched for months. Supabase will work with this code too (use its **Connection string →
URI** with `sslmode=require`), but you'd need to keep it active.
Free-plan limits change; check https://neon.com/docs/introduction/plans.

---

## Step 2: Set environment variables on your host

Add these in your host's dashboard (never put them in code or commit them):

| Variable | Value |
|---|---|
| `DATABASE_URL` | the Neon connection string from Step 1 |
| `REQUIRE_PERSISTENT_DB` | `1` (app refuses to start without a database, so it can never silently reset) |
| `SECRET_KEY` | long random string: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ADMIN_INITIAL_PASSWORD` | strong password for the first-ever `admin` account (used once) |
| `COOKIE_SECURE` | `1` (when your site is served over https) |

See `.env.example`.

## Step 3: Deploy

1. Replace these files in your project with the delivered ones: `app.py`, `main.js`,
   `index.html`, `admin.html`. Add `requirements.txt` and `.gitignore`. `styles.css` is unchanged.
2. **Delete `sgi_admissions.db` and the `uploads/` folder from your Git repo** (if committed) and keep the
   delivered `.gitignore`. A committed database file would overwrite live data on every deploy.
3. Install command: `pip install -r requirements.txt`
4. Start command (Linux hosts):
   `gunicorn app:app --workers 2 --threads 4 --timeout 60 --bind 0.0.0.0:$PORT`
   (Some hosts, e.g. Render, supply `$PORT` automatically.)

On first launch the app creates the tables and seeds your current hardcoded defaults
**once**. After that, saved values are never overwritten by defaults, not on restart,
not on redeploy, and not even if you delete every notice or program.

### Running locally (Windows PowerShell)
```powershell
pip install -r requirements.txt
$env:DATABASE_URL = "postgresql://...?sslmode=require"
python app.py
```
Without `DATABASE_URL` it falls back to a local SQLite file (fine for development,
and the Admin Portal shows a red warning so you can't mistake it for production).

---

## Step 4: Verify permanence (2 minutes)

1. Open `https://YOUR-SITE/healthz`. It should show `"database": "postgresql"`.
2. Log in at `/admin` and open **Live Website Content Manager**. You should see
   🟢 **Permanent storage: PostgreSQL**.
3. Change "25+" to "24+" and press **Save All Content**.
4. Open the public site in a different browser or phone: it shows **24+**.
5. **Restart or redeploy** the service from your host's dashboard, then reload the site.
   Still **24+**. Same on the next day, next month, next year.

---

## Step 5 (optional): Keep data you already entered locally

Only if your local `sgi_admissions.db` holds real content/leads/staff you want to keep:

```powershell
$env:DATABASE_URL = "postgresql://...?sslmode=require"
python migrate_sqlite_to_postgres.py            # or pass a path to the .db file
```
This replaces what is in the Postgres database with your local data, including
PDFs and photos. Run it once, before going live.

---

## Security fixes included

- **Your old server exposed its own source and database.** The previous catch-all route and
  Flask's built-in static folder would serve `/app.py`, `/sgi_admissions.db` (password
  hashes + all student leads) and `/admin.html` to anyone who guessed the URL. Only public
  assets (css/js/images/pdf/fonts) are served now; admin.html is reachable only through the
  login-protected `/admin`.
- `SECRET_KEY` and the initial admin password now come from environment variables
  instead of being hardcoded in source. **Because the old password was in your code, change
  the `admin` password** (or set `ADMIN_INITIAL_PASSWORD` before first launch on the new database).
- Debug mode is off unless `FLASK_DEBUG=1` is set.

## Backups

Neon's free plan keeps only a short point-in-time history window (check current plan details),
so don't rely on it as your only backup. Run occasionally:
`pg_dump "$DATABASE_URL" > sgi_backup.sql`
Leads can also be exported from the Admin Portal as CSV.

## What is still not editable from the Admin Portal

Only fields the portal already manages are database-backed (hero, stats, placements,
campus-life card, contact info, notices, programs, staff names/photos). Other text written
directly in `index.html` (for example the About paragraphs) is still static HTML. The campus-life
image is a file path you type; image files themselves still live in your project folder.
If you want those editable too, that's an add-on: new keys in `DEFAULT_SITE_CONTENT`, a field in
`admin.html`, and a `data-cms="key"` attribute in `index.html`.
