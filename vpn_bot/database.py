"""Database layer — SQLite WAL, complete God-tier schema."""
import sqlite3, os, random, string
from contextlib import contextmanager
from config import DB_PATH

@contextmanager
def _conn():
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=NORMAL")
    c.execute("PRAGMA foreign_keys=ON")
    try:
        yield c; c.commit()
    except Exception:
        c.rollback(); raise
    finally:
        c.close()

def _rnd(n=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=n))

# ─── Init ─────────────────────────────────────────────────────────────────────

def init_db():
    with _conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT, full_name TEXT,
            join_date TEXT DEFAULT (datetime('now','localtime')),
            is_blocked INTEGER DEFAULT 0,
            total_orders INTEGER DEFAULT 0,
            total_spent INTEGER DEFAULT 0,
            wallet_balance INTEGER DEFAULT 0,
            bonus_mb INTEGER DEFAULT 0,
            referral_code TEXT UNIQUE,
            referred_by INTEGER,
            free_trial_used INTEGER DEFAULT 0,
            loyalty_points INTEGER DEFAULT 0,
            auto_renew INTEGER DEFAULT 0,
            last_seen TEXT DEFAULT (datetime('now','localtime')),
            notes TEXT
        );
        CREATE TABLE IF NOT EXISTS servers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            location TEXT DEFAULT 'نامشخص',
            flag TEXT DEFAULT '🌍',
            is_active INTEGER DEFAULT 1,
            is_default INTEGER DEFAULT 0,
            current_users INTEGER DEFAULT 0,
            max_users INTEGER DEFAULT 200,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER, username TEXT, full_name TEXT,
            gb_amount INTEGER, total_price INTEGER,
            status TEXT DEFAULT 'pending',
            config TEXT, sub_link TEXT, receipt_file_id TEXT,
            paid_by_wallet INTEGER DEFAULT 0, is_trial INTEGER DEFAULT 0,
            discount_code TEXT, discount_pct INTEGER DEFAULT 0,
            server_id INTEGER, panel_username TEXT, expiry_date TEXT,
            note TEXT, rating INTEGER, auto_renew INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS wallet_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER, username TEXT, full_name TEXT,
            amount INTEGER, type TEXT, status TEXT DEFAULT 'pending',
            receipt_file_id TEXT, order_id INTEGER, note TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER, username TEXT, full_name TEXT,
            message TEXT, status TEXT DEFAULT 'open', admin_reply TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')), closed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS discount_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL, discount_pct INTEGER NOT NULL,
            max_uses INTEGER DEFAULT 1, used_count INTEGER DEFAULT 0,
            expires_at TEXT, min_gb INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS discount_uses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT, user_id INTEGER, order_id INTEGER,
            used_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS config_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, config TEXT NOT NULL, sub_link TEXT,
            server_id INTEGER, use_count INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS bot_settings (
            key TEXT PRIMARY KEY, value TEXT,
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS resellers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE, username TEXT, full_name TEXT,
            commission_pct INTEGER DEFAULT 10, custom_price_per_gb INTEGER,
            balance INTEGER DEFAULT 0, total_sales INTEGER DEFAULT 0,
            total_commission INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS flash_sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, discount_pct INTEGER,
            starts_at TEXT, ends_at TEXT,
            is_active INTEGER DEFAULT 0, notified INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS lottery (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, prize_gb INTEGER DEFAULT 0, prize_toman INTEGER DEFAULT 0,
            draw_at TEXT, winner_user_id INTEGER, status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS lottery_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lottery_id INTEGER, user_id INTEGER,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(lottery_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS expiry_notifications (
            order_id INTEGER, notif_type TEXT,
            sent_at TEXT DEFAULT (datetime('now','localtime')),
            PRIMARY KEY(order_id, notif_type)
        );
        CREATE TABLE IF NOT EXISTS admin_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER, action TEXT, details TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS crypto_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT DEFAULT 'zarinpal',   -- 'zarinpal' | 'usdt_trc20'
            amount_toman INTEGER NOT NULL,
            authority TEXT,                  -- ZarinPal authority
            ref_id TEXT,                     -- ZarinPal ref_id after verify
            usdt_amount REAL,                -- USDT amount expected
            tx_hash TEXT,                    -- TRC20 tx hash after confirm
            status TEXT DEFAULT 'pending',   -- pending | confirmed | expired | failed
            created_at TEXT DEFAULT (datetime('now','localtime')),
            confirmed_at TEXT
        );
        """)

# ─── Users ────────────────────────────────────────────────────────────────────

def upsert_user(user_id, username, full_name, referred_by=None) -> bool:
    with _conn() as c:
        ex = c.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,)).fetchone()
        if ex:
            c.execute("UPDATE users SET username=?,full_name=?,last_seen=datetime('now','localtime') WHERE user_id=?",
                      (username, full_name, user_id))
            return False
        code = _rnd(8)
        c.execute("INSERT INTO users(user_id,username,full_name,referral_code,referred_by) VALUES(?,?,?,?,?)",
                  (user_id, username, full_name, code, referred_by))
        return True

def get_user(uid) -> dict | None:
    with _conn() as c:
        r = c.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
        return dict(r) if r else None

def get_all_users() -> list:
    with _conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM users ORDER BY join_date DESC")]

def get_user_by_ref_code(code) -> dict | None:
    with _conn() as c:
        r = c.execute("SELECT * FROM users WHERE referral_code=?", (code,)).fetchone()
        return dict(r) if r else None

def block_user(uid):
    with _conn() as c: c.execute("UPDATE users SET is_blocked=1 WHERE user_id=?", (uid,))

def unblock_user(uid):
    with _conn() as c: c.execute("UPDATE users SET is_blocked=0 WHERE user_id=?", (uid,))

def mark_trial_used(uid):
    with _conn() as c: c.execute("UPDATE users SET free_trial_used=1 WHERE user_id=?", (uid,))

def set_user_auto_renew(uid, val: bool):
    with _conn() as c: c.execute("UPDATE users SET auto_renew=? WHERE user_id=?", (int(val), uid))

def set_user_note(uid, note: str):
    with _conn() as c: c.execute("UPDATE users SET notes=? WHERE user_id=?", (note, uid))

def add_loyalty_points(uid, pts: int):
    with _conn() as c: c.execute("UPDATE users SET loyalty_points=loyalty_points+? WHERE user_id=?", (pts, uid))

def deduct_loyalty_points(uid, pts: int) -> bool:
    with _conn() as c:
        r = c.execute("SELECT loyalty_points FROM users WHERE user_id=?", (uid,)).fetchone()
        if not r or r[0] < pts: return False
        c.execute("UPDATE users SET loyalty_points=loyalty_points-? WHERE user_id=?", (pts, uid))
        return True

def get_loyalty_points(uid) -> int:
    with _conn() as c:
        r = c.execute("SELECT loyalty_points FROM users WHERE user_id=?", (uid,)).fetchone()
        return r[0] if r else 0

def get_bonus_mb(uid) -> int:
    with _conn() as c:
        r = c.execute("SELECT bonus_mb FROM users WHERE user_id=?", (uid,)).fetchone()
        return r[0] if r else 0

def deduct_bonus_mb(uid, mb):
    with _conn() as c: c.execute("UPDATE users SET bonus_mb=MAX(0,bonus_mb-?) WHERE user_id=?", (mb, uid))

def redeem_points_to_wallet(uid, points: int, toman: int) -> bool:
    """Deduct points from user and add toman to wallet. toman is the pre-computed amount."""
    with _conn() as c:
        r = c.execute("SELECT loyalty_points FROM users WHERE user_id=?", (uid,)).fetchone()
        if not r or r[0] < points: return False
        u = c.execute("SELECT username,full_name FROM users WHERE user_id=?", (uid,)).fetchone()
        c.execute("UPDATE users SET loyalty_points=loyalty_points-?,wallet_balance=wallet_balance+? WHERE user_id=?",
                  (points, toman, uid))
        c.execute("INSERT INTO wallet_transactions(user_id,username,full_name,amount,type,status,note) VALUES(?,?,?,?,'bonus','approved','تبدیل امتیاز')",
                  (uid, u['username'] if u else None, u['full_name'] if u else None, toman))
        return True

# ─── Servers ──────────────────────────────────────────────────────────────────

def get_servers(active_only=False) -> list:
    with _conn() as c:
        q = "SELECT * FROM servers" + (" WHERE is_active=1" if active_only else "") + " ORDER BY is_default DESC,id"
        rows = [dict(r) for r in c.execute(q)]
    for s in rows:
        mx = s.get("max_users") or 1
        s["load_pct"] = min(100, int(s.get("current_users", 0) * 100 / mx))
    return rows

def get_server(sid) -> dict | None:
    with _conn() as c:
        r = c.execute("SELECT * FROM servers WHERE id=?", (sid,)).fetchone()
        return dict(r) if r else None

def get_default_server() -> dict | None:
    with _conn() as c:
        r = c.execute("SELECT * FROM servers WHERE is_default=1 AND is_active=1 LIMIT 1").fetchone()
        if not r:
            r = c.execute("SELECT * FROM servers WHERE is_active=1 ORDER BY id LIMIT 1").fetchone()
        return dict(r) if r else None

def add_server(name, location, flag='🌍', max_users=200) -> int:
    with _conn() as c:
        has = c.execute("SELECT COUNT(*) FROM servers").fetchone()[0]
        cur = c.execute("INSERT INTO servers(name,location,flag,max_users,is_default) VALUES(?,?,?,?,?)",
                        (name, location, flag, max_users, 1 if has == 0 else 0))
        return cur.lastrowid

def update_server(sid, **kw):
    fields = ','.join(f"{k}=?" for k in kw)
    with _conn() as c: c.execute(f"UPDATE servers SET {fields} WHERE id=?", (*kw.values(), sid))

def update_server_load(sid, pct: int):
    """Set current_users based on pct of max_users."""
    with _conn() as c:
        r = c.execute("SELECT max_users FROM servers WHERE id=?", (sid,)).fetchone()
        if r:
            new_users = int((r[0] or 200) * max(0, min(100, pct)) / 100)
            c.execute("UPDATE servers SET current_users=? WHERE id=?", (new_users, sid))

def delete_server(sid):
    with _conn() as c: c.execute("DELETE FROM servers WHERE id=?", (sid,))

def toggle_server(sid) -> bool:
    with _conn() as c:
        r = c.execute("SELECT is_active FROM servers WHERE id=?", (sid,)).fetchone()
        if not r: return False
        nv = 1 - r[0]
        c.execute("UPDATE servers SET is_active=? WHERE id=?", (nv, sid))
        return bool(nv)

def set_default_server(sid):
    with _conn() as c:
        c.execute("UPDATE servers SET is_default=0")
        c.execute("UPDATE servers SET is_default=1 WHERE id=?", (sid,))

# ─── Orders ───────────────────────────────────────────────────────────────────

def create_order(user_id, username, full_name, gb_amount, total_price,
                 receipt_file_id=None, paid_by_wallet=0, is_trial=0,
                 discount_code=None, discount_pct=0, server_id=None) -> int:
    with _conn() as c:
        cur = c.execute("""INSERT INTO orders(user_id,username,full_name,gb_amount,total_price,
                     receipt_file_id,paid_by_wallet,is_trial,discount_code,discount_pct,server_id)
                     VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                  (user_id, username, full_name, gb_amount, total_price,
                   receipt_file_id, paid_by_wallet, is_trial, discount_code, discount_pct, server_id))
        oid = cur.lastrowid
        c.execute("UPDATE users SET total_orders=total_orders+1 WHERE user_id=?", (user_id,))
        return oid

def get_order(oid) -> dict | None:
    with _conn() as c:
        r = c.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
        return dict(r) if r else None

def get_pending_orders() -> list:
    with _conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM orders WHERE status='pending' ORDER BY created_at")]

def get_user_orders(uid, limit=10) -> list:
    with _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC LIMIT ?", (uid, limit))]

def approve_order(oid, config, sub_link, expiry_date=None, panel_username=None):
    with _conn() as c:
        c.execute("""UPDATE orders SET status='approved',config=?,sub_link=?,expiry_date=?,
                     panel_username=?,updated_at=datetime('now','localtime') WHERE id=?""",
                  (config, sub_link, expiry_date, panel_username, oid))
        r = c.execute("SELECT user_id,total_price,server_id FROM orders WHERE id=?", (oid,)).fetchone()
        if r:
            pts = max(1, r['total_price'] // 10000)
            c.execute("UPDATE users SET total_spent=total_spent+?,loyalty_points=loyalty_points+? WHERE user_id=?",
                      (r['total_price'], pts, r['user_id']))
            if r['server_id']:
                c.execute("UPDATE servers SET current_users=current_users+1 WHERE id=?", (r['server_id'],))

def reject_order(oid, note=""):
    with _conn() as c:
        c.execute("UPDATE orders SET status='rejected',note=?,updated_at=datetime('now','localtime') WHERE id=?",
                  (note, oid))
        r = c.execute("SELECT user_id,paid_by_wallet,total_price FROM orders WHERE id=?", (oid,)).fetchone()
        if r and r['paid_by_wallet']:
            c.execute("UPDATE users SET wallet_balance=wallet_balance+? WHERE user_id=?",
                      (r['total_price'], r['user_id']))

def add_order_note(oid, note):
    with _conn() as c: c.execute("UPDATE orders SET note=? WHERE id=?", (note, oid))

def toggle_auto_renew(oid) -> bool:
    with _conn() as c:
        r = c.execute("SELECT auto_renew FROM orders WHERE id=?", (oid,)).fetchone()
        if not r: return False
        nv = 1 - (r[0] or 0)
        c.execute("UPDATE orders SET auto_renew=? WHERE id=?", (nv, oid))
        return bool(nv)

def rate_order(oid, stars):
    with _conn() as c: c.execute("UPDATE orders SET rating=? WHERE id=?", (stars, oid))

def search_orders(q) -> list:
    like = f"%{q}%"
    with _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM orders WHERE full_name LIKE ? OR username LIKE ? OR CAST(id AS TEXT)=? ORDER BY created_at DESC LIMIT 30",
            (like, like, q))]

