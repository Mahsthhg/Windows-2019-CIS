#!/usr/bin/env python3
"""
Ultimate Trading Tool - Complete Market Analysis Platform
Features: Technical Analysis, Backtesting, Risk Management, Market Scanner
"""

import argparse
import sys
import warnings
warnings.filterwarnings('ignore')

import pandas as pd
import numpy as np

try:
    import yfinance as yf
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich import box
    from rich.progress import Progress, SpinnerColumn, TextColumn
except ImportError:
    print("Installing required packages...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "yfinance", "rich", "pandas", "numpy", "-q"])
    import yfinance as yf
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich import box
    from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

# ══════════════════════════════════════════════════════════════
#  TECHNICAL INDICATORS
# ══════════════════════════════════════════════════════════════

def rsi(prices, period=14):
    delta = prices.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def macd(prices, fast=12, slow=26, signal=9):
    ema_f = prices.ewm(span=fast).mean()
    ema_s = prices.ewm(span=slow).mean()
    line = ema_f - ema_s
    sig = line.ewm(span=signal).mean()
    return line, sig, line - sig

def bollinger_bands(prices, period=20, std_mult=2):
    sma = prices.rolling(period).mean()
    std = prices.rolling(period).std()
    return sma + std_mult * std, sma, sma - std_mult * std

def atr(high, low, close, period=14):
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def stochastic(high, low, close, k=14, d=3):
    lo = low.rolling(k).min()
    hi = high.rolling(k).max()
    k_val = 100 * (close - lo) / (hi - lo)
    return k_val, k_val.rolling(d).mean()

def obv(close, volume):
    return (np.sign(close.diff()) * volume).fillna(0).cumsum()

def supertrend(high, low, close, period=10, mult=3):
    a = atr(high, low, close, period)
    mid = (high + low) / 2
    upper = mid + mult * a
    lower = mid - mult * a
    direction = pd.Series(0.0, index=close.index)
    for i in range(1, len(close)):
        if close.iloc[i] > upper.iloc[i - 1]:
            direction.iloc[i] = 1
        elif close.iloc[i] < lower.iloc[i - 1]:
            direction.iloc[i] = -1
        else:
            direction.iloc[i] = direction.iloc[i - 1]
    return direction

def vwap(high, low, close, volume):
    tp = (high + low + close) / 3
    return (tp * volume).cumsum() / volume.cumsum()

def fibonacci(high, low):
    diff = high - low
    return {
        "0.0%  (High)": high,
        "23.6%": high - 0.236 * diff,
        "38.2%": high - 0.382 * diff,
        "50.0%": high - 0.500 * diff,
        "61.8%": high - 0.618 * diff,
        "78.6%": high - 0.786 * diff,
        "100.0% (Low)": low,
    }

def williams_r(high, low, close, period=14):
    hi = high.rolling(period).max()
    lo = low.rolling(period).min()
    return -100 * (hi - close) / (hi - lo)

def cci(high, low, close, period=20):
    tp = (high + low + close) / 3
    sma = tp.rolling(period).mean()
    mad = tp.rolling(period).apply(lambda x: np.abs(x - x.mean()).mean())
    return (tp - sma) / (0.015 * mad)

# ══════════════════════════════════════════════════════════════
#  DATA FETCHER
# ══════════════════════════════════════════════════════════════

def fetch(symbol, period="1y", interval="1d"):
    try:
        df = yf.Ticker(symbol).history(period=period, interval=interval)
        if df.empty:
            return None
        df.columns = df.columns.str.lower()
        return df
    except Exception:
        return None

# ══════════════════════════════════════════════════════════════
#  SIGNAL ENGINE  (10 indicators → score −20 … +20)
# ══════════════════════════════════════════════════════════════

def generate_signals(df):
    c = df["close"]
    h = df["high"]
    l = df["low"]
    v = df["volume"]

    signals = {}
    score = 0

    # 1. RSI
    r = rsi(c)
    rv = r.iloc[-1]
    if rv < 30:
        signals["RSI"] = ("BUY", f"Oversold  ({rv:.1f})")
        score += 2
    elif rv > 70:
        signals["RSI"] = ("SELL", f"Overbought ({rv:.1f})")
        score -= 2
    else:
        signals["RSI"] = ("NEUTRAL", f"Normal ({rv:.1f})")

    # 2. MACD
    ml, sl, hl = macd(c)
    if hl.iloc[-1] > 0 and hl.iloc[-2] <= 0:
        signals["MACD"] = ("BUY", "Bullish crossover")
        score += 3
    elif hl.iloc[-1] < 0 and hl.iloc[-2] >= 0:
        signals["MACD"] = ("SELL", "Bearish crossover")
        score -= 3
    elif hl.iloc[-1] > 0:
        signals["MACD"] = ("BUY", "Bullish momentum")
        score += 1
    else:
        signals["MACD"] = ("SELL", "Bearish momentum")
        score -= 1

    # 3. Bollinger Bands
    up, mid, dn = bollinger_bands(c)
    lc = c.iloc[-1]
    if lc < dn.iloc[-1]:
        signals["Bollinger"] = ("BUY", "Below lower band")
        score += 2
    elif lc > up.iloc[-1]:
        signals["Bollinger"] = ("SELL", "Above upper band")
        score -= 2
    else:
        pos = (lc - dn.iloc[-1]) / (up.iloc[-1] - dn.iloc[-1])
        signals["Bollinger"] = ("NEUTRAL", f"Band position {pos:.0%}")

    # 4. EMA alignment
    e20 = c.ewm(span=20).mean()
    e50 = c.ewm(span=50).mean()
    e200 = c.ewm(span=200).mean()
    if lc > e20.iloc[-1] > e50.iloc[-1] > e200.iloc[-1]:
        signals["EMA Stack"] = ("BUY", "Price > EMA20 > EMA50 > EMA200")
        score += 3
    elif lc < e20.iloc[-1] < e50.iloc[-1] < e200.iloc[-1]:
        signals["EMA Stack"] = ("SELL", "Price < EMA20 < EMA50 < EMA200")
        score -= 3
    elif lc > e50.iloc[-1]:
        signals["EMA Stack"] = ("BUY", "Price above EMA50")
        score += 1
    else:
        signals["EMA Stack"] = ("SELL", "Price below EMA50")
        score -= 1

    # 5. Stochastic
    kv, dv = stochastic(h, l, c)
    if kv.iloc[-1] < 20 and dv.iloc[-1] < 20:
        signals["Stochastic"] = ("BUY", f"Oversold  K={kv.iloc[-1]:.1f} D={dv.iloc[-1]:.1f}")
        score += 2
    elif kv.iloc[-1] > 80 and dv.iloc[-1] > 80:
        signals["Stochastic"] = ("SELL", f"Overbought K={kv.iloc[-1]:.1f} D={dv.iloc[-1]:.1f}")
        score -= 2
    else:
        signals["Stochastic"] = ("NEUTRAL", f"K={kv.iloc[-1]:.1f} D={dv.iloc[-1]:.1f}")

    # 6. Volume analysis
    avg_v = v.rolling(20).mean()
    vr = v.iloc[-1] / avg_v.iloc[-1]
    if vr > 1.5:
        signals["Volume"] = ("CONFIRM", f"{vr:.1f}× average — strong participation")
        score += 1
    elif vr < 0.5:
        signals["Volume"] = ("WEAK", f"{vr:.1f}× average — low conviction")
        score -= 1
    else:
        signals["Volume"] = ("NEUTRAL", f"{vr:.1f}× average")

    # 7. OBV
    o = obv(c, v)
    o_ema = o.ewm(span=20).mean()
    if o.iloc[-1] > o_ema.iloc[-1]:
        signals["OBV"] = ("BUY", "Accumulation phase")
        score += 1
    else:
        signals["OBV"] = ("SELL", "Distribution phase")
        score -= 1

    # 8. SuperTrend
    st = supertrend(h, l, c)
    if st.iloc[-1] == 1:
        signals["SuperTrend"] = ("BUY", "Uptrend confirmed")
        score += 2
    elif st.iloc[-1] == -1:
        signals["SuperTrend"] = ("SELL", "Downtrend confirmed")
        score -= 2
    else:
        signals["SuperTrend"] = ("NEUTRAL", "Trend undefined")

    # 9. Williams %R
    wr = williams_r(h, l, c)
    wrv = wr.iloc[-1]
    if wrv < -80:
        signals["Williams %R"] = ("BUY", f"Oversold  ({wrv:.1f})")
        score += 1
    elif wrv > -20:
        signals["Williams %R"] = ("SELL", f"Overbought ({wrv:.1f})")
        score -= 1
    else:
        signals["Williams %R"] = ("NEUTRAL", f"{wrv:.1f}")

    # 10. CCI
    cc = cci(h, l, c)
    ccv = cc.iloc[-1]
    if ccv < -100:
        signals["CCI"] = ("BUY", f"Oversold  ({ccv:.0f})")
        score += 1
    elif ccv > 100:
        signals["CCI"] = ("SELL", f"Overbought ({ccv:.0f})")
        score -= 1
    else:
        signals["CCI"] = ("NEUTRAL", f"{ccv:.0f}")

    # Verdict
    if score >= 8:
        verdict = "STRONG BUY 🚀"
    elif score >= 3:
        verdict = "BUY 📈"
    elif score <= -8:
        verdict = "STRONG SELL 💥"
    elif score <= -3:
        verdict = "SELL 📉"
    else:
        verdict = "NEUTRAL ⏳"

    return signals, score, verdict

# ══════════════════════════════════════════════════════════════
#  BACKTEST ENGINE
# ══════════════════════════════════════════════════════════════

def backtest(df, strategy="rsi", capital=10_000):
    c = df["close"]
    h = df["high"]
    l = df["low"]
    v = df["volume"]
    cash = capital
    pos = 0.0
    entry_price = 0.0
    trades = []
    equity = []

    def open_long(i):
        nonlocal cash, pos, entry_price
        pos = cash / c.iloc[i]
        entry_price = c.iloc[i]
        cash = 0.0

    def close_long(i):
        nonlocal cash, pos
        cash = pos * c.iloc[i]
        pnl = (c.iloc[i] - entry_price) / entry_price * 100
        trades.append({"date": str(df.index[i])[:10], "entry": entry_price,
                       "exit": c.iloc[i], "pnl": pnl})
        pos = 0.0

    if strategy == "rsi":
        r = rsi(c)
        for i in range(30, len(df)):
            if r.iloc[i] < 30 and pos == 0:
                open_long(i)
            elif r.iloc[i] > 70 and pos > 0:
                close_long(i)
            equity.append(cash + pos * c.iloc[i])

    elif strategy == "macd":
        _, _, hist = macd(c)
        for i in range(30, len(df)):
            if hist.iloc[i] > 0 and hist.iloc[i - 1] <= 0 and pos == 0:
                open_long(i)
            elif hist.iloc[i] < 0 and hist.iloc[i - 1] >= 0 and pos > 0:
                close_long(i)
            equity.append(cash + pos * c.iloc[i])

    elif strategy == "ema_crossover":
        e20 = c.ewm(span=20).mean()
        e50 = c.ewm(span=50).mean()
        for i in range(50, len(df)):
            if e20.iloc[i] > e50.iloc[i] and e20.iloc[i - 1] <= e50.iloc[i - 1] and pos == 0:
                open_long(i)
            elif e20.iloc[i] < e50.iloc[i] and e20.iloc[i - 1] >= e50.iloc[i - 1] and pos > 0:
                close_long(i)
            equity.append(cash + pos * c.iloc[i])

    elif strategy == "supertrend":
        st = supertrend(h, l, c)
        for i in range(20, len(df)):
            if st.iloc[i] == 1 and st.iloc[i - 1] != 1 and pos == 0:
                open_long(i)
            elif st.iloc[i] == -1 and st.iloc[i - 1] != -1 and pos > 0:
                close_long(i)
            equity.append(cash + pos * c.iloc[i])

    # Close any open position
    if pos > 0:
        close_long(-1)

    final = cash
    eq = pd.Series(equity if equity else [capital])
    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]

    rolling_max = eq.expanding().max()
    drawdowns = (eq - rolling_max) / rolling_max * 100
    daily_ret = eq.pct_change().dropna()
    sharpe = (daily_ret.mean() / daily_ret.std() * np.sqrt(252)) if daily_ret.std() > 0 else 0

    return {
        "total_return": (final - capital) / capital * 100,
        "final_capital": final,
        "trades": len(trades),
        "win_rate": len(wins) / len(trades) * 100 if trades else 0,
        "avg_win": np.mean([t["pnl"] for t in wins]) if wins else 0,
        "avg_loss": np.mean([t["pnl"] for t in losses]) if losses else 0,
        "profit_factor": abs(sum(t["pnl"] for t in wins) / sum(t["pnl"] for t in losses))
                         if losses and sum(t["pnl"] for t in losses) != 0 else float("inf"),
        "max_drawdown": drawdowns.min(),
        "sharpe": sharpe,
        "buy_hold": (c.iloc[-1] - c.iloc[0]) / c.iloc[0] * 100,
        "recent_trades": trades[-8:],
    }

