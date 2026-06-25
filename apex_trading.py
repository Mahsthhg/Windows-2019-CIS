#!/usr/bin/env python3
"""
APEX TRADING SYSTEM v3.0
Multi-timeframe analysis · 11 indicators · ATR-based risk management
Pydroid compatible — menu driven, no command-line args needed
"""

# ─── Auto-install ─────────────────────────────────────────────
import subprocess, sys, warnings, time
warnings.filterwarnings('ignore')

for _pkg in ('yfinance', 'pandas', 'numpy', 'rich'):
    try:
        __import__(_pkg)
    except ImportError:
        print(f'Installing {_pkg}...')
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', _pkg, '-q'])
        print(f'OK: {_pkg}')

import pandas as pd
import numpy as np
import yfinance as yf
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console()

# ─── SYMBOL LISTS ─────────────────────────────────────────────
CRYPTO = [
    'BTC-USD', 'ETH-USD', 'BNB-USD', 'SOL-USD', 'XRP-USD',
    'ADA-USD', 'AVAX-USD', 'DOGE-USD', 'DOT-USD', 'MATIC-USD',
    'LINK-USD', 'ATOM-USD', 'LTC-USD', 'NEAR-USD', 'APT-USD',
    'INJ-USD',  'TRX-USD', 'ETC-USD', 'XLM-USD', 'FIL-USD',
]

STOCKS = [
    'AAPL', 'MSFT', 'NVDA', 'TSLA', 'AMZN',
    'GOOGL', 'META', 'AMD',  'NFLX', 'CRM',
    'COIN', 'MSTR', 'PLTR', 'SQ',   'HOOD',
]

# ─── DATA ─────────────────────────────────────────────────────
def fetch(symbol, period='3mo', interval='1d'):
    try:
        df = yf.Ticker(symbol).history(period=period, interval=interval)
        if len(df) < 30:
            return None
        df.columns = [c.lower() for c in df.columns]
        return df.dropna()
    except Exception:
        return None

# ─── INDICATORS ───────────────────────────────────────────────
def _rsi(c, n=14):
    d = c.diff()
    g = d.clip(lower=0).rolling(n).mean()
    l = (-d.clip(upper=0)).rolling(n).mean()
    return 100 - 100 / (1 + g / l.replace(0, np.nan))

def _macd(c, f=12, s=26, sig=9):
    m = c.ewm(span=f).mean() - c.ewm(span=s).mean()
    return m, m.ewm(span=sig).mean(), m - m.ewm(span=sig).mean()

def _bb(c, n=20, k=2):
    sma = c.rolling(n).mean()
    std = c.rolling(n).std()
    return sma + k * std, sma, sma - k * std

