"""
Moteur de données — Double mode :
- SIMULATION : données synthétiques réalistes (Brownian motion) pour tests
- REEL : Yahoo Finance (quand déployé localement avec accès internet)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from core.halal_filter import get_univers_halal, est_halal

# Prix de référence réalistes par actif (mis à jour manuellement si besoin)
PRIX_REFERENCE = {
    "GC=F":  3350.0,   # Or ($/oz)
    "SI=F":   33.5,    # Argent ($/oz)
    "PL=F":  1000.0,   # Platine
    "HG=F":    4.8,    # Cuivre
    "ZW=F":  530.0,    # Blé
    "ZC=F":  450.0,    # Maïs
    "ZS=F":  1100.0,   # Soja
    "KC=F":  200.0,    # Café
    "CC=F":  7500.0,   # Cacao
    "CT=F":   75.0,    # Coton
    "NG=F":    3.5,    # Gaz naturel
    "CL=F":   78.0,    # Pétrole
    "AAPL":  195.0,    # Apple
    "MSFT":  420.0,    # Microsoft
    "NVDA":  900.0,    # NVIDIA
    "TSLA":  175.0,    # Tesla
    "AMD":   155.0,    # AMD
    "GOOGL": 170.0,    # Alphabet
    "META":  520.0,    # Meta
    "AMZN":  195.0,    # Amazon
    "INTC":   20.0,    # Intel
    "QCOM":  165.0,    # Qualcomm
}

VOLATILITES = {
    "GC=F": 0.008, "SI=F": 0.015, "PL=F": 0.012, "HG=F": 0.018,
    "ZW=F": 0.014, "ZC=F": 0.013, "ZS=F": 0.011, "KC=F": 0.020,
    "CC=F": 0.025, "CT=F": 0.016, "NG=F": 0.030, "CL=F": 0.022,
    "AAPL": 0.016, "MSFT": 0.015, "NVDA": 0.030, "TSLA": 0.038,
    "AMD":  0.028, "GOOGL": 0.016, "META": 0.022, "AMZN": 0.018,
    "INTC": 0.022, "QCOM": 0.020,
}

def _gen_data(ticker: str, jours: int = 500) -> pd.DataFrame:
    """Génère des données OHLCV réalistes via mouvement brownien géométrique."""
    prix_base = PRIX_REFERENCE.get(ticker, 100.0)
    vol       = VOLATILITES.get(ticker, 0.018)
    drift     = 0.0002  # léger biais haussier (marché long terme)

    np.random.seed(abs(hash(ticker)) % 2**31)
    dates    = [datetime.now() - timedelta(days=jours - i) for i in range(jours)]
    rendements = np.random.normal(drift, vol, jours)
    prix     = prix_base * np.cumprod(1 + rendements)

    # Générer OHLC réaliste
    spread_h = abs(np.random.normal(0, vol * 1.2, jours))
    spread_l = abs(np.random.normal(0, vol * 1.2, jours))

    df = pd.DataFrame({
        "Open":   prix * (1 + np.random.normal(0, vol * 0.3, jours)),
        "High":   prix * (1 + spread_h),
        "Low":    prix * (1 - spread_l),
        "Close":  prix,
        "Volume": np.random.randint(500_000, 50_000_000, jours).astype(float),
    }, index=pd.DatetimeIndex(dates))

    # S'assurer que High >= Close >= Low
    df["High"] = df[["High", "Open", "Close"]].max(axis=1)
    df["Low"]  = df[["Low",  "Open", "Close"]].min(axis=1)
    return df

def _periode_vers_jours(periode: str) -> int:
    mapping = {"1d": 1, "5d": 5, "1mo": 30, "3mo": 90, "6mo": 180,
               "1y": 365, "2y": 730, "5y": 1825}
    return mapping.get(periode, 365)

def fetch_prix(ticker: str, periode: str = "6mo", intervalle: str = "1d") -> pd.DataFrame | None:
    """Récupère/génère l'historique de prix."""
    try:
        # Essai avec Yahoo Finance (fonctionne en local)
        import yfinance as yf
        t = yf.Ticker(ticker)
        df = t.history(period=periode, interval=intervalle)
        if not df.empty and len(df) > 10:
            return df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    except Exception:
        pass

    # Fallback : données synthétiques réalistes
    jours = _periode_vers_jours(periode)
    df = _gen_data(ticker, max(jours, 60))
    return df.tail(jours)

def fetch_prix_intraday(ticker: str, jours: int = 5) -> pd.DataFrame | None:
    return fetch_prix(ticker, periode=f"{jours}d", intervalle="1h")

def get_prix_actuel(ticker: str) -> dict | None:
    """Retourne le prix actuel (synthétique si Yahoo bloqué)."""
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        hist = t.history(period="2d", interval="1d")
        if not hist.empty and len(hist) >= 2:
            prix_actuel = float(hist["Close"].iloc[-1])
            prix_veille = float(hist["Close"].iloc[-2])
            variation   = ((prix_actuel - prix_veille) / prix_veille) * 100
            return {
                "ticker": ticker, "prix": round(prix_actuel, 4),
                "variation_pct": round(variation, 2),
                "volume": int(hist["Volume"].iloc[-1]),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "halal": est_halal(ticker)["halal"], "source": "yahoo"
            }
    except Exception:
        pass

    # Fallback synthétique
    df = _gen_data(ticker, 5)
    prix_actuel = float(df["Close"].iloc[-1])
    prix_veille = float(df["Close"].iloc[-2])
    variation   = ((prix_actuel - prix_veille) / prix_veille) * 100
    return {
        "ticker": ticker, "prix": round(prix_actuel, 4),
        "variation_pct": round(variation, 2),
        "volume": int(df["Volume"].iloc[-1]),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "halal": est_halal(ticker)["halal"], "source": "synthétique"
    }

def scan_marche(tickers: list = None, top_n: int = 10) -> pd.DataFrame:
    if tickers is None:
        tickers = get_univers_halal()
    resultats = []
    for ticker in tickers:
        data = get_prix_actuel(ticker)
        if data:
            resultats.append(data)
    if not resultats:
        return pd.DataFrame()
    df = pd.DataFrame(resultats).sort_values("variation_pct", ascending=False)
    return df.head(top_n)

def calculer_volatilite(df: pd.DataFrame, fenetre: int = 20) -> float:
    if df is None or len(df) < fenetre:
        return 0.0
    rendements = df["Close"].pct_change().dropna()
    vol = rendements.tail(fenetre).std() * np.sqrt(252)
    return round(float(vol), 4)

def calculer_rendement(df: pd.DataFrame, jours: int = 20) -> float:
    if df is None or len(df) < jours:
        return 0.0
    debut = float(df["Close"].iloc[-jours])
    fin   = float(df["Close"].iloc[-1])
    return round(((fin - debut) / debut) * 100, 2)

if __name__ == "__main__":
    print("=== TEST MOTEUR DE DONNÉES ===\n")
    for ticker in ["GC=F", "AAPL", "NVDA", "SI=F"]:
        prix = get_prix_actuel(ticker)
        if prix:
            signe = "▲" if prix["variation_pct"] >= 0 else "▼"
            print(f"  {ticker:8} | {prix['prix']:>10.2f} | {signe} {abs(prix['variation_pct']):.2f}% [{prix['source']}]")
