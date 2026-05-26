"""
AGENT 4 — RiskGuardian
Rôle : Surveillance temps réel du risque. Bloque le trading si limites dépassées.
C'est le gardien — son veto est absolu et non-contournable.
Fréquence : toutes les 30 secondes.
"""
import sys, os
from datetime import datetime, date
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agents.base_agent import BaseAgent
from orchestrator.state_bus import STATE
from config.config import RISK, AGENTS
from risk.risk_manager import GestionnaireRisque


class RiskGuardianAgent(BaseAgent):
    """
    Gardien absolu du risque.
    Surveille en continu : drawdown, perte journalière, positions, capital.
    Son blocage est prioritaire sur tout autre agent.
    """

    def __init__(self):
        super().__init__("RiskGuardian", AGENTS.freq_risk_guardian)
        self._gm = GestionnaireRisque(RISK.capital_initial)
        self._date_courante = date.today()
        self._alertes_envoyees: set = set()

    def on_start(self):
        """Initialise le capital depuis l'état sauvegardé."""
        risk_state = STATE.get_risk_state()
        capital_sauve = risk_state.get("capital_actuel", RISK.capital_initial)
        self._gm.capital_actuel = capital_sauve
        self._gm.capital_initial = RISK.capital_initial
        STATE.update_capital(capital_sauve)
        self._log(f"Capital restauré: {capital_sauve:.2f}€", "OK")

    def _reset_journalier(self):
        """Remet à zéro les compteurs quotidiens à minuit."""
        aujourd_hui = date.today()
        if aujourd_hui != self._date_courante:
            self._date_courante = aujourd_hui
            STATE.reset_perte_journaliere()
            self._alertes_envoyees.clear()
            self._log("Nouveau jour — compteurs remis à zéro", "OK")

    def _verifier_drawdown(self, risk: dict) -> tuple[bool, str]:
        dd = risk["drawdown_pct"] / 100
        if dd >= RISK.max_drawdown_pct:
            return False, f"Drawdown max atteint: {dd:.1%} (limite: {RISK.max_drawdown_pct:.1%})"
        if dd >= RISK.max_drawdown_pct * 0.8:
            alert_key = f"dd_warn_{int(dd*100)}"
            if alert_key not in self._alertes_envoyees:
                self._log(f"⚠️  Drawdown à {dd:.1%} — approche limite {RISK.max_drawdown_pct:.1%}", "WARN")
                self._alertes_envoyees.add(alert_key)
        return True, ""

    def _verifier_perte_journaliere(self, risk: dict) -> tuple[bool, str]:
        perte_j = risk["perte_journaliere"]
        cap     = risk["capital_actuel"]
        limite  = cap * RISK.max_perte_journaliere_pct
        if perte_j >= limite:
            return False, f"Perte journalière max: {perte_j:.2f}€ ≥ {limite:.2f}€"
        return True, ""

    def _verifier_capital_minimum(self, risk: dict) -> tuple[bool, str]:
        if risk["capital_actuel"] < 5.0:
            return False, f"Capital insuffisant: {risk['capital_actuel']:.2f}€ < 5€ minimum"
        return True, ""

    def _verifier_positions_stale(self) -> list:
        """Détecte les positions ouvertes depuis trop longtemps (>2 jours)."""
        import time
        positions = STATE.get_positions()
        stales = []
        for tid, pos in positions.items():
            age_h = (time.time() - pos.get("_ouverture_ts", time.time())) / 3600
            if age_h > 48:
                stales.append((tid, pos.get("ticker", "?"), age_h))
        return stales

    def _evaluer_positions_ouvertes(self):
        """Vérifie stop-loss et take-profit sur les positions ouvertes."""
        positions = STATE.get_positions()
        for trade_id, pos in list(positions.items()):
            ticker    = pos.get("ticker", "")
            prix_act  = STATE.get_prix(ticker)
            if prix_act is None:
                continue

            prix_ent  = pos.get("prix_entree", 0)
            stop_loss = pos.get("stop_loss", 0)
            take_prof = pos.get("take_profit", 0)
            sens      = pos.get("sens", "BUY")
            qty       = pos.get("quantite", 0)

            fermer = None
            if sens == "BUY":
                if stop_loss > 0 and prix_act <= stop_loss:
                    fermer = (prix_act, "STOP_LOSS")
                elif take_prof > 0 and prix_act >= take_prof:
                    fermer = (prix_act, "TAKE_PROFIT")
            else:
                if stop_loss > 0 and prix_act >= stop_loss:
                    fermer = (prix_act, "STOP_LOSS")
                elif take_prof > 0 and prix_act <= take_prof:
                    fermer = (prix_act, "TAKE_PROFIT")

            if fermer:
                prix_exit, raison = fermer
                pnl = (prix_exit - prix_ent) * qty * (1 if sens == "BUY" else -1)
                STATE.fermer_position(trade_id, pnl, raison)
                STATE.update_capital(STATE.get_risk_state()["capital_actuel"] + pnl)
                if pnl < 0:
                    STATE.add_perte_journaliere(abs(pnl))
                emoji = "✅" if raison == "TAKE_PROFIT" else "🛑"
                self._log(
                    f"{emoji} {raison}: {ticker} | PnL: {pnl:+.4f}€",
                    "OK" if pnl >= 0 else "WARN"
                )

    def executer(self):
        self._reset_journalier()
        risk = STATE.get_risk_state()

        # Évaluer stop-loss / take-profit
        self._evaluer_positions_ouvertes()

        # Vérifications de risque
        checks = [
            self._verifier_drawdown(risk),
            self._verifier_perte_journaliere(risk),
            self._verifier_capital_minimum(risk),
        ]

        bloquant = [(ok, msg) for ok, msg in checks if not ok]

        if bloquant:
            _, raison = bloquant[0]
            STATE.set_trading_autorise(False, raison)
            self._log(f"🚫 TRADING BLOQUÉ: {raison}", "ERR")
        else:
            STATE.set_trading_autorise(True)

        # Positions stales
        stales = self._verifier_positions_stale()
        for tid, ticker, age_h in stales:
            self._log(f"⚠️  Position {ticker} ouverte depuis {age_h:.0f}h", "WARN")

        # Log périodique
        if self._total_cycles % 4 == 0:
            self._log(
                f"Capital: {risk['capital_actuel']:.2f}€ | "
                f"Rendement: {risk['rendement_pct']:+.2f}% | "
                f"Drawdown: {risk['drawdown_pct']:.2f}% | "
                f"Positions: {risk['nb_positions']} | "
                f"Trading: {'✅' if risk['trading_autorise'] else '🚫'}"
            )


RISK_AGENT = RiskGuardianAgent()
