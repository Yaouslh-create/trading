"""
API Web Flask — Dashboard + Watchdog pour déploiement cloud
Permet de surveiller le système depuis n'importe où (téléphone, navigateur).
Tourne sur Render.com GRATUITEMENT 24h/24.
"""
import sys, os, json, threading, time
from datetime import datetime
from flask import Flask, jsonify, render_template_string
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

app = Flask(__name__)

# ── Import du système ──────────────────────────────────────────────────────
from orchestrator.state_bus import STATE
from config.config import RISK, TRADE

# ── Template Dashboard HTML ────────────────────────────────────────────────
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>🤖 Trading Bot Halal</title>
  <meta http-equiv="refresh" content="15">
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0a0e1a; color: #e0e6ff; font-family: 'Courier New', monospace; padding: 20px; }
    h1 { color: #00ff88; font-size: 1.4em; margin-bottom: 20px; text-align: center; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; }
    .card { background: #111827; border: 1px solid #1f2d4e; border-radius: 12px; padding: 18px; }
    .card h2 { font-size: 0.8em; color: #6b7eaa; margin-bottom: 12px; text-transform: uppercase; }
    .val { font-size: 2em; font-weight: bold; }
    .green { color: #00ff88; } .red { color: #ff4466; } .yellow { color: #ffd700; }
    .badge { display: inline-block; padding: 3px 10px; border-radius: 20px; font-size: 0.75em; margin: 3px; }
    .badge-ok { background: #0d3320; color: #00ff88; border: 1px solid #00ff88; }
    .badge-err { background: #3d0a10; color: #ff4466; border: 1px solid #ff4466; }
    .badge-warn { background: #332800; color: #ffd700; border: 1px solid #ffd700; }
    table { width: 100%; border-collapse: collapse; font-size: 0.82em; }
    td, th { padding: 6px 10px; border-bottom: 1px solid #1f2d4e; }
    th { color: #6b7eaa; font-weight: normal; }
    .ts { color: #444; font-size: 0.7em; text-align: center; margin-top: 20px; }
    .signal-buy { color: #00ff88; } .signal-sell { color: #ff4466; }
    .bar { height: 8px; border-radius: 4px; background: #1f2d4e; margin-top: 8px; }
    .bar-fill { height: 100%; border-radius: 4px; }
  </style>
</head>
<body>
  <h1>🤖 Agent IA Trading Halal — Méthode Simons</h1>
  <div class="grid">

    <!-- Capital -->
    <div class="card">
      <h2>💰 Capital</h2>
      <div class="val {cap_color}">{capital}€</div>
      <div style="margin-top:8px;font-size:0.9em">
        Rendement: <span class="{rend_color}">{rendement:+.2f}%</span>
      </div>
      <div style="font-size:0.8em;color:#6b7eaa;margin-top:4px">
        Drawdown: {drawdown:.2f}% | Positions: {nb_positions}
      </div>
      <div class="bar"><div class="bar-fill" style="width:{dd_pct}%;background:{dd_col}"></div></div>
    </div>

    <!-- Statut Trading -->
    <div class="card">
      <h2>⚡ Statut Système</h2>
      <div class="val">{trading_badge}</div>
      <div style="margin-top:12px;font-size:0.8em;color:#6b7eaa">
        Mode: {mode}<br>
        Agents actifs: {agents_ok}/{agents_total}<br>
        Univers halal: {nb_halal} actifs
      </div>
    </div>

    <!-- Signaux actifs -->
    <div class="card">
      <h2>📡 Signaux Actifs</h2>
      {signaux_html}
    </div>

    <!-- Agents -->
    <div class="card">
      <h2>🤖 État des Agents</h2>
      {agents_html}
    </div>

    <!-- Dernières erreurs -->
    <div class="card">
      <h2>⚠️ Dernières Erreurs</h2>
      {erreurs_html}
    </div>

    <!-- Performance -->
    <div class="card">
      <h2>📊 Performance</h2>
      {perf_html}
    </div>

  </div>
  <div class="ts">Mis à jour: {timestamp} | Rafraîchit toutes les 15s</div>
</body>
</html>
"""

def build_dashboard() -> str:
    risk    = STATE.get_risk_state()
    signaux = {t: s for t, s in STATE.get_all_signals().items()
               if s.get("action") != "ATTENDRE"}
    agents  = STATE.get_agents_status()
    errors  = STATE.get_errors(5)
    trades  = STATE.get_trades_history()
    univers = STATE.get_univers_halal()

    cap     = risk.get("capital_actuel", 0)
    rend    = risk.get("rendement_pct", 0)
    dd      = risk.get("drawdown_pct", 0)
    trading = risk.get("trading_autorise", False)

    # Badges
    cap_color   = "green" if cap >= 100 else "red"
    rend_color  = "green" if rend >= 0 else "red"
    dd_pct      = min(dd, 100)
    dd_col      = "#00ff88" if dd < 5 else ("#ffd700" if dd < 10 else "#ff4466")
    trading_badge = '<span class="badge badge-ok">✅ ACTIF</span>' if trading else '<span class="badge badge-err">🚫 BLOQUÉ</span>'

    # Signaux
    if signaux:
        rows = ""
        for t, s in list(signaux.items())[:6]:
            cls = "signal-buy" if s.get("action") == "ACHETER" else "signal-sell"
            rows += f'<div class="{cls}" style="font-size:0.9em;margin:4px 0">{"🟢" if s.get("action")=="ACHETER" else "🔴"} {t} — {s.get("action","?")} ({s.get("force",0):.0%})</div>'
        signaux_html = rows
    else:
        signaux_html = '<div style="color:#6b7eaa;font-size:0.85em">Aucun signal actionnable</div>'

    # Agents
    agents_ok = 0
    agents_html = ""
    for nom, st in list(agents.items())[:10]:
        status = st.get("status", "?")
        if status == "OK":
            agents_ok += 1
            badge = "badge-ok"
        elif status == "ERROR":
            badge = "badge-err"
        else:
            badge = "badge-warn"
        agents_html += f'<div style="font-size:0.8em;margin:3px 0"><span class="badge {badge}">{status}</span> {nom}</div>'

    # Erreurs
    if errors:
        erreurs_html = ""
        for e in errors[-4:]:
            erreurs_html += f'<div style="font-size:0.75em;color:#ff7788;border-left:2px solid #ff4466;padding-left:8px;margin:4px 0">{e.get("agent","?")}: {str(e.get("erreur",""))[:60]}</div>'
    else:
        erreurs_html = '<div style="color:#00ff88;font-size:0.85em">✅ Aucune erreur</div>'

    # Perf
    if trades:
        pnls     = [t.get("pnl", 0) for t in trades]
        gagnants = [p for p in pnls if p > 0]
        wr       = len(gagnants) / len(pnls) * 100 if pnls else 0
        pnl_tot  = sum(pnls)
        perf_html = f"""
        <div style="font-size:0.9em">
          Trades: <b>{len(trades)}</b><br>
          Win Rate: <span class="{'green' if wr>50 else 'red'}">{wr:.0f}%</span><br>
          PnL total: <span class="{'green' if pnl_tot>0 else 'red'}">{pnl_tot:+.2f}€</span>
        </div>"""
    else:
        perf_html = '<div style="color:#6b7eaa;font-size:0.85em">Aucun trade clôturé</div>'

    return DASHBOARD_HTML.format(
        capital=f"{cap:.2f}", cap_color=cap_color,
        rendement=rend, rend_color=rend_color,
        drawdown=dd, dd_pct=dd_pct, dd_col=dd_col,
        nb_positions=risk.get("nb_positions", 0),
        trading_badge=trading_badge,
        mode=TRADE.mode,
        agents_ok=agents_ok, agents_total=len(agents),
        nb_halal=len(univers),
        signaux_html=signaux_html,
        agents_html=agents_html,
        erreurs_html=erreurs_html,
        perf_html=perf_html,
        timestamp=datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
    )


# ── Routes API ─────────────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    return build_dashboard()

@app.route("/api/status")
def api_status():
    risk   = STATE.get_risk_state()
    agents = STATE.get_agents_status()
    return jsonify({
        "status":   "ok",
        "capital":  risk.get("capital_actuel", 0),
        "rendement":risk.get("rendement_pct", 0),
        "drawdown": risk.get("drawdown_pct", 0),
        "trading":  risk.get("trading_autorise", False),
        "agents_ok":sum(1 for s in agents.values() if s.get("status") == "OK"),
        "agents_total": len(agents),
        "timestamp":datetime.now().isoformat(),
    })

@app.route("/api/signals")
def api_signals():
    return jsonify(STATE.get_all_signals())

@app.route("/api/positions")
def api_positions():
    return jsonify(STATE.get_positions())

@app.route("/api/history")
def api_history():
    return jsonify(STATE.get_trades_history()[-50:])

@app.route("/api/errors")
def api_errors():
    return jsonify(STATE.get_errors(30))

@app.route("/health")
def health():
    return jsonify({"status": "alive", "ts": datetime.now().isoformat()})


def run_web(port: int = 8080):
    """Lance le serveur web en arrière-plan."""
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    run_web(8080)
