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

    # direct messages: sender -> receiver
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            text TEXT NOT NULL,
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


# ---------------------- CHAT PAGE ---------------------- #
@app.route("/chat")
@app.route("/chat/<username>")
@login_required
def chat(username=None):
    """
    Main chat UI.
    - Desktop: list + chat.
    - Mobile:
        * /chat       → only list of people
        * /chat/<u>   → only chat with that user (+ back button)
    - In the list, show last text message or "Let's chat".
    """
    current_username = session["username"]
    current_user_id = session["user_id"]

    conn = get_db()
    cur = conn.cursor()

    # Get all other users
    cur.execute(
        "SELECT id, username FROM users WHERE id != ? ORDER BY username ASC",
        (current_user_id,),
    )
    rows = cur.fetchall()

    users = []
    for row in rows:
        other_id = row["id"]

        # Find last message between me and this user (TEXT ONLY to avoid old schemas)
        cur2 = conn.cursor()
        cur2.execute(
            """
            SELECT text, created_at
            FROM messages
            WHERE (sender_id = ? AND receiver_id = ?)
               OR (sender_id = ? AND receiver_id = ?)
            ORDER BY id DESC
            LIMIT 1
            """,
            (current_user_id, other_id, other_id, current_user_id),
        )
        last = cur2.fetchone()

        if last and last["text"]:
            last_msg = last["text"]
        else:
            last_msg = "Let's chat"

        users.append(
            {
                "id": other_id,
                "username": row["username"],
                "last_msg": last_msg,
            }
        )

    conn.close()

    return render_template(
        "chat.html",
        current_username=current_username,
        active_username=username or "",
        users=users,
    )




# ---------------------- CHAT APIs ---------------------- #
@app.route("/api/messages/<username>", methods=["GET", "POST"])
@login_required
def api_messages(username):
    """Get or send messages in a personal chat with 'username'."""
    current_user_id = session["user_id"]

    conn = get_db()
    cur = conn.cursor()

    # find the other user
    cur.execute("SELECT id, username FROM users WHERE username = ?", (username,))
    other = cur.fetchone()

    if other is None:
        conn.close()
        return jsonify({"error": "User not found"}), 404

    other_id = other["id"]

    if other_id == current_user_id:
        conn.close()
        return jsonify({"error": "Cannot chat with yourself"}), 400

    if request.method == "POST":
        data = request.get_json() or {}
        text = (data.get("text") or "").strip()

        if not text:
            conn.close()
            return jsonify({"error": "Empty message"}), 400

        created_at = datetime.now().strftime("%I:%M %p")  # like 12:44 AM

        cur.execute(
            """
            INSERT INTO messages (sender_id, receiver_id, text, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (current_user_id, other_id, text, created_at),
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

    messages_list = [
        {
            "id": row["id"],
            "sender": row["sender"],
            "receiver": row["receiver"],
            "text": row["text"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]

    return jsonify(messages_list)


# Simple API to list users (not strictly required, but handy if needed later)
@app.route("/api/users")
@login_required
def api_users():
    current_user_id = session["user_id"]
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, username FROM users WHERE id != ? ORDER BY username ASC",
        (current_user_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return jsonify(
        [{"id": r["id"], "username": r["username"]} for r in rows]
    )


# ---------------------- MAIN ---------------------- #
if __name__ == "__main__":
    # Local only; on Render we use `gunicorn app:app`
    app.run(debug=True)


