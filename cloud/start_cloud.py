"""
Point d'entrée Cloud — Render.com
Lance les 11 agents + dashboard web sur le port fourni par Render.
"""
import sys, os, time, threading, signal
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PORT = int(os.environ.get("PORT", 10000))

print(f"""
╔══════════════════════════════════════════════════╗
║   TRADING BOT HALAL — CLOUD RENDER.COM           ║
║   Démarrage: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}              ║
║   Port: {PORT}                                      ║
╚══════════════════════════════════════════════════╝
""")

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

_all_agents = []
_stop = threading.Event()

def shutdown(sig=None, frame=None):
    print("\nArrêt propre...")
    _stop.set()
    for a in _all_agents:
        try: a.stop()
        except: pass
    STATE.sauvegarder()
    sys.exit(0)

signal.signal(signal.SIGINT,  shutdown)
signal.signal(signal.SIGTERM, shutdown)

def start(agent, delay=0):
    if delay: time.sleep(delay)
    agent.start()
    _all_agents.append(agent)
    print(f"  ✓ {agent.nom} démarré")

print("Phase 1 — Agents principaux...")
start(HalalScreenerAgent(),       0)
start(DataCollectorAgent(),       3)
start(RiskGuardianAgent(),        5)
start(SignalGeneratorAgent(),     7)
start(TradeExecutorAgent(),       9)
start(PerformanceTrackerAgent(), 10)
start(ErrorSentinelAgent(),      11)
start(BacktestValidatorAgent(),  13)

print("Phase 2 — Agents de vérification...")
start(CodeIntegrityAgent(),      15)
start(LogicConsistencyAgent(),   17)
start(MarketDataValidatorAgent(),19)

print(f"\n✅ {len(_all_agents)} agents démarrés")

web_thread = threading.Thread(target=run_web, args=(PORT,), daemon=True)
web_thread.start()
print(f"✓ Dashboard web sur port {PORT}")
print(f"\n🚀 Système opérationnel 24h/24\n")

cycle = 0
while not _stop.is_set():
    time.sleep(60)
    cycle += 1
    if cycle % 5 == 0:
        STATE.sauvegarder()
    # Auto-résurrection
    for agent in list(_all_agents):
        if not agent.is_alive():
            try:
                fresh = agent.__class__()
                fresh.start()
                _all_agents[_all_agents.index(agent)] = fresh
                print(f"  ♻️  {fresh.nom} ressuscité")
            except Exception as e:
                print(f"  ❌ Résurrection échouée: {e}")
    # Heartbeat
    risk = STATE.get_risk_state()
    alive = sum(1 for a in _all_agents if a.is_alive())
    print(f"  [{datetime.now().strftime('%H:%M')}] Agents:{alive}/{len(_all_agents)} Capital:{risk['capital_actuel']:.2f}€ Rend:{risk['rendement_pct']:+.2f}%")
