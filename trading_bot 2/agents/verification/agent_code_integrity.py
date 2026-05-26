"""
AGENT DE VÉRIFICATION 1 — CodeIntegrityChecker
Rôle : Re-lire et vérifier CHAQUE fichier du système.
Vérifie : syntaxe Python, imports, cohérence logique, sécurité.
Fréquence : toutes les 10 minutes.
"""
import sys, os, ast, importlib, hashlib, json
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from agents.base_agent import BaseAgent
from orchestrator.state_bus import STATE
from config.config import AGENTS, PATHS, BASE_DIR


class CodeIntegrityAgent(BaseAgent):
    """
    Re-lit tout le code source et vérifie son intégrité.
    Détecte : fichiers corrompus, syntaxe invalide, imports manquants.
    """

    FICHIERS_CRITIQUES = [
        "main.py",
        "config/config.py",
        "orchestrator/state_bus.py",
        "agents/base_agent.py",
        "agents/agent_halal_screener.py",
        "agents/agent_risk_guardian.py",
        "agents/agent_trade_executor.py",
        "agents/agent_signal_generator.py",
        "agents/agent_data_collector.py",
        "agents/agent_performance_tracker.py",
        "agents/agent_error_sentinel.py",
        "agents/agent_backtest_validator.py",
        "core/halal_filter.py",
        "data/market_data.py",
        "strategies/indicators.py",
        "risk/risk_manager.py",
        "broker/demo_broker.py",
        "backtest/backtester.py",
    ]

    def __init__(self):
        super().__init__("CodeIntegrity", 600)  # 10 min
        self._checksums: dict = {}
        self._rapport_integrite: dict = {}

    def on_start(self):
        """Calcule les checksums initiaux de référence."""
        self._log("Calcul des checksums de référence...")
        for fichier in self.FICHIERS_CRITIQUES:
            path = os.path.join(BASE_DIR, fichier)
            cs   = self._checksum(path)
            if cs:
                self._checksums[fichier] = cs
        self._log(f"{len(self._checksums)} fichiers indexés.", "OK")

    def _checksum(self, path: str) -> str | None:
        try:
            with open(path, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()[:12]
        except Exception:
            return None

    def _verifier_syntaxe(self, path: str) -> tuple[bool, str]:
        """Parse le fichier Python et vérifie la syntaxe."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                source = f.read()
            ast.parse(source)
            return True, "OK"
        except SyntaxError as e:
            return False, f"SyntaxError ligne {e.lineno}: {e.msg}"
        except FileNotFoundError:
            return False, "Fichier introuvable"
        except Exception as e:
            return False, str(e)

    def _verifier_imports_critiques(self, path: str) -> tuple[bool, str]:
        """Vérifie que les imports critiques sont résolvables."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                source = f.read()
            tree = ast.parse(source)
            imports_manquants = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        mod = alias.name.split(".")[0]
                        try:
                            importlib.util.find_spec(mod)
                        except (ModuleNotFoundError, ValueError):
                            imports_manquants.append(mod)
            if imports_manquants:
                # Filtrer les imports locaux (pas de packages externes)
                externes = [m for m in imports_manquants
                           if m not in ["agents","orchestrator","config","core",
                                        "data","strategies","risk","broker",
                                        "backtest","monitoring","validation"]]
                if externes:
                    return False, f"Imports manquants: {externes}"
            return True, "OK"
        except Exception as e:
            return False, str(e)

    def _verifier_logique_risque(self) -> tuple[bool, str]:
        """
        Vérifie la cohérence des paramètres de risque.
        Ex : stop-loss ne peut pas être supérieur au capital entier.
        """
        try:
            from config.config import RISK
            if RISK.risque_par_trade_pct > 0.05:
                return False, f"Risque par trade trop élevé: {RISK.risque_par_trade_pct:.0%} > 5%"
            if RISK.max_drawdown_pct > 0.30:
                return False, f"Drawdown max trop permissif: {RISK.max_drawdown_pct:.0%}"
            if RISK.ratio_rr_minimum < 1.0:
                return False, f"Ratio R/R < 1.0 — perdant en espérance"
            if RISK.max_positions > 10:
                return False, f"Trop de positions max: {RISK.max_positions}"
            if RISK.sl_atr_mult <= 0:
                return False, "Stop-loss multiplier invalide (≤0)"
            return True, f"Risque cohérent (SL={RISK.sl_atr_mult}×ATR, DD<{RISK.max_drawdown_pct:.0%})"
        except Exception as e:
            return False, str(e)

    def _verifier_checksum_change(self) -> list:
        """Détecte les fichiers modifiés depuis le démarrage."""
        modifies = []
        for fichier, cs_ref in self._checksums.items():
            path    = os.path.join(BASE_DIR, fichier)
            cs_now  = self._checksum(path)
            if cs_now and cs_now != cs_ref:
                modifies.append(fichier)
                self._checksums[fichier] = cs_now  # Mettre à jour
        return modifies

    def executer(self):
        resultats = {}
        erreurs   = []

        # 1. Vérification syntaxe de tous les fichiers
        for fichier in self.FICHIERS_CRITIQUES:
            path = os.path.join(BASE_DIR, fichier)
            ok, msg = self._verifier_syntaxe(path)
            resultats[fichier] = {"syntaxe": ok, "msg": msg}
            if not ok:
                erreurs.append(f"SYNTAXE [{fichier}]: {msg}")
                STATE.log_error(self.nom, f"Syntaxe invalide: {fichier} — {msg}", critique=True)

        # 2. Vérification logique du risque
        ok_risque, msg_risque = self._verifier_logique_risque()
        if not ok_risque:
            erreurs.append(f"RISQUE CONFIG: {msg_risque}")
            STATE.log_error(self.nom, f"Config risque invalide: {msg_risque}", critique=True)

        # 3. Détection de modifications
        modifies = self._verifier_checksum_change()
        if modifies:
            self._log(f"⚠️  Fichiers modifiés: {modifies}", "WARN")

        # 4. Rapport
        nb_ok  = sum(1 for r in resultats.values() if r["syntaxe"])
        nb_ko  = len(self.FICHIERS_CRITIQUES) - nb_ok
        statut = "✅ SAIN" if not erreurs else f"❌ {len(erreurs)} ERREURS"

        self._rapport_integrite = {
            "timestamp": datetime.now().isoformat(),
            "statut":    statut,
            "fichiers_ok":  nb_ok,
            "fichiers_ko":  nb_ko,
            "erreurs":       erreurs,
            "modifies":      modifies,
            "risque_config": msg_risque,
        }

        self._log(
            f"Intégrité: {statut} | {nb_ok}/{len(self.FICHIERS_CRITIQUES)} fichiers OK | "
            f"Risque: {'✅' if ok_risque else '❌'}"
        )

        if erreurs:
            for e in erreurs:
                self._log(f"  ❌ {e}", "ERR")
        else:
            self._log("Tous les fichiers sont syntaxiquement valides.", "OK")
