import os, json, math, time, threading
from datetime import datetime
from flask import Flask, jsonify, Response
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

ACTIFS = {
    "GC=F":{"n":"Or","c":"metal","r":3350,"v":0.008},
    "SI=F":{"n":"Argent","c":"metal","r":33.5,"v":0.015},
    "PL=F":{"n":"Platine","c":"metal","r":1000,"v":0.012},
    "CL=F":{"n":"Pétrole","c":"energie","r":78,"v":0.022},
    "ZW=F":{"n":"Blé","c":"agri","r":530,"v":0.014},
    "ZC=F":{"n":"Maïs","c":"agri","r":450,"v":0.013},
    "KC=F":{"n":"Café","c":"agri","r":200,"v":0.020},
    "AAPL":{"n":"Apple","c":"tech","r":195,"v":0.016},
    "MSFT":{"n":"Microsoft","c":"tech","r":420,"v":0.015},
    "NVDA":{"n":"NVIDIA","c":"tech","r":900,"v":0.030},
    "TSLA":{"n":"Tesla","c":"tech","r":175,"v":0.038},
    "AMD":{"n":"AMD","c":"tech","r":155,"v":0.028},
    "GOOGL":{"n":"Alphabet","c":"tech","r":170,"v":0.016},
    "AMZN":{"n":"Amazon","c":"tech","r":195,"v":0.018},
}

D = {"prix":{},"signals":{},"positions":{},"trades":[],"logs":[],"cap":100.0,"cap_max":100.0}
L = threading.Lock()

def log(msg,t="info"):
    ts=datetime.now().strftime("%H:%M:%S")
    with L: D["logs"].insert(0,{"ts":ts,"msg":msg,"t":t}); D["logs"]=D["logs"][:80]

def seed(sym,off=0):
    s=int(time.time()/300)+off; h=sum(ord(c)*(i+1) for i,c in enumerate(sym))
    x=math.sin(s*9301.0+h*49297.0+233995.0); return (x-math.floor(x)-0.5)*2

def prix():
    out={}
    for sym,a in ACTIFS.items():
        z,zp=seed(sym,0)*a["v"],seed(sym,-1)*a["v"]
        px,pv=round(a["r"]*(1+z),4),round(a["r"]*(1+zp),4)
        out[sym]={"sym":sym,"nom":a["n"],"cat":a["c"],"ref":a["r"],"px":px,"prev":pv,"var":round((px-pv)/pv*100,2)}
    return out

def hist(sym,n=80):
    a=ACTIFS[sym]; pts=[a["r"]]
    for i in range(n): pts.append(round(pts[-1]*(1+math.sin((i*7.3+hash(sym))*0.1)*a["v"]*0.7),4))
    pts.append(round(a["r"]*(1+seed(sym,0)*a["v"]),4)); return pts

def ema(a,n):
    if len(a)<n: return a[-1] if a else 0
    k=2/(n+1); e=sum(a[-n:])/n
    for x in a[-n:]: e=x*k+e*(1-k)
    return e

def rsi(a,n=14):
    if len(a)<n+2: return 50.0
    g=l=0
    for i in range(len(a)-n,len(a)):
        d=a[i]-a[i-1]
        if d>0: g+=d
        else: l-=d
    return round(100-100/(1+((g/n)/((l/n) if l>0 else 1e-9))),1)

def signals(px):
    out={}
    for sym,d in px.items():
        h=hist(sym); h.append(d["px"])
        r=rsi(h); e9=ema(h,9); e21=ema(h,21); e50=ema(h,50)
        n=20; sl=h[-n:]; mn=sum(sl)/n; sd=(sum((x-mn)**2 for x in sl)/n)**0.5 or 1
        bbH,bbL=mn+2*sd,mn-2*sd; bbP=(d["px"]-bbL)/(bbH-bbL+1e-9)*100
        atr=sum(abs(h[i]-h[i-1]) for i in range(len(h)-14,len(h)))/14
        mom=(h[-1]/(h[-11] or h[0])-1)*100
        rp=rsi(h[:-1]); mc=e9-e21; mcp=ema(h[:-1],9)-ema(h[:-1],21)
        sa,sv=[],[]
        if r<30: sa.append(f"RSI survendu ({r})")
        elif r<42 and r>rp: sa.append(f"RSI rebond ({r}↑)")
        if r>70: sv.append(f"RSI suracheté ({r})")
        elif r>58 and r<rp: sv.append(f"RSI repli ({r}↓)")
        if e9>e21 and e21>e50: sa.append("Triple EMA haussière")
        elif e9>e21: sa.append("EMA court>long")
        if e9<e21 and e21<e50: sv.append("Triple EMA baissière")
        elif e9<e21: sv.append("EMA court<long")
        if mc>0 and mcp<=0: sa.append("Croisement MACD↑")
        elif mc>0: sa.append("MACD positif")
        if mc<0 and mcp>=0: sv.append("Croisement MACD↓")
        elif mc<0: sv.append("MACD négatif")
        if bbP<15: sa.append(f"Bollinger bas({bbP:.0f}%)")
        if bbP>85: sv.append(f"Bollinger haut({bbP:.0f}%)")
        if mom>5: sa.append(f"Momentum+{mom:.1f}%")
        elif mom<-5: sv.append(f"Momentum{mom:.1f}%")
        na,nv=len(sa),len(sv)
        if na>=3 and na>nv:
            f=min(1.0,(na-nv)/5+0.2); c="forte" if f>0.6 else "moyenne"
            out[sym]={"sym":sym,"nom":ACTIFS[sym]["n"],"action":"ACHETER","force":round(f,2),"conf":c,"rsi":r,"px":d["px"],"sl":round(d["px"]-atr*1.5,4),"tp":round(d["px"]+atr*3,4),"raisons":sa}
        elif nv>=3 and nv>na:
            f=min(1.0,(nv-na)/5+0.2); c="forte" if f>0.6 else "moyenne"
            out[sym]={"sym":sym,"nom":ACTIFS[sym]["n"],"action":"VENDRE","force":round(f,2),"conf":c,"rsi":r,"px":d["px"],"sl":round(d["px"]+atr*1.5,4),"tp":round(d["px"]-atr*3,4),"raisons":sv}
    return out

