"""
AGENT 2 — HalalScreener
Rôle : Valider et maintenir l'univers d'actifs conformes à la charia.
Re-vérifie chaque heure. Exclut immédiatement tout actif devenu non-conforme.
Fréquence : 3600 secondes (1 heure).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agents.base_agent import BaseAgent
from orchestrator.state_bus import STATE
from config.config import TRADE, AGENTS
from core.halal_filter import (
    est_halal, filtrer_portefeuille, get_univers_halal,
    ACTIFS_HALAL_VALIDES, TICKERS_HARAM_CONNUS
)


class HalalScreenerAgent(BaseAgent):
    """
    Gardien de la conformité charia.
    - Valide l'univers complet toutes les heures
    - Vérifie les positions ouvertes en temps réel
    - Alerte si une position devient haram
    - Publie l'univers validé sur le bus d'état
    """

    def __init__(self):
        super().__init__("HalalScreener", AGENTS.freq_halal_screener)
        self._univers_valide: list = []
        self._historique_exclusions: list = []

    def on_start(self):
        """Validation initiale au démarrage — priorité absolue."""
        self._log("Validation initiale de l'univers halal...")
        self._valider_univers_complet()

    def _valider_actif(self, ticker: str) -> tuple[bool, str]:
        """Validation stricte d'un actif."""
        # 1. Liste noire explicite
        if ticker.upper() in TICKERS_HARAM_CONNUS:
            return False, "Liste noire haram"

        # 2. Liste blanche explicite
        for cat, actifs in ACTIFS_HALAL_VALIDES.items():
            if ticker in actifs:
                return True, f"Liste blanche ({cat})"

        # 3. Actif inconnu → refus par défaut (principe de précaution)
        return False, "Non répertorié — refus par précaution"

    def _valider_univers_complet(self):
        """Valide tous les actifs et met à jour l'univers sur le bus."""
        candidats = TRADE.univers_actifs
        valides, exclus = [], []

        for ticker in candidats:
            ok, raison = self._valider_actif(ticker)
            if ok:
                valides.append(ticker)
            else:
                exclus.append(ticker)
                self._log(f"❌ EXCLU: {ticker} — {raison}", "WARN")
                self._historique_exclusions.append({
                    "ticker": ticker, "raison": raison,
                    "timestamp": __import__("datetime").datetime.now().isoformat()
                })

        STATE.set_univers_halal(valides)
        self._univers_valide = valides
        self._log(
            f"Univers validé: {len(valides)} actifs halal | {len(exclus)} exclus",
            "OK"
        )

    def _verifier_positions_ouvertes(self):
        """
        Vérifie que les positions ouvertes sont toujours halal.
        Si une position devient haram → alerte critique.
        """
        positions = STATE.get_positions()
        for trade_id, pos in positions.items():
            ticker = pos.get("ticker", "")
            if not ticker:
                continue
            ok, raison = self._valider_actif(ticker)
            if not ok:
                msg = f"ALERTE: Position {ticker} devenue non-conforme! {raison}"
                self._log(msg, "ERR")
                STATE.log_error(self.nom, msg, critique=True)
                STATE.set_trading_autorise(
                    False,
                    f"Position haram détectée: {ticker}"
                )

    def executer(self):
        self._valider_univers_complet()
        self._verifier_positions_ouvertes()

        # Stats
        self._log(
            f"Univers: {self._univers_valide[:5]}... ({len(self._univers_valide)} total)",
            "INFO"
        )


HALAL_AGENT = HalalScreenerAgent()