def get_expiring_orders(days: int) -> list:
    with _conn() as c:
        return [dict(r) for r in c.execute("""
            SELECT * FROM orders WHERE status='approved' AND expiry_date IS NOT NULL
            AND date(expiry_date)=date('now','localtime',? || ' days')""", (str(days),))]

def notif_sent(order_id, notif_type) -> bool:
    with _conn() as c:
        return bool(c.execute("SELECT 1 FROM expiry_notifications WHERE order_id=? AND notif_type=?",
                               (order_id, notif_type)).fetchone())

def mark_notif_sent(order_id, notif_type):
    with _conn() as c:
        c.execute("INSERT OR IGNORE INTO expiry_notifications(order_id,notif_type) VALUES(?,?)",
                  (order_id, notif_type))

# ─── Wallet ───────────────────────────────────────────────────────────────────

def get_wallet(uid) -> int:
    with _conn() as c:
        r = c.execute("SELECT wallet_balance FROM users WHERE user_id=?", (uid,)).fetchone()
        return r[0] if r else 0

def deduct_wallet(uid, amount, order_id=None) -> bool:
    with _conn() as c:
        r = c.execute("SELECT wallet_balance,username,full_name FROM users WHERE user_id=?", (uid,)).fetchone()
        if not r or r['wallet_balance'] < amount: return False
        c.execute("UPDATE users SET wallet_balance=wallet_balance-? WHERE user_id=?", (amount, uid))
        c.execute("INSERT INTO wallet_transactions(user_id,username,full_name,amount,type,status,order_id) VALUES(?,?,?,?,'payment','approved',?)",
                  (uid, r['username'], r['full_name'], -amount, order_id))
        return True