def _atr(h, l, c, n=14):
    tr = pd.concat([h - l,
                    (h - c.shift()).abs(),
                    (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(span=n).mean()

def _stoch(h, l, c, k=14, d=3):
    lo = l.rolling(k).min()
    hi = h.rolling(k).max()
    kv = 100 * (c - lo) / (hi - lo + 1e-10)
    return kv, kv.rolling(d).mean()

def _obv(c, v):
    return (np.sign(c.diff()) * v).fillna(0).cumsum()

def _supertrend(h, l, c, n=10, mult=3.0):
    a = _atr(h, l, c, n)
    mid = (h + l) / 2
    ub, lb = mid + mult * a, mid - mult * a
    direction = pd.Series(1, index=c.index, dtype=float)
    for i in range(1, len(c)):
        if c.iloc[i] > ub.iloc[i - 1]:
            direction.iloc[i] = 1
        elif c.iloc[i] < lb.iloc[i - 1]:
            direction.iloc[i] = -1
        else:
            direction.iloc[i] = direction.iloc[i - 1]
    return direction

def _williams_r(h, l, c, n=14):
    return -100 * (h.rolling(n).max() - c) / (h.rolling(n).max() - l.rolling(n).min() + 1e-10)

def _cci(h, l, c, n=20):
    tp = (h + l + c) / 3
    return (tp - tp.rolling(n).mean()) / (0.015 * tp.rolling(n).std() + 1e-10)

def _adx(h, l, c, n=14):
    tr  = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    up, dn = h.diff(), -l.diff()
    pdm = up.where((up > dn) & (up > 0), 0.0)
    ndm = dn.where((dn > up) & (dn > 0), 0.0)
    atr14 = tr.ewm(span=n).mean()
    pdi = 100 * pdm.ewm(span=n).mean() / (atr14 + 1e-10)
    ndi = 100 * ndm.ewm(span=n).mean() / (atr14 + 1e-10)
    dx  = 100 * (pdi - ndi).abs() / (pdi + ndi + 1e-10)
    return dx.ewm(span=n).mean(), pdi, ndi

# ─── SIGNAL ENGINE ────────────────────────────────────────────
def _safe(series, idx=-1):
    """Return series.iloc[idx] or NaN safely."""
    try:
        v = series.iloc[idx]
        return float(v) if not pd.isna(v) else float('nan')
    except Exception:
        return float('nan')

def analyze_df(df):
    """Score one timeframe. Returns (score, signals) or (None, None)."""
    if df is None or len(df) < 50:
        return None, None

    c, h, l, v = df['close'], df['high'], df['low'], df['volume']
    score = 0
    sigs  = {}

    # ── 1. RSI ──────────────────────────────────────────────
    rv = _safe(_rsi(c))
    if not np.isnan(rv):
        if rv <= 30:   score += 2; sigs['RSI'] = ('STRONG BUY',  f'{rv:.1f} — oversold')
        elif rv <= 45: score += 1; sigs['RSI'] = ('BUY',         f'{rv:.1f} — bullish zone')
        elif rv >= 70: score -= 2; sigs['RSI'] = ('STRONG SELL', f'{rv:.1f} — overbought')
        elif rv >= 55: score -= 1; sigs['RSI'] = ('SELL',        f'{rv:.1f} — bearish zone')
        else:                      sigs['RSI'] = ('NEUTRAL',     f'{rv:.1f}')

    # ── 2. MACD ─────────────────────────────────────────────
    _, _, hist = _macd(c)
    h0, h1 = _safe(hist, -1), _safe(hist, -2)
    if not any(np.isnan([h0, h1])):
        if   h0 > 0 and h1 <= 0: score += 2; sigs['MACD'] = ('STRONG BUY',  'Fresh bullish crossover')
        elif h0 < 0 and h1 >= 0: score -= 2; sigs['MACD'] = ('STRONG SELL', 'Fresh bearish crossover')
        elif h0 > 0:              score += 1; sigs['MACD'] = ('BUY',         'Bullish momentum')
        else:                     score -= 1; sigs['MACD'] = ('SELL',        'Bearish momentum')

    # ── 3. Bollinger Bands ──────────────────────────────────
    up_b, _, dn_b = _bb(c)
    lc = _safe(c)
    uv, dv = _safe(up_b), _safe(dn_b)
    if not any(np.isnan([lc, uv, dv])) and uv != dv:
        if lc < dv:   score += 2; sigs['BB'] = ('STRONG BUY',  'Price below lower band')
        elif lc > uv: score -= 2; sigs['BB'] = ('STRONG SELL', 'Price above upper band')
        else:
            pos = (lc - dv) / (uv - dv)
            if pos < 0.3:   score += 1; sigs['BB'] = ('BUY',  f'Lower third {pos:.0%}')
            elif pos > 0.7: score -= 1; sigs['BB'] = ('SELL', f'Upper third {pos:.0%}')
            else:                       sigs['BB'] = ('NEUTRAL', f'Mid-band {pos:.0%}')

    # ── 4. EMA alignment ────────────────────────────────────
    e20  = _safe(c.ewm(span=20).mean())
    e50  = _safe(c.ewm(span=50).mean())
    span = min(200, len(c) - 1)
    e200 = _safe(c.ewm(span=span).mean())
    if not any(np.isnan([lc, e20, e50, e200])):
        if   lc > e20 > e50 > e200: score += 2; sigs['EMA'] = ('STRONG BUY',  'P>EMA20>EMA50>EMA200')
        elif lc < e20 < e50 < e200: score -= 2; sigs['EMA'] = ('STRONG SELL', 'P<EMA20<EMA50<EMA200')
        elif lc > e50:               score += 1; sigs['EMA'] = ('BUY',         'Price above EMA50')
        else:                        score -= 1; sigs['EMA'] = ('SELL',        'Price below EMA50')

    # ── 5. SuperTrend ───────────────────────────────────────
    st = _supertrend(h, l, c)
    sv, sp = _safe(st, -1), _safe(st, -2)
    if not any(np.isnan([sv, sp])):
        if   sv == 1 and sp != 1:  score += 2; sigs['SuperTrend'] = ('STRONG BUY',  'Just flipped BULLISH ✨')
        elif sv == -1 and sp != -1: score -= 2; sigs['SuperTrend'] = ('STRONG SELL', 'Just flipped BEARISH ⚠️')
        elif sv == 1:               score += 1; sigs['SuperTrend'] = ('BUY',         'Uptrend active')
        elif sv == -1:              score -= 1; sigs['SuperTrend'] = ('SELL',        'Downtrend active')

    # ── 6. Stochastic ───────────────────────────────────────
    kv_s, dv_s = _stoch(h, l, c)
    k0, d0 = _safe(kv_s, -1), _safe(dv_s, -1)
    k1, d1 = _safe(kv_s, -2), _safe(dv_s, -2)
    if not any(np.isnan([k0, d0, k1, d1])):
        if   k0 < 20 and d0 < 20: score += 2; sigs['Stochastic'] = ('STRONG BUY',  f'Oversold K={k0:.0f} D={d0:.0f}')
        elif k0 > 80 and d0 > 80: score -= 2; sigs['Stochastic'] = ('STRONG SELL', f'Overbought K={k0:.0f} D={d0:.0f}')
        elif k0 > d0 and k1 <= d1: score += 1; sigs['Stochastic'] = ('BUY',  f'K crossed up  K={k0:.0f}')
        elif k0 < d0 and k1 >= d1: score -= 1; sigs['Stochastic'] = ('SELL', f'K crossed down K={k0:.0f}')
        else:                                   sigs['Stochastic'] = ('NEUTRAL', f'K={k0:.0f} D={d0:.0f}')

    # ── 7. Volume pressure ──────────────────────────────────
    avg_v = v.rolling(20).mean()
    av = _safe(avg_v)
    lv = _safe(v)
    if not any(np.isnan([av, lv])) and av > 0:
        vr = lv / av
        up = lc > _safe(c, -2)
        if vr > 2.0:
            if up:  score += 2; sigs['Volume'] = ('STRONG BUY',  f'{vr:.1f}× avg — buying surge')
            else:   score -= 2; sigs['Volume'] = ('STRONG SELL', f'{vr:.1f}× avg — selling surge')
        elif vr > 1.3:
            if up:  score += 1; sigs['Volume'] = ('BUY',  f'{vr:.1f}× avg volume')
            else:   score -= 1; sigs['Volume'] = ('SELL', f'{vr:.1f}× avg volume')
        else:                   sigs['Volume'] = ('NEUTRAL', f'{vr:.1f}× avg volume')

    # ── 8. OBV ──────────────────────────────────────────────
    obv  = _obv(c, v)
    oema = obv.ewm(span=20).mean()
    o0, oe0 = _safe(obv, -1), _safe(oema, -1)
    o5, oe5 = _safe(obv, -6), _safe(oema, -6)
    if not any(np.isnan([o0, oe0, o5, oe5])):
        if   o0 > oe0 and o5 < oe5: score += 2; sigs['OBV'] = ('STRONG BUY',  'OBV crossed above EMA')
        elif o0 < oe0 and o5 > oe5: score -= 2; sigs['OBV'] = ('STRONG SELL', 'OBV crossed below EMA')
        elif o0 > oe0:               score += 1; sigs['OBV'] = ('BUY',         'Accumulation phase')
        else:                        score -= 1; sigs['OBV'] = ('SELL',        'Distribution phase')

    # ── 9. ADX ──────────────────────────────────────────────
    adx_s, pdi_s, ndi_s = _adx(h, l, c)
    adxv = _safe(adx_s)
    pdiv = _safe(pdi_s)
    ndiv = _safe(ndi_s)
    if not any(np.isnan([adxv, pdiv, ndiv])):
        if adxv > 25 and pdiv > ndiv: score += 2; sigs['ADX'] = ('STRONG BUY',  f'Strong uptrend ADX={adxv:.0f}')
        elif adxv > 25:                score -= 2; sigs['ADX'] = ('STRONG SELL', f'Strong downtrend ADX={adxv:.0f}')
        else:                                      sigs['ADX'] = ('NEUTRAL',     f'Weak trend ADX={adxv:.0f}')

    # ── 10. Williams %R ─────────────────────────────────────
    wrv = _safe(_williams_r(h, l, c))
    if not np.isnan(wrv):
        if   wrv < -80: score += 1; sigs['Williams %R'] = ('BUY',  f'Oversold ({wrv:.0f})')
        elif wrv > -20: score -= 1; sigs['Williams %R'] = ('SELL', f'Overbought ({wrv:.0f})')
        else:                       sigs['Williams %R'] = ('NEUTRAL', f'{wrv:.0f}')

    # ── 11. CCI ─────────────────────────────────────────────
    cciv = _safe(_cci(h, l, c))
    if not np.isnan(cciv):
        if   cciv < -150: score += 2; sigs['CCI'] = ('STRONG BUY',  f'Extreme oversold ({cciv:.0f})')
        elif cciv < -100: score += 1; sigs['CCI'] = ('BUY',         f'Oversold ({cciv:.0f})')
        elif cciv > 150:  score -= 2; sigs['CCI'] = ('STRONG SELL', f'Extreme overbought ({cciv:.0f})')
        elif cciv > 100:  score -= 1; sigs['CCI'] = ('SELL',        f'Overbought ({cciv:.0f})')
        else:                         sigs['CCI'] = ('NEUTRAL',     f'{cciv:.0f}')

    return score, sigs

# ─── MULTI-TIMEFRAME ──────────────────────────────────────────
def multi_tf(symbol):
    """
    Analyze 3 timeframes and combine. Higher confidence when all agree.
    """
    timeframes = [('1d', '6mo'), ('4h', '60d'), ('1h', '20d')]
    weights    = {'1d': 0.5,    '4h': 0.3,     '1h': 0.2}

    tf_scores  = {}
    main_df    = None
    main_sigs  = {}

    for interval, period in timeframes:
        df = fetch(symbol, period, interval)
        sc, sigs = analyze_df(df)
        if sc is None:
            continue
        tf_scores[interval] = sc
        if interval == '1d':
            main_df   = df
            main_sigs = sigs or {}

    if not tf_scores:
        return None

    total_w = sum(weights[tf] for tf in weights if tf in tf_scores)
    combined = sum(tf_scores[tf] * weights[tf]
                   for tf in weights if tf in tf_scores) / total_w

    vals = list(tf_scores.values())
    all_bull = all(s > 0 for s in vals)
    all_bear = all(s < 0 for s in vals)
    agreement = 'FULL' if (all_bull or all_bear) else (
                'PARTIAL' if len(vals) > 1 else 'SINGLE')

    return {
        'symbol':   symbol,
        'df':       main_df,
        'signals':  main_sigs,
        'tf_scores': tf_scores,
        'score':    combined,
        'agreement': agreement,
        'bullish':  combined > 0,
    }

# ─── RISK / TRADE PLAN ────────────────────────────────────────
def trade_plan(df, bullish, capital=1000.0, risk_pct=2.0):
    """ATR-based entry, stop-loss, and three profit targets."""
    c, h, l = df['close'], df['high'], df['low']
    entry   = float(c.iloc[-1])
    atr_val = float(_atr(h, l, c).iloc[-1])

    if np.isnan(atr_val) or atr_val <= 0:
        return None

    mult = 1.5  # risk multiplier
    if bullish:
        stop = entry - mult * atr_val
        tp1  = entry + 1.0 * mult * atr_val
        tp2  = entry + 2.0 * mult * atr_val
        tp3  = entry + 3.0 * mult * atr_val
    else:
        stop = entry + mult * atr_val
        tp1  = entry - 1.0 * mult * atr_val
        tp2  = entry - 2.0 * mult * atr_val
        tp3  = entry - 3.0 * mult * atr_val

    risk_unit = abs(entry - stop)
    risk_usd  = capital * risk_pct / 100
    units     = risk_usd / risk_unit
    pos_val   = units * entry

    return {
        'direction':  'LONG 📈' if bullish else 'SHORT 📉',
        'entry':      entry,
        'stop':       stop,
        'tp1': tp1, 'tp2': tp2, 'tp3': tp3,
        'atr':        atr_val,
        'risk_usd':   risk_usd,
        'risk_pct':   risk_pct,
        'units':      units,
        'pos_val':    pos_val,
        'port_pct':   pos_val / capital * 100,
        'capital':    capital,
        'support':    float(l.rolling(20).min().iloc[-1]),
        'resistance': float(h.rolling(20).max().iloc[-1]),
    }

# ─── VERDICT HELPERS ──────────────────────────────────────────
def verdict(score):
    if score >= 10:  return '🚀 STRONG BUY',  'bold green'
    if score >=  5:  return '📈 BUY',          'green'
    if score >=  2:  return '💚 WEAK BUY',    'yellow'
    if score <= -10: return '💥 STRONG SELL', 'bold red'
    if score <=  -5: return '📉 SELL',         'red'
    if score <=  -2: return '🔶 WEAK SELL',   'yellow'
    return '⏳ NEUTRAL', 'dim white'

SIG_FMT = {
    'STRONG BUY':  ('🟢🟢', 'bold green'),
    'BUY':         ('🟢  ', 'green'),
    'NEUTRAL':     ('⚪  ', 'white'),
    'SELL':        ('🔴  ', 'red'),
    'STRONG SELL': ('🔴🔴', 'bold red'),
}

# ─── DISPLAY ──────────────────────────────────────────────────
BANNER = """[bold cyan]
╔══════════════════════════════════════════════════════╗
║         ⚡  APEX TRADING SYSTEM  v3.0               ║
║   Multi-TF · 11 Indicators · ATR Risk Manager       ║
╚══════════════════════════════════════════════════════╝[/bold cyan]"""


def show_analysis(result, capital):
    sym = result['symbol']
    df  = result['df']
    if df is None:
        console.print(f'[red]No daily data for {sym}[/red]')
        return

    c   = df['close']
    lp  = float(c.iloc[-1])
    chg = (lp - float(c.iloc[-2])) / float(c.iloc[-2]) * 100
    cc  = 'green' if chg >= 0 else 'red'
    cs  = f'+{chg:.2f}%' if chg >= 0 else f'{chg:.2f}%'
    sc  = result['score']
    tfs = result['tf_scores']
    vt, vc = verdict(sc)

    console.print(Panel(
        f'[bold white]{sym}[/bold white]   '
        f'[bold yellow]${lp:,.4f}[/bold yellow]   [{cc}]{cs}[/{cc}]\n'
        f'[dim]Score: {sc:+.1f}/22   TF Agreement: {result["agreement"]}   '
        f'1D:{tfs.get("1d",0):+.0f}  4H:{tfs.get("4h",0):+.0f}  '
        f'1H:{tfs.get("1h",0):+.0f}[/dim]',
        title='[bold cyan]APEX — Multi-Timeframe Analysis[/bold cyan]',
        border_style='cyan'
    ))

    # Signals table
    t = Table(title='Technical Signals (Daily TF)',
              box=box.ROUNDED, border_style='green',
              show_lines=True, min_width=62)
    t.add_column('Indicator', style='bold cyan', width=14)
    t.add_column('Signal',    width=16)
    t.add_column('Detail')
    for ind, (sig, det) in result['signals'].items():
        icon, col = SIG_FMT.get(sig, ('⚪', 'white'))
        t.add_row(ind, f'[{col}]{icon} {sig}[/{col}]', f'[dim]{det}[/dim]')
    console.print(t)

    # Verdict banner
    console.print(Panel(
        f'[bold {vc}]{vt}[/bold {vc}]\n[dim]Composite score: {sc:+.1f} / 22[/dim]',
        border_style=vc, title='[bold]OVERALL SIGNAL[/bold]'
    ))

    # Trade plan
    tp = trade_plan(df, result['bullish'], capital)
    if tp is None:
        return

    ec = 'green' if result['bullish'] else 'red'
    tr = Table(title='📋 Complete Trade Plan',
               box=box.ROUNDED, border_style='yellow', min_width=58)
    tr.add_column('Parameter', style='bold cyan')
    tr.add_column('Value', justify='right')

    rows = [
        ('Direction',          f'[bold {ec}]{tp["direction"]}[/bold {ec}]'),
        ('Capital',            f'${tp["capital"]:,.2f}'),
        ('Max Risk',           f'[red]{tp["risk_pct"]:.1f}%  =  ${tp["risk_usd"]:,.2f}[/red]'),
        ('─────────────────', '─────────────'),
        ('⚡ ENTRY',          f'[bold yellow]${tp["entry"]:,.4f}[/bold yellow]'),
        ('🔴 STOP LOSS',      f'[bold red]${tp["stop"]:,.4f}[/bold red]   '
                               f'[dim]({abs(tp["entry"]-tp["stop"])/tp["entry"]*100:.2f}% away)[/dim]'),
        ('─────────────────', '─────────────'),
        ('🎯 Target 1  (1:1)', f'[green]${tp["tp1"]:,.4f}[/green]   [dim]→ take 50% here[/dim]'),
        ('🎯 Target 2  (2:1)', f'[bold green]${tp["tp2"]:,.4f}[/bold green]   [dim]→ take 30% here[/dim]'),
        ('🎯 Target 3  (3:1)', f'[bold green]${tp["tp3"]:,.4f}[/bold green]   [dim]→ let 20% run[/dim]'),
        ('─────────────────', '─────────────'),
        ('Units',              f'{tp["units"]:.6f}'),
        ('Position Value',     f'${tp["pos_val"]:,.2f}'),
        ('Portfolio Weight',   f'{tp["port_pct"]:.1f}%'),
        ('ATR (14)',           f'${tp["atr"]:,.4f}'),
        ('20D Support',        f'${tp["support"]:,.4f}'),
        ('20D Resistance',     f'${tp["resistance"]:,.4f}'),
    ]
    for label, val in rows:
        tr.add_row(label, val)
    console.print(tr)

    is_long = result['bullish']
    console.print(Panel(
        f'[bold]EXECUTION STEPS:[/bold]\n\n'
        f'[yellow]1.[/yellow] Price is at [bold yellow]${tp["entry"]:,.4f}[/bold yellow] right now\n'
        f'[yellow]2.[/yellow] [bold {"green" if is_long else "red"}]{"BUY" if is_long else "SELL SHORT"}[/bold {"green" if is_long else "red"}]'
        f'  {tp["units"]:.6f} units  (≈ ${tp["pos_val"]:,.2f})\n'
        f'[yellow]3.[/yellow] [bold red]IMMEDIATELY[/bold red] set Stop Loss: [red]${tp["stop"]:,.4f}[/red]\n'
        f'[yellow]4.[/yellow] At [green]${tp["tp1"]:,.4f}[/green] → sell 50% of position + move SL to entry\n'
        f'[yellow]5.[/yellow] At [bold green]${tp["tp2"]:,.4f}[/bold green] → sell 30% of position\n'
        f'[yellow]6.[/yellow] At [bold green]${tp["tp3"]:,.4f}[/bold green] → sell remaining 20%\n'
        f'[yellow]7.[/yellow] [dim]If price hits Stop Loss → accept the loss, never move it wider[/dim]',
        title='[bold cyan]📌 Step-by-Step Execution[/bold cyan]',
        border_style='cyan'
    ))


def show_scanner_table(results):
    if not results:
        console.print('[yellow]No signals above threshold.[/yellow]')
        return

    t = Table(
        title=f'🔍 Scanner Results — {len(results)} signals found',
        box=box.ROUNDED, border_style='cyan', show_lines=True
    )
    t.add_column('#',        width=3,  justify='right')
    t.add_column('Symbol',   width=10, style='bold')
    t.add_column('Price',    width=14, justify='right')
    t.add_column('Signal',   width=16)
    t.add_column('Score',    width=7,  justify='center')
    t.add_column('TF Agree', width=9)
    t.add_column('1D/4H/1H', width=12)

    for i, r in enumerate(results, 1):
        sc = r['score']
        vt, vc = verdict(sc)
        tfs = r['tf_scores']
        ag_c = 'green' if r['agreement'] == 'FULL' else 'yellow'
        t.add_row(
            str(i),
            r['symbol'],
            f'${r["price"]:,.4f}',
            f'[{vc}]{vt}[/{vc}]',
            f'{sc:+.1f}',
            f'[{ag_c}]{r["agreement"]}[/{ag_c}]',
            f'{tfs.get("1d",0):+.0f}/{tfs.get("4h",0):+.0f}/{tfs.get("1h",0):+.0f}',
        )
    console.print(t)

# ─── SCANNER ──────────────────────────────────────────────────
def run_scan(symbols, min_score=3.0):
    results = []
    n = len(symbols)
    for i, sym in enumerate(symbols):
        try:
            console.print(f'[dim]  [{i+1}/{n}] {sym}...[/dim]', end='\r')
            r = multi_tf(sym)
            if r and abs(r['score']) >= min_score and r['df'] is not None:
                r['price'] = float(r['df']['close'].iloc[-1])
                results.append(r)
            time.sleep(0.25)          # respect Yahoo Finance rate limit
        except Exception:
            pass
    console.print(' ' * 55, end='\r')
    return sorted(results, key=lambda x: abs(x['score']), reverse=True)

# ─── MENU ─────────────────────────────────────────────────────
def main():
    capital   = 1000.0
    min_score = 3.0

    console.print(BANNER)

    while True:
        console.print(Panel(
            f'[bold cyan]1[/bold cyan] — 🔍 Scan CRYPTO ({len(CRYPTO)} coins)\n'
            f'[bold cyan]2[/bold cyan] — 🔍 Scan STOCKS ({len(STOCKS)} stocks)\n'
            f'[bold cyan]3[/bold cyan] — 🔍 Scan ALL markets ({len(CRYPTO+STOCKS)} symbols)\n'
            f'[bold cyan]4[/bold cyan] — 📊 Analyze one symbol manually\n'
            f'[bold cyan]5[/bold cyan] — 💰 Set capital [dim](now: ${capital:,.0f})[/dim]\n'
            f'[bold cyan]6[/bold cyan] — 🎚  Set min signal score [dim](now: {min_score:.0f}/22)[/dim]\n'
            f'[bold cyan]7[/bold cyan] — ❌ Exit',
            title='[bold]⚡ APEX MAIN MENU[/bold]', border_style='cyan'
        ))

        choice = input('\nChoose (1-7): ').strip()

        if choice in ('1', '2', '3'):
            pool = {'1': CRYPTO, '2': STOCKS, '3': CRYPTO + STOCKS}[choice]
            console.print(f'\n[cyan]Scanning {len(pool)} symbols — please wait...[/cyan]\n')
            results = run_scan(pool, min_score)
            show_scanner_table(results)

            if results:
                pick = input(
                    f'\nEnter number to get full analysis (1-{len(results)}) '
                    f'or press Enter to skip: '
                ).strip()
                if pick.isdigit() and 1 <= int(pick) <= len(results):
                    show_analysis(results[int(pick) - 1], capital)

        elif choice == '4':
            sym = input('Symbol (e.g. BTC-USD or AAPL): ').strip().upper()
            if sym:
                console.print(f'\n[cyan]Analyzing {sym} across 3 timeframes...[/cyan]\n')
                r = multi_tf(sym)
                if r:
                    show_analysis(r, capital)
                else:
                    console.print(f'[red]Could not fetch data for {sym}[/red]')

        elif choice == '5':
            try:
                capital = float(input('Enter capital ($): ').strip())
                console.print(f'[green]Capital set to ${capital:,.2f}[/green]')
            except ValueError:
                console.print('[red]Invalid number[/red]')

        elif choice == '6':
            try:
                min_score = float(input('Min score (1-15, default 3): ').strip())
                console.print(f'[green]Min score set to {min_score}[/green]')
            except ValueError:
                console.print('[red]Invalid number[/red]')

        elif choice == '7':
            console.print('\n[cyan]Trade safe. Never risk money you cannot afford to lose. 🙏[/cyan]\n')
            break

        else:
            console.print('[red]Invalid choice — enter 1 to 7[/red]')

        input('\n  Press Enter to continue...')
        console.clear()
        console.print(BANNER)


if __name__ == '__main__':
    main()
