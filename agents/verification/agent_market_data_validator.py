"""
AGENT DE VÉRIFICATION 3 — MarketDataValidator
Rôle : Valider la qualité et la fraîcheur des données de marché.
Détecte : données stale, prix aberrants, trous dans les séries, anomalies.
Fréquence : toutes les 5 minutes.
"""
import sys, os, time
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from agents.base_agent import BaseAgent
from orchestrator.state_bus import STATE
from data.market_data import PRIX_REFERENCE, fetch_prix


class MarketDataValidatorAgent(BaseAgent):

    MAX_AGE_DONNEE_SEC   = 300    # Donnée périmée si > 5 min
    MAX_ECART_REFERENCE  = 0.60   # 60% max d'écart vs référence
    MIN_VOLUME           = 100    # Volume minimal acceptable
    MAX_TROU_JOURS       = 5      # Trous max acceptables dans la série

    def __init__(self):
        super().__init__("MarketDataValidator", 300)
        self._anomalies_connues: set = set()
        self._stats: dict = {}

    def _verifier_fraicheur(self, ticker: str, data: dict) -> tuple[bool, str]:
        age = time.time() - data.get("_ts", 0)
        if age > self.MAX_AGE_DONNEE_SEC:
            return False, f"Donnée âgée de {age:.0f}s (max {self.MAX_AGE_DONNEE_SEC}s)"
        return True, f"Fraîche ({age:.0f}s)"

    def _verifier_prix_coherent(self, ticker: str, prix: float) -> tuple[bool, str]:
        ref = PRIX_REFERENCE.get(ticker)
        if ref is None or ref <= 0:
            return True, "Pas de référence"
        ecart = abs(prix - ref) / ref
        if ecart > self.MAX_ECART_REFERENCE:
            return False, f"Prix aberrant: {prix:.2f} vs ref {ref:.2f} (écart {ecart:.0%})"
        return True, f"OK ({ecart:.1%} vs ref)"

    def _verifier_serie_ohlcv(self, ticker: str) -> tuple[bool, str]:
        """Vérifie la qualité de la série OHLCV complète."""
        try:
            df = fetch_prix(ticker, "3mo", "1d")
            if df is None or len(df) < 20:
                return False, f"Série trop courte: {len(df) if df is not None else 0} points"

            # 1. Pas de NaN
            nan_count = df.isnull().sum().sum()
            if nan_count > 0:
                return False, f"{nan_count} valeurs NaN"

            # 2. High >= Close >= Low toujours
            violations_hcl = ((df["High"] < df["Close"]) | (df["Close"] < df["Low"])).sum()
            if violations_hcl > 0:
                return False, f"{violations_hcl} violations High>=Close>=Low"

            # 3. Pas de prix négatifs
            if (df["Close"] <= 0).any():
                return False, "Prix négatifs ou nuls détectés"

            # 4. Volume non négatif
            if (df["Volume"] < 0).any():
                return False, "Volume négatif"

            # 5. Pas de sauts de prix extrêmes (>30% en un jour)
            rend = df["Close"].pct_change().abs()
            sauts = (rend > 0.30).sum()
            if sauts > 2:
                return False, f"{sauts} sauts de prix > 30% en un jour"

            # 6. Trous dans la série temporelle
            if hasattr(df.index, 'date'):
                diffs = pd.Series(df.index).diff().dt.days.dropna()
                max_trou = diffs.max()
                if max_trou > self.MAX_TROU_JOURS:
                    return False, f"Trou de {max_trou:.0f} jours dans la série"

            return True, f"Série OK ({len(df)} points)"

        except Exception as e:
            return False, f"Erreur: {e}"

    def _verifier_correlation_actifs(self) -> str:
        """
        Vérifie que les corrélations entre actifs sont raisonnables.
        Ex : Or et Argent doivent être corrélés positivement.
        """
        try:
            paires_attendues = [("GC=F", "SI=F", 0.3)]  # Or/Argent corrélation positive
            for t1, t2, seuil in paires_attendues:
                df1 = fetch_prix(t1, "3mo", "1d")
                df2 = fetch_prix(t2, "3mo", "1d")
                if df1 is not None and df2 is not None:
                    r1 = df1["Close"].pct_change().dropna()
                    r2 = df2["Close"].pct_change().dropna()
                    min_len = min(len(r1), len(r2))
                    corr = np.corrcoef(r1.values[-min_len:], r2.values[-min_len:])[0, 1]
                    if corr < seuil:
                        return f"⚠️ Corrélation {t1}/{t2} = {corr:.2f} (attendu > {seuil})"
            return "OK"
        except Exception as e:
            return f"Erreur corrélation: {e}"

    def executer(self):
        market_data = STATE.get_all_market_data()
        univers     = STATE.get_univers_halal()

        if not univers:
            self._log("Univers vide — attente HalalScreener", "WARN")
            return

        ok_count = 0
        ko_tickers = []

        for ticker in univers:
            data = market_data.get(ticker, {})
            erreurs_ticker = []

            # 1. Fraîcheur
            if data:
                ok_f, msg_f = self._verifier_fraicheur(ticker, data)
                if not ok_f:
                    erreurs_ticker.append(msg_f)

                # 2. Cohérence prix
                prix = data.get("prix", 0)
                if prix > 0:
                    ok_p, msg_p = self._verifier_prix_coherent(ticker, prix)
                    if not ok_p:
                        erreurs_ticker.append(msg_p)
                        key = f"prix_{ticker}"
                        if key not in self._anomalies_connues:
                            STATE.log_error(self.nom, f"Prix aberrant {ticker}: {msg_p}", critique=False)
                            self._anomalies_connues.add(key)

            # 3. Qualité série OHLCV (seulement quelques actifs par cycle pour ne pas surcharger)
            if self._total_cycles % 3 == 0 or ticker in ["GC=F", "AAPL"]:
                ok_s, msg_s = self._verifier_serie_ohlcv(ticker)
                if not ok_s:
                    erreurs_ticker.append(f"Série: {msg_s}")

            if erreurs_ticker:
                ko_tickers.append((ticker, erreurs_ticker))
            else:
                ok_count += 1

        # 4. Corrélation (une fois sur 3)
        if self._total_cycles % 3 == 0:
            corr_status = self._verifier_correlation_actifs()
            if corr_status != "OK":
                self._log(corr_status, "WARN")

        # Rapport
        total = len(univers)
        self._log(
            f"Données: {ok_count}/{total} valides | "
            f"{len(ko_tickers)} problèmes détectés"
        )

        for ticker, errs in ko_tickers[:3]:
            for err in errs:
                self._log(f"  ⚠️  {ticker}: {err}", "WARN")

        self._stats = {
            "timestamp": datetime.now().isoformat(),
            "ok": ok_count,
            "ko": len(ko_tickers),
            "total": total,
        }
