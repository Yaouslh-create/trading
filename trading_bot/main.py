"""
ORCHESTRATEUR PRINCIPAL — Lance et coordonne les 8 agents
Inspiré de l'architecture de Renaissance Technologies :
Chaque module est indépendant, testable, remplaçable.
Zéro point de défaillance unique.
"""
import sys, os, time, signal, json
from datetime import datetime
sys.path.insert(0, os.path.dirname(__file__))

# ── Import de tous les agents ──────────────────────────────────────────────
from orchestrator.state_bus import STATE
from config.config import RISK, TRADE, PATHS

from agents.agent_data_collector     import DataCollectorAgent
from agents.agent_halal_screener     import HalalScreenerAgent
from agents.agent_signal_generator   import SignalGeneratorAgent
from agents.agent_risk_guardian      import RiskGuardianAgent
from agents.agent_trade_executor     import TradeExecutorAgent
from agents.agent_performance_tracker import PerformanceTrackerAgent
from agents.agent_error_sentinel     import ErrorSentinelAgent
from agents.agent_backtest_validator  import BacktestValidatorAgent


BANNER = """
\033[32m╔══════════════════════════════════════════════════════════════════╗
║       SYSTÈME MULTI-AGENTS DE TRADING HALAL — MÉTHODE SIMONS      ║
║  8 Agents autonomes | Capital: {cap}€ | Mode: {mode}              ║
╠══════════════════════════════════════════════════════════════════╣
║  Agent 1: DataCollector      — Données marché temps réel          ║
║  Agent 2: HalalScreener      — Conformité charia permanente        ║
║  Agent 3: SignalGenerator    — Analyse multi-indicateurs           ║
║  Agent 4: RiskGuardian       — Surveillance risque (veto absolu)   ║
║  Agent 5: TradeExecutor      — Exécution triple-validée            ║
║  Agent 6: PerformanceTracker — Métriques Sharpe/Sortino/Calmar     ║
║  Agent 7: ErrorSentinel      — Santé système & auto-correction     ║
║  Agent 8: BacktestValidator  — Validation stratégie quotidienne    ║
╚══════════════════════════════════════════════════════════════════╝\033[0m
""".format(cap=RISK.capital_initial, mode=TRADE.mode)