# ══════════════════════════════════════════════════════════════
#  RISK MANAGER
# ══════════════════════════════════════════════════════════════

def position_size(capital, risk_pct, entry, stop):
    risk_dollar = capital * risk_pct / 100
    risk_per_unit = abs(entry - stop)
    units = risk_dollar / risk_per_unit
    return {
        "units": units,
        "position_value": units * entry,
        "portfolio_pct": units * entry / capital * 100,
        "risk_dollar": risk_dollar,
        "risk_per_unit": risk_per_unit,
    }

def take_profit_levels(entry, stop, ratios=(1, 1.5, 2, 3)):
    risk = abs(entry - stop)
    is_long = entry > stop
    return {
        f"R{r} Target ({r}:1 R:R)": (entry + risk * r) if is_long else (entry - risk * r)
        for r in ratios
    }

# ══════════════════════════════════════════════════════════════
#  DISPLAY
# ══════════════════════════════════════════════════════════════

BANNER = """[bold cyan]
╔══════════════════════════════════════════════════════════════╗
║          🚀  ULTIMATE TRADING TOOL  |  v2.0                 ║
║     Technical Analysis · Backtest · Risk · Scanner          ║
╚══════════════════════════════════════════════════════════════╝[/bold cyan]"""

def _signal_row(indicator, signal, detail):
    icons = {"BUY": "🟢", "SELL": "🔴", "NEUTRAL": "⚪", "CONFIRM": "🔵", "WEAK": "🟡"}
    colors = {"BUY": "green", "SELL": "red", "NEUTRAL": "white", "CONFIRM": "cyan", "WEAK": "yellow"}
    icon = icons.get(signal, "⚪")
    col = colors.get(signal, "white")
    return indicator, f"[bold {col}]{icon} {signal}[/bold {col}]", f"[dim]{detail}[/dim]"

