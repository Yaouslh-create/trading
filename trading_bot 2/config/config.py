"""
Configuration centrale — Source unique de vérité pour tout le système.
Modifier ici = propager partout automatiquement.
"""
import os
from dataclasses import dataclass, field
from typing import List

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

@dataclass
class RiskConfig:
    capital_initial:           float = 100.0
    risque_par_trade_pct:      float = 0.015    # 1.5% par trade
    max_positions:             int   = 4
    max_drawdown_pct:          float = 0.12     # stop si -12%
    max_perte_journaliere_pct: float = 0.04     # stop si -4%/jour
    max_pct_capital_par_pos:   float = 0.30     # max 30% par position
    ratio_rr_minimum:          float = 2.0      # ratio R/R minimum 1:2
    kelly_fraction:            float = 0.25     # fraction Kelly conservatrice
    sl_atr_mult:               float = 1.5      # stop = 1.5x ATR
    tp_atr_mult:               float = 3.0      # take = 3.0x ATR

@dataclass
class TradingConfig:
    mode:              str  = "DEMO"            # "DEMO" ou "REEL"
    intervalle_scan:   int  = 300               # secondes entre scans
    min_confirmations: int  = 3                 # min signaux alignés
    min_confiance:     str  = "moyenne"         # "faible"|"moyenne"|"forte"
    univers_actifs:    List[str] = field(default_factory=lambda: [
        "GC=F","SI=F","PL=F",                   # Métaux précieux
        "ZW=F","ZC=F","KC=F",                   # Matières premières agri
        "AAPL","MSFT","NVDA","GOOGL",            # Tech US
        "TSLA","AMD","AMZN","META",              # Tech croissance
    ])

@dataclass
class AgentConfig:
    # Fréquences d'exécution (secondes)
    freq_data_collector:    int = 60
    freq_halal_screener:    int = 3600          # chaque heure
    freq_signal_generator:  int = 120           # chaque 2 min
    freq_risk_guardian:     int = 30            # chaque 30s
    freq_trade_executor:    int = 5             # chaque 5s
    freq_performance_tracker: int = 300         # chaque 5 min
    freq_backtest_validator:  int = 86400       # chaque jour
    freq_error_sentinel:    int = 10            # chaque 10s

@dataclass
class PathConfig:
    logs_dir:       str = os.path.join(BASE_DIR, "logs")
    data_dir:       str = os.path.join(BASE_DIR, "data", "cache")
    reports_dir:    str = os.path.join(BASE_DIR, "reporting", "outputs")
    state_file:     str = os.path.join(BASE_DIR, "logs", "system_state.json")
    trades_file:    str = os.path.join(BASE_DIR, "logs", "demo_trades.json")
    signals_file:   str = os.path.join(BASE_DIR, "logs", "signals.json")
    errors_file:    str = os.path.join(BASE_DIR, "logs", "errors.json")
    perf_file:      str = os.path.join(BASE_DIR, "logs", "performance.json")

# Instances globales
RISK   = RiskConfig()
TRADE  = TradingConfig()
AGENTS = AgentConfig()
PATHS  = PathConfig()

# Créer les dossiers nécessaires
for d in [PATHS.logs_dir, PATHS.data_dir, PATHS.reports_dir]:
    os.makedirs(d, exist_ok=True)
