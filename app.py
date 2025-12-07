from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    jsonify,
    flash,
    send_from_directory,
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from functools import wraps
import sqlite3
import os
import time

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-key")

BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "chat.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ---------------------- DB HELPERS ---------------------- #
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Creates users + messages tables only if not exist."""
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            text TEXT,
            image_path TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(sender_id) REFERENCES users(id),
            FOREIGN KEY(receiver_id) REFERENCES users(id)
        );
    """)

    conn.commit()
    conn.close()


# Initialize database
init_db()


# ---------------------- LOGIN REQUIRED DECORATOR ---------------------- #
def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapper


# ---------------------- HOME ---------------------- #
@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("chat"))
    return redirect(url_for("login"))


# ---------------------- REGISTER ---------------------- #
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()

        if not username or not password:
            flash("Username & Password required", "error")
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
            flash("Username already taken", "error")
            conn.close()
            return redirect(url_for("register"))

        conn.close()
        flash("Registration successful!", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


# ---------------------- LOGIN ---------------------- #
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()

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
            flash("Incorrect username or password", "error")
            return redirect(url_for("login"))

    return render_template("login.html")


# ---------------------- LOGOUT ---------------------- #
@app.route("/logout")
@login_required
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------- CHAT PAGE ---------------------- #
@app.route("/chat")
@app.route("/chat/<username>")
@login_required
def chat(username=None):
    return render_template(
        "chat.html",
        current_username=session["username"],
        active_username=username or "",
    )


# ---------------------- FILE SERVE ---------------------- #
@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


# ---------------------- HELPER ---------------------- #
def get_chat_partner(username, current_user_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM users WHERE username = ? AND id != ?",
        (username, current_user_id)
    )
    user = cur.fetchone()
    conn.close()
    return user


# ---------------------- API: TEXT MESSAGES ---------------------- #
@app.route("/api/messages/<username>", methods=["GET", "POST"])
@login_required
def api_messages(username):
    current_id = session["user_id"]
    current_user = session["username"]

    other = get_chat_partner(username, current_id)
    if not other:
        return jsonify({"error": "User does not exist"}), 404

    other_id = other["id"]

    conn = get_db()
    cur = conn.cursor()

    # SEND TEXT
    if request.method == "POST":
        text = request.json.get("text", "").strip()
        if not text:
            return jsonify({"error": "Empty message"}), 400

        time_now = datetime.now().strftime("%I:%M %p")

        cur.execute(
            "INSERT INTO messages (sender_id, receiver_id, text, image_path, created_at) VALUES (?, ?, ?, ?, ?)",
            (current_id, other_id, text, None, time_now)
        )
        conn.commit()
        conn.close()
        return jsonify({"status": "ok"})

    # GET ALL MESSAGES
    cur.execute(
        """
        SELECT m.id, su.username AS sender, m.text, m.image_path, m.created_at
        FROM messages m
        JOIN users su ON m.sender_id = su.id
        WHERE (m.sender_id = ? AND m.receiver_id = ?)
           OR (m.sender_id = ? AND m.receiver_id = ?)
        ORDER BY m.id ASC
        """,
        (current_id, other_id, other_id, current_id)
    )
    rows = cur.fetchall()
    conn.close()

    msgs = []
    for row in rows:
        msgs.append({
            "id": row["id"],
            "sender": row["sender"],
            "text": row["text"] or "",
            "image_url": url_for("uploaded_file", filename=row["image_path"]) if row["image_path"] else None,
            "created_at": row["created_at"],
        })

    return jsonify(msgs)


# ---------------------- API: SEND IMAGE ---------------------- #
@app.route("/api/messages/<username>/image", methods=["POST"])
@login_required
def send_image(username):
    current_id = session["user_id"]
    other = get_chat_partner(username, current_id)
    if not other:
        return jsonify({"error": "User not found"}), 404

    other_id = other["id"]
    file = request.files.get("image")

    if not file:
        return jsonify({"error": "No image sent"}), 400

    filename = f"{current_id}_{int(time.time())}_{secure_filename(file.filename)}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    time_now = datetime.now().strftime("%I:%M %p")

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO messages (sender_id, receiver_id, text, image_path, created_at) VALUES (?, ?, ?, ?, ?)",
        (current_id, other_id, None, filename, time_now)
    )
    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True)