def show_analysis(symbol, df, signals, score, verdict):
    c = df["close"]
    lp = c.iloc[-1]
    chg = (lp - c.iloc[-2]) / c.iloc[-2] * 100
    chg_col = "green" if chg >= 0 else "red"
    chg_str = f"+{chg:.2f}%" if chg >= 0 else f"{chg:.2f}%"

    console.print(Panel(
        f"[bold white]{symbol.upper()}[/bold white]   "
        f"[bold yellow]${lp:,.4f}[/bold yellow]   "
        f"[bold {chg_col}]{chg_str}[/bold {chg_col}]   "
        f"[dim]Vol: {df['volume'].iloc[-1]:,.0f}[/dim]",
        title="[bold cyan]Market Snapshot[/bold cyan]", border_style="cyan"
    ))

    # 52-week range
    h52 = df["high"].rolling(252).max().iloc[-1]
    l52 = df["low"].rolling(252).min().iloc[-1]
    atr_val = atr(df["high"], df["low"], df["close"]).iloc[-1]
    vwap_val = vwap(df["high"], df["low"], df["close"], df["volume"]).iloc[-1]

    stats = Table(show_header=False, box=box.SIMPLE, padding=(0, 3))
    stats.add_column(style="dim"); stats.add_column(style="bold yellow")
    stats.add_column(style="dim"); stats.add_column(style="bold yellow")
    stats.add_row("52W High", f"${h52:,.4f}", "52W Low", f"${l52:,.4f}")
    stats.add_row("ATR(14)",  f"${atr_val:,.4f}", "VWAP",    f"${vwap_val:,.4f}")
    console.print(Panel(stats, title="Key Metrics", border_style="blue"))

    # Signals
    t = Table(title="Technical Indicators", box=box.ROUNDED, border_style="green", show_lines=True, min_width=65)
    t.add_column("Indicator", style="bold cyan", width=14)
    t.add_column("Signal", width=18)
    t.add_column("Details")
    for ind, (sig, det) in signals.items():
        t.add_row(*_signal_row(ind, sig, det))
    console.print(t)

    # Verdict
    vc = "green" if "BUY" in verdict else ("red" if "SELL" in verdict else "yellow")
    console.print(Panel(
        f"[bold {vc}]{verdict}[/bold {vc}]   [dim]Composite score: {score:+d} / 20[/dim]",
        title="[bold]Overall Signal[/bold]", border_style=vc
    ))

