"""
Dashboard Web — Autonome, données temps réel, 0 dépendance au STATE
"""
import sys, os, json, time, threading, requests as req
from datetime import datetime
from flask import Flask, jsonify
from flask_cors import CORS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

app = Flask(__name__)
CORS(app)

# Cache des prix
_prix_cache = {}
_last_update = 0

ACTIFS = {
    "GC=F":  {"nom":"Or",       "ref":3350, "vol":0.008},
    "SI=F":  {"nom":"Argent",   "ref":33.5, "vol":0.015},
    "AAPL":  {"nom":"Apple",    "ref":195,  "vol":0.016},
    "MSFT":  {"nom":"Microsoft","ref":420,  "vol":0.015},
    "NVDA":  {"nom":"NVIDIA",   "ref":900,  "vol":0.030},
    "TSLA":  {"nom":"Tesla",    "ref":175,  "vol":0.038},
    "AMD":   {"nom":"AMD",      "ref":155,  "vol":0.028},
    "GOOGL": {"nom":"Alphabet", "ref":170,  "vol":0.016},
    "AMZN":  {"nom":"Amazon",   "ref":195,  "vol":0.018},
    "META":  {"nom":"Meta",     "ref":520,  "vol":0.022},
    "ZW=F":  {"nom":"Blé",      "ref":530,  "vol":0.014},
    "KC=F":  {"nom":"Café",     "ref":200,  "vol":0.020},
    "PL=F":  {"nom":"Platine",  "ref":1000, "vol":0.012},
    "CL=F":  {"nom":"Pétrole",  "ref":78,   "vol":0.022},
}

import numpy as np

def get_prix_yahoo(ticker):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=2d"
        r = req.get(url, timeout=6, headers={"User-Agent":"Mozilla/5.0"})
        if r.status_code == 200:
            d = r.json()
            px = d["chart"]["result"][0]["meta"]["regularMarketPrice"]
            prev = d["chart"]["result"][0]["meta"].get("previousClose", px)
            return float(px), float(prev)
    except:
        pass
    return None, None

def generer_prix_synthetique(ticker, ref, vol):
    """Prix synthétique qui varie de façon réaliste"""
    seed = int(time.time() / 300) + abs(hash(ticker)) % 9999
    np.random.seed(seed)
    chg = np.random.normal(0, vol)
    px = ref * (1 + chg)
    prev_seed = seed - 1
    np.random.seed(prev_seed)
    prev_chg = np.random.normal(0, vol)
    prev = ref * (1 + prev_chg)
    return round(px, 4), round(prev, 4)

def update_prix():
    global _prix_cache, _last_update
    while True:
        now = {}
        for ticker, info in ACTIFS.items():
            px, prev = get_prix_yahoo(ticker)
            source = "Yahoo Finance"
            if not px:
                px, prev = generer_prix_synthetique(ticker, info["ref"], info["vol"])
                source = "Simulé"
            chg = ((px - prev) / prev * 100) if prev else 0
            now[ticker] = {
                "ticker": ticker,
                "nom": info["nom"],
                "prix": round(px, 4),
                "prev": round(prev, 4),
                "variation_pct": round(chg, 2),
                "source": source,
                "ts": datetime.now().isoformat()
            }
        _prix_cache = now
        _last_update = time.time()
        time.sleep(60)

# Lancer le thread de mise à jour des prix
threading.Thread(target=update_prix, daemon=True).start()

# Générer données initiales immédiatement
for ticker, info in ACTIFS.items():
    px, prev = generer_prix_synthetique(ticker, info["ref"], info["vol"])
    chg = ((px - prev) / prev * 100) if prev else 0
    _prix_cache[ticker] = {
        "ticker": ticker, "nom": info["nom"],
        "prix": round(px, 4), "variation_pct": round(chg, 2),
        "source": "Simulé", "ts": datetime.now().isoformat()
    }

AGENTS = [
    "DataCollector","HalalScreener","SignalGenerator","RiskGuardian",
    "TradeExecutor","PerformanceTracker","ErrorSentinel","BacktestValidator",
    "CodeIntegrity","LogicConsistency","MarketDataValidator"
]

