"""
HalalTrader Pro - Point d'entrée Render.com
Flask sur main thread, PORT dynamique, zéro crash possible
"""
import os
import sys
import threading
import time
from datetime import datetime

# Port Render (OBLIGATOIRE - Render assigne le port via env var)
PORT = int(os.environ.get("PORT", 10000))

print(f"[{datetime.now()}] Démarrage HalalTrader Pro sur port {PORT}")
sys.stdout.flush()

# Ajouter le répertoire courant au path
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

# Importer l'app Flask (avec gestion d'erreur)
try:
    from dashboard_web.web_api import app
    print(f"[{datetime.now()}] ✅ Flask app importée")
    sys.stdout.flush()
except Exception as e:
    print(f"[{datetime.now()}] ❌ Erreur import Flask: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Lancer les agents en background (optionnel - ne peut pas crasher Flask)
def start_agents_safe():
    time.sleep(5)  # Attendre que Flask soit bien démarré
    try:
        from agents.agent_halal_screener       import HalalScreenerAgent
        from agents.agent_data_collector       import DataCollectorAgent
        from agents.agent_risk_guardian        import RiskGuardianAgent
        from agents.agent_signal_generator     import SignalGeneratorAgent
        from agents.agent_trade_executor       import TradeExecutorAgent
        from agents.agent_performance_tracker  import PerformanceTrackerAgent
        from agents.agent_error_sentinel       import ErrorSentinelAgent
        from agents.verification.agent_code_integrity        import CodeIntegrityAgent
        from agents.verification.agent_logic_consistency     import LogicConsistencyAgent
        from agents.verification.agent_market_data_validator import MarketDataValidatorAgent

        agents = [
            HalalScreenerAgent(), DataCollectorAgent(), RiskGuardianAgent(),
            SignalGeneratorAgent(), TradeExecutorAgent(), PerformanceTrackerAgent(),
            ErrorSentinelAgent(), CodeIntegrityAgent(), LogicConsistencyAgent(),
            MarketDataValidatorAgent(),
        ]
        for a in agents:
            try:
                a.start()
                print(f"  ✓ {a.nom}")
                sys.stdout.flush()
            except Exception as e:
                print(f"  ⚠️  {a.nom}: {e}")
        print(f"[{datetime.now()}] ✅ {len(agents)} agents démarrés")
    except Exception as e:
        print(f"[{datetime.now()}] ⚠️  Agents non disponibles: {e}")
    sys.stdout.flush()

threading.Thread(target=start_agents_safe, daemon=True).start()

# Flask sur le MAIN THREAD (Render détecte le port ici)
print(f"[{datetime.now()}] 🚀 Flask écoute sur 0.0.0.0:{PORT}")
sys.stdout.flush()
app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False, threaded=True)