def show_backtest(stats, strategy, symbol, capital):
    rc = "green" if stats["total_return"] > 0 else "red"
    ac = "green" if stats["total_return"] > stats["buy_hold"] else "red"

    t = Table(title=f"Backtest — {strategy.upper()}  |  {symbol}  |  Capital ${capital:,.0f}",
              box=box.ROUNDED, border_style="magenta", min_width=50)
    t.add_column("Metric", style="bold cyan")
    t.add_column("Value", justify="right")

    rows = [
        ("Strategy Return",   f"[{rc}]{stats['total_return']:.2f}%[/{rc}]"),
        ("Buy & Hold Return", f"{stats['buy_hold']:.2f}%"),
        ("Alpha vs B&H",      f"[{ac}]{stats['total_return'] - stats['buy_hold']:.2f}%[/{ac}]"),
        ("Final Capital",     f"${stats['final_capital']:,.2f}"),
        ("Total Trades",      str(stats["trades"])),
        ("Win Rate",          f"{'🟢' if stats['win_rate'] > 50 else '🔴'} {stats['win_rate']:.1f}%"),
        ("Avg Win",           f"[green]+{stats['avg_win']:.2f}%[/green]"),
        ("Avg Loss",          f"[red]{stats['avg_loss']:.2f}%[/red]"),
        ("Profit Factor",     f"{'🟢' if stats['profit_factor'] > 1.5 else '🔴'} {stats['profit_factor']:.2f}"),
        ("Max Drawdown",      f"[red]{stats['max_drawdown']:.2f}%[/red]"),
        ("Sharpe Ratio",      f"{'🟢' if stats['sharpe'] > 1 else '🔴'} {stats['sharpe']:.2f}"),
    ]
    for label, val in rows:
        t.add_row(label, val)
    console.print(t)

    if stats["recent_trades"]:
        rt = Table(title="Recent Trades", box=box.SIMPLE, min_width=50)
        rt.add_column("Date", style="dim"); rt.add_column("Entry")
        rt.add_column("Exit"); rt.add_column("P&L", justify="right")
        for tr in stats["recent_trades"][-6:]:
            pc = "green" if tr["pnl"] > 0 else "red"
            ps = "+" if tr["pnl"] > 0 else ""
            rt.add_row(tr["date"], f"${tr['entry']:,.4f}", f"${tr['exit']:,.4f}",
                       f"[{pc}]{ps}{tr['pnl']:.2f}%[/{pc}]")
        console.print(rt)

