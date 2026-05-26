"""
AGENT 3 — SignalGenerator
Rôle : Analyser tous les actifs halal et générer des signaux de trading.
Multi-indicateurs avec système de vote pondéré.
Fréquence : toutes les 2 minutes.
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agents.base_agent import BaseAgent
from orchestrator.state_bus import STATE
from config.config import TRADE, AGENTS
from strategies.indicators import generer_signal, calculer_tous_indicateurs
from data.market_data import fetch_prix


class SignalGeneratorAgent(BaseAgent):
    """
    Moteur d'analyse multi-indicateurs.
    Génère des signaux avec score de confiance agrégé.
    Ne publie que les signaux qui dépassent le seuil minimum.
    """

    CONFIANCE_REQUISE = {"faible": 1, "moyenne": 2, "forte": 3}

    def __init__(self):
        super().__init__("SignalGenerator", AGENTS.freq_signal_generator)
        self._df_cache: dict = {}
        self._derniere_analyse: dict = {}

    def _charger_df(self, ticker: str):
        """Charge ou récupère le DataFrame depuis le cache."""
        market = STATE.get_market_data(ticker)

        # Recharger si pas en cache ou données obsolètes (>30 min)
        age = time.time() - self._df_cache.get(ticker, {}).get("_ts", 0)
        if ticker not in self._df_cache or age > 1800:
            df = fetch_prix(ticker, "6mo", "1d")
            if df is not None and len(df) >= 35:
                self._df_cache[ticker] = {"df": df, "_ts": time.time()}
            else:
                return None

        cached = self._df_cache.get(ticker)
        return cached["df"] if cached else None

    def _score_confiance(self, confiance: str) -> int:
        return self.CONFIANCE_REQUISE.get(confiance, 0)

    def _requise_min(self) -> int:
        return self.CONFIANCE_REQUISE.get(TRADE.min_confiance, 2)

    def _analyser_ticker(self, ticker: str) -> dict | None:
        """Analyse complète d'un actif."""
        df = self._charger_df(ticker)
        if df is None:
            return None

        try:
            signal = generer_signal(ticker, df)
            indicateurs = signal.indicateurs

            # Score composite (0–100)
            score = 0
            if signal.action != "ATTENDRE":
                score += signal.force * 60
                score += self._score_confiance(signal.confiance) * 10
                score += min(len(signal.raisons), 4) * 5

            return {
                "ticker":       ticker,
                "action":       signal.action,
                "force":        signal.force,
                "confiance":    signal.confiance,
                "score":        round(score, 1),
                "raisons":      signal.raisons,
                "prix_entree":  signal.prix_entree,
                "stop_loss":    signal.stop_loss,
                "take_profit":  signal.take_profit,
                "indicateurs":  indicateurs,
                "rsi":          indicateurs.get("rsi"),
                "tendance":     indicateurs.get("tendance"),
                "macd_histo":   indicateurs.get("macd_histo"),
            }
        except Exception as e:
            STATE.log_error(self.nom, f"Analyse {ticker}: {e}")
            return None

    def executer(self):
        univers = STATE.get_univers_halal()
        if not univers:
            self._log("Univers halal vide — attente HalalScreener", "WARN")
            return

        actionnables = []

        for ticker in univers:
            analyse = self._analyser_ticker(ticker)
            if analyse is None:
                continue

            # Publier le signal sur le bus (même ATTENDRE pour le monitoring)
            STATE.set_signal(ticker, analyse)

            # Collecter les signaux actionnables
            if (analyse["action"] != "ATTENDRE" and
                    self._score_confiance(analyse["confiance"]) >= self._requise_min()):
                actionnables.append(analyse)

        # Trier par score décroissant
        actionnables.sort(key=lambda x: x["score"], reverse=True)

        if actionnables:
            self._log(
                f"⚡ {len(actionnables)} signal(s) actionnable(s) sur {len(univers)} actifs",
                "OK"
            )
            for sig in actionnables[:3]:
                emoji = "🟢" if sig["action"] == "ACHETER" else "🔴"
                self._log(
                    f"  {emoji} {sig['ticker']:8} | {sig['action']} | "
                    f"Score:{sig['score']:.0f} | {sig['confiance']} | "
                    f"RSI:{sig.get('rsi','?'):.0f}"
                )
        else:
            self._log(f"Analyse complète — aucun signal actionnable sur {len(univers)} actifs")

        self._derniere_analyse = {
            "timestamp":       __import__("datetime").datetime.now().isoformat(),
            "nb_analyses":     len(univers),
            "nb_actionnables": len(actionnables),
            "top_signal":      actionnables[0] if actionnables else None,
        }


SIGNAL_AGENT = SignalGeneratorAgent()
