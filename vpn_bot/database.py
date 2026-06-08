import sqlite3
import random
import string
from config import DB_PATH


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    return c


def init_db() -> None:
    db = _conn()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id        INTEGER PRIMARY KEY,
            username       TEXT,
            full_name      TEXT,
            join_date      TEXT    DEFAULT (datetime('now','localtime')),
            is_blocked     INTEGER DEFAULT 0,
            total_orders   INTEGER DEFAULT 0,
            total_spent    INTEGER DEFAULT 0,
            wallet_balance INTEGER DEFAULT 0,
            referral_code  TEXT    UNIQUE,
            referred_by    INTEGER,
            free_trial_used INTEGER DEFAULT 0,
            notif_expiry   INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS orders (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            username        TEXT,
            full_name       TEXT,
            gb_amount       INTEGER NOT NULL,
            total_price     INTEGER NOT NULL,
            paid_by_wallet  INTEGER DEFAULT 0,
            receipt_file_id TEXT,
            status          TEXT    DEFAULT 'pending',
            config          TEXT,
            sub_link        TEXT,
            panel_username  TEXT,
            expiry_date     TEXT,
            admin_note      TEXT,
            rating          INTEGER,
            rating_note     TEXT,
            is_trial        INTEGER DEFAULT 0,
            created_at      TEXT    DEFAULT (datetime('now','localtime')),
            updated_at      TEXT    DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS wallet_transactions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            amount      INTEGER NOT NULL,
            type        TEXT    NOT NULL,
            note        TEXT,
            order_id    INTEGER,
            receipt_file_id TEXT,
            status      TEXT    DEFAULT 'pending',
            created_at  TEXT    DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS support_tickets (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            username    TEXT,
            full_name   TEXT,
            message     TEXT    NOT NULL,
            admin_reply TEXT,
            status      TEXT    DEFAULT 'open',
            created_at  TEXT    DEFAULT (datetime('now','localtime')),
            updated_at  TEXT    DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS discount_codes (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            code         TEXT    UNIQUE NOT NULL,
            discount_pct INTEGER NOT NULL,
            max_uses     INTEGER DEFAULT 1,
            used_count   INTEGER DEFAULT 0,
            is_active    INTEGER DEFAULT 1,
            created_at   TEXT    DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS code_uses (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            code     TEXT    NOT NULL,
            user_id  INTEGER NOT NULL,
            order_id INTEGER,
            used_at  TEXT    DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS config_templates (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT    NOT NULL UNIQUE,
            config     TEXT    NOT NULL,
            sub_link   TEXT,
            use_count  INTEGER DEFAULT 0,
            created_at TEXT    DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS referrals (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id  INTEGER NOT NULL,
            referee_id   INTEGER NOT NULL UNIQUE,
            bonus_given  INTEGER DEFAULT 0,
            created_at   TEXT    DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS expiry_notified (
            order_id   INTEGER PRIMARY KEY,
            notified_at TEXT   DEFAULT (datetime('now','localtime'))
        );
    """)
    db.commit()
    db.close()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _rand_code(n=8) -> str:
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=n))


# ─── Users ────────────────────────────────────────────────────────────────────

def upsert_user(user_id: int, username, full_name: str, referred_by: int = None) -> bool:
    """Returns True if this is a new user."""
    db = _conn()
    exists = db.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,)).fetchone()
    code = _rand_code()
    db.execute("""
        INSERT INTO users (user_id, username, full_name, referral_code, referred_by)
        VALUES (?,?,?,?,?)
        ON CONFLICT(user_id) DO UPDATE SET
            username=excluded.username, full_name=excluded.full_name
    """, (user_id, username, full_name, code, referred_by if not exists else None))
    if not exists and referred_by:
        db.execute("""
            INSERT OR IGNORE INTO referrals (referrer_id, referee_id) VALUES (?,?)
        """, (referred_by, user_id))
    db.commit()
    db.close()
    return not bool(exists)


def get_user(user_id: int) -> dict | None:
    db = _conn()
    r = db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    db.close()
    return dict(r) if r else None


def get_user_by_ref_code(code: str) -> dict | None:
    db = _conn()
    r = db.execute("SELECT * FROM users WHERE referral_code=?", (code.upper(),)).fetchone()
    db.close()
    return dict(r) if r else None


def get_all_users() -> list[dict]:
    db = _conn()
    rows = db.execute("SELECT * FROM users WHERE is_blocked=0 ORDER BY join_date DESC").fetchall()
    db.close()
    return [dict(r) for r in rows]


def block_user(uid: int):
    db = _conn(); db.execute("UPDATE users SET is_blocked=1 WHERE user_id=?", (uid,)); db.commit(); db.close()


def unblock_user(uid: int):
    db = _conn(); db.execute("UPDATE users SET is_blocked=0 WHERE user_id=?", (uid,)); db.commit(); db.close()


def mark_trial_used(uid: int):
    db = _conn(); db.execute("UPDATE users SET free_trial_used=1 WHERE user_id=?", (uid,)); db.commit(); db.close()


# ─── Wallet ───────────────────────────────────────────────────────────────────

def get_wallet(user_id: int) -> int:
    db = _conn()
    r = db.execute("SELECT wallet_balance FROM users WHERE user_id=?", (user_id,)).fetchone()
    db.close()
    return r["wallet_balance"] if r else 0


def create_wallet_charge(user_id: int, amount: int, receipt_file_id: str) -> int:
    db = _conn()
    cur = db.execute("""
        INSERT INTO wallet_transactions (user_id, amount, type, receipt_file_id, status)
        VALUES (?, ?, 'charge', ?, 'pending')
    """, (user_id, amount, receipt_file_id))
    tx_id = cur.lastrowid
    db.commit(); db.close()
    return tx_id


def approve_wallet_charge(tx_id: int) -> dict | None:
    db = _conn()
    tx = db.execute("SELECT * FROM wallet_transactions WHERE id=?", (tx_id,)).fetchone()
    if not tx:
        db.close(); return None
    db.execute("UPDATE wallet_transactions SET status='approved' WHERE id=?", (tx_id,))
    db.execute("UPDATE users SET wallet_balance=wallet_balance+? WHERE user_id=?",
               (tx["amount"], tx["user_id"]))
    db.commit(); db.close()
    return dict(tx)


def reject_wallet_charge(tx_id: int) -> dict | None:
    db = _conn()
    tx = db.execute("SELECT * FROM wallet_transactions WHERE id=?", (tx_id,)).fetchone()
    if tx:
        db.execute("UPDATE wallet_transactions SET status='rejected' WHERE id=?", (tx_id,))
        db.commit()
    db.close()
    return dict(tx) if tx else None


def deduct_wallet(user_id: int, amount: int, order_id: int) -> bool:
    db = _conn()
    bal = db.execute("SELECT wallet_balance FROM users WHERE user_id=?", (user_id,)).fetchone()
    if not bal or bal["wallet_balance"] < amount:
        db.close(); return False
    db.execute("UPDATE users SET wallet_balance=wallet_balance-? WHERE user_id=?", (amount, user_id))
    db.execute("INSERT INTO wallet_transactions (user_id,amount,type,note,order_id,status) VALUES (?,?,?,?,?,'approved')",
               (user_id, -amount, 'purchase', f'سفارش #{order_id}', order_id))
    db.commit(); db.close()
    return True


def admin_adjust_wallet(user_id: int, amount: int, note: str = "تنظیم دستی ادمین"):
    db = _conn()
    db.execute("UPDATE users SET wallet_balance=MAX(0,wallet_balance+?) WHERE user_id=?", (amount, user_id))
    db.execute("INSERT INTO wallet_transactions (user_id,amount,type,note,status) VALUES (?,?,'admin_adjust',?,'approved')",
               (user_id, amount, note))
    db.commit(); db.close()


def get_wallet_history(user_id: int, limit=10) -> list[dict]:
    db = _conn()
    rows = db.execute("""
        SELECT * FROM wallet_transactions WHERE user_id=?
        ORDER BY created_at DESC LIMIT ?
    """, (user_id, limit)).fetchall()
    db.close()
    return [dict(r) for r in rows]


def get_pending_wallet_charges() -> list[dict]:
    db = _conn()
    rows = db.execute("""
        SELECT wt.*, u.full_name, u.username
        FROM wallet_transactions wt
        JOIN users u ON u.user_id=wt.user_id
        WHERE wt.status='pending' AND wt.type='charge'
        ORDER BY wt.created_at ASC
    """).fetchall()
    db.close()
    return [dict(r) for r in rows]


# ─── Orders ───────────────────────────────────────────────────────────────────

def create_order(user_id, username, full_name, gb_amount, total_price,
                 receipt_file_id=None, paid_by_wallet=0, is_trial=0) -> int:
    db = _conn()
    cur = db.execute("""
        INSERT INTO orders (user_id,username,full_name,gb_amount,total_price,
                            receipt_file_id,paid_by_wallet,is_trial)
        VALUES (?,?,?,?,?,?,?,?)
    """, (user_id, username or "—", full_name, gb_amount, total_price,
          receipt_file_id, paid_by_wallet, is_trial))
    oid = cur.lastrowid
    db.execute("UPDATE users SET total_orders=total_orders+1 WHERE user_id=?", (user_id,))
    db.commit(); db.close()
    return oid


def get_order(order_id: int) -> dict | None:
    db = _conn()
    r = db.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    db.close()
    return dict(r) if r else None


def get_user_orders(user_id: int, limit=10) -> list[dict]:
    db = _conn()
    rows = db.execute(
        "SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


def get_pending_orders() -> list[dict]:
    db = _conn()
    rows = db.execute(
        "SELECT * FROM orders WHERE status='pending' ORDER BY created_at ASC"
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


def approve_order(order_id: int, config: str, sub_link: str,
                  expiry_date: str = None, panel_username: str = None) -> dict | None:
    db = _conn()
    db.execute("""
        UPDATE orders SET status='approved', config=?, sub_link=?,
            expiry_date=?, panel_username=?, updated_at=datetime('now','localtime')
        WHERE id=?
    """, (config, sub_link, expiry_date, panel_username, order_id))
    row = db.execute("SELECT user_id,total_price FROM orders WHERE id=?", (order_id,)).fetchone()
    if row:
        db.execute("UPDATE users SET total_spent=total_spent+? WHERE user_id=?",
                   (row["total_price"], row["user_id"]))
        _check_referral_bonus(db, row["user_id"], order_id)
    db.commit(); db.close()
    return dict(row) if row else None


def _check_referral_bonus(db, user_id: int, order_id: int):
    """اگر اولین خرید موفق کاربر است، به هر دو طرف جایزه بده."""
    from config import REFERRAL_BONUS_GB, REFERRAL_BONUS_TOMAN
    approved_count = db.execute(
        "SELECT COUNT(*) FROM orders WHERE user_id=? AND status='approved'",
        (user_id,)
    ).fetchone()[0]
    if approved_count != 1:
        return
    ref = db.execute(
        "SELECT * FROM referrals WHERE referee_id=? AND bonus_given=0",
        (user_id,)
    ).fetchone()
    if not ref:
        return
    if REFERRAL_BONUS_TOMAN > 0:
        db.execute("UPDATE users SET wallet_balance=wallet_balance+? WHERE user_id=?",
                   (REFERRAL_BONUS_TOMAN, ref["referrer_id"]))
        db.execute("UPDATE users SET wallet_balance=wallet_balance+? WHERE user_id=?",
                   (REFERRAL_BONUS_TOMAN, user_id))
        db.execute("INSERT INTO wallet_transactions (user_id,amount,type,note,status) VALUES (?,?,'referral_bonus','جایزه معرفی','approved')",
                   (ref["referrer_id"], REFERRAL_BONUS_TOMAN))
        db.execute("INSERT INTO wallet_transactions (user_id,amount,type,note,status) VALUES (?,?,'referral_bonus','جایزه معرفی دوستان','approved')",
                   (user_id, REFERRAL_BONUS_TOMAN))
    db.execute("UPDATE referrals SET bonus_given=1 WHERE id=?", (ref["id"],))


def reject_order(order_id: int, note: str = "") -> dict | None:
    db = _conn()
    db.execute("""
        UPDATE orders SET status='rejected', admin_note=?,
            updated_at=datetime('now','localtime') WHERE id=?
    """, (note, order_id))
    # اگر با کیف پول پرداخت شده بود، برگشت داده شود
    order = db.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if order and order["paid_by_wallet"]:
        db.execute("UPDATE users SET wallet_balance=wallet_balance+? WHERE user_id=?",
                   (order["total_price"], order["user_id"]))
        db.execute("INSERT INTO wallet_transactions (user_id,amount,type,note,order_id,status) VALUES (?,?,'refund','بازگشت مبلغ سفارش رد شده',?,'approved')",
                   (order["user_id"], order["total_price"], order_id))
    row = db.execute("SELECT user_id FROM orders WHERE id=?", (order_id,)).fetchone()
    db.commit(); db.close()
    return dict(row) if row else None


def rate_order(order_id: int, rating: int, note: str = ""):
    db = _conn()
    db.execute("UPDATE orders SET rating=?, rating_note=? WHERE id=?", (rating, note, order_id))
    db.commit(); db.close()


def add_order_note(order_id: int, note: str):
    db = _conn()
    db.execute("UPDATE orders SET admin_note=? WHERE id=?", (note, order_id))
    db.commit(); db.close()


def search_orders(query: str) -> list[dict]:
    db = _conn()
    q = f"%{query}%"
    rows = db.execute("""
        SELECT * FROM orders
        WHERE CAST(id AS TEXT) LIKE ? OR username LIKE ? OR full_name LIKE ?
        ORDER BY created_at DESC LIMIT 20
    """, (q, q, q)).fetchall()
    db.close()
    return [dict(r) for r in rows]


def get_expiring_orders(days: int) -> list[dict]:
    db = _conn()
    rows = db.execute("""
        SELECT o.*, u.user_id
        FROM orders o JOIN users u ON u.user_id=o.user_id
        WHERE o.status='approved'
          AND o.expiry_date IS NOT NULL
          AND date(o.expiry_date) = date('now','localtime',?||' days')
          AND o.id NOT IN (SELECT order_id FROM expiry_notified)
          AND u.notif_expiry = 1
    """, (str(days),)).fetchall()
    db.close()
    return [dict(r) for r in rows]


def mark_expiry_notified(order_id: int):
    db = _conn()
    db.execute("INSERT OR IGNORE INTO expiry_notified (order_id) VALUES (?)", (order_id,))
    db.commit(); db.close()


# ─── Config Templates ─────────────────────────────────────────────────────────

def save_template(name: str, config: str, sub_link: str = "") -> int:
    db = _conn()
    cur = db.execute("""
        INSERT INTO config_templates (name, config, sub_link)
        VALUES (?,?,?)
        ON CONFLICT(name) DO UPDATE SET config=excluded.config, sub_link=excluded.sub_link
    """, (name, config, sub_link))
    tid = cur.lastrowid; db.commit(); db.close()
    return tid


def get_templates() -> list[dict]:
    db = _conn()
    rows = db.execute("SELECT * FROM config_templates ORDER BY use_count DESC").fetchall()
    db.close()
    return [dict(r) for r in rows]


def get_template(tid: int) -> dict | None:
    db = _conn()
    r = db.execute("SELECT * FROM config_templates WHERE id=?", (tid,)).fetchone()
    db.close()
    return dict(r) if r else None


def use_template(tid: int):
    db = _conn()
    db.execute("UPDATE config_templates SET use_count=use_count+1 WHERE id=?", (tid,))
    db.commit(); db.close()


def delete_template(tid: int):
    db = _conn()
    db.execute("DELETE FROM config_templates WHERE id=?", (tid,))
    db.commit(); db.close()


# ─── Discount Codes ───────────────────────────────────────────────────────────

def get_discount_code(code: str) -> dict | None:
    db = _conn()
    r = db.execute("""
        SELECT * FROM discount_codes
        WHERE code=? AND is_active=1 AND used_count < max_uses
    """, (code.upper(),)).fetchone()
    db.close()
    return dict(r) if r else None


def use_discount_code(code: str, user_id: int, order_id: int):
    db = _conn()
    db.execute("UPDATE discount_codes SET used_count=used_count+1 WHERE code=?", (code,))
    db.execute("INSERT INTO code_uses (code,user_id,order_id) VALUES (?,?,?)",
               (code, user_id, order_id))
    db.commit(); db.close()


def create_discount_code(code: str, pct: int, max_uses: int = 1):
    db = _conn()
    db.execute("INSERT OR REPLACE INTO discount_codes (code,discount_pct,max_uses) VALUES (?,?,?)",
               (code.upper(), pct, max_uses))
    db.commit(); db.close()


# ─── Support Tickets ──────────────────────────────────────────────────────────

def create_ticket(user_id: int, username, full_name: str, message: str) -> int:
    db = _conn()
    cur = db.execute("""
        INSERT INTO support_tickets (user_id,username,full_name,message)
        VALUES (?,?,?,?)
    """, (user_id, username, full_name, message))
    tid = cur.lastrowid; db.commit(); db.close()
    return tid


def close_ticket(tid: int, reply: str) -> int | None:
    db = _conn()
    db.execute("""
        UPDATE support_tickets SET admin_reply=?, status='closed',
            updated_at=datetime('now','localtime') WHERE id=?
    """, (reply, tid))
    r = db.execute("SELECT user_id FROM support_tickets WHERE id=?", (tid,)).fetchone()
    db.commit(); db.close()
    return r["user_id"] if r else None


def get_open_tickets() -> list[dict]:
    db = _conn()
    rows = db.execute(
        "SELECT * FROM support_tickets WHERE status='open' ORDER BY created_at DESC LIMIT 20"
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


# ─── Statistics ───────────────────────────────────────────────────────────────

def get_stats() -> dict:
    db = _conn()
    s = {}
    s["total_users"]     = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    s["blocked_users"]   = db.execute("SELECT COUNT(*) FROM users WHERE is_blocked=1").fetchone()[0]
    s["pending_orders"]  = db.execute("SELECT COUNT(*) FROM orders WHERE status='pending'").fetchone()[0]
    s["approved_orders"] = db.execute("SELECT COUNT(*) FROM orders WHERE status='approved'").fetchone()[0]
    s["rejected_orders"] = db.execute("SELECT COUNT(*) FROM orders WHERE status='rejected'").fetchone()[0]
    s["total_revenue"]   = db.execute("SELECT COALESCE(SUM(total_price),0) FROM orders WHERE status='approved'").fetchone()[0]
    s["wallet_revenue"]  = db.execute("SELECT COALESCE(SUM(total_price),0) FROM orders WHERE status='approved' AND paid_by_wallet=1").fetchone()[0]
    s["total_gb_sold"]   = db.execute("SELECT COALESCE(SUM(gb_amount),0) FROM orders WHERE status='approved'").fetchone()[0]
    s["open_tickets"]    = db.execute("SELECT COUNT(*) FROM support_tickets WHERE status='open'").fetchone()[0]
    s["total_wallet"]    = db.execute("SELECT COALESCE(SUM(wallet_balance),0) FROM users").fetchone()[0]
    s["avg_rating"]      = db.execute("SELECT COALESCE(AVG(rating),0) FROM orders WHERE rating IS NOT NULL").fetchone()[0]
    today = "date('now','localtime')"
    s["today_orders"]    = db.execute(f"SELECT COUNT(*) FROM orders WHERE date(created_at)={today}").fetchone()[0]
    s["today_revenue"]   = db.execute(f"SELECT COALESCE(SUM(total_price),0) FROM orders WHERE date(created_at)={today} AND status='approved'").fetchone()[0]
    db.close()
    return s


def export_orders_csv() -> str:
    db = _conn()
    rows = db.execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT 1000").fetchall()
    db.close()
    lines = ["id,user_id,username,gb_amount,total_price,status,expiry_date,created_at"]
    for r in rows:
        lines.append(f"{r['id']},{r['user_id']},{r['username'] or ''},{r['gb_amount']},"
                     f"{r['total_price']},{r['status']},{r['expiry_date'] or ''},{r['created_at']}")
    return "\n".join(lines)
