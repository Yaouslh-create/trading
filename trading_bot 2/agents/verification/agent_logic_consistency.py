"""
AGENT DE VÉRIFICATION 2 — LogicConsistencyChecker
Rôle : Vérifier la cohérence LOGIQUE entre tous les agents.
Re-simule chaque décision clé et valide son résultat attendu.
Fréquence : toutes les 15 minutes.
"""
import sys, os, math
from datetime import datetime
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from agents.base_agent import BaseAgent
from orchestrator.state_bus import STATE
from config.config import RISK, TRADE


class LogicConsistencyAgent(BaseAgent):
    """
    Rejoue les décisions critiques du système et vérifie leur cohérence.
    Teste : calcul du sizing, signaux, filtres halal, stop-loss.
    """

    def __init__(self):
        super().__init__("LogicConsistency", 900)  # 15 min
        self._tests_passes = 0
        self._tests_echoues = 0

    def _test(self, nom: str, condition: bool, attendu, obtenu) -> bool:
        if condition:
            self._tests_passes += 1
            return True
        else:
            self._tests_echoues += 1
            msg = f"TEST ÉCHOUÉ [{nom}]: attendu={attendu}, obtenu={obtenu}"
            self._log(msg, "ERR")
            STATE.log_error(self.nom, msg, critique=True)
            return False

    def _verifier_filtre_halal(self) -> int:
        """Re-vérifie que les tickers haram sont bien exclus."""
        from core.halal_filter import est_halal
        passes = 0

        # Tickers qui DOIVENT être haram
        haram_attendus = ["JPM", "BAC", "MO", "PM", "LVS", "WYNN", "BA", "LMT"]
        for t in haram_attendus:
            r = est_halal(t)
            ok = self._test(f"haram_{t}", not r["halal"], False, r["halal"])
            if ok: passes += 1

        # Tickers qui DOIVENT être halal
        halal_attendus = ["AAPL", "MSFT", "NVDA", "GC=F", "SI=F"]
        for t in halal_attendus:
            r = est_halal(t)
            ok = self._test(f"halal_{t}", r["halal"], True, r["halal"])
            if ok: passes += 1

        return passes

    def _verifier_calcul_sizing(self) -> int:
        """Vérifie le calcul de taille de position avec des valeurs connues."""
        from risk.risk_manager import GestionnaireRisque
        gm = GestionnaireRisque(100.0)
        passes = 0

        # Test 1 : risque max 1.5% sur capital 100€ → max 1.50€ risqué
        sizing = gm.calculer_taille_position("TEST", 100.0, 95.0, 0.5)
        risque_max_theorique = 100.0 * RISK.risque_par_trade_pct
        ok = self._test(
            "sizing_risque_max",
            sizing.risque_euros <= risque_max_theorique * 1.01,  # 1% tolérance
            f"<= {risque_max_theorique:.2f}€",
            f"{sizing.risque_euros:.2f}€"
        )
        if ok: passes += 1

        # Test 2 : capital insuffisant → refus
        gm2 = GestionnaireRisque(100.0)
        gm2.capital_actuel = 3.0  # Trop petit
        sizing2 = gm2.calculer_taille_position("TEST", 100.0, 95.0, 0.5)
        ok2 = self._test(
            "sizing_capital_insuffisant",
            not sizing2.autorise,
            "refusé",
            "autorisé" if sizing2.autorise else "refusé"
        )
        if ok2: passes += 1

        # Test 3 : stop-loss == prix → refus
        sizing3 = gm.calculer_taille_position("TEST", 100.0, 100.0, 0.5)
        ok3 = self._test(
            "sizing_sl_egal_prix",
            not sizing3.autorise,
            "refusé",
            "autorisé" if sizing3.autorise else "refusé"
        )
        if ok3: passes += 1

        # Test 4 : montant max 30% du capital
        sizing4 = gm.calculer_taille_position("TEST", 100.0, 50.0, 1.0)
        max_expected = 100.0 * RISK.max_pct_capital_par_pos
        ok4 = self._test(
            "sizing_plafond_30pct",
            sizing4.taille_position <= max_expected + 0.01,
            f"<= {max_expected:.2f}€",
            f"{sizing4.taille_position:.2f}€"
        )
        if ok4: passes += 1

        return passes

    def _verifier_indicateurs(self) -> int:
        """Vérifie que les indicateurs retournent des valeurs dans les plages attendues."""
        import pandas as pd
        from strategies.indicators import rsi, macd, bollinger, atr, calculer_tous_indicateurs
        from data.market_data import fetch_prix
        passes = 0

        # Données synthétiques déterministes
        np.random.seed(42)
        n = 100
        close = pd.Series(100 * np.cumprod(1 + np.random.normal(0, 0.01, n)))
        df = pd.DataFrame({
            "Open": close * 0.999,
            "High": close * 1.005,
            "Low":  close * 0.995,
            "Close": close,
            "Volume": np.ones(n) * 1e6
        })

        # RSI entre 0 et 100
        rsi_val = rsi(close)
        ok1 = self._test("rsi_plage", 0 <= float(rsi_val.iloc[-1]) <= 100, "0-100", float(rsi_val.iloc[-1]))
        if ok1: passes += 1

        # Bollinger : High > Mid > Low
        bb_h, bb_m, bb_l = bollinger(close)
        ok2 = self._test(
            "bollinger_ordre",
            float(bb_h.iloc[-1]) > float(bb_m.iloc[-1]) > float(bb_l.iloc[-1]),
            "H>M>L", f"{bb_h.iloc[-1]:.2f}>{bb_m.iloc[-1]:.2f}>{bb_l.iloc[-1]:.2f}"
        )
        if ok2: passes += 1

        # ATR positif
        atr_val = atr(df)
        ok3 = self._test("atr_positif", float(atr_val.iloc[-1]) > 0, "> 0", float(atr_val.iloc[-1]))
        if ok3: passes += 1

        # calculer_tous_indicateurs : résultat non vide
        ind = calculer_tous_indicateurs(df)
        ok4 = self._test("indicateurs_complets", len(ind) >= 10, ">= 10 clés", len(ind))
        if ok4: passes += 1

        # Signal : action doit être parmi les valeurs valides
        from strategies.indicators import generer_signal
        signal = generer_signal("TEST", df)
        ok5 = self._test(
            "signal_action_valide",
            signal.action in ["ACHETER", "VENDRE", "ATTENDRE"],
            "ACHETER/VENDRE/ATTENDRE",
            signal.action
        )
        if ok5: passes += 1

        # Force entre 0 et 1
        ok6 = self._test("signal_force_plage", 0.0 <= signal.force <= 1.0, "0-1", signal.force)
        if ok6: passes += 1

        # Stop-loss cohérent avec la direction
        if signal.action == "ACHETER" and signal.stop_loss > 0:
            ok7 = self._test(
                "sl_sous_prix_achat",
                signal.stop_loss < signal.prix_entree,
                f"< {signal.prix_entree:.2f}",
                signal.stop_loss
            )
            if ok7: passes += 1

        return passes

    def _verifier_broker_demo(self) -> int:
        """Vérifie que le broker démo calcule correctement PnL et capital."""
        from broker.demo_broker import BrokerDemo
        passes = 0

        broker = BrokerDemo(100.0)
        cap_init = broker.capital

        # Achat : capital doit baisser
        res = broker.passer_ordre_market("TEST", "BUY", 1.0, 10.0)
        ok1 = self._test("broker_achat_capital_baisse", broker.capital < cap_init, "< 100", broker.capital)
        if ok1: passes += 1

        # Vente : capital doit remonter
        if res["succes"]:
            cap_avant_vente = broker.capital
            broker.passer_ordre_market("TEST", "SELL", 1.0, 12.0)  # vendre à profit
            ok2 = self._test("broker_vente_profit", broker.capital > cap_avant_vente, f"> {cap_avant_vente:.2f}", broker.capital)
            if ok2: passes += 1

        # Vente sans position → refus
        res_ko = broker.passer_ordre_market("INEXISTANT", "SELL", 999.0, 10.0)
        ok3 = self._test("broker_vente_sans_pos", not res_ko["succes"], "refusé", "ok" if res_ko["succes"] else "refusé")
        if ok3: passes += 1

        return passes

    def _verifier_coherence_state_bus(self) -> int:
        """Vérifie l'intégrité du bus d'état partagé."""
        passes = 0

        # Capital actuel doit être un float positif
        risk = STATE.get_risk_state()
        ok1 = self._test("state_capital_positif", risk["capital_actuel"] > 0, "> 0", risk["capital_actuel"])
        if ok1: passes += 1

        # Drawdown entre 0 et 100%
        ok2 = self._test("state_drawdown_plage", 0 <= risk["drawdown_pct"] <= 100, "0-100", risk["drawdown_pct"])
        if ok2: passes += 1

        # Univers halal non vide
        univers = STATE.get_univers_halal()
        ok3 = self._test("state_univers_non_vide", len(univers) > 0, "> 0 actifs", len(univers))
        if ok3: passes += 1

        # trading_autorise est un bool
        ok4 = self._test("state_trading_bool", isinstance(risk["trading_autorise"], bool), "bool", type(risk["trading_autorise"]).__name__)
        if ok4: passes += 1

        return passes

    def executer(self):
        self._log("=== VÉRIFICATION LOGIQUE COMPLÈTE DU SYSTÈME ===")
        self._tests_passes  = 0
        self._tests_echoues = 0

        suite = [
            ("Filtre Halal",       self._verifier_filtre_halal),
            ("Calcul Sizing",      self._verifier_calcul_sizing),
            ("Indicateurs",        self._verifier_indicateurs),
            ("Broker Démo",        self._verifier_broker_demo),
            ("Bus d'état",         self._verifier_coherence_state_bus),
        ]

        for nom_suite, fn in suite:
            try:
                n = fn()
                self._log(f"  ✅ {nom_suite}: {n} tests OK")
            except Exception as e:
                self._tests_echoues += 1
                self._log(f"  ❌ {nom_suite}: EXCEPTION — {e}", "ERR")
                STATE.log_error(self.nom, f"Suite {nom_suite}: {e}", critique=True)

        total = self._tests_passes + self._tests_echoues
        taux  = self._tests_passes / total * 100 if total > 0 else 0

        emoji = "✅" if self._tests_echoues == 0 else ("⚠️" if taux > 80 else "🚨")
        self._log(
            f"\n  {emoji} Résultat: {self._tests_passes}/{total} tests passés ({taux:.0f}%) "
            f"| Échecs: {self._tests_echoues}",
            "OK" if self._tests_echoues == 0 else "ERR"
        )
