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

# Secret key: use env var on Render, fallback for local dev
app.secret_key = os.environ.get("SECRET_KEY", "dev-change-this-key")

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
    """Create tables if they don't exist."""
    conn = get_db()
    cur = conn.cursor()

    # users
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

    # direct messages: sender -> receiver, text or image
    cur.execute(
        """
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


# ---------------------- AUTH ROUTES ---------------------- #
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


# ---------------------- CHAT PAGES ---------------------- #
@app.route("/chat")
@app.route("/chat/<username>")
@login_required
def chat(username=None):
    """Main chat UI. User chooses partner only via search."""
    current_username = session["username"]
    current_user_id = session["user_id"]

    active_username = None
    if username:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM users WHERE username = ? AND id != ?",
            (username, current_user_id),
        )
        other = cur.fetchone()
        conn.close()

        if other:
            active_username = username
        else:
            flash("User not found.", "error")
            return redirect(url_for("chat"))

    return render_template(
        "chat.html",
        current_username=current_username,
        active_username=active_username,
    )


# ---------------------- FILE SERVE ---------------------- #
@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


# ---------------------- CHAT APIs ---------------------- #
def _get_other_user(username, current_user_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, username FROM users WHERE username = ? AND id != ?",
        (username, current_user_id),
    )
    user = cur.fetchone()
    conn.close()
    return user


@app.route("/api/messages/<username>", methods=["GET", "POST"])
@login_required
def api_messages(username):
    """Get or send TEXT messages in a personal chat with 'username'."""
    current_user_id = session["user_id"]
    current_username = session["username"]

    other = _get_other_user(username, current_user_id)
    if other is None:
        return jsonify({"error": "User not found"}), 404

    other_id = other["id"]

    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        data = request.get_json() or {}
        text = (data.get("text") or "").strip()

        if not text:
            conn.close()
            return jsonify({"error": "Empty message"}), 400

        created_at = datetime.now().strftime("%I:%M %p")

        cur.execute(
            """
            INSERT INTO messages (sender_id, receiver_id, text, image_path, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (current_user_id, other_id, text, None, created_at),
        )
        conn.commit()
        conn.close()
        return jsonify({"status": "ok"})

    # GET: all messages between the two users
    cur.execute(
        """
        SELECT m.id,
               su.username AS sender,
               ru.username AS receiver,
               m.text,
               m.image_path,
               m.created_at
        FROM messages m
        JOIN users su ON m.sender_id = su.id
        JOIN users ru ON m.receiver_id = ru.id
        WHERE (m.sender_id = ? AND m.receiver_id = ?)
           OR (m.sender_id = ? AND m.receiver_id = ?)
        ORDER BY m.id ASC
        """,
        (current_user_id, other_id, other_id, current_user_id),
    )
    rows = cur.fetchall()
    conn.close()

    messages_list = []
    for row in rows:
        image_url = (
            url_for("uploaded_file", filename=row["image_path"])
            if row["image_path"]
            else None
        )
        messages_list.append(
            {
                "id": row["id"],
                "sender": row["sender"],
                "receiver": row["receiver"],
                "text": row["text"] or "",
                "image_url": image_url,
                "created_at": row["created_at"],
            }
        )
    return jsonify(messages_list)


@app.route("/api/messages/<username>/image", methods=["POST"])
@login_required
def api_messages_image(username):
    """Send an IMAGE message to 'username'."""
    current_user_id = session["user_id"]

    other = _get_other_user(username, current_user_id)
    if other is None:
        return jsonify({"error": "User not found"}), 404

    other_id = other["id"]

    file = request.files.get("image")
    if not file or file.filename == "":
        return jsonify({"error": "No image provided"}), 400

    # Save file
    filename = f"{current_user_id}_{int(time.time())}_{secure_filename(file.filename)}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    created_at = datetime.now().strftime("%I:%M %p")

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO messages (sender_id, receiver_id, text, image_path, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (current_user_id, other_id, None, filename, created_at),
    )
    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


# ---------------------- MAIN ---------------------- #
if __name__ == "__main__":
    app.run(debug=True)
