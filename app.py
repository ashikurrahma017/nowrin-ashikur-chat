from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    jsonify,
    flash,
)
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps
import sqlite3
import os

app = Flask(__name__)

# Secret key: use env var on Render, fallback for local dev
app.secret_key = os.environ.get("SECRET_KEY", "dev-change-this-key")

# SQLite database path
DB_PATH = os.path.join(os.path.dirname(__file__), "chat.db")


# ---------------------- DB HELPERS ---------------------- #
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            text TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """
    )

    conn.commit()
    conn.close()


# Run DB init once when module is imported
init_db()


# ---------------------- AUTH DECORATOR ---------------------- #
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


# ---------------------- ROUTES ---------------------- #
@app.route("/")
def index():
    """Home – redirect based on login status."""
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
                "INSERT INTO users (username, password_hash, created_at) "
                "VALUES (?, ?, ?)",
                (
                    username,
                    generate_password_hash(password),
                    datetime.utcnow().isoformat(),
                ),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            flash("Username already taken. Choose another one.", "error")
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
        cur.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,),
        )
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

        created_at = datetime.now().strftime("%I:%M %p")  # like 12:44 AM

        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO messages (user_id, username, text, created_at) "
            "VALUES (?, ?, ?, ?)",
            (session["user_id"], session["username"], text, created_at),
        )
        conn.commit()
        conn.close()

        return jsonify({"status": "ok"})

    # GET: return all messages
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, username, text, created_at FROM messages ORDER BY id ASC"
    )
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


# ---------------------- MAIN ---------------------- #
if __name__ == "__main__":
    # Local only; on Render we use `gunicorn app:app`
    app.run(debug=True)
