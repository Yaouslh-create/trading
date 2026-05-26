"""
Moteur de Backtesting — Validation sur données historiques
Simons testait des années d'historique avant tout trade réel.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pandas as pd
import numpy as np
from datetime import datetime
from data.market_data import fetch_prix
from strategies.indicators import generer_signal, calculer_tous_indicateurs


def backtest_strategie(ticker: str, periode: str = "2y", capital_depart: float = 100.0) -> dict:
    print(f"  Backtesting {ticker} sur {periode}...")
    df = fetch_prix(ticker, periode=periode, intervalle="1d")
    if df is None or len(df) < 60:
        return {"erreur": f"Données insuffisantes pour {ticker}"}

    capital     = capital_depart
    capital_max = capital_depart
    position    = None
    trades      = []
    courbe      = []

    FRAIS   = 0.001   # 0.1% par trade (réaliste)
    SLIP    = 0.0003  # 0.03% slippage

    for i in range(35, len(df)):
        df_w = df.iloc[:i]
        prix = float(df["Close"].iloc[i])
        date = str(df.index[i].date())

        courbe.append(capital + (position["quantite"] * prix if position else 0))

        # Gestion stop / take profit
        if position is not None:
            sens = 1 if position["sens"] == "ACHETER" else -1
            touche_sl = (sens == 1 and prix <= position["stop_loss"]) or \
                        (sens == -1 and prix >= position["stop_loss"])
            touche_tp = (sens == 1 and prix >= position["take_profit"]) or \
                        (sens == -1 and prix <= position["take_profit"])

            if touche_sl or touche_tp:
                prix_exit = position["stop_loss"] if touche_sl else position["take_profit"]
                produit   = position["quantite"] * prix_exit * (1 - FRAIS)
                pnl       = produit - position["cout"]
                capital  += produit
                if capital > capital_max:
                    capital_max = capital
                trades.append({
                    "date_entree":  position["date"],
                    "date_sortie":  date,
                    "ticker":       ticker,
                    "sens":         position["sens"],
                    "prix_entree":  position["prix_entree"],
                    "prix_sortie":  round(prix_exit, 4),
                    "pnl":          round(pnl, 4),
                    "pnl_pct":      round(pnl / position["cout"] * 100, 2),
                    "sortie":       "STOP" if touche_sl else "TP",
                    "capital":      round(capital, 2),
                })
                position = None

        # Nouveau signal si pas de position
        if position is None and capital > 5.0:
            signal = generer_signal(ticker, df_w)
            if signal.action != "ATTENDRE" and signal.confiance != "faible":
                risque_trade = capital * 0.015   # 1.5% max risqué
                risque_unite = abs(signal.prix_entree - signal.stop_loss)
                if risque_unite > 0:
                    quantite = (risque_trade / risque_unite) * signal.force
                    prix_achat = prix * (1 + SLIP)
                    cout       = quantite * prix_achat * (1 + FRAIS)
                    max_pos    = capital * 0.30   # max 30% du capital
                    if cout > max_pos:
                        quantite = (max_pos / prix_achat) / (1 + FRAIS)
                        cout     = quantite * prix_achat * (1 + FRAIS)
                    if cout <= capital and cout > 0.5:
                        capital -= cout
                        position = {
                            "sens":         signal.action,
                            "prix_entree":  prix_achat,
                            "stop_loss":    signal.stop_loss,
                            "take_profit":  signal.take_profit,
                            "quantite":     quantite,
                            "cout":         cout,
                            "date":         date,
                        }

    if not trades:
        val_finale = capital + (position["quantite"] * float(df["Close"].iloc[-1]) if position else 0)
        return {"ticker": ticker, "erreur": "Aucun trade clôturé", "capital_final": round(val_finale, 2)}

    df_t = pd.DataFrame(trades)
    gagnants = df_t[df_t["pnl"] > 0]
    perdants  = df_t[df_t["pnl"] <= 0]

    val_finale  = capital + (position["quantite"] * float(df["Close"].iloc[-1]) if position else 0)
    rendement   = (val_finale - capital_depart) / capital_depart * 100
    drawdown    = (capital_max - min(courbe)) / capital_max * 100 if courbe else 0
    win_rate    = len(gagnants) / len(df_t) * 100
    g_moy       = gagnants["pnl"].mean() if len(gagnants) > 0 else 0
    p_moy       = perdants["pnl"].mean()  if len(perdants) > 0 else -0.001
    pf          = abs(gagnants["pnl"].sum() / perdants["pnl"].sum()) if perdants["pnl"].sum() != 0 else 99.0

    rend_j = pd.Series(courbe).pct_change().dropna()
    sharpe = (rend_j.mean() / rend_j.std() * np.sqrt(252)) if rend_j.std() > 0 else 0

    return {
        "ticker": ticker, "periode": periode,
        "capital_depart": capital_depart, "capital_final": round(val_finale, 2),
        "rendement_pct": round(rendement, 2), "nb_trades": len(df_t),
        "win_rate": round(win_rate, 1), "profit_factor": round(pf, 2),
        "sharpe_ratio": round(float(sharpe), 2),
        "drawdown_max_pct": round(drawdown, 2),
        "gain_moyen": round(g_moy, 4), "perte_moyenne": round(p_moy, 4),
        "ratio_rr": round(abs(g_moy / p_moy), 2) if p_moy != 0 else 0,
        "trades": trades[-5:], "courbe_capital": courbe,
    }


def backtest_multi(tickers: list, periode: str = "1y", capital: float = 100.0) -> pd.DataFrame:
    resultats = []
    for ticker in tickers:
        r = backtest_strategie(ticker, periode, capital)
        if "erreur" not in r:
            resultats.append({
                "Ticker":        r["ticker"],
                "Rendement%":    r["rendement_pct"],
                "WinRate%":      r["win_rate"],
                "ProfitFactor":  r["profit_factor"],
                "Sharpe":        r["sharpe_ratio"],
                "Drawdown%":     r["drawdown_max_pct"],
                "NbTrades":      r["nb_trades"],
                "Capital€":      r["capital_final"],
            })
    if not resultats:
        return pd.DataFrame()
    return pd.DataFrame(resultats).sort_values("Rendement%", ascending=False)


if __name__ == "__main__":
    print("=== BACKTEST MULTI-ACTIFS HALAL (2 ans) ===\n")
    tickers = ["GC=F", "SI=F", "AAPL", "NVDA", "MSFT", "TSLA", "AMD"]
    res = backtest_multi(tickers, periode="2y", capital=100.0)
    if not res.empty:
        print(res.to_string(index=False))
        best = res.iloc[0]
        print(f"\n  🏆 Meilleur actif: {best['Ticker']} ({best['Rendement%']:+.1f}%)")
        print(f"     WinRate: {best['WinRate%']}% | ProfitFactor: {best['ProfitFactor']}")
        print(f"     Sharpe: {best['Sharpe']} | MaxDrawdown: {best['Drawdown%']}%")
