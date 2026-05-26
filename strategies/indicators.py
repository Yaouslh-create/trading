"""
Moteur d'indicateurs techniques — Signaux quantitatifs
Inspiré de l'approche mathématique de Renaissance Technologies.
Règle Simons : plusieurs confirmations obligatoires, ratio R/R élevé.
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass


@dataclass
class Signal:
    ticker: str
    action: str          # "ACHETER", "VENDRE", "ATTENDRE"
    force: float         # 0.0 à 1.0
    confiance: str       # "faible", "moyenne", "forte"
    raisons: list
    prix_entree: float
    stop_loss: float
    take_profit: float
    indicateurs: dict


def rsi(serie, periode=14):
    delta = serie.diff()
    gains = delta.clip(lower=0)
    pertes = (-delta).clip(lower=0)
    mg = gains.ewm(com=periode-1, adjust=False).mean()
    mp = pertes.ewm(com=periode-1, adjust=False).mean()
    rs = mg / mp
    return 100 - (100 / (1 + rs))

def macd(serie, rapide=12, lent=26, signal=9):
    ema_r = serie.ewm(span=rapide, adjust=False).mean()
    ema_l = serie.ewm(span=lent,   adjust=False).mean()
    ligne = ema_r - ema_l
    sig   = ligne.ewm(span=signal, adjust=False).mean()
    return ligne, sig, ligne - sig

def bollinger(serie, periode=20, ecarts=2.0):
    moy = serie.rolling(periode).mean()
    std = serie.rolling(periode).std()
    return moy + std*ecarts, moy, moy - std*ecarts

def ema(serie, periode):
    return serie.ewm(span=periode, adjust=False).mean()

def atr(df, periode=14):
    hb = df["High"] - df["Low"]
    hc = (df["High"] - df["Close"].shift()).abs()
    bc = (df["Low"]  - df["Close"].shift()).abs()
    tr = pd.concat([hb, hc, bc], axis=1).max(axis=1)
    return tr.ewm(span=periode, adjust=False).mean()

def volume_relatif(df, periode=20):
    if len(df) < periode:
        return 1.0
    va = float(df["Volume"].iloc[-1])
    vm = float(df["Volume"].tail(periode).mean())
    return round(va / vm, 2) if vm > 0 else 1.0


def calculer_tous_indicateurs(df: pd.DataFrame) -> dict:
    if df is None or len(df) < 30:
        return {}
    close = df["Close"]
    n = len(df)
    rsi_s       = rsi(close)
    macd_l, macd_sig, macd_h = macd(close)
    bb_h, bb_m, bb_b = bollinger(close)
    ema9  = ema(close, 9)
    ema21 = ema(close, 21)
    ema50 = ema(close, 50) if n >= 50 else ema21
    atr_s = atr(df)
    mom   = (close / close.shift(10) - 1) * 100
    vol_r = volume_relatif(df)
    prix  = float(close.iloc[-1])
    return {
        "prix":           round(prix, 4),
        "rsi":            round(float(rsi_s.iloc[-1]),   2),
        "rsi_prev":       round(float(rsi_s.iloc[-2]),   2),
        "macd":           round(float(macd_l.iloc[-1]),  4),
        "macd_signal":    round(float(macd_sig.iloc[-1]),4),
        "macd_histo":     round(float(macd_h.iloc[-1]),  4),
        "macd_histo_prev":round(float(macd_h.iloc[-2]),  4),
        "bb_haute":       round(float(bb_h.iloc[-1]),    4),
        "bb_milieu":      round(float(bb_m.iloc[-1]),    4),
        "bb_basse":       round(float(bb_b.iloc[-1]),    4),
        "ema9":           round(float(ema9.iloc[-1]),     4),
        "ema21":          round(float(ema21.iloc[-1]),    4),
        "ema50":          round(float(ema50.iloc[-1]),    4),
        "atr":            round(float(atr_s.iloc[-1]),    4),
        "momentum_10j":   round(float(mom.iloc[-1]),      2),
        "volume_relatif": vol_r,
        "tendance":       "HAUSSIERE" if ema9.iloc[-1] > ema21.iloc[-1] else "BAISSIERE",
        "prix_bb_pct":    round((prix - float(bb_b.iloc[-1])) / (float(bb_h.iloc[-1]) - float(bb_b.iloc[-1])) * 100, 1),
    }


def generer_signal(ticker: str, df: pd.DataFrame) -> Signal:
    """
    Génère un signal de trading multi-confirmation.
    Minimum 3 signaux alignés requis (style Renaissance).
    """
    indic = calculer_tous_indicateurs(df)
    if not indic:
        return Signal(ticker=ticker, action="ATTENDRE", force=0.0,
                      confiance="faible", raisons=["Données insuffisantes"],
                      prix_entree=0, stop_loss=0, take_profit=0, indicateurs={})

    prix      = indic["prix"]
    rsi_v     = indic["rsi"]
    rsi_prev  = indic["rsi_prev"]
    macd_h    = indic["macd_histo"]
    macd_prev = indic["macd_histo_prev"]
    bb_h      = indic["bb_haute"]
    bb_b      = indic["bb_basse"]
    bb_pct    = indic["prix_bb_pct"]
    ema9_v    = indic["ema9"]
    ema21_v   = indic["ema21"]
    ema50_v   = indic["ema50"]
    atr_v     = indic["atr"]
    mom_v     = indic["momentum_10j"]
    vol_r     = indic["volume_relatif"]
    tendance  = indic["tendance"]

    sa = []  # signaux achat
    sv = []  # signaux vente

    # 1. RSI — zone extrême + retournement
    if rsi_v < 30:
        sa.append(f"RSI très survendu ({rsi_v:.0f})")
    elif rsi_v < 40 and rsi_v > rsi_prev:
        sa.append(f"RSI survendu + rebond ({rsi_v:.0f}↑)")
    if rsi_v > 70:
        sv.append(f"RSI très suracheté ({rsi_v:.0f})")
    elif rsi_v > 60 and rsi_v < rsi_prev:
        sv.append(f"RSI suracheté + repli ({rsi_v:.0f}↓)")

    # 2. MACD — croisement (plus fiable que direction seule)
    if macd_h > 0 and macd_prev <= 0:
        sa.append("Croisement MACD haussier ✦")
    elif macd_h > 0 and macd_h > macd_prev:
        sa.append("MACD en accélération haussière")
    if macd_h < 0 and macd_prev >= 0:
        sv.append("Croisement MACD baissier ✦")
    elif macd_h < 0 and macd_h < macd_prev:
        sv.append("MACD en accélération baissière")

    # 3. EMA — tendance principale
    if ema9_v > ema21_v and ema21_v > ema50_v:
        sa.append("Triple EMA alignée haussière")
    elif ema9_v > ema21_v:
        sa.append("EMA9 > EMA21 (tendance haussière)")
    if ema9_v < ema21_v and ema21_v < ema50_v:
        sv.append("Triple EMA alignée baissière")
    elif ema9_v < ema21_v:
        sv.append("EMA9 < EMA21 (tendance baissière)")

    # 4. Bollinger — position dans les bandes
    if bb_pct < 15:
        sa.append(f"Prix près bande basse Bollinger ({bb_pct:.0f}%)")
    if bb_pct > 85:
        sv.append(f"Prix près bande haute Bollinger ({bb_pct:.0f}%)")

    # 5. Momentum
    if mom_v > 5:
        sa.append(f"Momentum fort +{mom_v:.1f}%")
    elif mom_v < -5:
        sv.append(f"Momentum négatif {mom_v:.1f}%")

    # 6. Volume — confirmation institutionnelle
    if vol_r > 1.8:
        note = "Achat institutionnel probable" if len(sa) >= len(sv) else "Vente institutionnelle probable"
        if len(sa) >= len(sv):
            sa.append(f"Volume x{vol_r:.1f} — {note}")
        else:
            sv.append(f"Volume x{vol_r:.1f} — {note}")

    na, nv = len(sa), len(sv)

    # Stop-loss ATR (dynamique, adapté à la volatilité)
    sl_mult = 1.5
    tp_mult = 2.5  # Ratio R/R 1:2.5

    if na >= 3 and na > nv:
        force = min(1.0, (na - nv) / 5.0 + 0.2)
        conf  = "forte" if force > 0.6 else ("moyenne" if force > 0.35 else "faible")
        return Signal(
            ticker=ticker, action="ACHETER", force=round(force, 2),
            confiance=conf, raisons=sa,
            prix_entree=prix,
            stop_loss=round(prix - atr_v * sl_mult, 4),
            take_profit=round(prix + atr_v * tp_mult, 4),
            indicateurs=indic
        )
    elif nv >= 3 and nv > na:
        force = min(1.0, (nv - na) / 5.0 + 0.2)
        conf  = "forte" if force > 0.6 else ("moyenne" if force > 0.35 else "faible")
        return Signal(
            ticker=ticker, action="VENDRE", force=round(force, 2),
            confiance=conf, raisons=sv,
            prix_entree=prix,
            stop_loss=round(prix + atr_v * sl_mult, 4),
            take_profit=round(prix - atr_v * tp_mult, 4),
            indicateurs=indic
        )
    else:
        return Signal(
            ticker=ticker, action="ATTENDRE", force=0.0, confiance="faible",
            raisons=[f"Signal mixte ({na}↑ vs {nv}↓) — pas assez de confirmations"],
            prix_entree=prix, stop_loss=0, take_profit=0, indicateurs=indic
        )


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from data.market_data import fetch_prix
    print("=== TEST INDICATEURS ===\n")
    for ticker in ["GC=F", "AAPL", "NVDA"]:
        df = fetch_prix(ticker, "6mo", "1d")
        if df is not None:
            signal = generer_signal(ticker, df)
            print(f"  {ticker:8} | {signal.action:8} | Force: {signal.force:.0%} | {signal.confiance}")
            for r in signal.raisons[:3]:
                print(f"           → {r}")
            print()