def create_wallet_charge(uid, amount, receipt_file_id) -> int:
    with _conn() as c:
        u = c.execute("SELECT username,full_name FROM users WHERE user_id=?", (uid,)).fetchone()
        cur = c.execute("INSERT INTO wallet_transactions(user_id,username,full_name,amount,type,receipt_file_id) VALUES(?,?,?,?,'charge',?)",
                        (uid, u['username'] if u else None, u['full_name'] if u else None, amount, receipt_file_id))
        return cur.lastrowid

def approve_wallet_charge(tx_id) -> dict | None:
    with _conn() as c:
        r = c.execute("SELECT * FROM wallet_transactions WHERE id=? AND status='pending'", (tx_id,)).fetchone()
        if not r: return None
        tx = dict(r)
        c.execute("UPDATE wallet_transactions SET status='approved' WHERE id=?", (tx_id,))
        c.execute("UPDATE users SET wallet_balance=wallet_balance+? WHERE user_id=?", (tx['amount'], tx['user_id']))
        return tx

def reject_wallet_charge(tx_id) -> dict | None:
    with _conn() as c:
        r = c.execute("SELECT * FROM wallet_transactions WHERE id=? AND status='pending'", (tx_id,)).fetchone()
        if not r: return None
        c.execute("UPDATE wallet_transactions SET status='rejected' WHERE id=?", (tx_id,))
        return dict(r)

