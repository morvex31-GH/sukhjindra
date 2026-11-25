"""
One-time copy of an existing local SQLite site (sgi_admissions.db + uploads/) into PostgreSQL.

Use this ONLY if you already have real content/leads/staff in a local sgi_admissions.db that
you want to keep. If you are starting fresh, skip it - the app seeds itself on first launch.

    # Windows PowerShell:  $env:DATABASE_URL="postgresql://..."
    # macOS/Linux:         export DATABASE_URL="postgresql://..."
    python migrate_sqlite_to_postgres.py [path/to/sgi_admissions.db]

It REPLACES whatever is currently in the target Postgres database's app tables.
"""
import os
import sys
import sqlite3
import mimetypes

if not os.environ.get("DATABASE_URL"):
    sys.exit("Set DATABASE_URL to your PostgreSQL connection string first.")

import app as A                      # importing creates the Postgres schema
if not A.USE_PG:
    sys.exit("DATABASE_URL must start with postgresql:// (or postgres://).")

SRC = sys.argv[1] if len(sys.argv) > 1 else A.DB_NAME
if not os.path.isfile(SRC):
    sys.exit(f"SQLite file not found: {SRC}")

src = sqlite3.connect(SRC)
src.row_factory = sqlite3.Row
dst = A.get_db()
cur = dst.cursor()

TABLES = ["users", "leads", "notices", "programs", "site_content", "files"]   # "files" = uploads already stored in the DB
cur.execute("TRUNCATE users, leads, notices, programs, site_content, files, app_meta RESTART IDENTITY")

for table in TABLES:
    try:
        rows = src.execute(f"SELECT * FROM {table}").fetchall()
    except sqlite3.OperationalError:
        print(f"  {table}: not in source, skipped")
        continue
    if not rows:
        print(f"  {table}: 0 rows")
        continue
    cols = rows[0].keys()
    sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})"
    for r in rows:
        cur.execute(sql, tuple(r[c] for c in cols))
    if "id" in cols:   # keep the SERIAL counter ahead of the copied ids
        cur._c.execute(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM {table}")
    print(f"  {table}: copied {len(rows)} rows")

# uploaded PDFs / avatars that were sitting on local disk
n_files = 0
for folder, kind in ((A.UPLOAD_NOTICES_DIR, "notice"), (A.UPLOAD_AVATARS_DIR, "avatar")):
    if os.path.isdir(folder):
        for fname in os.listdir(folder):
            path = os.path.join(folder, fname)
            if os.path.isfile(path):
                with open(path, "rb") as fh:
                    cur.execute("INSERT INTO files (name, kind, mimetype, data) VALUES (?, ?, ?, ?) ON CONFLICT(name) DO NOTHING",
                                (fname, kind, mimetypes.guess_type(fname)[0] or "application/octet-stream", fh.read()))
                n_files += 1
print(f"  uploads found on local disk (legacy): {n_files}")

# mark the store as already seeded so defaults are never re-inserted over your data
for flag in ("seeded_admin", "seeded_notices", "seeded_programs"):
    cur.execute("INSERT INTO app_meta (key, value) VALUES (?, '1')", (flag,))

dst.commit()
dst.close()
# fill any site_content keys that are new since your DB was created (never overwrites)
A.init_db()
print("Done. Your data now lives in PostgreSQL.")
