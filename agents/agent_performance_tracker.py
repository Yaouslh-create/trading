"""
AGENT 6 — PerformanceTracker
Rôle : Suivre toutes les métriques de performance en temps réel.
Calcule : Sharpe, Drawdown, Win Rate, Profit Factor, PnL cumulé.
Sauvegarde automatique. Fréquence : 5 minutes.
"""
import sys, os, json, time
import numpy as np
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agents.base_agent import BaseAgent
from orchestrator.state_bus import STATE
from config.config import AGENTS, PATHS, RISK


class PerformanceTrackerAgent(BaseAgent):

    def __init__(self):
        super().__init__("PerformanceTracker", AGENTS.freq_performance_tracker)
        self._courbe_capital: list = [RISK.capital_initial]
        self._snapshots: list = []

    def on_start(self):
        """Charge l'historique de performance si disponible."""
        try:
            if os.path.exists(PATHS.perf_file):
                with open(PATHS.perf_file) as f:
                    data = json.load(f)
                    self._courbe_capital = data.get("courbe_capital", [RISK.capital_initial])
                    self._log(f"Historique chargé: {len(self._courbe_capital)} points", "OK")
        except Exception:
            pass

    def _calculer_metriques(self, trades: list, capital_actuel: float) -> dict:
        """Calcule toutes les métriques style hedge fund."""
        if not trades:
            return {
                "nb_trades": 0, "win_rate": 0, "profit_factor": 0,
                "sharpe": 0, "sortino": 0, "calmar": 0,
                "gain_moyen": 0, "perte_moyenne": 0, "pnl_total": 0,
                "rendement_pct": round((capital_actuel - RISK.capital_initial) / RISK.capital_initial * 100, 2),
                "max_drawdown": 0, "max_serie_perdante": 0, "esperance": 0,
            }

        pnls     = [t.get("pnl", 0) for t in trades]
        gagnants = [p for p in pnls if p > 0]
        perdants = [p for p in pnls if p <= 0]

        win_rate = len(gagnants) / len(pnls) * 100
        sum_g    = sum(gagnants) if gagnants else 0
        sum_p    = abs(sum(perdants)) if perdants else 1e-9
        pf       = sum_g / sum_p

        # Série perdante max
        max_serie = 0
        serie_act = 0
        for p in pnls:
            if p <= 0:
                serie_act += 1
                max_serie = max(max_serie, serie_act)
            else:
                serie_act = 0

        # Sharpe annualisé
        courbe = self._courbe_capital
        if len(courbe) > 2:
            rend_j  = np.diff(courbe) / np.array(courbe[:-1])
            sharpe  = (np.mean(rend_j) / np.std(rend_j) * np.sqrt(252)) if np.std(rend_j) > 0 else 0
            # Sortino (ne pénalise que les baisses)
            neg     = rend_j[rend_j < 0]
            sortino = (np.mean(rend_j) / np.std(neg) * np.sqrt(252)) if len(neg) > 0 and np.std(neg) > 0 else 0
        else:
            sharpe = sortino = 0

        # Max drawdown
        if len(courbe) > 1:
            pic = courbe[0]
            dd  = 0
            for c in courbe:
                if c > pic:
                    pic = c
                dd = max(dd, (pic - c) / pic * 100)
        else:
            dd = 0

        # Calmar ratio (rendement / drawdown max)
        rendement = (capital_actuel - RISK.capital_initial) / RISK.capital_initial * 100
        calmar    = rendement / dd if dd > 0 else 0

        return {
            "nb_trades":          len(pnls),
            "win_rate":           round(win_rate, 1),
            "profit_factor":      round(pf, 2),
            "sharpe":             round(float(sharpe), 2),
            "sortino":            round(float(sortino), 2),
            "calmar":             round(float(calmar), 2),
            "gain_moyen":         round(np.mean(gagnants), 4) if gagnants else 0,
            "perte_moyenne":      round(np.mean(perdants), 4) if perdants else 0,
            "pnl_total":          round(sum(pnls), 4),
            "rendement_pct":      round(rendement, 2),
            "max_drawdown":       round(dd, 2),
            "max_serie_perdante": max_serie,
            "esperance":          round(np.mean(pnls), 4),
        }

    def _afficher_rapport(self, m: dict, risk: dict):
        """Affiche un rapport de performance clair."""
        rend_col = "\033[32m" if m["rendement_pct"] >= 0 else "\033[31m"
        reset    = "\033[0m"
        self._log(
            f"\n"
            f"  ══════════ RAPPORT PERFORMANCE ══════════\n"
            f"  Capital:      {risk['capital_actuel']:.2f}€  (départ: {RISK.capital_initial:.2f}€)\n"
            f"  Rendement:    {rend_col}{m['rendement_pct']:+.2f}%{reset}\n"
            f"  Trades:       {m['nb_trades']} | Win Rate: {m['win_rate']:.1f}%\n"
            f"  Profit Factor:{m['profit_factor']:.2f}  | Sharpe: {m['sharpe']:.2f}\n"
            f"  Sortino:      {m['sortino']:.2f}     | Calmar: {m['calmar']:.2f}\n"
            f"  Max Drawdown: {m['max_drawdown']:.2f}%\n"
            f"  Espérance:    {m['esperance']:+.4f}€/trade\n"
            f"  Positions:    {risk['nb_positions']} ouvertes\n"
            f"  ══════════════════════════════════════════"
        )

    def executer(self):
        risk   = STATE.get_risk_state()
        trades = STATE.get_trades_history()

        # Mise à jour courbe de capital
        self._courbe_capital.append(risk["capital_actuel"])
        if len(self._courbe_capital) > 10000:
            self._courbe_capital = self._courbe_capital[-5000:]

        metriques = self._calculer_metriques(trades, risk["capital_actuel"])

        # Snapshot horodaté
        snapshot = {**metriques, **risk, "timestamp": datetime.now().isoformat()}
        self._snapshots.append(snapshot)

        # Sauvegarde
        try:
            with open(PATHS.perf_file, "w") as f:
                json.dump({
                    "metriques_actuelles": metriques,
                    "courbe_capital":      self._courbe_capital[-500:],
                    "snapshots":           self._snapshots[-100:],
                    "derniere_maj":        datetime.now().isoformat(),
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            STATE.log_error(self.nom, f"Sauvegarde perf: {e}")

        self._afficher_rapport(metriques, risk)


PERF_AGENT = PerformanceTrackerAgent()