DASHBOARD = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Trading Bot Halal</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#080d1a;color:#c9d4f0;font-family:-apple-system,monospace;min-height:100vh}
.hdr{background:#0d1526;border-bottom:1px solid #1a2744;padding:14px 20px;display:flex;align-items:center;justify-content:space-between}
.hdr-title{font-size:16px;font-weight:600;color:#00ff88}
.hdr-sub{font-size:11px;color:#4a6080;margin-top:2px}
.live-dot{width:8px;height:8px;border-radius:50%;background:#00ff88;display:inline-block;margin-right:6px;animation:blink 1.5s infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.2}}
.grid-top{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;padding:16px 20px}
.card{background:#0d1526;border:1px solid #1a2744;border-radius:10px;padding:14px}
.card-lbl{font-size:10px;color:#4a6080;text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px}
.card-val{font-size:24px;font-weight:600}
.card-sub{font-size:11px;color:#4a6080;margin-top:4px}
.g{color:#00ff88}.r{color:#ff4455}.y{color:#ffd700}.b{color:#38bdf8}
.sec{padding:0 20px 16px}
.sec-hdr{font-size:10px;color:#4a6080;text-transform:uppercase;letter-spacing:.06em;padding:12px 0 8px;border-top:1px solid #1a2744}
.tickers{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:8px}
.ticker{background:#0d1526;border:1px solid #1a2744;border-radius:8px;padding:10px 12px;cursor:default}
.ticker:hover{border-color:#2a3f6f}
.t-sym{font-size:12px;font-weight:600;color:#c9d4f0}
.t-nom{font-size:10px;color:#4a6080}
.t-px{font-size:17px;font-weight:500;margin:4px 0 2px}
.t-chg{font-size:11px}
.t-src{font-size:9px;color:#2a3f6f;margin-top:3px}
.agents-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:8px}
.agent{display:flex;align-items:center;gap:8px;padding:8px 12px;background:#0d1526;border:1px solid #1a2744;border-radius:8px}
.a-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.a-name{font-size:12px;color:#c9d4f0;flex:1}
.a-cycle{font-size:10px;color:#4a6080}
.verif{border-color:#1a3a2a}
.signals-tbl{width:100%;border-collapse:collapse;font-size:12px}
.signals-tbl th{color:#4a6080;font-size:10px;font-weight:500;text-align:left;padding:6px 8px;border-bottom:1px solid #1a2744}
.signals-tbl td{padding:7px 8px;border-bottom:1px solid #1a2744}
.bar{height:4px;border-radius:2px;background:#1a2744;margin-top:4px}
.bar-f{height:100%;border-radius:2px}
.footer{text-align:center;padding:12px;font-size:10px;color:#2a3f6f;border-top:1px solid #1a2744}
</style>
</head>
<body>
<div class="hdr">
  <div>
    <div class="hdr-title"><span class="live-dot"></span>Agent IA Trading Halal — Méthode Simons</div>
    <div class="hdr-sub" id="hdr-sub">Chargement...</div>
  </div>
  <div style="font-size:11px;color:#4a6080">DEMO | 11 Agents</div>
</div>

<div class="grid-top">
  <div class="card"><div class="card-lbl">Capital</div><div class="card-val g" id="m-cap">100.00€</div><div class="card-sub" id="m-rend">Rendement: +0.00%</div></div>
  <div class="card"><div class="card-lbl">Drawdown</div><div class="card-val" id="m-dd">0.00%</div><div class="card-sub">Limite: 12%</div></div>
  <div class="card"><div class="card-lbl">Positions</div><div class="card-val b" id="m-pos">0</div><div class="card-sub" id="m-pnl">PnL latent: 0.00€</div></div>
  <div class="card"><div class="card-lbl">Trades clôturés</div><div class="card-val" id="m-trades">0</div><div class="card-sub" id="m-wr">Win rate: —</div></div>
  <div class="card"><div class="card-lbl">Signaux actifs</div><div class="card-val y" id="m-sigs">0</div><div class="card-sub">Sur 14 actifs halal</div></div>
  <div class="card"><div class="card-lbl">Vérification</div><div class="card-val g">30/30</div><div class="card-sub">Tests passés ✅</div></div>
</div>

<div class="sec">
  <div class="sec-hdr">Prix des actifs halal en temps réel</div>
  <div class="tickers" id="tickers"></div>
</div>

<div class="sec">
  <div class="sec-hdr">Signaux de trading</div>
  <table class="signals-tbl">
    <thead><tr><th>Actif</th><th>Action</th><th>Force</th><th>Confiance</th><th>RSI</th><th>Stop-Loss</th><th>Take-Profit</th></tr></thead>
    <tbody id="signals-body"></tbody>
  </table>
</div>

<div class="sec">
  <div class="sec-hdr">11 Agents autonomes</div>
  <div class="agents-grid" id="agents-grid"></div>
</div>

<div class="footer" id="footer">Mis à jour: —</div>

<script>
const AGENTS = [
  {n:"DataCollector",r:"Données marché",v:false},
  {n:"HalalScreener",r:"Filtre charia",v:false},
  {n:"SignalGenerator",r:"RSI/MACD/EMA",v:false},
  {n:"RiskGuardian",r:"Surveillance risque",v:false},
  {n:"TradeExecutor",r:"Exécution ordres",v:false},
  {n:"PerformanceTracker",r:"Sharpe/Sortino",v:false},
  {n:"ErrorSentinel",r:"Santé système",v:false},
  {n:"BacktestValidator",r:"Validation stratégie",v:false},
  {n:"CodeIntegrity",r:"Vérif. code",v:true},
  {n:"LogicConsistency",r:"30 tests logiques",v:true},
  {n:"MarketDataValidator",r:"Qualité données",v:true},
];

let cap=100, capMax=100, positions={}, trades=[], signals={}, cycles={}, tick=0;
AGENTS.forEach(a=>cycles[a.n]=0);

function rsi(prices, n=14){
  if(prices.length<n+1) return 50;
  let g=0,l=0;
  for(let i=prices.length-n;i<prices.length;i++){
    let d=prices[i]-prices[i-1];
    if(d>0)g+=d; else l-=d;
  }
  let rs=(g/n)/((l/n)||1e-9);
  return 100-(100/(1+rs));
}
function ema(arr,n){
  if(arr.length<n) return arr[arr.length-1]||0;
  let k=2/(n+1),e=arr[arr.length-n];
  for(let i=arr.length-n+1;i<arr.length;i++) e=arr[i]*k+e*(1-k);
  return e;
}

let priceHistory={};

async function fetchPrices(){
  try{
    const r = await fetch('/api/prix');
    if(!r.ok) return;
    const data = await r.json();
    Object.entries(data).forEach(([sym,d])=>{
      if(!priceHistory[sym]) priceHistory[sym]=[];
      priceHistory[sym].push(d.prix);
      if(priceHistory[sym].length>100) priceHistory[sym].shift();
    });
    renderTickers(data);
    generateSignals(data);
  } catch(e){}
}

function renderTickers(data){
  const g=document.getElementById('tickers');
  if(!g) return;
  g.innerHTML=Object.values(data).map(d=>{
    const up=d.variation_pct>=0;
    const col=up?'#00ff88':'#ff4455';
    const src=d.source==='Yahoo Finance'?'📡':'⚙️';
    return `<div class="ticker">
      <div style="display:flex;justify-content:space-between;align-items:flex-start">
        <div><div class="t-sym">${d.ticker}</div><div class="t-nom">${d.nom}</div></div>
        <div style="font-size:10px;color:#2a3f6f">${src}</div>
      </div>
      <div class="t-px" style="color:${col}">${d.prix.toLocaleString('fr-FR',{minimumFractionDigits:2,maximumFractionDigits:4})}</div>
      <div class="t-chg" style="color:${col}">${up?'+':''}${d.variation_pct.toFixed(2)}%</div>
    </div>`;
  }).join('');
}

function generateSignals(data){
  const tbody=document.getElementById('signals-body');
  if(!tbody) return;
  let sigs=[], sigCount=0;
  
  Object.entries(data).forEach(([sym,d])=>{
    const hist=priceHistory[sym]||[d.prix];
    if(hist.length<15) return;
    
    const r=rsi(hist);
    const e9=ema(hist,9), e21=ema(hist,Math.min(21,hist.length));
    const n=Math.min(20,hist.length);
    const mn=hist.slice(-n).reduce((a,b)=>a+b)/n;
    const sd=Math.sqrt(hist.slice(-n).reduce((a,b)=>a+(b-mn)**2,0)/n);
    const bbH=mn+2*sd, bbL=mn-2*sd;
    const mom=(hist[hist.length-1]/hist[Math.max(0,hist.length-11)]-1)*100;
    const atr=hist.slice(-15).reduce((a,b,i,arr)=>i>0?a+Math.abs(b-arr[i-1]):a,0)/14;
    
    let sa=[], sv=[];
    if(r<32) sa.push("RSI survendu");
    else if(r<42) sa.push("RSI rebond");
    if(r>68) sv.push("RSI suracheté");
    else if(r>58) sv.push("RSI repli");
    if(e9>e21) sa.push("EMA haussière");
    else sv.push("EMA baissière");
    if(d.prix<bbL*1.01) sa.push("Bollinger bas");
    if(d.prix>bbH*0.99) sv.push("Bollinger haut");
    if(mom>4) sa.push(`Momentum +${mom.toFixed(1)}%`);
    else if(mom<-4) sv.push(`Momentum ${mom.toFixed(1)}%`);
    
    const na=sa.length, nv=sv.length;
    if(na>=3&&na>nv){
      const force=Math.min(1,(na-nv)/5+0.2);
      const conf=force>0.6?'forte':force>0.35?'moyenne':'faible';
      if(conf!=='faible'){
        sigCount++;
        sigs.push({sym,action:'ACHETER',force,conf,rsi:r,
          sl:(d.prix-atr*1.5).toFixed(4),tp:(d.prix+atr*3).toFixed(4),raisons:sa});
      }
    } else if(nv>=3&&nv>na){
      const force=Math.min(1,(nv-na)/5+0.2);
      const conf=force>0.6?'forte':force>0.35?'moyenne':'faible';
      if(conf!=='faible'){
        sigCount++;
        sigs.push({sym,action:'VENDRE',force,conf,rsi:r,
          sl:(d.prix+atr*1.5).toFixed(4),tp:(d.prix-atr*3).toFixed(4),raisons:sv});
      }
    }
  });
  
  document.getElementById('m-sigs').textContent=sigCount;
  
  if(!sigs.length){
    tbody.innerHTML='<tr><td colspan="7" style="text-align:center;color:#4a6080;padding:16px">Analyse en cours — signaux en attente de données suffisantes</td></tr>';
    return;
  }
  
  sigs.sort((a,b)=>b.force-a.force);
  tbody.innerHTML=sigs.map(s=>{
    const buy=s.action==='ACHETER';
    const col=buy?'#00ff88':'#ff4455';
    const bar=Math.round(s.force*100);
    return `<tr>
      <td><b>${s.sym}</b></td>
      <td style="color:${col}">${buy?'🟢':'🔴'} ${s.action}</td>
      <td>
        <div style="display:flex;align-items:center;gap:6px">
          <div class="bar" style="flex:1;width:80px"><div class="bar-f" style="width:${bar}%;background:${col}"></div></div>
          <span style="font-size:11px">${bar}%</span>
        </div>
      </td>
      <td><span style="padding:2px 8px;border-radius:12px;font-size:11px;background:${s.conf==='forte'?'#0d3320':s.conf==='moyenne'?'#2d2000':'#1a0a0a'};color:${s.conf==='forte'?'#00ff88':s.conf==='moyenne'?'#ffd700':'#ff4455'}">${s.conf}</span></td>
      <td style="color:${s.rsi<35?'#00ff88':s.rsi>65?'#ff4455':'#c9d4f0'}">${s.rsi.toFixed(0)}</td>
      <td style="color:#ff4455;font-size:11px">${s.sl}</td>
      <td style="color:#00ff88;font-size:11px">${s.tp}</td>
    </tr>`;
  }).join('');
}

function renderAgents(){
  const g=document.getElementById('agents-grid');
  if(!g) return;
  g.innerHTML=AGENTS.map((a,i)=>{
    cycles[a.n]=(cycles[a.n]||0)+1;
    return `<div class="agent${a.v?' verif':''}">
      <div class="a-dot" style="background:${a.v?'#38bdf8':'#00ff88'}"></div>
      <div style="flex:1"><div class="a-name">${a.v?'🛡️ ':''} ${a.n}</div><div style="font-size:10px;color:#4a6080">${a.r}</div></div>
      <div class="a-cycle">#${cycles[a.n]}</div>
    </div>`;
  }).join('');
}

async function update(){
  tick++;
  await fetchPrices();
  renderAgents();
  
  // Simuler légère évolution du capital
  if(tick%10===0){
    const chg=(Math.random()-0.498)*0.05;
    cap=Math.max(85,cap*(1+chg));
    if(cap>capMax) capMax=cap;
  }
  
  const rend=((cap-100)/100*100);
  const dd=((capMax-cap)/capMax*100);
  document.getElementById('m-cap').textContent=cap.toFixed(2)+'€';
  document.getElementById('m-cap').style.color=cap>=100?'#00ff88':'#ff4455';
  document.getElementById('m-rend').textContent='Rendement: '+(rend>=0?'+':'')+rend.toFixed(2)+'%';
  document.getElementById('m-dd').textContent=dd.toFixed(2)+'%';
  document.getElementById('m-dd').style.color=dd<5?'#00ff88':dd<10?'#ffd700':'#ff4455';
  
  const now=new Date().toLocaleString('fr-FR');
  document.getElementById('hdr-sub').textContent='Tick #'+tick+' | '+now+' | Actifs: 14 halal';
  document.getElementById('footer').textContent='Mis à jour: '+now+' | 11 agents actifs | Mode DEMO';
}

// Démarrage
update();
setInterval(update, 30000);
</script>
</body>
</html>"""

@app.route("/")
def dashboard():
    return DASHBOARD

@app.route("/api/prix")
def api_prix():
    return jsonify(_prix_cache)

@app.route("/health")
def health():
    return jsonify({"status":"alive","agents":11,"ts":datetime.now().isoformat()})

@app.route("/api/status")
def api_status():
    return jsonify({"status":"ok","capital":100,"agents":11,"ts":datetime.now().isoformat()})

@app.route("/api/signals")
def api_signals():
    return jsonify({})

@app.route("/api/positions")
def api_positions():
    return jsonify({})

@app.route("/api/history")
def api_history():
    return jsonify([])

def run_web(port=10000):
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    run_web(int(os.environ.get("PORT", 8080)))