def show_risk(symbol, df, capital, risk_pct, entry, stop):
    pos = position_size(capital, risk_pct, entry, stop)
    tps = take_profit_levels(entry, stop)
    atr_val = atr(df["high"], df["low"], df["close"]).iloc[-1] if df is not None else None
    is_long = entry > stop

    t = Table(title=f"Risk Manager — {symbol}  ({'LONG 📈' if is_long else 'SHORT 📉'})",
              box=box.ROUNDED, border_style="yellow", min_width=50)
    t.add_column("Parameter", style="bold cyan")
    t.add_column("Value", justify="right")

    rows = [
        ("Capital",          f"${capital:,.2f}"),
        ("Risk %",           f"{risk_pct:.1f}%"),
        ("Risk Amount",      f"[red]${pos['risk_dollar']:,.2f}[/red]"),
        ("Entry Price",      f"${entry:,.4f}"),
        ("Stop Loss",        f"[red]${stop:,.4f}[/red]"),
        ("Risk / Unit",      f"${pos['risk_per_unit']:,.4f}"),
        ("Units to Trade",   f"{pos['units']:.4f}"),
        ("Position Value",   f"${pos['position_value']:,.2f}"),
        ("Portfolio Weight", f"{pos['portfolio_pct']:.1f}%"),
    ]
    if atr_val:
        rows.append(("ATR(14)", f"${atr_val:,.4f}  ({atr_val/entry*100:.2f}% of price)"))
    for label, val in rows:
        t.add_row(label, val)
    console.print(t)

    tp_t = Table(title="Take Profit Targets", box=box.SIMPLE, min_width=50)
    tp_t.add_column("Level"); tp_t.add_column("Price", justify="right")
    tp_t.add_column("Profit $", justify="right"); tp_t.add_column("Profit %", justify="right")
    for label, price in tps.items():
        profit = pos["units"] * abs(price - entry)
        pct = abs(price - entry) / entry * 100
        tp_t.add_row(f"[green]{label}[/green]", f"[green]${price:,.4f}[/green]",
                     f"[green]+${profit:,.2f}[/green]", f"[green]+{pct:.2f}%[/green]")
    console.print(tp_t)

