"""
AGENT 5 — TradeExecutor
Rôle : Valider et exécuter les ordres de trading.
Triple vérification avant chaque ordre : Halal ✓ Risque ✓ Signal ✓
Fréquence : toutes les 5 secondes (réactif).
"""
import sys, os, time
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agents.base_agent import BaseAgent
from orchestrator.state_bus import STATE
from config.config import RISK, TRADE, AGENTS
from broker.demo_broker import BrokerDemo
from core.halal_filter import est_halal
from risk.risk_manager import GestionnaireRisque


class TradeExecutorAgent(BaseAgent):
    """
    Exécuteur d'ordres avec triple validation.
    Chaque ordre passe par :
    1. Validation halal (re-vérification)
    2. Validation risque (capital, drawdown, positions)
    3. Validation signal (fraîcheur, confiance minimale)
    Si un seul check échoue → ordre annulé.
    """

    DELAI_SIGNAL_MAX  = 300   # Signal valable max 5 minutes
    COOLDOWN_TICKER   = 600   # 10 min entre 2 trades sur le même ticker

    def __init__(self):
        super().__init__("TradeExecutor", AGENTS.freq_trade_executor)
        self._broker = BrokerDemo(RISK.capital_initial)
        self._gm     = GestionnaireRisque(RISK.capital_initial)
        self._derniers_trades: dict = {}   # {ticker: timestamp}
        self._ordres_envoyes: set   = set()

    def _check_halal(self, ticker: str) -> tuple[bool, str]:
        """Re-vérifie la conformité halal au moment de l'ordre."""
        univers = STATE.get_univers_halal()
        if ticker not in univers:
            return False, f"{ticker} absent de l'univers halal validé"
        r = est_halal(ticker)
        if not r["halal"]:
            return False, f"Non-conforme: {r['raison']}"
        return True, "Halal ✓"

    def _check_risque(self, ticker: str, signal: dict) -> tuple[bool, str]:
        """Vérifie toutes les règles de risque."""
        risk = STATE.get_risk_state()

        if not risk["trading_autorise"]:
            return False, f"Trading bloqué: {risk['raison_blocage']}"

        if risk["capital_actuel"] < 5.0:
            return False, f"Capital insuffisant: {risk['capital_actuel']:.2f}€"

        if risk["nb_positions"] >= RISK.max_positions:
            return False, f"Max positions atteint: {risk['nb_positions']}/{RISK.max_positions}"

        # Vérifier si ce ticker est déjà en position
        positions = STATE.get_positions()
        for pos in positions.values():
            if pos.get("ticker") == ticker:
                return False, f"Position déjà ouverte sur {ticker}"

        # Cooldown entre trades sur le même ticker
        dernier = self._derniers_trades.get(ticker, 0)
        if time.time() - dernier < self.COOLDOWN_TICKER:
            restant = int(self.COOLDOWN_TICKER - (time.time() - dernier))
            return False, f"Cooldown {ticker}: encore {restant}s"

        return True, "Risque ✓"

    def _check_signal(self, ticker: str, signal: dict) -> tuple[bool, str]:
        """Vérifie la fraîcheur et la qualité du signal."""
        age = time.time() - signal.get("_ts", 0)
        if age > self.DELAI_SIGNAL_MAX:
            return False, f"Signal expiré ({age:.0f}s > {self.DELAI_SIGNAL_MAX}s)"

        if signal.get("action") == "ATTENDRE":
            return False, "Action ATTENDRE"

        force = signal.get("force", 0)
        if force < 0.3:
            return False, f"Force trop faible: {force:.0%}"

        confiance = signal.get("confiance", "faible")
        if confiance == "faible":
            return False, "Confiance faible"

        prix_ent = signal.get("prix_entree", 0)
        sl       = signal.get("stop_loss", 0)
        tp       = signal.get("take_profit", 0)

        if prix_ent <= 0 or sl <= 0 or tp <= 0:
            return False, f"Niveaux invalides (prix={prix_ent}, sl={sl}, tp={tp})"

        # Ratio R/R
        risque  = abs(prix_ent - sl)
        reward  = abs(tp - prix_ent)
        rr      = reward / risque if risque > 0 else 0
        if rr < RISK.ratio_rr_minimum:
            return False, f"Ratio R/R insuffisant: {rr:.1f} < {RISK.ratio_rr_minimum}"

        return True, f"Signal ✓ (force={force:.0%}, rr={rr:.1f})"

    def _calculer_taille(self, signal: dict, capital: float) -> tuple[float, float]:
        """Calcule la taille optimale de position."""
        prix    = signal["prix_entree"]
        sl      = signal["stop_loss"]
        force   = signal["force"]

        risque_euros = capital * RISK.risque_par_trade_pct
        risque_unite = abs(prix - sl)
        if risque_unite <= 0:
            return 0, 0

        kelly    = RISK.kelly_fraction + force * 0.25
        risque_j = risque_euros * kelly
        quantite = risque_j / risque_unite

        max_pos  = capital * RISK.max_pct_capital_par_pos
        valeur   = quantite * prix
        if valeur > max_pos:
            quantite = max_pos / prix
            valeur   = max_pos

        return round(quantite, 6), round(valeur, 2)

    def _executer_ordre(self, ticker: str, signal: dict):
        """Exécute l'ordre après triple validation."""
        risk     = STATE.get_risk_state()
        capital  = risk["capital_actuel"]
        sens     = "BUY" if signal["action"] == "ACHETER" else "SELL"
        prix_act = STATE.get_prix(ticker) or signal["prix_entree"]

        quantite, valeur = self._calculer_taille(signal, capital)
        if quantite <= 0 or valeur < 0.5:
            self._log(f"Taille position trop petite pour {ticker} ({valeur:.2f}€)", "WARN")
            return

        resultat = self._broker.passer_ordre_market(ticker, sens, quantite, prix_act)

        if resultat["succes"]:
            ordre = resultat["ordre"]
            trade_id = ordre["id"]

            # Enregistrer sur le bus d'état
            STATE.ouvrir_position(trade_id, {
                "ticker":       ticker,
                "sens":         sens,
                "prix_entree":  ordre["prix_execute"],
                "stop_loss":    signal["stop_loss"],
                "take_profit":  signal["take_profit"],
                "quantite":     quantite,
                "montant":      valeur,
                "signal_force": signal["force"],
                "signal_conf":  signal["confiance"],
            })
            STATE.update_capital(ordre["capital_apres"])
            self._derniers_trades[ticker] = time.time()

            emoji = "🟢" if sens == "BUY" else "🔴"
            self._log(
                f"{emoji} ORDRE EXÉCUTÉ: {sens} {ticker} | "
                f"Qty: {quantite:.6f} @ {prix_act:.4f} | "
                f"Montant: {valeur:.2f}€ | "
                f"SL: {signal['stop_loss']:.4f} | TP: {signal['take_profit']:.4f}",
                "TRADE"
            )
        else:
            self._log(f"Ordre rejeté ({ticker}): {resultat['raison']}", "WARN")

    def executer(self):
        signaux = STATE.get_all_signals()
        if not signaux:
            return

        # Filtrer et trier les signaux actionnables
        actionnables = []
        for ticker, signal in signaux.items():
            if signal.get("action") == "ATTENDRE":
                continue
            # Triple check
            ok_h, msg_h = self._check_halal(ticker)
            ok_r, msg_r = self._check_risque(ticker, signal)
            ok_s, msg_s = self._check_signal(ticker, signal)

            if ok_h and ok_r and ok_s:
                actionnables.append((ticker, signal))
            else:
                raisons = []
                if not ok_h: raisons.append(f"HALAL:{msg_h}")
                if not ok_r: raisons.append(f"RISQUE:{msg_r}")
                if not ok_s: raisons.append(f"SIGNAL:{msg_s}")

        # Exécuter le meilleur signal seulement (pour ce cycle)
        if actionnables:
            actionnables.sort(key=lambda x: x[1].get("score", 0), reverse=True)
            ticker, signal = actionnables[0]
            self._log(
                f"✅ Triple validation OK pour {ticker} — Exécution...",
                "OK"
            )
            self._executer_ordre(ticker, signal)

    def get_portefeuille(self, prix_actuels: dict = None) -> dict:
        return self._broker.get_portefeuille(prix_actuels)


EXECUTOR_AGENT = TradeExecutorAgent()
