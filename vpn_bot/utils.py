"""Shared helpers: VIP, rate limiting, formatting, HTML escaping."""
import html
import time
from config import VIP_LEVELS, RATE_LIMIT_PER_MINUTE


def h(text) -> str:
    """HTML-escape برای جلوگیری از باگ parse_mode HTML."""
    return html.escape(str(text) if text is not None else "")

# ─── VIP ──────────────────────────────────────────────────────────────────────

def get_vip(total_spent: int) -> tuple[str, int]:
    """Returns (label, discount_pct) for the user's current VIP level."""
    for label, threshold, discount in VIP_LEVELS:
        if total_spent >= threshold:
            return label, discount
    return "👤 عادی", 0


def next_vip(total_spent: int) -> tuple[str, int] | None:
    """Returns (next_label, remaining_toman) or None if already max."""
    for label, threshold, _ in reversed(VIP_LEVELS):
        if threshold > total_spent:
            return label, threshold - total_spent
    return None


def vip_progress_bar(total_spent: int) -> str:
    """Visual progress bar toward next VIP level."""
    nxt = next_vip(total_spent)
    if not nxt:
        return "💎 حداکثر سطح"
    label, remaining = nxt
    # find current threshold
    current_label, current_threshold, _ = ("👤 عادی", 0, 0)
    for lbl, thr, _ in reversed(VIP_LEVELS):
        if total_spent >= thr:
            current_label, current_threshold = lbl, thr
            break
    next_thr = current_threshold + remaining
    progress = (total_spent - current_threshold) / max(next_thr - current_threshold, 1)
    filled = int(progress * 10)
    bar = "█" * filled + "░" * (10 - filled)
    return f"[{bar}] {int(progress*100)}% تا {label}"


# ─── Rate Limiting ────────────────────────────────────────────────────────────

_rl: dict[int, list[float]] = {}

def is_rate_limited(user_id: int) -> bool:
    now = time.time()
    times = [t for t in _rl.get(user_id, []) if now - t < 60]
    if len(times) >= RATE_LIMIT_PER_MINUTE:
        _rl[user_id] = times
        return True
    times.append(now)
    _rl[user_id] = times
    return False


# ─── Formatting ───────────────────────────────────────────────────────────────

def fmt(p: int) -> str:
    return f"{p:,} تومان"

def fmt_gb(gb: int) -> str:
    return f"{gb} گیگابایت"

def fmt_dt(s: str) -> str:
    return s[:16] if s else "—"

STAR_MAP = {1: "⭐", 2: "⭐⭐", 3: "⭐⭐⭐", 4: "⭐⭐⭐⭐", 5: "⭐⭐⭐⭐⭐"}
TX_EMOJI = {
    "charge":        "💳 شارژ کیف پول",
    "purchase":      "🛒 خرید",
    "admin_adjust":  "🔧 تنظیم ادمین",
    "referral_bonus":"🎁 جایزه معرفی",
    "refund":        "↩️ بازگشت وجه",
}

STATUS_EMOJI  = {"pending": "⏳", "approved": "✅", "rejected": "❌"}
STATUS_LABEL  = {"pending": "در انتظار", "approved": "تایید شده", "rejected": "رد شده"}