def show_levels(symbol, df):
    h = df["high"]
    l = df["low"]
    c = df["close"]
    last = c.iloc[-1]

    period_h = h.rolling(60).max().iloc[-1]
    period_l = l.rolling(60).min().iloc[-1]
    fibs = fibonacci(period_h, period_l)

    # VWAP & EMAs
    vwap_val = vwap(h, l, c, df["volume"]).iloc[-1]
    e20 = c.ewm(span=20).mean().iloc[-1]
    e50 = c.ewm(span=50).mean().iloc[-1]
    e200 = c.ewm(span=200).mean().iloc[-1]

    all_levels = {**fibs, "VWAP": vwap_val,
                  "EMA 20": e20, "EMA 50": e50, "EMA 200": e200}

    t = Table(title=f"Key Levels — {symbol}", box=box.ROUNDED, border_style="cyan", min_width=55)
    t.add_column("Level", style="bold"); t.add_column("Price", justify="right")
    t.add_column("Distance", justify="right"); t.add_column("Type")

    for name, price in sorted(all_levels.items(), key=lambda x: x[1], reverse=True):
        dist = (price - last) / last * 100
        dc = "green" if dist >= 0 else "red"
        ds = f"+{dist:.2f}%" if dist >= 0 else f"{dist:.2f}%"
        ltype = "Resistance" if price > last else "Support"
        tc = "red" if ltype == "Resistance" else "green"
        t.add_row(name, f"${price:,.4f}", f"[{dc}]{ds}[/{dc}]", f"[{tc}]{ltype}[/{tc}]")
    console.print(t)