class Orchestrateur:

    ORDRE_DEMARRAGE = [
        # (Agent, délai avant démarrage en secondes)
        ("HalalScreener",      0),    # En premier : définit l'univers
        ("DataCollector",      2),    # Données dès que l'univers est prêt
        ("RiskGuardian",       4),    # Risque avant tout trade
        ("SignalGenerator",    6),    # Signaux après données
        ("TradeExecutor",      8),    # Exécution après signaux + risque
        ("PerformanceTracker", 10),   # Performance en parallèle
        ("ErrorSentinel",      12),   # Surveillance après démarrage complet
        ("BacktestValidator",  15),   # Validation en dernier (plus lent)
    ]

    def __init__(self):
        self._agents: dict = {}
        self._running = False
        self._start_time = None

        # Capturer Ctrl+C pour arrêt propre
        signal.signal(signal.SIGINT,  self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, sig, frame):
        print("\n\033[33m  [ORCHESTRATEUR] Signal reçu — arrêt propre en cours...\033[0m")
        self.arreter()

    def _creer_agents(self):
        """Instancie tous les agents."""
        self._agents = {
            "HalalScreener":     HalalScreenerAgent(),
            "DataCollector":     DataCollectorAgent(),
            "RiskGuardian":      RiskGuardianAgent(),
            "SignalGenerator":   SignalGeneratorAgent(),
            "TradeExecutor":     TradeExecutorAgent(),
            "PerformanceTracker":PerformanceTrackerAgent(),
            "ErrorSentinel":     ErrorSentinelAgent(),
            "BacktestValidator": BacktestValidatorAgent(),
        }

        # Enregistrer les agents dans le sentinel
        sentinel = self._agents["ErrorSentinel"]
        sentinel.enregistrer_agents(list(self._agents.values()))

        # S'abonner aux événements critiques
        STATE.subscribe("critical_error",    self._on_erreur_critique)
        STATE.subscribe("risk_status_changed", self._on_risque_change)
        STATE.subscribe("new_signal",        self._on_nouveau_signal)

    def _on_erreur_critique(self, data: dict):
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"  \033[31m[{ts}] 🚨 ERREUR CRITIQUE: {data.get('agent','?')} — {data.get('erreur','')[:80]}\033[0m")

    def _on_risque_change(self, data: dict):
        ts    = datetime.now().strftime("%H:%M:%S")
        emoji = "✅" if data.get("autorise") else "🚫"
        print(f"  \033[33m[{ts}] {emoji} RISQUE: {data.get('raison','')}\033[0m")

    def _on_nouveau_signal(self, data: dict):
        action = data.get("action", "")
        if action and action != "ATTENDRE":
            ts    = datetime.now().strftime("%H:%M:%S")
            emoji = "🟢" if action == "ACHETER" else "🔴"
            print(f"  \033[35m[{ts}] {emoji} SIGNAL: {data.get('ticker','?')} → {action}\033[0m")

    def demarrer(self, duree_max: int = None):
        """Démarre tous les agents dans l'ordre optimal."""
        print(BANNER)
        self._creer_agents()
        self._running  = True
        self._start_time = datetime.now()

        print(f"  \033[36mDémarrage séquentiel des agents...\033[0m\n")

        # Démarrage en cascade avec délais
        for nom, delai in self.ORDRE_DEMARRAGE:
            if delai > 0:
                time.sleep(delai)
            agent = self._agents[nom]
            agent.start()
            print(f"  \033[32m✓ {nom} démarré\033[0m")

        print(f"\n  \033[32m✅ Tous les agents actifs — Système opérationnel\033[0m\n")

        try:
            debut = time.time()
            while self._running:
                if duree_max and (time.time() - debut) >= duree_max:
                    print(f"\n  [ORCHESTRATEUR] Durée max atteinte ({duree_max}s)")
                    break

                # Affichage périodique (toutes les 60s)
                if int(time.time()) % 60 == 0:
                    self._afficher_tableau_bord()
                    time.sleep(1)

                time.sleep(0.5)

        finally:
            self.arreter()

    def arreter(self):
        """Arrêt propre de tous les agents dans l'ordre inverse."""
        if not self._running:
            return
        self._running = False
        print("\n  \033[33mArrêt des agents...\033[0m")

        for nom, _ in reversed(self.ORDRE_DEMARRAGE):
            agent = self._agents.get(nom)
            if agent:
                agent.stop()
                try:
                    agent.join(timeout=5)
                except RuntimeError:
                    pass
                print(f"  ✓ {nom} arrêté")

        STATE.sauvegarder()
        self._generer_rapport_final()
        print("\n  \033[32m✅ Système arrêté proprement. Données sauvegardées.\033[0m\n")

    def _afficher_tableau_bord(self):
        """Tableau de bord compact en console."""
        risk    = STATE.get_risk_state()
        agents  = STATE.get_agents_status()
        signaux = {t: s for t, s in STATE.get_all_signals().items()
                   if s.get("action") != "ATTENDRE"}

        runtime = (datetime.now() - self._start_time).seconds // 60 if self._start_time else 0
        agents_ok = sum(1 for s in agents.values() if s.get("status") == "OK")

        print(f"""
  \033[36m══════════════════════════════════════════════════════════
  📊 TABLEAU DE BORD | Runtime: {runtime}min
  Capital: {risk['capital_actuel']:.2f}€ | Rend: {risk['rendement_pct']:+.2f}% | DD: {risk['drawdown_pct']:.2f}%
  Positions: {risk['nb_positions']} | Trading: {'✅' if risk['trading_autorise'] else '🚫 BLOQUÉ'}
  Agents OK: {agents_ok}/{len(agents)} | Signaux actifs: {len(signaux)}
  ══════════════════════════════════════════════════════════\033[0m""")

    def _generer_rapport_final(self):
        """Génère un rapport JSON de session."""
        risk   = STATE.get_risk_state()
        trades = STATE.get_trades_history()
        errors = STATE.get_error_counts()
        runtime = (datetime.now() - self._start_time).total_seconds() if self._start_time else 0

        rapport = {
            "session": {
                "debut":   self._start_time.isoformat() if self._start_time else "",
                "fin":     datetime.now().isoformat(),
                "duree_s": round(runtime, 0),
            },
            "performance": {
                "capital_initial": RISK.capital_initial,
                "capital_final":   risk["capital_actuel"],
                "rendement_pct":   risk["rendement_pct"],
                "nb_trades":       len(trades),
                "drawdown_max":    risk["drawdown_pct"],
            },
            "systeme": {
                "erreurs_par_agent": errors,
                "agents": STATE.get_agents_status(),
            },
        }

        try:
            path = os.path.join(PATHS.reports_dir, f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            with open(path, "w") as f:
                json.dump(rapport, f, indent=2, ensure_ascii=False)
            print(f"  Rapport session: {path}")
        except Exception:
            pass


def main():
    """Point d'entrée principal."""
    import argparse
    parser = argparse.ArgumentParser(description="Système multi-agents trading halal")
    parser.add_argument("--duree",  type=int, default=None, help="Durée max en secondes (None = infini)")
    parser.add_argument("--mode",   type=str, default="DEMO", choices=["DEMO","REEL"])
    args = parser.parse_args()

    from config.config import TRADE
    TRADE.mode = args.mode

    orchester = Orchestrateur()
    orchester.demarrer(duree_max=args.duree)


if __name__ == "__main__":
    main()
