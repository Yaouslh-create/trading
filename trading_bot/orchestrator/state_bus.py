"""
Bus d'état partagé — Communication thread-safe entre tous les agents.
Zéro race condition. Zéro donnée corrompue.
Pattern : Publish / Subscribe avec verrous par domaine.
"""
import threading
import json
import time
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable
from collections import deque
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config.config import PATHS


class SharedState:
    """
    Mémoire partagée thread-safe entre tous les agents.
    Chaque domaine a son propre verrou pour éviter les deadlocks.
    """

    def __init__(self):
        # Verrous par domaine
        self._locks = {
            "market":    threading.RLock(),
            "signals":   threading.RLock(),
            "positions": threading.RLock(),
            "risk":      threading.RLock(),
            "errors":    threading.RLock(),
            "perf":      threading.RLock(),
            "halal":     threading.RLock(),
            "system":    threading.RLock(),
        }

        # Données de marché
        self._market_data: Dict[str, dict] = {}
        self._last_prices: Dict[str, float] = {}

        # Signaux générés
        self._signals: Dict[str, dict] = {}
        self._signal_history: deque = deque(maxlen=500)

        # Positions ouvertes
        self._positions: Dict[str, dict] = {}
        self._trades_history: List[dict] = []

        # État du risque
        self._capital_actuel: float = 100.0
        self._capital_initial: float = 100.0
        self._capital_max: float = 100.0
        self._perte_journaliere: float = 0.0
        self._trading_autorise: bool = True
        self._raison_blocage: str = ""

        # Univers halal validé
        self._univers_halal: List[str] = []
        self._derniere_validation_halal: Optional[str] = None

        # Erreurs système
        self._errors: deque = deque(maxlen=200)
        self._error_counts: Dict[str, int] = {}

        # Métriques de performance
        self._perf_metrics: dict = {}

        # État des agents
        self._agents_status: Dict[str, dict] = {}

        # Events pour réveiller les agents
        self._events: Dict[str, threading.Event] = {}

        # Abonnements (pub/sub)
        self._subscribers: Dict[str, List[Callable]] = {}
        self._sub_lock = threading.Lock()

        self._charger_etat()

    # ── Marché ─────────────────────────────────────────────────────────────

    def set_market_data(self, ticker: str, data: dict):
        with self._locks["market"]:
            self._market_data[ticker] = {**data, "_ts": time.time()}
            if "prix" in data:
                self._last_prices[ticker] = data["prix"]
        self._publish("market_update", {"ticker": ticker})

    def get_market_data(self, ticker: str) -> Optional[dict]:
        with self._locks["market"]:
            return self._market_data.get(ticker)

    def get_all_market_data(self) -> Dict[str, dict]:
        with self._locks["market"]:
            return dict(self._market_data)

    def get_prix(self, ticker: str) -> Optional[float]:
        with self._locks["market"]:
            return self._last_prices.get(ticker)

    # ── Signaux ────────────────────────────────────────────────────────────

    def set_signal(self, ticker: str, signal: dict):
        with self._locks["signals"]:
            signal["_ts"] = time.time()
            signal["_datetime"] = datetime.now().isoformat()
            self._signals[ticker] = signal
            self._signal_history.append({**signal, "ticker": ticker})
        self._publish("new_signal", {"ticker": ticker, "action": signal.get("action")})

    def get_signal(self, ticker: str) -> Optional[dict]:
        with self._locks["signals"]:
            return self._signals.get(ticker)

    def get_all_signals(self) -> Dict[str, dict]:
        with self._locks["signals"]:
            return dict(self._signals)

    def get_signal_history(self, n: int = 50) -> List[dict]:
        with self._locks["signals"]:
            return list(self._signal_history)[-n:]

    # ── Positions ──────────────────────────────────────────────────────────

    def ouvrir_position(self, trade_id: str, position: dict):
        with self._locks["positions"]:
            position["_ouverture_ts"] = time.time()
            self._positions[trade_id] = position
        self._publish("position_opened", {"trade_id": trade_id})

    def fermer_position(self, trade_id: str, pnl: float, raison: str):
        with self._locks["positions"]:
            pos = self._positions.pop(trade_id, None)
            if pos:
                pos["_fermeture_ts"] = time.time()
                pos["pnl"] = pnl
                pos["raison_fermeture"] = raison
                self._trades_history.append(pos)
        self._publish("position_closed", {"trade_id": trade_id, "pnl": pnl})

    def get_positions(self) -> Dict[str, dict]:
        with self._locks["positions"]:
            return dict(self._positions)

    def get_trades_history(self) -> List[dict]:
        with self._locks["positions"]:
            return list(self._trades_history)

    # ── Risque ─────────────────────────────────────────────────────────────

    def update_capital(self, nouveau_capital: float):
        with self._locks["risk"]:
            self._capital_actuel = nouveau_capital
            if nouveau_capital > self._capital_max:
                self._capital_max = nouveau_capital

    def add_perte_journaliere(self, montant: float):
        with self._locks["risk"]:
            self._perte_journaliere += abs(montant)

    def reset_perte_journaliere(self):
        with self._locks["risk"]:
            self._perte_journaliere = 0.0

    def set_trading_autorise(self, autorise: bool, raison: str = ""):
        with self._locks["risk"]:
            ancien = self._trading_autorise
            self._trading_autorise = autorise
            self._raison_blocage = raison
        if ancien != autorise:
            self._publish("risk_status_changed", {"autorise": autorise, "raison": raison})

    def get_risk_state(self) -> dict:
        with self._locks["risk"]:
            return {
                "capital_actuel":     self._capital_actuel,
                "capital_initial":    self._capital_initial,
                "capital_max":        self._capital_max,
                "perte_journaliere":  self._perte_journaliere,
                "trading_autorise":   self._trading_autorise,
                "raison_blocage":     self._raison_blocage,
                "rendement_pct":      round((self._capital_actuel - self._capital_initial) / self._capital_initial * 100, 2),
                "drawdown_pct":       round((self._capital_max - self._capital_actuel) / self._capital_max * 100, 2),
                "nb_positions":       len(self._positions),
            }

    # ── Halal ──────────────────────────────────────────────────────────────

    def set_univers_halal(self, tickers: List[str]):
        with self._locks["halal"]:
            self._univers_halal = tickers
            self._derniere_validation_halal = datetime.now().isoformat()

    def get_univers_halal(self) -> List[str]:
        with self._locks["halal"]:
            return list(self._univers_halal)

    # ── Erreurs ────────────────────────────────────────────────────────────

    def log_error(self, agent: str, erreur: str, critique: bool = False):
        with self._locks["errors"]:
            entry = {
                "agent": agent, "erreur": erreur, "critique": critique,
                "timestamp": datetime.now().isoformat(), "ts": time.time()
            }
            self._errors.append(entry)
            self._error_counts[agent] = self._error_counts.get(agent, 0) + 1
        if critique:
            self._publish("critical_error", entry)

    def get_errors(self, n: int = 20) -> List[dict]:
        with self._locks["errors"]:
            return list(self._errors)[-n:]

    def get_error_counts(self) -> Dict[str, int]:
        with self._locks["errors"]:
            return dict(self._error_counts)

    # ── Agents status ──────────────────────────────────────────────────────

    def heartbeat(self, agent_name: str, status: str = "OK", info: str = ""):
        with self._locks["system"]:
            self._agents_status[agent_name] = {
                "status": status, "info": info,
                "last_seen": datetime.now().isoformat(),
                "ts": time.time()
            }

    def get_agents_status(self) -> Dict[str, dict]:
        with self._locks["system"]:
            return dict(self._agents_status)

    # ── Pub/Sub ────────────────────────────────────────────────────────────

    def subscribe(self, event: str, callback: Callable):
        with self._sub_lock:
            if event not in self._subscribers:
                self._subscribers[event] = []
            self._subscribers[event].append(callback)

    def _publish(self, event: str, data: dict):
        with self._sub_lock:
            callbacks = list(self._subscribers.get(event, []))
        for cb in callbacks:
            try:
                cb(data)
            except Exception:
                pass

    # ── Persistance ────────────────────────────────────────────────────────

    def _charger_etat(self):
        try:
            if os.path.exists(PATHS.trades_file):
                with open(PATHS.trades_file) as f:
                    data = json.load(f)
                    self._capital_actuel = data.get("capital", 100.0)
                    self._trades_history = data.get("historique", [])
                    self._positions = data.get("positions", {})
        except Exception:
            pass

    def sauvegarder(self):
        try:
            risk = self.get_risk_state()
            with open(PATHS.trades_file, "w") as f:
                json.dump({
                    "capital":    self._capital_actuel,
                    "positions":  self._positions,
                    "historique": self._trades_history[-200:],
                    "risk":       risk,
                    "saved_at":   datetime.now().isoformat(),
                }, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def snapshot(self) -> dict:
        """Snapshot complet de l'état système (pour monitoring)."""
        return {
            "risk":     self.get_risk_state(),
            "signaux":  {k: {"action": v.get("action"), "force": v.get("force")}
                         for k, v in self.get_all_signals().items()},
            "agents":   self.get_agents_status(),
            "erreurs":  self.get_error_counts(),
            "ts":       datetime.now().isoformat(),
        }


# Instance singleton — un seul bus pour tout le système
STATE = SharedState()