def show_scanner(results):
    t = Table(title="Market Scanner", box=box.ROUNDED, border_style="cyan", show_lines=True)
    t.add_column("Symbol", style="bold"); t.add_column("Price", justify="right")
    t.add_column("Change", justify="right"); t.add_column("Signal")
    t.add_column("Score", justify="center"); t.add_column("RSI", justify="right")

    for r in sorted(results, key=lambda x: x["score"], reverse=True):
        cc = "green" if r["change"] >= 0 else "red"
        cs = f"+{r['change']:.2f}%" if r["change"] >= 0 else f"{r['change']:.2f}%"
        vc = "green" if "BUY" in r["verdict"] else ("red" if "SELL" in r["verdict"] else "yellow")
        t.add_row(
            r["symbol"], f"${r['price']:,.4f}",
            f"[{cc}]{cs}[/{cc}]", f"[{vc}]{r['verdict']}[/{vc}]",
            f"{r['score']:+d}", f"{r['rsi']:.1f}"
        )
    console.print(t)

def show_compare(symbol_stats):
    t = Table(title="Strategy Comparison", box=box.ROUNDED, border_style="magenta", show_lines=True)
    t.add_column("Strategy", style="bold cyan")
    t.add_column("Return", justify="right"); t.add_column("Win Rate", justify="right")
    t.add_column("Sharpe", justify="right"); t.add_column("Max DD", justify="right")
    t.add_column("Trades", justify="right")

    for name, s in symbol_stats.items():
        rc = "green" if s["total_return"] > 0 else "red"
        t.add_row(
            name,
            f"[{rc}]{s['total_return']:.2f}%[/{rc}]",
            f"{'🟢' if s['win_rate'] > 50 else '🔴'} {s['win_rate']:.1f}%",
            f"{'🟢' if s['sharpe'] > 1 else '🔴'} {s['sharpe']:.2f}",
            f"[red]{s['max_drawdown']:.2f}%[/red]",
            str(s["trades"]),
        )
    console.print(t)

# ══════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        prog="trading_tool",
        description="🚀 Ultimate Trading Tool — complete market analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands
  analyze   — full technical analysis + key levels
  backtest  — backtest a strategy (rsi / macd / ema_crossover / supertrend)
  compare   — compare all strategies side-by-side
  scan      — multi-symbol signal scanner
  risk      — position-size & take-profit calculator
  levels    — Fibonacci + VWAP + EMA support/resistance

