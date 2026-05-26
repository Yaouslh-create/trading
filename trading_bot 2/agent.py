"""
Agent IA de Trading Halal — Cerveau principal
Inspiré de Jim Simons / Renaissance Technologies
Capital : 100€ | Mode : DÉMO d'abord
"""

import time
import sys
import os
from datetime import datetime
from colorama import Fore, Style, init

init(autoreset=True)

sys.path.insert(0, os.path.dirname(__file__))
from core.halal_filter   import est_halal, get_univers_halal, ACTIFS_HALAL_VALIDES
from data.market_data    import fetch_prix, get_prix_actuel, fetch_prix_intraday
from strategies.indicators import generer_signal
from risk.risk_manager   import GestionnaireRisque
from broker.demo_broker  import BrokerDemo


# ─── Configuration ────────────────────────────────────────────────────────────

CAPITAL_INITIAL    = 100.0
MODE               = "DEMO"          # "DEMO" ou "REEL" (ne pas changer sans tests)
INTERVALLE_SCAN    = 300             # Scan toutes les 5 minutes
UNIVERS_ACTIFS     = [
    "GC=F",   # Or
    "SI=F",   # Argent
    "AAPL",   # Apple
    "MSFT",   # Microsoft
    "NVDA",   # NVIDIA
    "TSLA",   # Tesla
    "AMD",    # AMD
    "GOOGL",  # Alphabet
]

# ─── Classe Agent ─────────────────────────────────────────────────────────────