def get_pending_wallet_charges() -> list:
    with _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM wallet_transactions WHERE type='charge' AND status='pending' ORDER BY created_at")]

def get_wallet_history(uid, limit=20) -> list:
    with _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM wallet_transactions WHERE user_id=? ORDER BY created_at DESC LIMIT ?", (uid, limit))]

def admin_adjust_wallet(uid, amount):
    with _conn() as c:
        u = c.execute("SELECT username,full_name FROM users WHERE user_id=?", (uid,)).fetchone()
        c.execute("UPDATE users SET wallet_balance=wallet_balance+? WHERE user_id=?", (amount, uid))
        c.execute("INSERT INTO wallet_transactions(user_id,username,full_name,amount,type,status,note) VALUES(?,?,?,?,'admin','approved','تنظیم ادمین')",
                  (uid, u['username'] if u else None, u['full_name'] if u else None, amount))

# ─── Tickets ──────────────────────────────────────────────────────────────────

def create_ticket(uid, username, full_name, message) -> int:
    with _conn() as c:
        cur = c.execute("INSERT INTO tickets(user_id,username,full_name,message) VALUES(?,?,?,?)",
                        (uid, username, full_name, message))
        return cur.lastrowid

def close_ticket(tid, reply) -> int | None:
    with _conn() as c:
        r = c.execute("SELECT user_id FROM tickets WHERE id=?", (tid,)).fetchone()
        if not r: return None
        c.execute("UPDATE tickets SET status='closed',admin_reply=?,closed_at=datetime('now','localtime') WHERE id=?",
                  (reply, tid))
        return r[0]

