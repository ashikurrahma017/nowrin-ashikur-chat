from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = "change_this_to_a_very_secret_random_key"  # IMPORTANT: change in production
DB_PATH = "chat.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    if not os.path.exists(DB_PATH):
        conn = get_db()
        cur = conn.cursor()

        # Users table
        cur.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """)

        # Messages table
        cur.execute("""
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            text TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        """)

        conn.commit()
        conn.close()


@app.before_first_request
def setup():
    init_db()


def login_required(view_func):
    from functools import wraps

    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapped


@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("chat"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            flash("Username and password are required.", "error")
            return redirect(url_for("register"))

        conn = get_db()
        cur = conn.cursor()

        try:
            cur.execute(
                "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                (username, generate_password_hash(password), datetime.utcnow().isoformat())
            )
            conn.commit()
        except sqlite3.IntegrityError:
            flash("Username already taken. Choose another.", "error")
            conn.close()
            return redirect(url_for("register"))

        conn.close()
        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id, username, password_hash FROM users WHERE username = ?", (username,))
        user = cur.fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("chat"))
        else:
            flash("Invalid username or password.", "error")
            return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/chat")
@login_required
def chat():
    return render_template("chat.html", username=session.get("username"))


@app.route("/messages", methods=["GET", "POST"])
@login_required
def messages():
    if request.method == "POST":
        data = request.get_json() or {}
        text = (data.get("text") or "").strip()

        if not text:
            return jsonify({"error": "Empty message"}), 400

        user_id = session["user_id"]
        username = session["username"]
        created_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M")

        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO messages (user_id, username, text, created_at) VALUES (?, ?, ?, ?)",
            (user_id, username, text, created_at),
        )
        conn.commit()
        conn.close()

        return jsonify({"status": "ok"})

    # GET -> return all messages (or last N)
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, username, text, created_at FROM messages ORDER BY id ASC")
    rows = cur.fetchall()
    conn.close()

    messages_list = [
        {
            "id": row["id"],
            "username": row["username"],
            "text": row["text"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]

    return jsonify(messages_list)


if __name__ == "__main__":
    app.run(debug=True)