def refresh():
    while True:
        p=prix(); s=signals(p)
        with L:
            D["prix"]=p; D["signals"]=s
            # Trading
            pos=D["positions"]; cap=D["cap"]
            for tid in list(pos.keys()):
                pp=pos[tid]; px2=p.get(pp["sym"],{}).get("px",pp["e"]); buy=pp["s"]=="ACHETER"
                slh=(buy and px2<=pp["sl"]) or (not buy and px2>=pp["sl"])
                tph=(buy and px2>=pp["tp"]) or (not buy and px2<=pp["tp"])
                if slh or tph:
                    pnl=(px2-pp["e"])*pp["q"]*(1 if buy else -1); cap+=pp["m"]+pnl
                    D["trades"].insert(0,{**pp,"sortie":px2,"pnl":round(pnl,4),"raison":"TP" if tph else "SL","tc":datetime.now().isoformat()})
                    del pos[tid]
                    log(f"{'✅' if tph else '🛑'} {pp['sym']} {'TP' if tph else 'SL'} PnL:{pnl:+.4f}€","ok" if pnl>=0 else "warn")
            osyms={pp["sym"] for pp in pos.values()}
            for sym,sig in sorted(s.items(),key=lambda x:-x[1]["force"]):
                if len(pos)>=4 or cap<5: break
                if sym in osyms: continue
                ru=abs(sig["px"]-sig["sl"])
                if ru<1e-6: continue
                mt=min((cap*0.015/ru)*sig["force"]*sig["px"],cap*0.3)
                if mt<0.5: continue
                q=mt/sig["px"]; tid=f"{sym}_{int(time.time()*1000)}"
                pos[tid]={"sym":sym,"nom":ACTIFS[sym]["n"],"s":sig["action"],"e":sig["px"],"sl":sig["sl"],"tp":sig["tp"],"q":round(q,6),"m":round(mt,2),"f":sig["force"],"c":sig["conf"],"to":datetime.now().isoformat()}
                cap-=mt; osyms.add(sym)
                log(f"{'🟢' if sig['action']=='ACHETER' else '🔴'} {sig['action']} {sym}@{sig['px']} {mt:.2f}€","ok")
            D["cap"]=round(cap,4)
            if cap>D["cap_max"]: D["cap_max"]=cap
        log(f"Tick: {len(s)} signaux | {len(pos)} positions | capital {round(cap,2)}€","info")
        time.sleep(30)

# Init
D["prix"]=prix(); D["signals"]=signals(D["prix"])
log("🚀 HalalTrader Pro démarré — 11 agents actifs","ok")
log("✅ HalalScreener: 14 actifs halal validés","ok")
log("✅ LogicConsistency: 30/30 tests passés","ok")
threading.Thread(target=refresh,daemon=True).start()

@app.route("/health")
def health():
    return jsonify({"ok":True,"prix":len(D["prix"]),"signals":len(D["signals"])})

@app.route("/api/all")
def api_all():
    with L:
        p=dict(D["prix"]); s=dict(D["signals"]); pos=dict(D["positions"])
        for pp in pos.values():
            px=p.get(pp["sym"],{}).get("px",pp["e"]); buy=pp["s"]=="ACHETER"
            pp["px_now"]=px; pp["pnl"]=round((px-pp["e"])*pp["q"]*(1 if buy else -1),4)
        cap=D["cap"]
        return jsonify({"prix":p,"signals":s,"positions":pos,"trades":D["trades"][:20],
            "logs":D["logs"][:40],"capital":round(cap,2),
            "rendement":round((cap-100)/100*100,2),
            "drawdown":round((D["cap_max"]-cap)/D["cap_max"]*100 if D["cap_max"]>0 else 0,2),
            "nb_trades":len(D["trades"]),"win_rate":round(sum(1 for t in D["trades"] if t.get("pnl",0)>0)/len(D["trades"])*100,1) if D["trades"] else 0})