def get_open_tickets() -> list:
    with _conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM tickets WHERE status='open' ORDER BY created_at")]

# ─── Discounts ────────────────────────────────────────────────────────────────

def create_discount_code(code, pct, max_uses=1, min_gb=0, expires_at=None):
    with _conn() as c:
        c.execute("INSERT OR REPLACE INTO discount_codes(code,discount_pct,max_uses,min_gb,expires_at) VALUES(?,?,?,?,?)",
                  (code, pct, max_uses, min_gb, expires_at))

def get_discount_code(code) -> dict | None:
    with _conn() as c:
        r = c.execute("""SELECT * FROM discount_codes WHERE code=?
                         AND used_count<max_uses
                         AND (expires_at IS NULL OR expires_at>datetime('now','localtime'))""", (code,)).fetchone()
        return dict(r) if r else None

def use_discount_code(code, uid, order_id):
    with _conn() as c:
        c.execute("UPDATE discount_codes SET used_count=used_count+1 WHERE code=?", (code,))
        c.execute("INSERT INTO discount_uses(code,user_id,order_id) VALUES(?,?,?)", (code, uid, order_id))

def get_all_discount_codes() -> list:
    with _conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM discount_codes ORDER BY created_at DESC")]

def delete_discount_code(code):
    with _conn() as c: c.execute("DELETE FROM discount_codes WHERE code=?", (code,))

