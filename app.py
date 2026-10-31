"""Dynamic QR Code Service
- POST /api/create      -> create short code + QR for a URL
- GET  /r/<code>        -> redirect to current destination (counts scan)
- PUT  /api/update/<c>  -> change destination without changing the QR
- GET  /api/stats/<c>   -> scan count
- GET  /qr/<code>.png   -> QR image
- GET  /health          -> health check (used for SLA / TTR monitoring)
"""
import io
import os
import secrets
import sqlite3
import string
import time
from urllib.parse import urlparse

import qrcode
from flask import Flask, jsonify, redirect, render_template, request, send_file

app = Flask(__name__)

DB_PATH = os.environ.get("DB_PATH", "data/qr.db")
BASE_URL = os.environ.get("BASE_URL", "").rstrip("/")
ALPHABET = string.ascii_letters + string.digits
START_TIME = time.time()


def get_db():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS links (
                code TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                scans INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL
            )"""
        )


def valid_url(url):
    try:
        p = urlparse(url)
    except ValueError:
        return False
    return p.scheme in ("http", "https") and bool(p.netloc)


def new_code(conn, length=6):
    while True:
        code = "".join(secrets.choice(ALPHABET) for _ in range(length))
        if not conn.execute("SELECT 1 FROM links WHERE code=?", (code,)).fetchone():
            return code


def short_url(code):
    base = BASE_URL or request.host_url.rstrip("/")
    return f"{base}/r/{code}"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    try:
        with get_db() as conn:
            conn.execute("SELECT 1").fetchone()
    except Exception as exc:  # DB unreachable -> unhealthy
        return jsonify(status="unhealthy", error=str(exc)), 503
    return jsonify(status="ok", uptime_seconds=round(time.time() - START_TIME, 1))


@app.route("/api/create", methods=["POST"])
def create():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not valid_url(url):
        return jsonify(error="Valid http/https URL required"), 400
    with get_db() as conn:
        code = new_code(conn)
        conn.execute(
            "INSERT INTO links (code, url, created_at) VALUES (?, ?, ?)",
            (code, url, time.time()),
        )
    return jsonify(code=code, short_url=short_url(code), qr_image=f"/qr/{code}.png", url=url), 201


@app.route("/r/<code>")
def go(code):
    with get_db() as conn:
        row = conn.execute("SELECT url FROM links WHERE code=?", (code,)).fetchone()
        if not row:
            return jsonify(error="Unknown code"), 404
        conn.execute("UPDATE links SET scans = scans + 1 WHERE code=?", (code,))
    return redirect(row["url"], code=302)


@app.route("/api/update/<code>", methods=["PUT"])
def update(code):
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not valid_url(url):
        return jsonify(error="Valid http/https URL required"), 400
    with get_db() as conn:
        cur = conn.execute("UPDATE links SET url=? WHERE code=?", (url, code))
        if cur.rowcount == 0:
            return jsonify(error="Unknown code"), 404
    return jsonify(code=code, url=url)


@app.route("/api/stats/<code>")
def stats(code):
    with get_db() as conn:
        row = conn.execute(
            "SELECT code, url, scans, created_at FROM links WHERE code=?", (code,)
        ).fetchone()
    if not row:
        return jsonify(error="Unknown code"), 404
    return jsonify(dict(row))


@app.route("/qr/<code>.png")
def qr_png(code):
    with get_db() as conn:
        if not conn.execute("SELECT 1 FROM links WHERE code=?", (code,)).fetchone():
            return jsonify(error="Unknown code"), 404
    img = qrcode.make(short_url(code), box_size=10, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
