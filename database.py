import sqlite3

DATABASE = "bot.db"


def connect():
    return sqlite3.connect(DATABASE)


def init_db():
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            voice TEXT NOT NULL DEFAULT 'omr'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS library (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            voice TEXT NOT NULL,
            file_path TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    # Usage tracking for rate limiting & stats (public mode)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usage (
            user_id INTEGER NOT NULL,
            day TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            last_request REAL NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, day)
        )
    """)

    conn.commit()
    conn.close()


def is_new_user(user_id):
    """Return True if this user_id has never been seen before."""
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
    exists = cursor.fetchone() is not None
    conn.close()
    return not exists


def check_and_record_usage(user_id, cooldown_seconds, daily_limit):
    """Rate-limit check + recording in one call.

    Returns:
        (True, remaining_today) if the request is allowed
        (False, message) if the user hit a limit
    """
    import time as _time

    now = _time.time()
    today = _time.strftime("%Y-%m-%d")

    conn = connect()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT count, last_request FROM usage WHERE user_id = ? AND day = ?",
        (user_id, today),
    )
    row = cursor.fetchone()

    if row:
        count, last_request = row
        if now - last_request < cooldown_seconds:
            wait = int(cooldown_seconds - (now - last_request)) + 1
            conn.close()
            return False, f"⏳ Please wait {wait}s before your next request."
        if count >= daily_limit:
            conn.close()
            return False, (
                f"📊 Daily limit reached ({daily_limit} generations/day).\n"
                "Come back tomorrow! 🌙"
            )
        new_count = count + 1
        cursor.execute(
            """
            UPDATE usage SET count = ?, last_request = ?
            WHERE user_id = ? AND day = ?
            """,
            (new_count, now, user_id, today),
        )
    else:
        new_count = 1
        cursor.execute(
            "INSERT INTO usage (user_id, day, count, last_request) VALUES (?, ?, ?, ?)",
            (user_id, today, new_count, now),
        )

    conn.commit()
    conn.close()
    return True, daily_limit - new_count


def get_stats():
    """Global stats for the owner: (total_users, generations_today, generations_total)."""
    import time as _time

    today = _time.strftime("%Y-%m-%d")

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    cursor.execute("SELECT COALESCE(SUM(count), 0) FROM usage WHERE day = ?", (today,))
    gens_today = cursor.fetchone()[0]

    cursor.execute("SELECT COALESCE(SUM(count), 0) FROM usage")
    gens_total = cursor.fetchone()[0]

    conn.close()
    return total_users, gens_today, gens_total


def add_user(user_id):
    conn = connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT OR IGNORE INTO users (user_id, voice)
        VALUES (?, 'omr')
        """,
        (user_id,)
    )

    conn.commit()
    conn.close()


def get_voice(user_id):
    conn = connect()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT voice FROM users WHERE user_id = ?",
        (user_id,)
    )

    result = cursor.fetchone()
    conn.close()

    if result:
        return result[0]

    return "omr"


def set_voice(user_id, voice):
    conn = connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO users (user_id, voice)
        VALUES (?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET voice = excluded.voice
        """,
        (user_id, voice)
    )

    conn.commit()
    conn.close()


def save_to_library(user_id, text, voice, file_path):
    """Save audio to user's library."""
    conn = connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO library (user_id, text, voice, file_path)
        VALUES (?, ?, ?, ?)
        """,
        (user_id, text, voice, file_path)
    )

    conn.commit()
    library_id = cursor.lastrowid
    conn.close()

    return library_id


def get_library(user_id, limit=10):
    """Get user's library (most recent first)."""
    conn = connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, text, voice, file_path, created_at
        FROM library
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (user_id, limit)
    )

    results = cursor.fetchall()
    conn.close()

    return results


def get_library_item(user_id, item_id):
    """Get a specific library item."""
    conn = connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, text, voice, file_path, created_at
        FROM library
        WHERE user_id = ? AND id = ?
        """,
        (user_id, item_id)
    )

    result = cursor.fetchone()
    conn.close()

    return result


def delete_from_library(user_id, item_id):
    """Delete audio from user's library."""
    conn = connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        DELETE FROM library
        WHERE user_id = ? AND id = ?
        """,
        (user_id, item_id)
    )

    conn.commit()
    conn.close()