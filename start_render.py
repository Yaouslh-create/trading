"""
Point d'entrée Render.com — Flask sur thread principal
Les agents tournent en background, Flask bloque le main thread (requis par Render)
"""
import sys, os, time, threading, signal
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
PORT = int(os.environ.get("PORT", 10000))

print(f"=== HalalTrader Pro — Render.com ===")
print(f"Démarrage: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Port: {PORT}")

# Importer les agents (en background)
try:
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
    AGENTS_OK = True
    print("✅ Agents importés")
except Exception as e:
    AGENTS_OK = False
    print(f"⚠️  Agents non disponibles: {e}")

# Importer Flask app
from dashboard_web.web_api import app, run_web
print("✅ Dashboard importé")

# Lancer les agents dans des threads background
_agents = []
if AGENTS_OK:
    def start_agents():
        time.sleep(2)  # Laisser Flask démarrer d'abord
        agent_classes = [
            HalalScreenerAgent, DataCollectorAgent, RiskGuardianAgent,
            SignalGeneratorAgent, TradeExecutorAgent, PerformanceTrackerAgent,
            ErrorSentinelAgent, BacktestValidatorAgent,
            CodeIntegrityAgent, LogicConsistencyAgent, MarketDataValidatorAgent,
        ]
        for i, cls in enumerate(agent_classes):
            try:
                a = cls()
                a.start()
                _agents.append(a)
                print(f"  ✓ {a.nom} démarré")
                time.sleep(1)
            except Exception as e:
                print(f"  ⚠️  {cls.__name__}: {e}")
        print(f"\n✅ {len(_agents)} agents actifs")

    threading.Thread(target=start_agents, daemon=True).start()

# Auto-résurrection des agents
def watchdog():
    time.sleep(60)
    while True:
        for i, a in enumerate(list(_agents)):
            if not a.is_alive():
                try:
                    fresh = a.__class__()
                    fresh.start()
                    _agents[i] = fresh
                    print(f"  ♻️  {fresh.nom} ressuscité")
                except: pass
        time.sleep(60)

threading.Thread(target=watchdog, daemon=True).start()

# Flask sur le thread PRINCIPAL (requis par Render pour détecter le port)
print(f"\n🚀 Démarrage serveur web sur port {PORT}...")
run_web(PORT)
