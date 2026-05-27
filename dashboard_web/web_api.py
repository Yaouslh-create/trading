"""
API Web Flask — Dashboard + endpoints
Version corrigée : accepte toutes les connexions
"""
import sys, os, json, threading, time
from datetime import datetime
from flask import Flask, jsonify, render_template_string, request
from flask_cors import CORS

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = Flask(__name__)
CORS(app)  # Autorise toutes les origines

try:
    from orchestrator.state_bus import STATE
    from config.config import RISK, TRADE
except:
    STATE = None
    class MockRisk:
        capital_initial = 100.0
        mode = "DEMO"
    RISK = MockRisk()
    TRADE = MockRisk()

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>🤖 Trading Bot Halal</title>
  <meta http-equiv="refresh" content="15">
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{background:#0a0e1a;color:#e0e6ff;font-family:monospace;padding:16px}
    h1{color:#00ff88;font-size:1.3em;margin-bottom:16px;text-align:center}
    .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-bottom:20px}
    .card{background:#111827;border:1px solid #1f2d4e;border-radius:10px;padding:14px}
    .card h2{font-size:10px;color:#6b7eaa;margin-bottom:8px;text-transform:uppercase}
    .val{font-size:1.8em;font-weight:bold}
    .green{color:#00ff88}.red{color:#ff4466}.yellow{color:#ffd700}
    .badge{display:inline-block;padding:2px 10px;border-radius:20px;font-size:11px}
    .b-ok{background:#0d3320;color:#00ff88;border:1px solid #00ff88}
    .b-err{background:#3d0a10;color:#ff4466;border:1px solid #ff4466}
    .agents{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:8px}
    .agent{display:flex;align-items:center;gap:8px;padding:8px 12px;border:1px solid #1f2d4e;border-radius:8px;background:#111827}
    .dot{width:8px;height:8px;border-radius:50%;background:#00ff88}
    .agent-name{font-size:12px;color:#e0e6ff}
    .ts{color:#444;font-size:11px;text-align:center;margin-top:16px}
    table{width:100%;border-collapse:collapse;font-size:12px;margin-top:8px}
    td,th{padding:6px 8px;border-bottom:1px solid #1f2d4e;text-align:left}
    th{color:#6b7eaa;font-size:10px}
  </style>
</head>
<body>
  <h1>🤖 Agent IA Trading Halal — Méthode Simons</h1>
  <div class="grid">
    <div class="card">
      <h2>💰 Capital</h2>
      <div class="val green" id="capital">{{capital}}€</div>
      <div style="font-size:12px;margin-top:4px">Rendement: <span class="green">{{rendement}}</span></div>
    </div>
    <div class="card">
      <h2>⚡ Statut</h2>
      <div style="margin-top:4px"><span class="badge b-ok">✅ DEMO ACTIF</span></div>
      <div style="font-size:11px;color:#6b7eaa;margin-top:8px">{{nb_agents}} agents actifs</div>
    </div>
    <div class="card">
      <h2>📊 Trades</h2>
      <div class="val">{{nb_trades}}</div>
      <div style="font-size:12px;margin-top:4px;color:#6b7eaa">Clôturés</div>
    </div>
    <div class="card">
      <h2>📡 Signaux</h2>
      <div class="val yellow">{{nb_signaux}}</div>
      <div style="font-size:12px;margin-top:4px;color:#6b7eaa">Actifs sur 14 actifs</div>
    </div>
  </div>

  <div style="margin-bottom:12px">
    <div style="font-size:10px;color:#6b7eaa;text-transform:uppercase;margin-bottom:8px">11 Agents Autonomes</div>
    <div class="agents">
      {% for agent in agents %}
      <div class="agent"><div class="dot"></div><span class="agent-name">{{agent}}</span></div>
      {% endfor %}
    </div>
  </div>

  {% if signaux %}
  <div>
    <div style="font-size:10px;color:#6b7eaa;text-transform:uppercase;margin-bottom:8px">Signaux de trading</div>
    <table>
      <thead><tr><th>Actif</th><th>Action</th><th>Force</th><th>Confiance</th></tr></thead>
      <tbody>
        {% for s in signaux %}
        <tr>
          <td>{{s.ticker}}</td>
          <td style="color:{{'#00ff88' if s.action=='ACHETER' else '#ff4466'}}">{{s.action}}</td>
          <td>{{s.force}}</td>
          <td>{{s.confiance}}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% endif %}

  <div class="ts">Mis à jour: {{timestamp}} | Rafraîchit toutes les 15s</div>
</body>
</html>
"""

AGENTS_NOMS = [
    "DataCollector", "HalalScreener", "SignalGenerator",
    "RiskGuardian", "TradeExecutor", "PerformanceTracker",
    "ErrorSentinel", "BacktestValidator",
    "CodeIntegrity", "LogicConsistency", "MarketDataValidator"
]

@app.route("/")
def dashboard():
    try:
        risk    = STATE.get_risk_state() if STATE else {"capital_actuel":100,"rendement_pct":0}
        signaux_raw = STATE.get_all_signals() if STATE else {}
        trades  = STATE.get_trades_history() if STATE else []
        signaux = [
            {"ticker":t,"action":s.get("action"),"force":f"{s.get('force',0):.0%}","confiance":s.get("confiance","")}
            for t,s in signaux_raw.items() if s.get("action") != "ATTENDRE"
        ]
        cap  = risk.get("capital_actuel", 100)
        rend = risk.get("rendement_pct", 0)
        return render_template_string(DASHBOARD_HTML,
            capital=f"{cap:.2f}",
            rendement=f"{rend:+.2f}%",
            nb_agents=11,
            nb_trades=len(trades),
            nb_signaux=len(signaux),
            agents=AGENTS_NOMS,
            signaux=signaux,
            timestamp=datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        )
    except Exception as e:
        return f"<h1 style='color:green;font-family:monospace'>🤖 Trading Bot Halal — En ligne</h1><p>Agents en cours de démarrage... ({e})</p>"

@app.route("/health")
def health():
    return jsonify({"status": "alive", "ts": datetime.now().isoformat(), "agents": 11})

@app.route("/api/status")
def api_status():
    try:
        risk = STATE.get_risk_state() if STATE else {}
        return jsonify({"status":"ok","capital":risk.get("capital_actuel",100),"ts":datetime.now().isoformat()})
    except:
        return jsonify({"status":"starting","ts":datetime.now().isoformat()})

@app.route("/api/signals")
def api_signals():
    try:
        return jsonify(STATE.get_all_signals() if STATE else {})
    except:
        return jsonify({})

@app.route("/api/positions")
def api_positions():
    try:
        return jsonify(STATE.get_positions() if STATE else {})
    except:
        return jsonify({})

@app.route("/api/history")
def api_history():
    try:
        return jsonify(STATE.get_trades_history()[-50:] if STATE else [])
    except:
        return jsonify([])

def run_web(port=10000):
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    run_web(int(os.environ.get("PORT", 8080)))
