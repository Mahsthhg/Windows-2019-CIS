import sqlite3
import random
import string
from datetime import datetime
from config import DB_PATH


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    conn = _get_conn()
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id      INTEGER PRIMARY KEY,
            username     TEXT,
            full_name    TEXT,
            join_date    TEXT    DEFAULT (datetime('now','localtime')),
            is_blocked   INTEGER DEFAULT 0,
            total_orders INTEGER DEFAULT 0,
            total_spent  INTEGER DEFAULT 0,
            referral_code TEXT   UNIQUE,
            referred_by  INTEGER
        );

        CREATE TABLE IF NOT EXISTS orders (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id        INTEGER NOT NULL,
            username       TEXT,
            full_name      TEXT,
            gb_amount      INTEGER NOT NULL,
            total_price    INTEGER NOT NULL,
            receipt_file_id TEXT,
            status         TEXT DEFAULT 'pending',
            config         TEXT,
            sub_link       TEXT,
            admin_note     TEXT,
            created_at     TEXT DEFAULT (datetime('now','localtime')),
            updated_at     TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS support_tickets (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,
            username     TEXT,
            full_name    TEXT,
            message      TEXT NOT NULL,
            admin_reply  TEXT,
            status       TEXT DEFAULT 'open',
            created_at   TEXT DEFAULT (datetime('now','localtime')),
            updated_at   TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS discount_codes (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            code         TEXT UNIQUE NOT NULL,
            discount_pct INTEGER NOT NULL,
            max_uses     INTEGER DEFAULT 1,
            used_count   INTEGER DEFAULT 0,
            is_active    INTEGER DEFAULT 1,
            created_at   TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS code_uses (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            code     TEXT NOT NULL,
            user_id  INTEGER NOT NULL,
            order_id INTEGER,
            used_at  TEXT DEFAULT (datetime('now','localtime'))
        );
    """)

    conn.commit()
    conn.close()


# ─── User ─────────────────────────────────────────────────────────────────────

def upsert_user(user_id: int, username: str | None, full_name: str) -> None:
    referral_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    conn = _get_conn()
    conn.execute("""
        INSERT INTO users (user_id, username, full_name, referral_code)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username  = excluded.username,
            full_name = excluded.full_name
    """, (user_id, username, full_name, referral_code))
    conn.commit()
    conn.close()


def get_user(user_id: int) -> dict | None:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_users() -> list[dict]:
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM users WHERE is_blocked = 0").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def block_user(user_id: int) -> None:
    conn = _get_conn()
    conn.execute("UPDATE users SET is_blocked = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def unblock_user(user_id: int) -> None:
    conn = _get_conn()
    conn.execute("UPDATE users SET is_blocked = 0 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


# ─── Orders ───────────────────────────────────────────────────────────────────

def create_order(user_id, username, full_name, gb_amount, total_price, receipt_file_id) -> int:
    conn = _get_conn()
    cur = conn.execute("""
        INSERT INTO orders (user_id, username, full_name, gb_amount, total_price, receipt_file_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, username or "—", full_name, gb_amount, total_price, receipt_file_id))
    order_id = cur.lastrowid
    conn.execute("UPDATE users SET total_orders = total_orders + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return order_id


def get_order(order_id: int) -> dict | None:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_orders(user_id: int) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT 10",
        (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_pending_orders() -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM orders WHERE status = 'pending' ORDER BY created_at ASC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def approve_order(order_id: int, config: str, sub_link: str) -> dict | None:
    conn = _get_conn()
    conn.execute("""
        UPDATE orders
        SET status = 'approved', config = ?, sub_link = ?,
            updated_at = datetime('now','localtime')
        WHERE id = ?
    """, (config, sub_link, order_id))
    row = conn.execute("SELECT user_id, total_price FROM orders WHERE id = ?", (order_id,)).fetchone()
    if row:
        conn.execute("""
            UPDATE users SET total_spent = total_spent + ? WHERE user_id = ?
        """, (row["total_price"], row["user_id"]))
    conn.commit()
    conn.close()
    return dict(row) if row else None


def reject_order(order_id: int, note: str = "") -> dict | None:
    conn = _get_conn()
    conn.execute("""
        UPDATE orders
        SET status = 'rejected', admin_note = ?,
            updated_at = datetime('now','localtime')
        WHERE id = ?
    """, (note, order_id))
    row = conn.execute("SELECT user_id FROM orders WHERE id = ?", (order_id,)).fetchone()
    conn.commit()
    conn.close()
    return dict(row) if row else None


# ─── Support Tickets ──────────────────────────────────────────────────────────

def create_ticket(user_id: int, username: str | None, full_name: str, message: str) -> int:
    conn = _get_conn()
    cur = conn.execute("""
        INSERT INTO support_tickets (user_id, username, full_name, message)
        VALUES (?, ?, ?, ?)
    """, (user_id, username, full_name, message))
    ticket_id = cur.lastrowid
    conn.commit()
    conn.close()
    return ticket_id


def get_ticket(ticket_id: int) -> dict | None:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM support_tickets WHERE id = ?", (ticket_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def close_ticket(ticket_id: int, reply: str) -> int | None:
    conn = _get_conn()
    conn.execute("""
        UPDATE support_tickets
        SET admin_reply = ?, status = 'closed',
            updated_at = datetime('now','localtime')
        WHERE id = ?
    """, (reply, ticket_id))
    row = conn.execute("SELECT user_id FROM support_tickets WHERE id = ?", (ticket_id,)).fetchone()
    conn.commit()
    conn.close()
    return row["user_id"] if row else None


# ─── Discount Codes ───────────────────────────────────────────────────────────

def get_discount_code(code: str) -> dict | None:
    conn = _get_conn()
    row = conn.execute("""
        SELECT * FROM discount_codes
        WHERE code = ? AND is_active = 1 AND used_count < max_uses
    """, (code.upper(),)).fetchone()
    conn.close()
    return dict(row) if row else None


def use_discount_code(code: str, user_id: int, order_id: int) -> None:
    conn = _get_conn()
    conn.execute("UPDATE discount_codes SET used_count = used_count + 1 WHERE code = ?", (code,))
    conn.execute("INSERT INTO code_uses (code, user_id, order_id) VALUES (?, ?, ?)",
                 (code, user_id, order_id))
    conn.commit()
    conn.close()


def create_discount_code(code: str, discount_pct: int, max_uses: int = 1) -> None:
    conn = _get_conn()
    conn.execute("""
        INSERT OR REPLACE INTO discount_codes (code, discount_pct, max_uses)
        VALUES (?, ?, ?)
    """, (code.upper(), discount_pct, max_uses))
    conn.commit()
    conn.close()


# ─── Statistics ───────────────────────────────────────────────────────────────

def get_stats() -> dict:
    conn = _get_conn()
    s = {}
    s["total_users"]    = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    s["pending_orders"] = conn.execute("SELECT COUNT(*) FROM orders WHERE status='pending'").fetchone()[0]
    s["approved_orders"]= conn.execute("SELECT COUNT(*) FROM orders WHERE status='approved'").fetchone()[0]
    s["rejected_orders"]= conn.execute("SELECT COUNT(*) FROM orders WHERE status='rejected'").fetchone()[0]
    s["total_revenue"]  = conn.execute("SELECT COALESCE(SUM(total_price),0) FROM orders WHERE status='approved'").fetchone()[0]
    s["total_gb_sold"]  = conn.execute("SELECT COALESCE(SUM(gb_amount),0) FROM orders WHERE status='approved'").fetchone()[0]
    s["open_tickets"]   = conn.execute("SELECT COUNT(*) FROM support_tickets WHERE status='open'").fetchone()[0]
    conn.close()
    return s
