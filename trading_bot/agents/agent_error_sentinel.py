"""
AGENT 7 — ErrorSentinel
Rôle : Surveiller la santé du système et auto-corriger les anomalies.
Détecte : agents morts, données corrompues, boucles d'erreurs, dérives.
Fréquence : toutes les 10 secondes.
"""
import sys, os, time, json
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agents.base_agent import BaseAgent
from orchestrator.state_bus import STATE
from config.config import AGENTS, PATHS


class ErrorSentinelAgent(BaseAgent):
    """
    Gardien de la santé système.
    Surveille tous les agents, détecte les anomalies, déclenche les alertes.
    """

    TIMEOUT_AGENT_SEC = 120      # Agent considéré mort si pas de heartbeat depuis 2 min
    MAX_ERREURS_AGENT = 20       # Seuil d'alerte par agent
    PRIX_DERIVE_MAX   = 0.50     # Alert si prix dévie de >50% (donnée corrompue)

    def __init__(self):
        super().__init__("ErrorSentinel", AGENTS.freq_error_sentinel)
        self._agents_surveilles: list = []
        self._alertes_actives: set = set()
        self._derniers_etats: dict = {}
        self._rapport_sante: dict = {}

    def enregistrer_agents(self, agents: list):
        """Enregistre les agents à surveiller."""
        self._agents_surveilles = agents
        self._log(f"Surveillance de {len(agents)} agents", "OK")

    def _verifier_heartbeats(self) -> list:
        """Détecte les agents silencieux depuis trop longtemps."""
        agents_status = STATE.get_agents_status()
        morts = []
        for agent in self._agents_surveilles:
            nom = getattr(agent, "nom", str(agent))
            status = agents_status.get(nom, {})
            dernier_ts = status.get("ts", 0)
            age = time.time() - dernier_ts

            if dernier_ts == 0:
                morts.append((nom, "Jamais démarré"))
            elif age > self.TIMEOUT_AGENT_SEC:
                morts.append((nom, f"Silencieux depuis {age:.0f}s"))

        return morts

    def _verifier_erreurs(self) -> list:
        """Détecte les agents avec trop d'erreurs."""
        counts = STATE.get_error_counts()
        surcharges = []
        for agent, n in counts.items():
            prev = self._derniers_etats.get(f"err_{agent}", 0)
            if n - prev > 5:   # >5 nouvelles erreurs depuis dernier check
                surcharges.append((agent, n, n - prev))
            self._derniers_etats[f"err_{agent}"] = n
        return surcharges

    def _verifier_coherence_donnees(self) -> list:
        """Vérifie que les prix sont cohérents (pas de données corrompues)."""
        from data.market_data import PRIX_REFERENCE
        anomalies = []
        market = STATE.get_all_market_data()

        for ticker, data in market.items():
            prix = data.get("prix", 0)
            ref  = PRIX_REFERENCE.get(ticker, 0)
            if ref > 0 and prix > 0:
                derive = abs(prix - ref) / ref
                if derive > self.PRIX_DERIVE_MAX:
                    anomalies.append((ticker, prix, ref, derive))
        return anomalies

    def _verifier_positions_orphelines(self) -> list:
        """Détecte les positions dans le bus sans ordre correspondant dans le broker."""
        positions_bus    = set(STATE.get_positions().keys())
        orphelines = []
        for pid in positions_bus:
            pos = STATE.get_positions().get(pid, {})
            age = time.time() - pos.get("_ouverture_ts", time.time())
            if age > 86400:   # >24h
                orphelines.append((pid, pos.get("ticker", "?"), age))
        return orphelines

    def _generer_rapport(self) -> dict:
        risk    = STATE.get_risk_state()
        agents  = STATE.get_agents_status()
        errors  = STATE.get_errors(10)

        nb_ok      = sum(1 for s in agents.values() if s.get("status") == "OK")
        nb_agents  = len(agents)
        nb_erreurs = sum(STATE.get_error_counts().values())

        sante = "CRITIQUE" if nb_ok < nb_agents * 0.5 else \
                "DEGRADEE"  if nb_ok < nb_agents else "NORMALE"

        rapport = {
            "sante_globale":    sante,
            "agents_ok":        f"{nb_ok}/{nb_agents}",
            "erreurs_totales":  nb_erreurs,
            "trading_autorise": risk.get("trading_autorise", False),
            "capital":          risk.get("capital_actuel", 0),
            "positions":        risk.get("nb_positions", 0),
            "timestamp":        datetime.now().isoformat(),
        }
        return rapport

    def executer(self):
        alertes = []

        # 1. Heartbeats
        morts = self._verifier_heartbeats()
        for nom, raison in morts:
            key = f"mort_{nom}"
            if key not in self._alertes_actives:
                self._log(f"💀 AGENT MORT: {nom} — {raison}", "ERR")
                STATE.log_error(self.nom, f"Agent mort: {nom} — {raison}", critique=True)
                self._alertes_actives.add(key)
                alertes.append(key)
        # Retirer les alertes résolues
        agents_ok = {s for s, d in STATE.get_agents_status().items()
                     if d.get("status") == "OK"}
        for nom in agents_ok:
            self._alertes_actives.discard(f"mort_{nom}")

        # 2. Erreurs en cascade
        surcharges = self._verifier_erreurs()
        for agent, total, nouvelles in surcharges:
            key = f"surge_{agent}"
            if key not in self._alertes_actives:
                self._log(f"🚨 SURGE ERREURS: {agent} +{nouvelles} erreurs (total: {total})", "ERR")
                STATE.log_error(self.nom, f"Surge erreurs {agent}: +{nouvelles}", critique=True)
                self._alertes_actives.add(key)

        # 3. Cohérence des données
        anomalies = self._verifier_coherence_donnees()
        for ticker, prix, ref, derive in anomalies:
            key = f"anomalie_{ticker}"
            if key not in self._alertes_actives:
                self._log(f"⚠️  DONNÉE SUSPECTE: {ticker} prix={prix:.2f} (ref={ref:.2f}, écart={derive:.0%})", "WARN")
                self._alertes_actives.add(key)

        # 4. Positions orphelines
        orphelines = self._verifier_positions_orphelines()
        for pid, ticker, age_s in orphelines:
            self._log(f"⚠️  POSITION ORPHELINE: {ticker} depuis {age_s/3600:.1f}h", "WARN")

        # Rapport de santé
        self._rapport_sante = self._generer_rapport()

        if self._total_cycles % 6 == 0:  # toutes les minutes
            s = self._rapport_sante
            emoji = {"NORMALE": "💚", "DEGRADEE": "🟡", "CRITIQUE": "🔴"}.get(s["sante_globale"], "❓")
            self._log(
                f"{emoji} Santé: {s['sante_globale']} | "
                f"Agents: {s['agents_ok']} | "
                f"Erreurs: {s['erreurs_totales']} | "
                f"Trading: {'✅' if s['trading_autorise'] else '🚫'}"
            )

        # Sauvegarde erreurs
        try:
            with open(PATHS.errors_file, "w") as f:
                json.dump({
                    "rapport":  self._rapport_sante,
                    "erreurs":  STATE.get_errors(50),
                    "counts":   STATE.get_error_counts(),
                    "alertes":  list(self._alertes_actives),
                }, f, indent=2, ensure_ascii=False)
        except Exception:
            pass


SENTINEL_AGENT = ErrorSentinelAgent()