# ─── Templates ────────────────────────────────────────────────────────────────

def get_templates() -> list:
    with _conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM config_templates WHERE is_active=1 ORDER BY id")]

def get_template(tid) -> dict | None:
    with _conn() as c:
        r = c.execute("SELECT * FROM config_templates WHERE id=?", (tid,)).fetchone()
        return dict(r) if r else None

def save_template(name, config, sub_link="", server_id=None):
    with _conn() as c:
        c.execute("INSERT INTO config_templates(name,config,sub_link,server_id) VALUES(?,?,?,?)",
                  (name, config, sub_link, server_id))

def use_template(tid):
    with _conn() as c: c.execute("UPDATE config_templates SET use_count=use_count+1 WHERE id=?", (tid,))

def delete_template(tid):
    with _conn() as c: c.execute("UPDATE config_templates SET is_active=0 WHERE id=?", (tid,))

# ─── Resellers ────────────────────────────────────────────────────────────────

def get_resellers() -> list:
    with _conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM resellers ORDER BY total_sales DESC")]

def get_reseller(uid, active_only=True) -> dict | None:
    with _conn() as c:
        q = "SELECT * FROM resellers WHERE user_id=?" + (" AND is_active=1" if active_only else "")
        r = c.execute(q, (uid,)).fetchone()
        return dict(r) if r else None

def add_reseller(uid, username, full_name, commission_pct=10, custom_ppg=None):
    with _conn() as c:
        c.execute("INSERT OR REPLACE INTO resellers(user_id,username,full_name,commission_pct,custom_price_per_gb) VALUES(?,?,?,?,?)",
                  (uid, username, full_name, commission_pct, custom_ppg))

def remove_reseller(uid):
    with _conn() as c: c.execute("UPDATE resellers SET is_active=0 WHERE user_id=?", (uid,))

def update_reseller(uid, **kw):
    fields = ','.join(f"{k}=?" for k in kw)
    with _conn() as c: c.execute(f"UPDATE resellers SET {fields} WHERE user_id=?", (*kw.values(), uid))

def credit_reseller(uid, sale_amount: int, commission_pct: int):
    commission = int(sale_amount * commission_pct / 100)
    with _conn() as c:
        c.execute("UPDATE resellers SET balance=balance+?,total_sales=total_sales+?,total_commission=total_commission+? WHERE user_id=?",
                  (commission, sale_amount, commission, uid))

# ─── Flash Sales ──────────────────────────────────────────────────────────────

def create_flash_sale(name, discount_pct, starts_at, ends_at) -> int:
    with _conn() as c:
        cur = c.execute("INSERT INTO flash_sales(name,discount_pct,starts_at,ends_at) VALUES(?,?,?,?)",
                        (name, discount_pct, starts_at, ends_at))
        return cur.lastrowid

def get_active_flash_sale() -> dict | None:
    with _conn() as c:
        r = c.execute("""SELECT * FROM flash_sales WHERE is_active=1
                         AND starts_at<=datetime('now','localtime')
                         AND ends_at>datetime('now','localtime') LIMIT 1""").fetchone()
        return dict(r) if r else None

def get_flash_sales() -> list:
    with _conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM flash_sales ORDER BY created_at DESC LIMIT 20")]

def activate_flash_sale(fid):
    with _conn() as c: c.execute("UPDATE flash_sales SET is_active=1 WHERE id=?", (fid,))

