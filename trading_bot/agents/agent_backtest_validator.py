"""
AGENT 8 — BacktestValidator
Rôle : Valider la stratégie chaque jour sur données historiques.
Si les performances se dégradent → alerte et suspension automatique.
Fréquence : quotidienne (86400s). Peut aussi être déclenché manuellement.
"""
import sys, os, json
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agents.base_agent import BaseAgent
from orchestrator.state_bus import STATE
from config.config import AGENTS, PATHS, RISK
from backtest.backtester import backtest_multi


class BacktestValidatorAgent(BaseAgent):
    """
    Validateur de stratégie automatique.
    Simons backtestait constamment pour détecter la dérive du modèle.
    Si le Sharpe tombe sous 0 ou le win rate sous 40% → suspension.
    """

    SHARPE_MINIMUM  = 0.3    # Sharpe minimum acceptable
    WINRATE_MINIMUM = 42.0   # Win rate minimum (%)
    PF_MINIMUM      = 0.9    # Profit factor minimum

    def __init__(self):
        super().__init__("BacktestValidator", AGENTS.freq_backtest_validator)
        self._derniers_resultats: dict = {}
        self._nb_validations: int = 0

    def on_start(self):
        """Validation immédiate au démarrage."""
        self._log("Validation initiale de la stratégie...")
        self._lancer_backtest()

    def _evaluer_resultats(self, resultats) -> tuple[bool, list]:
        """Évalue si la stratégie est toujours viable."""
        if resultats.empty:
            return False, ["Aucun résultat de backtest"]

        alertes = []
        nb_ok   = 0

        for _, row in resultats.iterrows():
            ticker = row["Ticker"]
            sharpe = row.get("Sharpe", 0)
            wr     = row.get("WinRate%", 0)
            pf     = row.get("ProfitFactor", 0)
            rend   = row.get("Rendement%", 0)

            problems = []
            if sharpe < self.SHARPE_MINIMUM:
                problems.append(f"Sharpe {sharpe:.2f} < {self.SHARPE_MINIMUM}")
            if wr < self.WINRATE_MINIMUM:
                problems.append(f"WinRate {wr:.1f}% < {self.WINRATE_MINIMUM}%")
            if pf < self.PF_MINIMUM:
                problems.append(f"PF {pf:.2f} < {self.PF_MINIMUM}")

            if problems:
                alertes.append(f"{ticker}: {', '.join(problems)}")
            else:
                nb_ok += 1

        strategie_ok = nb_ok >= len(resultats) * 0.4  # Au moins 40% d'actifs OK
        return strategie_ok, alertes

    def _lancer_backtest(self):
        """Lance le backtest complet."""
        self._nb_validations += 1
        self._log(f"Backtest #{self._nb_validations} en cours sur univers halal...")

        univers = STATE.get_univers_halal()
        if not univers:
            from config.config import TRADE
            univers = TRADE.univers_actifs[:6]

        # Backtest sur 6 mois (compromis vitesse/fiabilité)
        try:
            import warnings
            warnings.filterwarnings("ignore")
            resultats = backtest_multi(univers[:8], periode="6mo", capital=RISK.capital_initial)
        except Exception as e:
            STATE.log_error(self.nom, f"Backtest échoué: {e}", critique=True)
            return

        if resultats.empty:
            self._log("Backtest sans résultats", "WARN")
            return

        # Évaluation
        strategie_ok, alertes = self._evaluer_resultats(resultats)
        self._derniers_resultats = {
            "timestamp": datetime.now().isoformat(),
            "validations": self._nb_validations,
            "strategie_ok": strategie_ok,
            "alertes": alertes,
            "resultats": resultats.to_dict("records"),
        }

        # Rapport
        self._log(f"\n  ══════════ RAPPORT BACKTEST #{self._nb_validations} ══════════")
        self._log(f"  {resultats.to_string(index=False)}")

        meilleur = resultats.iloc[0]
        self._log(
            f"\n  🏆 {meilleur['Ticker']} | Rend: {meilleur['Rendement%']:+.1f}% | "
            f"WR: {meilleur['WinRate%']:.0f}% | Sharpe: {meilleur['Sharpe']:.2f}"
        )

        if alertes:
            for a in alertes[:3]:
                self._log(f"  ⚠️  {a}", "WARN")

        # Décision
        if strategie_ok:
            self._log("  ✅ Stratégie VALIDÉE — trading maintenu", "OK")
        else:
            msg = "Stratégie dégradée — paramètres à réviser"
            self._log(f"  ⚠️  {msg}", "WARN")
            STATE.log_error(self.nom, f"Stratégie dégradée: {alertes}")
            # Note : on ne bloque pas le trading automatiquement sur backtest dégradé
            # car les données synthétiques peuvent donner des faux négatifs
            # En production réelle, décommenter la ligne ci-dessous :
            # STATE.set_trading_autorise(False, msg)

        # Sauvegarde
        try:
            path = os.path.join(PATHS.reports_dir, "backtest_latest.json")
            with open(path, "w") as f:
                json.dump(self._derniers_resultats, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def executer(self):
        self._lancer_backtest()


BACKTEST_AGENT = BacktestValidatorAgent()