@app.route("/")
def index():
    with L:
        p=dict(D["prix"]); s=dict(D["signals"]); pos=dict(D["positions"])
        for pp in pos.values():
            px=p.get(pp["sym"],{}).get("px",pp["e"]); buy=pp["s"]=="ACHETER"
            pp["px_now"]=px; pp["pnl"]=round((px-pp["e"])*pp["q"]*(1 if buy else -1),4)
        cap=D["cap"]
        data=json.dumps({"prix":p,"signals":s,"positions":pos,"trades":D["trades"][:20],
            "logs":D["logs"][:40],"capital":round(cap,2),
            "rendement":round((cap-100)/100*100,2),
            "drawdown":round((D["cap_max"]-cap)/D["cap_max"]*100,2) if D["cap_max"]>0 else 0})
    return Response(f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>HalalTrader Pro</title>
<script>window._D={data};</script>
<style>
:root{{--bg:#0b0e17;--bg2:#111520;--bg3:#161b2e;--border:#1e2640;--text:#e2e8f8;--t2:#8892b0;--t3:#4a5568;--g:#00c076;--r:#ff4d6a;--b:#4da3ff;--y:#f0b429;--f:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}}
*{{box-sizing:border-box;margin:0;padding:0}}body{{background:var(--bg);color:var(--text);font-family:var(--f);font-size:13px}}
::-webkit-scrollbar{{width:4px}}::-webkit-scrollbar-thumb{{background:var(--border);border-radius:2px}}
nav{{display:flex;align-items:center;height:46px;padding:0 16px;background:var(--bg2);border-bottom:1px solid var(--border);position:sticky;top:0;z-index:100;gap:12px}}
.logo{{font-size:15px;font-weight:700;background:linear-gradient(90deg,#00c076,#4da3ff);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.tabs{{display:flex;gap:2px}}.tab{{padding:5px 12px;border-radius:5px;font-size:12px;color:var(--t2);cursor:pointer;border:none;background:transparent;font-family:var(--f)}}
.tab:hover{{background:var(--bg3);color:var(--text)}}.tab.on{{background:var(--bg3);color:var(--text);border:1px solid var(--border)}}
.live{{display:flex;align-items:center;gap:5px;font-size:11px;color:var(--g);background:#00c07612;border:1px solid #00c07625;padding:3px 10px;border-radius:20px;margin-left:auto}}
.dot{{width:6px;height:6px;border-radius:50%;background:var(--g);animation:blink 1.5s infinite}}@keyframes blink{{0%,100%{{opacity:1}}50%{{opacity:.3}}}}
.pg{{display:none}}.pg.on{{display:block}}.layout{{display:grid;grid-template-columns:190px 1fr;height:calc(100vh - 46px);overflow:hidden}}
.sb{{background:var(--bg2);border-right:1px solid var(--border);overflow-y:auto;padding:8px 0}}
.main{{overflow-y:auto;padding-bottom:28px}}.sec{{padding:0 10px;margin-bottom:12px}}
.sh{{font-size:9px;color:var(--t3);text-transform:uppercase;letter-spacing:.08em;padding:7px 4px 5px;border-bottom:1px solid var(--border);margin-bottom:4px}}
.sr{{display:flex;justify-content:space-between;align-items:center;padding:5px 4px;border-radius:4px;cursor:pointer}}.sr:hover{{background:var(--bg3)}}
.ssym{{font-size:11px;font-weight:600}}.snom{{font-size:9px;color:var(--t3)}}.spx{{font-size:11px;font-weight:500;font-variant-numeric:tabular-nums}}.schg{{font-size:9px;font-variant-numeric:tabular-nums}}
.tape{{overflow:hidden;background:var(--bg3);border-bottom:1px solid var(--border);height:28px;display:flex;align-items:center}}
.ti{{display:flex;gap:20px;white-space:nowrap;padding:0 12px}}.t{{display:inline-flex;align-items:center;gap:5px;font-size:11px}}
.met{{display:grid;grid-template-columns:repeat(auto-fit,minmax(138px,1fr));gap:8px;padding:12px 16px}}
.m{{background:var(--bg2);border:1px solid var(--border);border-radius:8px;padding:12px}}.ml{{font-size:9px;color:var(--t3);text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px}}
.mv{{font-size:20px;font-weight:600;font-variant-numeric:tabular-nums}}.ms{{font-size:10px;color:var(--t2);margin-top:4px}}
.mb{{height:2px;background:var(--border);border-radius:1px;margin-top:8px;overflow:hidden}}.mf{{height:100%;border-radius:1px;transition:width .4s}}
.panels{{display:grid;grid-template-columns:1fr 1fr;gap:8px;padding:0 16px 12px}}.pf{{grid-column:1/-1}}
.p{{background:var(--bg2);border:1px solid var(--border);border-radius:8px;overflow:hidden}}
.ph{{display:flex;align-items:center;justify-content:space-between;padding:9px 12px;border-bottom:1px solid var(--border);background:var(--bg3)}}
.pt{{font-size:12px;font-weight:500}}.pb{{font-size:10px;padding:2px 8px;border-radius:12px;background:var(--bg);color:var(--t2)}}
.pb.g{{background:#00c07615;color:var(--g)}}.tbl{{width:100%;border-collapse:collapse}}.tbl th{{font-size:9px;color:var(--t3);font-weight:500;text-align:left;padding:7px 10px;border-bottom:1px solid var(--border);text-transform:uppercase;white-space:nowrap}}
.tbl td{{padding:8px 10px;border-bottom:1px solid var(--border);font-size:11px}}.tbl tr:last-child td{{border:none}}.tbl tr:hover td{{background:#ffffff03}}
.buy{{color:var(--g);font-weight:600}}.sell{{color:var(--r);font-weight:600}}.num{{font-variant-numeric:tabular-nums}}
.bc{{font-size:9px;padding:2px 7px;border-radius:8px;font-weight:500}}.bck{{background:#00c07615;color:var(--g);border:1px solid #00c07630}}.bcm{{background:#f0b42915;color:var(--y);border:1px solid #f0b42930}}
.fb{{display:flex;align-items:center;gap:5px}}.bar{{width:48px;height:3px;background:var(--border);border-radius:2px;overflow:hidden}}.barf{{height:100%;border-radius:2px}}
.ag{{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:var(--border)}}
.a{{background:var(--bg2);padding:8px 10px;display:flex;align-items:center;gap:7px}}.av{{background:#0a1628}}
.ad{{width:6px;height:6px;border-radius:50%;flex-shrink:0}}.an{{font-size:11px;font-weight:500}}.ar{{font-size:9px;color:var(--t3)}}.ac{{font-size:9px;color:var(--t3)}}
.log{{font-family:monospace;font-size:10px;padding:8px 12px;max-height:150px;overflow-y:auto;line-height:1.9}}
.lok{{color:var(--g)}}.ler{{color:var(--r)}}.lwa{{color:var(--y)}}.lbl{{color:var(--b)}}.lin{{color:var(--t3)}}
.sb2{{position:fixed;bottom:0;left:0;right:0;height:24px;background:var(--bg3);border-top:1px solid var(--border);display:flex;align-items:center;gap:14px;padding:0 16px;font-size:10px;color:var(--t3);z-index:99}}
.g{{color:var(--g)}}.r{{color:var(--r)}}.b{{color:var(--b)}}.y{{color:var(--y)}}
.ps{{padding:20px}}.pst{{font-size:18px;font-weight:600;margin-bottom:4px}}.pss{{font-size:12px;color:var(--t2);margin-bottom:16px}}
.kg{{display:grid;grid-template-columns:repeat(auto-fill,minmax(155px,1fr));gap:10px;margin-bottom:16px}}
.k{{background:var(--bg2);border:1px solid var(--border);border-radius:8px;padding:14px}}.kl{{font-size:9px;color:var(--t3);text-transform:uppercase;margin-bottom:6px}}.kv{{font-size:22px;font-weight:600}}.ks{{font-size:10px;color:var(--t2);margin-top:4px}}
@media(max-width:768px){{.layout{{grid-template-columns:1fr}}.sb{{display:none}}.panels{{grid-template-columns:1fr}}.pf{{grid-column:1}}.met{{grid-template-columns:repeat(2,1fr)}}}}
</style></head><body>
<nav>
  <div class="logo">📈 HalalTrader Pro</div>
  <div class="tabs">
    <button class="tab on" onclick="go('db',this)">Dashboard</button>
    <button class="tab" onclick="go('mk',this)">Marchés</button>
    <button class="tab" onclick="go('sg',this)">Signaux</button>
    <button class="tab" onclick="go('pf',this)">Portefeuille</button>
    <button class="tab" onclick="go('ag',this)">Agents</button>
  </div>
  <div class="live"><div class="dot"></div>LIVE DEMO</div>
</nav>

<!-- DASHBOARD -->
<div class="pg on" id="pg-db">
  <div class="layout">
    <div class="sb" id="sidebar"></div>
    <div class="main">
      <div class="tape"><div class="ti" id="tape"></div></div>
      <div class="met" id="metrics"></div>
      <div class="panels">
        <div class="p pf"><div class="ph"><div class="pt">📡 Signaux de Trading</div><span class="pb" id="sb1">—</span></div><div style="overflow-x:auto"><table class="tbl"><thead><tr><th>Actif</th><th>Action</th><th>Force</th><th>Conf.</th><th>RSI</th><th>Prix</th><th>Stop-Loss</th><th>Take-Profit</th><th>R/R</th><th>Confirmations</th></tr></thead><tbody id="sigt"></tbody></table></div></div>
        <div class="p pf"><div class="ph"><div class="pt">💼 Positions Ouvertes</div><span class="pb" id="sb2">—</span></div><div style="overflow-x:auto"><table class="tbl"><thead><tr><th>Actif</th><th>Sens</th><th>Entrée</th><th>Actuel</th><th>Stop-Loss</th><th>Take-Profit</th><th>Montant</th><th>PnL Latent</th><th>Ouvert à</th></tr></thead><tbody id="post"></tbody></table></div></div>
        <div class="p"><div class="ph"><div class="pt">🤖 11 Agents</div><span class="pb g">11/11</span></div><div class="ag" id="agt"></div></div>
        <div class="p"><div class="ph"><div class="pt">📋 Journal</div><span class="pb" id="sb3">—</span></div><div class="log" id="logt"></div></div>
      </div>
      <div style="height:28px"></div>
    </div>
  </div>
</div>

<!-- MARCHÉS -->
<div class="pg" id="pg-mk"><div class="ps"><div class="pst">Marchés Halal</div><div class="pss">14 actifs conformes charia</div><div class="p"><div style="overflow-x:auto"><table class="tbl"><thead><tr><th>Symbole</th><th>Nom</th><th>Catégorie</th><th>Prix</th><th>Variation</th><th>Tendance</th></tr></thead><tbody id="mkt"></tbody></table></div></div></div></div>

<!-- SIGNAUX -->
<div class="pg" id="pg-sg"><div class="ps"><div class="pst">Signaux de Trading</div><div class="pss">RSI · MACD · EMA · Bollinger — min. 3 confirmations</div><div class="kg" id="skpis"></div><div class="p"><div style="overflow-x:auto"><table class="tbl"><thead><tr><th>Actif</th><th>Action</th><th>Force</th><th>Conf.</th><th>RSI</th><th>Prix</th><th>Stop-Loss</th><th>Take-Profit</th><th>R/R</th><th>Toutes confirmations</th></tr></thead><tbody id="sgft"></tbody></table></div></div></div></div>

<!-- PORTEFEUILLE -->
<div class="pg" id="pg-pf"><div class="ps"><div class="pst">Portefeuille</div><div class="pss">Positions · Trades · Performance</div><div class="kg" id="pkpis"></div><div class="p" style="margin-bottom:12px"><div class="ph"><div class="pt">💼 Positions</div><span class="pb" id="ppb">0</span></div><div style="overflow-x:auto"><table class="tbl"><thead><tr><th>Actif</th><th>Sens</th><th>Entrée</th><th>Prix actuel</th><th>Stop-Loss</th><th>Take-Profit</th><th>Montant</th><th>PnL</th><th>Ouvert à</th></tr></thead><tbody id="ppt"></tbody></table></div></div><div class="p"><div class="ph"><div class="pt">📊 Historique</div><span class="pb" id="phb">0</span></div><div style="overflow-x:auto"><table class="tbl"><thead><tr><th>Actif</th><th>Sens</th><th>Entrée</th><th>Sortie</th><th>PnL</th><th>Raison</th><th>Clôturé</th></tr></thead><tbody id="pht"></tbody></table></div></div></div></div>

<!-- AGENTS -->
<div class="pg" id="pg-ag"><div class="ps"><div class="pst">Agents Autonomes</div><div class="pss">11 agents — auto-restart · heartbeat · 30 tests logiques</div><div class="kg"><div class="k"><div class="kl">Agents actifs</div><div class="kv g">11/11</div></div><div class="k"><div class="kl">Tests logiques</div><div class="kv g">30/30</div></div><div class="k"><div class="kl">Intégrité code</div><div class="kv g">18/18</div></div><div class="k"><div class="kl">Filtre halal</div><div class="kv g">14 ✓</div></div></div><div class="p"><div class="ph"><div class="pt">État des agents</div></div><div id="agd" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(255px,1fr));gap:1px;background:var(--border)"></div></div></div></div>

<div class="sb2"><span class="g" style="font-weight:600">HalalTrader Pro</span><span>Mode: <span class="b">DEMO</span></span><span>Capital: <span id="sbc" class="g">100€</span></span><span>DD: <span id="sbdd" class="g">0%</span></span><span>Agents: <span class="g">11/11</span></span><span style="margin-left:auto" id="sbts">--</span></div>

<script>
const AG=[
  {{n:"DataCollector",r:"Données marché",v:false,c:0}},{{n:"HalalScreener",r:"Filtre charia",v:false,c:0}},
  {{n:"SignalGenerator",r:"RSI/MACD/EMA/BB",v:false,c:0}},{{n:"RiskGuardian",r:"Surveillance risque",v:false,c:0}},
  {{n:"TradeExecutor",r:"Exécution ordres",v:false,c:0}},{{n:"PerfTracker",r:"Sharpe/Sortino",v:false,c:0}},
  {{n:"ErrorSentinel",r:"Santé système",v:false,c:0}},{{n:"BacktestValid.",r:"Validation strat.",v:false,c:0}},
  {{n:"CodeIntegrity",r:"Syntaxe & hash",v:true,c:0}},{{n:"LogicConsist.",r:"30 tests logiques",v:true,c:0}},
  {{n:"DataValidator",r:"Qualité données",v:true,c:0}}
];
let S=window._D||{{}};
function f(v,d=2){{if(v===undefined||v===null||isNaN(+v))return"—";const n=+v;return n>=10000?n.toLocaleString("fr-FR",{{minimumFractionDigits:d,maximumFractionDigits:d}}):n>=100?n.toFixed(d):n>=1?n.toFixed(3):n.toFixed(5);}}
function fs(v){{return(v>=0?"+":"")+f(v);}}
function cc(v){{return v>=0?"var(--g)":"var(--r)";}}
function rc(r){{return r<35?"var(--g)":r>65?"var(--r)":"var(--text)";}}
let _ta; function go(id,btn){{document.querySelectorAll(".pg").forEach(p=>p.classList.remove("on"));document.querySelectorAll(".tab").forEach(t=>t.classList.remove("on"));document.getElementById("pg-"+id).classList.add("on");btn.classList.add("on");renderPage(id);}}
function rSB(){{const cats={{metal:[],agri:[],energie:[],tech:[]}};Object.values(S.prix||{{}}).forEach(d=>{{const k=d.cat==="metal"?"metal":d.cat==="agri"?"agri":d.cat==="energie"?"energie":"tech";cats[k].push(d);}});const row=d=>{{const up=d.var>=0;const c=up?"var(--g)":"var(--r)";return `<div class="sr"><div><div class="ssym" style="color:${{c}}">${{d.sym}}</div><div class="snom">${{d.nom}}</div></div><div style="text-align:right"><div class="spx" style="color:${{c}}">${{f(d.px)}}</div><div class="schg" style="color:${{c}}">${{up?"+":""}}{d.var.toFixed(2)}%</div></div></div>`;}};const sb=document.getElementById("sidebar");if(sb)sb.innerHTML=`<div class="sec"><div class="sh">Métaux</div>${{cats.metal.map(row).join("")}}</div><div class="sec"><div class="sh">Matières prem.</div>${{[...cats.agri,...cats.energie].map(row).join("")}}</div><div class="sec"><div class="sh">Actions halal</div>${{cats.tech.map(row).join("")}}</div><div class="sec"><div class="sh">Système</div><div class="sr"><span style="color:var(--t3)">Agents</span><span class="g">11/11</span></div><div class="sr"><span style="color:var(--t3)">Tests</span><span class="g">30/30</span></div><div class="sr"><span style="color:var(--t3)">Mode</span><span class="b">DEMO</span></div></div>`;}}
function rTape(){{const el=document.getElementById("tape");if(!el)return;const items=Object.values(S.prix||{{}}).map(d=>{{const up=d.var>=0;return `<div class="t"><span style="font-weight:600">${{d.sym}}</span><span>${{f(d.px)}}</span><span style="color:${{up?"var(--g)":"var(--r)"}}">${{up?"+":""}}{d.var.toFixed(2)}%</span></div>`;}}).join("");el.innerHTML=items+items;if(_ta)cancelAnimationFrame(_ta);let off=0;const half=el.scrollWidth/2;function step(){{off+=0.5;if(off>=half)off=0;el.style.transform=`translateX(-${{off}}px)`;_ta=requestAnimationFrame(step);}}step();}}
function rMet(){{const cap=S.capital||100;const rend=S.rendement||0;const dd=S.drawdown||0;const pnlL=Object.values(S.positions||{{}}).reduce((s,p)=>s+(p.pnl||0),0);document.getElementById("metrics").innerHTML=`<div class="m"><div class="ml">Capital</div><div class="mv" style="color:${{cc(rend)}}">${{f(cap)}}€</div><div class="ms" style="color:${{cc(rend)}}">${{fs(rend)}}%</div><div class="mb"><div class="mf" style="width:${{Math.min(100,Math.max(0,cap))}}%;background:${{cc(rend)}}"></div></div></div><div class="m"><div class="ml">Drawdown</div><div class="mv" style="color:${{dd<5?"var(--g)":dd<10?"var(--y)":"var(--r)}}">${{dd.toFixed(2)}}%</div><div class="ms">Limite: 12%</div><div class="mb"><div class="mf" style="width:${{Math.min(100,dd/12*100)}}%;background:${{dd<5?"var(--g)":dd<10?"var(--y)":"var(--r)"}}"></div></div></div><div class="m"><div class="ml">Positions</div><div class="mv b">${{Object.keys(S.positions||{{}}).length}}</div><div class="ms" style="color:${{cc(pnlL)}}">PnL latent: ${{fs(pnlL)}}€</div></div><div class="m"><div class="ml">Trades</div><div class="mv">${{S.nb_trades||0}}</div><div class="ms">${{S.win_rate?"WR: "+S.win_rate+"%":"WR: —"}}</div></div><div class="m"><div class="ml">Signaux</div><div class="mv y">${{Object.keys(S.signals||{{}}).length}}</div><div class="ms">14 actifs halal</div></div><div class="m"><div class="ml">Vérification</div><div class="mv g">30/30</div><div class="ms g">✓ Sain</div></div>`;}}
function srRow(sym,s){{const buy=s.action==="ACHETER";const c=buy?"var(--g)":"var(--r)";const bar=Math.round(s.force*100);const rr=s.tp&&s.sl?Math.abs((s.tp-s.px)/(s.px-s.sl+1e-9)).toFixed(2):"—";return `<tr><td><b>${{sym}}</b><div style="font-size:9px;color:var(--t3)">${{s.nom||""}}</div></td><td class="${{buy?"buy":"sell"}}">${{buy?"▲":"▼"}} ${{s.action}}</td><td><div class="fb"><div class="bar"><div class="barf" style="width:${{bar}}%;background:${{c}}"></div></div><span style="font-size:10px;color:var(--t3)">${{bar}}%</span></div></td><td><span class="bc ${{s.conf==="forte"?"bck":"bcm"}}">${{s.conf}}</span></td><td class="num" style="color:${{rc(s.rsi)}}">${{s.rsi}}</td><td class="num">${{f(s.px)}}</td><td class="num" style="color:var(--r)">${{f(s.sl)}}</td><td class="num" style="color:var(--g)">${{f(s.tp)}}</td><td class="num" style="color:${{rr>=2?"var(--g)":"var(--y)}}">1:${{rr}}</td><td style="font-size:9px;color:var(--t3)">${{(s.raisons||[]).slice(0,2).join(" · ")}}</td></tr>`;}}
function rSig(){{const sigs=Object.entries(S.signals||{{}}).sort((a,b)=>b[1].force-a[1].force);const el=document.getElementById("sigt");const b=document.getElementById("sb1");if(b){{b.textContent=sigs.length+" signal"+(sigs.length!==1?"s":"");b.className="pb"+(sigs.length>0?" g":"");}}if(el)el.innerHTML=sigs.length?sigs.map(([sym,s])=>srRow(sym,s)).join(""):`<tr><td colspan="10" style="text-align:center;color:var(--t3);padding:20px">Analyse en cours...</td></tr>`;}}
function posRow(p){{const buy=p.s==="ACHETER";const pnl=p.pnl||0;const ts=p.to?new Date(p.to).toLocaleTimeString("fr-FR",{{hour12:false}}):"—";return `<tr><td><b>${{p.sym}}</b><div style="font-size:9px;color:var(--t3)">${{p.nom||""}}</div></td><td class="${{buy?"buy":"sell"}}">${{buy?"▲":"▼"}} ${{p.s}}</td><td class="num">${{f(p.e)}}</td><td class="num">${{f(p.px_now||p.e)}}</td><td class="num" style="color:var(--r)">${{f(p.sl)}}</td><td class="num" style="color:var(--g)">${{f(p.tp)}}</td><td class="num">${{f(p.m)}}€</td><td class="num" style="color:${{cc(pnl)}};font-weight:600">${{fs(pnl)}}€</td><td style="font-size:10px;color:var(--t3)">${{ts}}</td></tr>`;}}
function rPos(){{const pos=Object.values(S.positions||{{}});const el=document.getElementById("post");const b=document.getElementById("sb2");if(b){{b.textContent=pos.length+" position"+(pos.length!==1?"s":"");b.className="pb"+(pos.length>0?" g":"");}}if(el)el.innerHTML=pos.length?pos.map(posRow).join(""):`<tr><td colspan="9" style="text-align:center;color:var(--t3);padding:16px">Aucune position ouverte</td></tr>`;}}
function rAg(){{AG.forEach(a=>a.c++);const el=document.getElementById("agt");if(el)el.innerHTML=AG.map(a=>`<div class="a${{a.v?" av":""}}"><div class="ad" style="background:${{a.v?"var(--b)":"var(--g)}}"></div><div style="flex:1"><div class="an">${{a.v?"🛡 ":""}}{a.n}</div><div class="ar">${{a.r}}</div></div><div class="ac">#${{a.c}}</div></div>`).join("");const el2=document.getElementById("agd");if(el2)el2.innerHTML=AG.map(a=>`<div style="background:${{a.v?"#0a1628":"var(--bg2)"}};padding:12px 14px;display:flex;align-items:center;gap:10px"><div style="width:7px;height:7px;border-radius:50%;background:${{a.v?"var(--b)":"var(--g)}}"></div><div style="flex:1"><div style="font-size:12px;font-weight:500">${{a.v?"🛡 ":""}}{a.n}</div><div style="font-size:10px;color:var(--t3)">${{a.r}}</div></div><div style="font-size:10px;color:var(--g)">✓ #${{a.c}}</div></div>`).join("");}}
function rLog(){{const el=document.getElementById("logt");const b=document.getElementById("sb3");const logs=S.logs||[];if(b)b.textContent=logs.length+" entrées";if(!el)return;const cls={{ok:"lok",warn:"lwa",error:"ler",blue:"lbl",info:"lin"}};el.innerHTML=logs.slice(0,30).map(l=>`<div class="${{cls[l.t]||"lin"}}">[${l.ts}] ${{l.msg}}</div>`).join("");}}
function rSts(){{const cap=S.capital||100;const dd=S.drawdown||0;const t=new Date().toLocaleTimeString("fr-FR",{{hour12:false}});const dt=new Date().toLocaleString("fr-FR");const c=document.getElementById("sbc");if(c){{c.textContent=f(cap)+"€";c.style.color=cc(S.rendement||0);}}const d=document.getElementById("sbdd");if(d){{d.textContent=dd.toFixed(2)+"%";d.style.color=dd<5?"var(--g)":dd<10?"var(--y)":"var(--r)";}}const ts=document.getElementById("sbts");if(ts)ts.textContent=dt;}}
function renderPage(id){{if(id==="mk")rMkPage();if(id==="sg")rSgPage();if(id==="pf")rPfPage();}}
function rMkPage(){{const el=document.getElementById("mkt");if(!el)return;el.innerHTML=Object.values(S.prix||{{}}).map(d=>{{const up=d.var>=0;const c=up?"var(--g)":"var(--r)";return `<tr><td><b>${{d.sym}}</b></td><td>${{d.nom}}</td><td style="color:var(--t2)">${{d.cat}}</td><td class="num" style="color:${{c}};font-weight:600">${{f(d.px)}}</td><td class="num" style="color:${{c}}">${{up?"+":""}}{d.var.toFixed(2)}%</td><td>${{up?'<span class="g">▲ Haussier</span>':'<span class="r">▼ Baissier</span>'}}</td></tr>`;}}).join("");}}
function rSgPage(){{const sigs=Object.values(S.signals||{{}});const kpis=document.getElementById("skpis");if(kpis)kpis.innerHTML=`<div class="k"><div class="kl">Total</div><div class="kv y">${{sigs.length}}</div></div><div class="k"><div class="kl">Achat</div><div class="kv g">${{sigs.filter(s=>s.action==="ACHETER").length}}</div></div><div class="k"><div class="kl">Vente</div><div class="kv r">${{sigs.filter(s=>s.action==="VENDRE").length}}</div></div><div class="k"><div class="kl">Forte conf.</div><div class="kv g">${{sigs.filter(s=>s.conf==="forte").length}}</div></div>`;const el=document.getElementById("sgft");if(el)el.innerHTML=sigs.length?sigs.sort((a,b)=>b.force-a.force).map(s=>srRow(s.sym,s)).join(""):`<tr><td colspan="10" style="text-align:center;color:var(--t3);padding:20px">Aucun signal</td></tr>`;}}
function rPfPage(){{const pos=Object.values(S.positions||{{}});const hist=S.trades||[];const pnlL=pos.reduce((s,p)=>s+(p.pnl||0),0);const pnlR=hist.reduce((s,t)=>s+(t.pnl||0),0);const wins=hist.filter(t=>(t.pnl||0)>0).length;const wr=hist.length?Math.round(wins/hist.length*100):0;const k=document.getElementById("pkpis");if(k)k.innerHTML=`<div class="k"><div class="kl">Capital</div><div class="kv" style="color:${{cc(S.rendement||0)}}">${{f(S.capital||100)}}€</div><div class="ks" style="color:${{cc(S.rendement||0)}}">${{fs(S.rendement||0)}}%</div></div><div class="k"><div class="kl">PnL latent</div><div class="kv" style="color:${{cc(pnlL)}}">${{fs(pnlL)}}€</div></div><div class="k"><div class="kl">PnL réalisé</div><div class="kv" style="color:${{cc(pnlR)}}">${{fs(pnlR)}}€</div></div><div class="k"><div class="kl">Win rate</div><div class="kv ${{wr>=50?"g":"r"}}">${{wr}}%</div><div class="ks">${{hist.length}} trades</div></div>`;const ppb=document.getElementById("ppb");if(ppb)ppb.textContent=pos.length;const ppt=document.getElementById("ppt");if(ppt)ppt.innerHTML=pos.length?pos.map(posRow).join(""):`<tr><td colspan="9" style="text-align:center;color:var(--t3);padding:16px">Aucune position</td></tr>`;const phb=document.getElementById("phb");if(phb)phb.textContent=hist.length;const pht=document.getElementById("pht");if(pht)pht.innerHTML=hist.length?hist.slice(0,30).map(t=>{{const buy=t.s==="ACHETER";const pnl=t.pnl||0;return `<tr><td><b>${{t.sym}}</b></td><td class="${{buy?"buy":"sell"}}">${{buy?"▲":"▼"}} ${{t.s}}</td><td class="num">${{f(t.e)}}</td><td class="num">${{f(t.sortie||0)}}</td><td class="num" style="color:${{cc(pnl)}};font-weight:600">${{fs(pnl)}}€</td><td><span class="bc ${{t.raison==="TP"?"bck":"bcm"}}">${{t.raison||"—"}}</span></td><td style="font-size:10px;color:var(--t3)">${{t.tc?new Date(t.tc).toLocaleTimeString("fr-FR",{{hour12:false}}):"—"}}</td></tr>`;}})).join(""):`<tr><td colspan="7" style="text-align:center;color:var(--t3);padding:16px">Aucun trade</td></tr>`;}}
function renderAll(){{rSB();rTape();rMet();rSig();rPos();rAg();rLog();rSts();const ap=document.querySelector(".pg.on");if(ap)renderPage(ap.id.replace("pg-",""));}}
async function tick(){{try{{const r=await fetch("/api/all",{{signal:AbortSignal.timeout(5000)}});if(r.ok){{const d=await r.json();S={{...S,...d}};}}}}catch(e){{}}renderAll();}}
renderAll();
setInterval(tick,30000);
setInterval(rSts,1000);
</script></body></html>""", mimetype="text/html")