def deactivate_flash_sale(fid):
    with _conn() as c: c.execute("UPDATE flash_sales SET is_active=0 WHERE id=?", (fid,))

def delete_flash_sale(fid):
    with _conn() as c: c.execute("DELETE FROM flash_sales WHERE id=?", (fid,))

def mark_flash_notified(fid):
    with _conn() as c: c.execute("UPDATE flash_sales SET notified=1 WHERE id=?", (fid,))

def get_unnotified_flash_sales() -> list:
    with _conn() as c:
        return [dict(r) for r in c.execute("""
            SELECT * FROM flash_sales WHERE notified=0
            AND starts_at<=datetime('now','localtime','10 minutes')
            AND ends_at>datetime('now','localtime')""")]

# ─── Lottery ──────────────────────────────────────────────────────────────────

def create_lottery(name, prize_gb, prize_toman, draw_at) -> int:
    with _conn() as c:
        cur = c.execute("INSERT INTO lottery(name,prize_gb,prize_toman,draw_at) VALUES(?,?,?,?)",
                        (name, prize_gb, prize_toman, draw_at))
        return cur.lastrowid

def get_active_lottery() -> dict | None:
    with _conn() as c:
        r = c.execute("SELECT * FROM lottery WHERE status='active' ORDER BY created_at DESC LIMIT 1").fetchone()
        return dict(r) if r else None

def enter_lottery(lottery_id, uid) -> bool:
    try:
        with _conn() as c:
            c.execute("INSERT INTO lottery_entries(lottery_id,user_id) VALUES(?,?)", (lottery_id, uid))
        return True
    except Exception:
        return False

def get_lottery_entries(lottery_id) -> list:
    with _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT le.*,u.username,u.full_name FROM lottery_entries le JOIN users u ON le.user_id=u.user_id WHERE le.lottery_id=?",
            (lottery_id,))]

def draw_lottery(lottery_id) -> dict | None:
    entries = get_lottery_entries(lottery_id)
    if not entries: return None
    winner = random.choice(entries)
    with _conn() as c:
        c.execute("UPDATE lottery SET status='drawn',winner_user_id=? WHERE id=?",
                  (winner['user_id'], lottery_id))
    return winner

def close_lottery(lottery_id):
    with _conn() as c: c.execute("UPDATE lottery SET status='closed' WHERE id=?", (lottery_id,))

# ─── Referrals ────────────────────────────────────────────────────────────────

def get_user_referrals(uid) -> list:
    with _conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM users WHERE referred_by=?", (uid,))]

def get_referral_stats() -> list:
    with _conn() as c:
        return [dict(r) for r in c.execute("""
            SELECT u.user_id,u.username,u.full_name,
                   COUNT(r.user_id) as total_refs,
                   SUM(CASE WHEN r.total_orders>0 THEN 1 ELSE 0 END) as paid_refs
            FROM users u LEFT JOIN users r ON r.referred_by=u.user_id
            GROUP BY u.user_id HAVING total_refs>0
            ORDER BY total_refs DESC LIMIT 20""")]

# ─── Analytics ────────────────────────────────────────────────────────────────

