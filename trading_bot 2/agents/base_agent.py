"""
Classe de base pour tous les agents.
Chaque agent : thread autonome, auto-restart, heartbeat, gestion d'erreurs.
"""
import threading
import time
import traceback
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from orchestrator.state_bus import STATE
from datetime import datetime


class BaseAgent(threading.Thread):
    """
    Agent autonome avec :
    - Exécution cyclique configurable
    - Auto-restart sur erreur (max 5 tentatives)
    - Heartbeat vers le bus d'état
    - Circuit-breaker si trop d'erreurs consécutives
    """

    MAX_ERREURS_CONSECUTIVES = 5
    DELAI_RESTART_BASE       = 2   # secondes (double à chaque échec)

    def __init__(self, nom: str, intervalle_sec: float):
        super().__init__(name=nom, daemon=True)
        self.nom              = nom
        self.intervalle       = intervalle_sec
        self._stop_event      = threading.Event()
        self._pause_event     = threading.Event()
        self._erreurs_consec  = 0
        self._total_cycles    = 0
        self._total_erreurs   = 0
        self._dernier_cycle   = None
        self._actif           = False
        self._log(f"Agent initialisé (intervalle: {intervalle_sec}s)")

    def _log(self, msg: str, niveau: str = "INFO"):
        ts = datetime.now().strftime("%H:%M:%S")
        niveaux = {"INFO": "\033[36m", "OK": "\033[32m", "WARN": "\033[33m",
                   "ERR": "\033[31m", "TRADE": "\033[35m"}
        c = niveaux.get(niveau, "")
        print(f"  \033[37m[{ts}]\033[0m {c}[{self.nom}]\033[0m {msg}")

    def executer(self):
        """À implémenter dans chaque agent — logique métier."""
        raise NotImplementedError

    def on_start(self):
        """Optionnel — initialisation avant le premier cycle."""
        pass

    def on_stop(self):
        """Optionnel — nettoyage avant l'arrêt."""
        pass

    def run(self):
        self._actif = True
        STATE.heartbeat(self.nom, "STARTING")
        self._log("Démarrage...", "OK")

        try:
            self.on_start()
        except Exception as e:
            self._log(f"Erreur on_start: {e}", "ERR")

        while not self._stop_event.is_set():
            # Pause si demandée
            if self._pause_event.is_set():
                STATE.heartbeat(self.nom, "PAUSED")
                time.sleep(1)
                continue

            # Circuit-breaker
            if self._erreurs_consec >= self.MAX_ERREURS_CONSECUTIVES:
                self._log(
                    f"Circuit-breaker activé ({self._erreurs_consec} erreurs consécutives). "
                    f"Pause 60s.", "ERR"
                )
                STATE.heartbeat(self.nom, "CIRCUIT_BROKEN",
                                f"{self._erreurs_consec} erreurs consécutives")
                STATE.log_error(self.nom,
                                f"Circuit-breaker: {self._erreurs_consec} erreurs consécutives",
                                critique=True)
                time.sleep(60)
                self._erreurs_consec = 0
                continue

            debut = time.time()
            try:
                self.executer()
                self._erreurs_consec = 0
                self._total_cycles  += 1
                self._dernier_cycle  = datetime.now().isoformat()
                STATE.heartbeat(self.nom, "OK",
                                f"Cycle {self._total_cycles} — {datetime.now().strftime('%H:%M:%S')}")

            except Exception as e:
                self._erreurs_consec += 1
                self._total_erreurs  += 1
                tb = traceback.format_exc()
                self._log(f"Erreur cycle: {e} (consec: {self._erreurs_consec})", "ERR")
                STATE.log_error(self.nom, f"{type(e).__name__}: {str(e)}\n{tb}",
                                critique=self._erreurs_consec >= 3)

                delai_restart = self.DELAI_RESTART_BASE * (2 ** min(self._erreurs_consec, 5))
                STATE.heartbeat(self.nom, "ERROR",
                                f"Restart dans {delai_restart}s")
                time.sleep(delai_restart)
                continue

            # Attente jusqu'au prochain cycle
            elapsed = time.time() - debut
            restant = max(0, self.intervalle - elapsed)
            self._stop_event.wait(timeout=restant)

        self._actif = False
        try:
            self.on_stop()
        except Exception:
            pass
        STATE.heartbeat(self.nom, "STOPPED")
        self._log("Arrêté.", "WARN")

    def stop(self):
        self._stop_event.set()

    def pause(self):
        self._pause_event.set()
        self._log("En pause.", "WARN")

    def reprendre(self):
        self._pause_event.clear()
        self._log("Reprise.", "OK")

    def statut(self) -> dict:
        return {
            "nom":           self.nom,
            "actif":         self._actif,
            "cycles":        self._total_cycles,
            "erreurs":       self._total_erreurs,
            "erreurs_consec":self._erreurs_consec,
            "dernier_cycle": self._dernier_cycle,
            "intervalle":    self.intervalle,
        }
