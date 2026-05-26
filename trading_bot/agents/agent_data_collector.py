"""
AGENT 1 — DataCollector
Rôle : Collecter les données de marché en temps réel pour tous les actifs halal.
Fréquence : toutes les 60 secondes.
Sortie : STATE._market_data + STATE._last_prices
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agents.base_agent import BaseAgent
from orchestrator.state_bus import STATE
from config.config import TRADE, AGENTS
from data.market_data import fetch_prix, get_prix_actuel


class DataCollectorAgent(BaseAgent):

    def __init__(self):
        super().__init__("DataCollector", AGENTS.freq_data_collector)
        self._data_cache = {}       # {ticker: DataFrame}
        self._prix_cache = {}       # {ticker: float}

    def on_start(self):
        """Pré-charge les données au démarrage."""
        self._log("Pré-chargement des données historiques...")
        univers = STATE.get_univers_halal() or TRADE.univers_actifs
        loaded = 0
        for ticker in univers:
            try:
                df = fetch_prix(ticker, "6mo", "1d")
                if df is not None and len(df) >= 30:
                    self._data_cache[ticker] = df
                    loaded += 1
            except Exception as e:
                STATE.log_error(self.nom, f"Pré-charge {ticker}: {e}")
        self._log(f"{loaded}/{len(univers)} actifs chargés.", "OK")

    def executer(self):
        univers = STATE.get_univers_halal() or TRADE.univers_actifs
        if not univers:
            self._log("Univers halal vide — attente HalalScreener", "WARN")
            return

        ok, ko = 0, 0
        for ticker in univers:
            try:
                # Prix actuel
                prix_info = get_prix_actuel(ticker)
                if prix_info:
                    STATE.set_market_data(ticker, {
                        "prix":          prix_info["prix"],
                        "variation_pct": prix_info["variation_pct"],
                        "volume":        prix_info["volume"],
                        "source":        prix_info.get("source", "?"),
                        "halal":         prix_info.get("halal", True),
                    })
                    self._prix_cache[ticker] = prix_info["prix"]

                # DataFrame OHLCV complet (mis à jour périodiquement)
                if ticker not in self._data_cache or self._total_cycles % 10 == 0:
                    df = fetch_prix(ticker, "6mo", "1d")
                    if df is not None and len(df) >= 30:
                        self._data_cache[ticker] = df

                # Exposer le DataFrame au bus
                if ticker in self._data_cache:
                    STATE.set_market_data(ticker, {
                        **STATE.get_market_data(ticker),
                        "_df_rows": len(self._data_cache[ticker]),
                        "_has_ohlcv": True,
                    })
                ok += 1

            except Exception as e:
                ko += 1
                STATE.log_error(self.nom, f"Collecte {ticker}: {e}")

        if ok + ko > 0:
            self._log(f"Données: {ok} OK, {ko} erreurs | {len(self._data_cache)} DFs en cache")

    def get_df(self, ticker: str):
        """Accès direct au DataFrame (pour les autres agents)."""
        return self._data_cache.get(ticker)


# Instance partagée — accessible par les autres agents
DATA_AGENT = DataCollectorAgent()