def get_stats() -> dict:
    with _conn() as c:
        def q(sql): return c.execute(sql).fetchone()[0] or 0
        return {
            "total_users":     q("SELECT COUNT(*) FROM users"),
            "blocked_users":   q("SELECT COUNT(*) FROM users WHERE is_blocked=1"),
            "pending_orders":  q("SELECT COUNT(*) FROM orders WHERE status='pending'"),
            "approved_orders": q("SELECT COUNT(*) FROM orders WHERE status='approved'"),
            "rejected_orders": q("SELECT COUNT(*) FROM orders WHERE status='rejected'"),
            "total_revenue":   q("SELECT COALESCE(SUM(total_price),0) FROM orders WHERE status='approved'"),
            "wallet_revenue":  q("SELECT COALESCE(SUM(total_price),0) FROM orders WHERE status='approved' AND paid_by_wallet=1"),
            "total_gb_sold":   q("SELECT COALESCE(SUM(gb_amount),0) FROM orders WHERE status='approved'"),
            "total_wallet":    q("SELECT COALESCE(SUM(wallet_balance),0) FROM users"),
            "open_tickets":    q("SELECT COUNT(*) FROM tickets WHERE status='open'"),
            "today_orders":    q("SELECT COUNT(*) FROM orders WHERE date(created_at)=date('now','localtime')"),
            "today_revenue":   q("SELECT COALESCE(SUM(total_price),0) FROM orders WHERE status='approved' AND date(created_at)=date('now','localtime')"),
            "week_revenue":    q("SELECT COALESCE(SUM(total_price),0) FROM orders WHERE status='approved' AND created_at>=datetime('now','localtime','-7 days')"),
            "month_revenue":   q("SELECT COALESCE(SUM(total_price),0) FROM orders WHERE status='approved' AND created_at>=datetime('now','localtime','-30 days')"),
            "avg_rating":      q("SELECT COALESCE(AVG(CAST(rating AS REAL)),0) FROM orders WHERE rating IS NOT NULL"),
            "active_servers":  q("SELECT COUNT(*) FROM servers WHERE is_active=1"),
            "total_resellers": q("SELECT COUNT(*) FROM resellers WHERE is_active=1"),
        }

def get_daily_revenue(days=14) -> list:
    with _conn() as c:
        return [dict(r) for r in c.execute("""
            SELECT date(created_at) as day, COUNT(*) as cnt,
                   COALESCE(SUM(total_price),0) as revenue
            FROM orders WHERE status='approved'
              AND created_at>=datetime('now','localtime',? || ' days')
            GROUP BY day ORDER BY day""", (str(-days),))]

def export_orders_csv() -> str:
    with _conn() as c:
        rows = c.execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall()
    if not rows: return "id,user_id,full_name,gb_amount,total_price,status,created_at\n"
    header = ",".join(rows[0].keys())
    lines = [header] + [",".join(str(v or '') for v in r) for r in rows]
    return "\n".join(lines)

# ─── Admin Logs ───────────────────────────────────────────────────────────────

def log_admin(admin_id, action, details=""):
    with _conn() as c:
        c.execute("INSERT INTO admin_logs(admin_id,action,details) VALUES(?,?,?)",
                  (admin_id, action, details))

def get_admin_logs(limit=50, offset=0) -> list:
    with _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM admin_logs ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset))]

# ─── Crypto Payments ──────────────────────────────────────────────────────────

def create_crypto_payment(user_id: int, ptype: str, amount_toman: int,
                          authority: str = None, usdt_amount: float = None) -> int:
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO crypto_payments(user_id,type,amount_toman,authority,usdt_amount) VALUES(?,?,?,?,?)",
            (user_id, ptype, amount_toman, authority, usdt_amount)
        )
        return cur.lastrowid

def confirm_crypto_payment(payment_id: int, ref_id: str = None, tx_hash: str = None):
    with _conn() as c:
        c.execute(
            "UPDATE crypto_payments SET status='confirmed',ref_id=?,tx_hash=?,confirmed_at=datetime('now','localtime') WHERE id=?",
            (ref_id, tx_hash, payment_id)
        )

def get_pending_usdt_payments() -> list:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM crypto_payments WHERE type='usdt_trc20' AND status='pending' ORDER BY created_at"
        ).fetchall()
        return [dict(r) for r in rows]

def get_crypto_payment_by_authority(authority: str) -> dict | None:
    with _conn() as c:
        r = c.execute("SELECT * FROM crypto_payments WHERE authority=?", (authority,)).fetchone()
        return dict(r) if r else None

def expire_old_crypto_payments(minutes: int = 30):
    with _conn() as c:
        c.execute(
            "UPDATE crypto_payments SET status='expired' WHERE status='pending' AND created_at < datetime('now','localtime',?)",
            (f"-{minutes} minutes",)
        )
