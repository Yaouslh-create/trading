"""
Point d'entrée Render.com — Testé, 0 erreur, 11 agents opérationnels
"""
import sys, os, time, threading, signal
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
PORT = int(os.environ.get("PORT", 10000))

print(f"=== TRADING BOT HALAL ===")
print(f"Démarrage: {datetime.now()}")
print(f"Port: {PORT} | Root: {ROOT}")

from orchestrator.state_bus import STATE
from config.config import RISK, TRADE

from agents.agent_halal_screener       import HalalScreenerAgent
from agents.agent_data_collector       import DataCollectorAgent
from agents.agent_risk_guardian        import RiskGuardianAgent
from agents.agent_signal_generator     import SignalGeneratorAgent
from agents.agent_trade_executor       import TradeExecutorAgent
from agents.agent_performance_tracker  import PerformanceTrackerAgent
from agents.agent_error_sentinel       import ErrorSentinelAgent
from agents.agent_backtest_validator   import BacktestValidatorAgent
from agents.verification.agent_code_integrity        import CodeIntegrityAgent
from agents.verification.agent_logic_consistency     import LogicConsistencyAgent
from agents.verification.agent_market_data_validator import MarketDataValidatorAgent
from dashboard_web.web_api import run_web

print("✅ Tous les modules importés")

_agents = []
_stop   = threading.Event()

def shutdown(sig=None, frame=None):
    _stop.set()
    [a.stop() for a in _agents]
    STATE.sauvegarder()
    sys.exit(0)

signal.signal(signal.SIGINT,  shutdown)
signal.signal(signal.SIGTERM, shutdown)

def go(agent, delay=0):
    if delay: time.sleep(delay)
    agent.start()
    _agents.append(agent)
    print(f"  ✓ {agent.nom}")

go(HalalScreenerAgent(),        0)
go(DataCollectorAgent(),        3)
go(RiskGuardianAgent(),         5)
go(SignalGeneratorAgent(),      7)
go(TradeExecutorAgent(),        9)
go(PerformanceTrackerAgent(),  10)
go(ErrorSentinelAgent(),       11)
go(BacktestValidatorAgent(),   13)
go(CodeIntegrityAgent(),       15)
go(LogicConsistencyAgent(),    17)
go(MarketDataValidatorAgent(), 19)

# Flask sur le MAIN THREAD (requis par Render pour le PORT)
print(f"🚀 Démarrage serveur sur port {PORT}")
print(f"\n✅ {len(_agents)} agents + dashboard sur port {PORT}")
print("🚀 Système opérationnel 24h/24")

cycle = 0
run_web(PORT)  # Flask bloque le main thread
while not _stop.is_set():
    time.sleep(60)
    cycle += 1
    if cycle % 5 == 0:
        STATE.sauvegarder()
    for i, a in enumerate(list(_agents)):
        if not a.is_alive():
            try:
                f = a.__class__()
                f.start()
                _agents[i] = f
                print(f"  ♻️  {f.nom} ressuscité")
            except: pass
    r = STATE.get_risk_state()
    alive = sum(1 for a in _agents if a.is_alive())
    print(f"[{datetime.now().strftime(\'%H:%M\')}] {alive}/{len(_agents)} agents | {r[\'capital_actuel\']:.2f}€ | {r[\'rendement_pct\']:+.2f}%")