class AgentTradingHalal:

    def __init__(self):
        print(self._header())
        self.broker     = BrokerDemo(CAPITAL_INITIAL)
        self.risk       = GestionnaireRisque(CAPITAL_INITIAL)
        self.cycle      = 0
        self.signaux_log = []

    def _header(self) -> str:
        return f"""
{Fore.GREEN}╔══════════════════════════════════════════════════════════╗
║          AGENT IA DE TRADING HALAL — SIMONS METHOD          ║
║      Capital : {CAPITAL_INITIAL}€  |  Mode : {MODE}  |  v1.0          ║
╚══════════════════════════════════════════════════════════════╝{Style.RESET_ALL}
"""

    def _log(self, niveau: str, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        couleurs = {"INFO": Fore.CYAN, "OK": Fore.GREEN, "WARN": Fore.YELLOW,
                    "ERR": Fore.RED, "TRADE": Fore.MAGENTA}
        c = couleurs.get(niveau, "")
        print(f"  {Fore.WHITE}[{ts}]{Style.RESET_ALL} {c}[{niveau}]{Style.RESET_ALL} {msg}")

    def _filtrer_univers(self, tickers: list) -> list:
        """Ne conserve que les actifs halal confirmés."""
        valides = []
        for t in tickers:
            r = est_halal(t)
            if r["halal"]:
                valides.append(t)
            else:
                self._log("WARN", f"Exclu (haram): {t} — {r['raison']}")
        return valides

    def analyser_actif(self, ticker: str) -> dict | None:
        """Récupère les données et génère un signal pour un actif."""
        df = fetch_prix(ticker, periode="3mo", intervalle="1d")
        if df is None or len(df) < 30:
            return None

        signal = generer_signal(ticker, df)
        prix   = get_prix_actuel(ticker)

        return {
            "ticker":  ticker,
            "signal":  signal,
            "prix":    prix,
        }

    def executer_signal(self, analyse: dict):
        """Décide d'exécuter ou non un trade basé sur le signal."""
        signal = analyse["signal"]
        ticker = analyse["ticker"]
        prix_info = analyse["prix"]

        if signal.action == "ATTENDRE":
            return

        if signal.confiance == "faible":
            self._log("INFO", f"{ticker} — signal {signal.action} mais confiance FAIBLE, ignoré")
            return

        prix_actuel = prix_info["prix"] if prix_info else signal.prix_entree

        peut, raison_risque = self.risk.peut_trader()
        if not peut:
            self._log("WARN", f"Trading bloqué: {raison_risque}")
            return

        sizing = self.risk.calculer_taille_position(
            ticker, signal.prix_entree, signal.stop_loss, signal.force
        )

        if not sizing.autorise:
            self._log("WARN", f"Position refusée: {sizing.raison}")
            return

        sens = "BUY" if signal.action == "ACHETER" else "SELL"
        qty  = sizing.nb_unites

        self._log("TRADE", f"{'🟢 ACHAT' if sens=='BUY' else '🔴 VENTE'} {ticker}")
        self._log("TRADE", f"  Prix: {prix_actuel:.4f} | Qty: {qty:.6f} | Montant: {sizing.taille_position:.2f}€")
        self._log("TRADE", f"  Stop-loss: {signal.stop_loss:.4f} | Take-profit: {signal.take_profit:.4f}")
        self._log("TRADE", f"  Force signal: {signal.force:.0%} | Confiance: {signal.confiance}")

        resultat = self.broker.passer_ordre_market(ticker, sens, qty, prix_actuel)

        if resultat["succes"]:
            self._log("OK", f"Ordre DEMO exécuté ✓ | Capital restant: {resultat['ordre']['capital_apres']:.2f}€")
            trade_info = self.risk.ouvrir_position(ticker, signal)
            self.signaux_log.append({
                "timestamp": datetime.now().isoformat(),
                "ticker":    ticker,
                "action":    signal.action,
                "prix":      prix_actuel,
                "force":     signal.force,
                "confiance": signal.confiance,
                "raisons":   signal.raisons,
                "montant":   sizing.taille_position,
            })
        else:
            self._log("ERR", f"Ordre rejeté: {resultat['raison']}")

    def afficher_portefeuille(self):
        """Affiche l'état du portefeuille en console."""
        prix_actuels = {}
        for ticker in list(self.broker.positions.keys()):
            p = get_prix_actuel(ticker)
            if p:
                prix_actuels[ticker] = p["prix"]

        port = self.broker.get_portefeuille(prix_actuels)

        print(f"""
  {Fore.CYAN}═══════════════ PORTEFEUILLE DÉMO ═══════════════{Style.RESET_ALL}
  Capital liquide  : {Fore.GREEN}{port['capital_liquide']:.2f}€{Style.RESET_ALL}
  Valeur positions : {port['valeur_positions']:.2f}€
  TOTAL            : {Fore.YELLOW}{port['valeur_totale']:.2f}€{Style.RESET_ALL}
  Rendement        : {Fore.GREEN if port['rendement_pct'] >= 0 else Fore.RED}{port['rendement_pct']:+.2f}%{Style.RESET_ALL}
  Positions ouv.   : {port['nb_positions']}
  Trades total     : {port['nb_trades_total']}
  {Fore.CYAN}══════════════════════════════════════════════════{Style.RESET_ALL}""")

        if port["positions"]:
            print(f"  {'Ticker':<8} {'Qté':>10} {'P.Entrée':>10} {'P.Actuel':>10} {'PnL':>8} {'PnL%':>7}")
            print(f"  {'─'*8} {'─'*10} {'─'*10} {'─'*10} {'─'*8} {'─'*7}")
            for t, p in port["positions"].items():
                pnl_col = Fore.GREEN if p['pnl'] >= 0 else Fore.RED
                print(f"  {t:<8} {p['quantite']:>10.6f} {p['prix_moyen']:>10.4f} {p['prix_actuel']:>10.4f} "
                      f"{pnl_col}{p['pnl']:>+8.4f}{Style.RESET_ALL} {pnl_col}{p['pnl_pct']:>+6.2f}%{Style.RESET_ALL}")

    def cycle_analyse(self):
        """Un cycle complet d'analyse et de décision."""
        self.cycle += 1
        print(f"\n  {Fore.CYAN}── Cycle #{self.cycle} — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ──{Style.RESET_ALL}")

        univers = self._filtrer_univers(UNIVERS_ACTIFS)
        self._log("INFO", f"Analyse de {len(univers)} actifs halal...")

        signaux_actionnables = []

        for ticker in univers:
            analyse = self.analyser_actif(ticker)
            if analyse is None:
                continue

            signal = analyse["signal"]
            if signal.action != "ATTENDRE":
                signaux_actionnables.append(analyse)
                self._log("INFO",
                    f"{ticker:<8} → {Fore.GREEN if signal.action=='ACHETER' else Fore.RED}"
                    f"{signal.action}{Style.RESET_ALL} "
                    f"| Force: {signal.force:.0%} | Confiance: {signal.confiance}"
                )
                for r in signal.raisons[:2]:
                    self._log("INFO", f"         ↳ {r}")

        # Trier par force de signal (meilleur d'abord)
        signaux_actionnables.sort(key=lambda x: x["signal"].force, reverse=True)

        for analyse in signaux_actionnables[:2]:  # Max 2 trades par cycle
            self.executer_signal(analyse)

        self.afficher_portefeuille()

    def demarrer(self, nb_cycles: int = 3, pause_secondes: int = 5):
        """Lance l'agent en mode continu (démo)."""
        self._log("OK", f"Agent démarré — Mode {MODE} | Capital: {CAPITAL_INITIAL}€")
        self._log("INFO", f"Univers: {UNIVERS_ACTIFS}")
        print()

        try:
            for i in range(nb_cycles):
                self.cycle_analyse()
                if i < nb_cycles - 1:
                    self._log("INFO", f"Pause {pause_secondes}s avant prochain cycle...")
                    time.sleep(pause_secondes)
        except KeyboardInterrupt:
            self._log("WARN", "Agent arrêté par l'utilisateur")
        finally:
            self._log("OK", "Sauvegarde de l'état final...")
            self.broker._sauvegarder_etat()
            print(f"\n  {Fore.GREEN}Session terminée. Les trades sont dans logs/demo_trades.json{Style.RESET_ALL}\n")


if __name__ == "__main__":
    agent = AgentTradingHalal()
    agent.demarrer(nb_cycles=2, pause_secondes=3)