Examples
  python trading_tool.py analyze BTC-USD
  python trading_tool.py analyze AAPL --period 6mo --interval 1h
  python trading_tool.py backtest ETH-USD --strategy supertrend --capital 5000
  python trading_tool.py compare BTC-USD --period 2y
  python trading_tool.py scan BTC-USD ETH-USD AAPL TSLA NVDA
  python trading_tool.py risk BTC-USD --capital 10000 --risk 2 --entry 65000 --stop 63000
  python trading_tool.py levels SOL-USD
        """,
    )
    sub = parser.add_subparsers(dest="cmd")

    # analyze
    p = sub.add_parser("analyze"); p.add_argument("symbol")
    p.add_argument("--period", default="1y")
    p.add_argument("--interval", default="1d")

    # backtest
    p = sub.add_parser("backtest"); p.add_argument("symbol")
    p.add_argument("--strategy", default="rsi",
                   choices=["rsi", "macd", "ema_crossover", "supertrend"])
    p.add_argument("--period", default="2y")
    p.add_argument("--capital", type=float, default=10_000)

    # compare
    p = sub.add_parser("compare"); p.add_argument("symbol")
    p.add_argument("--period", default="2y")
    p.add_argument("--capital", type=float, default=10_000)

    # scan
    p = sub.add_parser("scan"); p.add_argument("symbols", nargs="+")
    p.add_argument("--period", default="3mo")

    # risk
    p = sub.add_parser("risk"); p.add_argument("symbol")
    p.add_argument("--capital", type=float, required=True)
    p.add_argument("--risk", type=float, default=2.0, dest="risk_pct")
    p.add_argument("--entry", type=float, required=True)
    p.add_argument("--stop", type=float, required=True)

    # levels
    p = sub.add_parser("levels"); p.add_argument("symbol")
    p.add_argument("--period", default="6mo")

    args = parser.parse_args()
    if not args.cmd:
        console.print(BANNER)
        parser.print_help()
        return

    console.print(BANNER)

    with Progress(SpinnerColumn(), TextColumn("[cyan]{task.description}"), transient=True) as prog:

        if args.cmd == "analyze":
            t = prog.add_task(f"Fetching {args.symbol}…"); prog.start()
            df = fetch(args.symbol, args.period, args.interval); prog.stop()
            if df is None:
                console.print(f"[red]❌ Could not fetch {args.symbol}[/red]"); return
            sigs, score, verdict = generate_signals(df)
            show_analysis(args.symbol, df, sigs, score, verdict)
            show_levels(args.symbol, df)

        elif args.cmd == "backtest":
            t = prog.add_task(f"Fetching {args.symbol}…"); prog.start()
            df = fetch(args.symbol, args.period); prog.stop()
            if df is None:
                console.print(f"[red]❌ Could not fetch {args.symbol}[/red]"); return
            stats = backtest(df, args.strategy, args.capital)
            show_backtest(stats, args.strategy, args.symbol, args.capital)

        elif args.cmd == "compare":
            t = prog.add_task(f"Fetching {args.symbol}…"); prog.start()
            df = fetch(args.symbol, args.period); prog.stop()
            if df is None:
                console.print(f"[red]❌ Could not fetch {args.symbol}[/red]"); return
            strats = ["rsi", "macd", "ema_crossover", "supertrend"]
            results = {}
            for s in strats:
                prog.add_task(f"Backtesting {s}…")
                results[s] = backtest(df, s, args.capital)
            show_compare(results)
            for name, stats in results.items():
                show_backtest(stats, name, args.symbol, args.capital)

        elif args.cmd == "scan":
            rows = []
            for sym in args.symbols:
                prog.add_task(f"Scanning {sym}…")
                df = fetch(sym, args.period)
                if df is not None:
                    sigs, score, verdict = generate_signals(df)
                    r = rsi(df["close"])
                    rows.append({
                        "symbol": sym,
                        "price": df["close"].iloc[-1],
                        "change": (df["close"].iloc[-1] - df["close"].iloc[-2]) / df["close"].iloc[-2] * 100,
                        "verdict": verdict, "score": score, "rsi": r.iloc[-1],
                    })
            prog.stop()
            show_scanner(rows)

        elif args.cmd == "risk":
            t = prog.add_task(f"Fetching {args.symbol}…"); prog.start()
            df = fetch(args.symbol, "3mo"); prog.stop()
            show_risk(args.symbol, df, args.capital, args.risk_pct, args.entry, args.stop)

        elif args.cmd == "levels":
            t = prog.add_task(f"Fetching {args.symbol}…"); prog.start()
            df = fetch(args.symbol, args.period); prog.stop()
            if df is None:
                console.print(f"[red]❌ Could not fetch {args.symbol}[/red]"); return
            show_levels(args.symbol, df)

    console.print(
        "\n[dim]⚠️  Educational purposes only — not financial advice.[/dim]\n"
    )


if __name__ == "__main__":
    main()
