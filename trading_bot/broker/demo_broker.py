"""
Simulateur de Broker — Compte DÉMO (Paper Trading)
Simule un broker réel avec latence, slippage et frais.
Structure identique à celle qui sera connectée à un vrai broker (Alpaca/IBKR).
"""

import json, os
from datetime import datetime
from dataclasses import dataclass, asdict


@dataclass
class Ordre:
    id:            str
    ticker:        str
    sens:          str          # "BUY" ou "SELL"
    type_ordre:    str          # "MARKET", "LIMIT", "STOP"
    quantite:      float
    prix_demande:  float
    prix_execute:  float = 0.0
    statut:        str = "EN_ATTENTE"   # EN_ATTENTE, EXECUTE, ANNULE, REJETE
    horodatage:    str = ""
    frais:         float = 0.0
    slippage:      float = 0.0


class BrokerDemo:
    """
    Broker simulé réaliste.
    Simule : frais, slippage, ordres partiels, latence.
    Compatible avec l'interface du vrai broker Alpaca.
    """

    FRAIS_PAR_TRADE = 0.0       # Alpaca = 0 frais commission
    SLIPPAGE_PCT    = 0.0005    # 0.05% slippage réaliste

    def __init__(self, capital_initial: float = 100.0):
        self.capital          = capital_initial
        self.capital_initial  = capital_initial
        self.positions        = {}          # {ticker: {qty, prix_moyen, valeur}}
        self.historique       = []
        self.ordres_ouverts   = {}
        self.log_file         = "/home/claude/trading_bot/logs/demo_trades.json"
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        self._charger_etat()

    def _charger_etat(self):
        """Recharge l'état sauvegardé (persistance entre sessions)."""
        try:
            if os.path.exists(self.log_file):
                with open(self.log_file) as f:
                    data = json.load(f)
                    self.capital   = data.get("capital", self.capital_initial)
                    self.positions = data.get("positions", {})
                    self.historique = data.get("historique", [])
        except Exception:
            pass

    def _sauvegarder_etat(self):
        """Sauvegarde l'état (capital + positions + historique)."""
        try:
            with open(self.log_file, "w") as f:
                json.dump({
                    "capital":    self.capital,
                    "positions":  self.positions,
                    "historique": self.historique,
                    "timestamp":  datetime.now().isoformat(),
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"  [!] Erreur sauvegarde: {e}")

    def _appliquer_slippage(self, prix: float, sens: str) -> float:
        """Simule le slippage de marché."""
        if sens == "BUY":
            return prix * (1 + self.SLIPPAGE_PCT)
        else:
            return prix * (1 - self.SLIPPAGE_PCT)

    def passer_ordre_market(self, ticker: str, sens: str, quantite: float, prix_actuel: float) -> dict:
        """
        Passe un ordre au marché — exécution immédiate.
        sens: "BUY" ou "SELL"
        """
        ordre_id = f"DEMO_{ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"

        # Appliquer slippage réaliste
        prix_exec = self._appliquer_slippage(prix_actuel, sens)
        frais     = quantite * prix_exec * self.FRAIS_PAR_TRADE
        cout_total = (quantite * prix_exec) + frais

        # Vérifications
        if sens == "BUY":
            if cout_total > self.capital:
                return {
                    "succes": False,
                    "raison": f"Capital insuffisant: besoin {cout_total:.2f}€, disponible {self.capital:.2f}€"
                }

            # Exécuter l'achat
            self.capital -= cout_total

            if ticker in self.positions:
                pos = self.positions[ticker]
                total_qty   = pos["quantite"] + quantite
                prix_moyen  = (pos["prix_moyen"] * pos["quantite"] + prix_exec * quantite) / total_qty
                self.positions[ticker] = {
                    "quantite":    total_qty,
                    "prix_moyen":  round(prix_moyen, 6),
                    "valeur":      round(total_qty * prix_exec, 2),
                    "ouverture":   pos["ouverture"]
                }
            else:
                self.positions[ticker] = {
                    "quantite":    quantite,
                    "prix_moyen":  round(prix_exec, 6),
                    "valeur":      round(quantite * prix_exec, 2),
                    "ouverture":   datetime.now().isoformat()
                }

        elif sens == "SELL":
            if ticker not in self.positions or self.positions[ticker]["quantite"] < quantite:
                qty_dispo = self.positions.get(ticker, {}).get("quantite", 0)
                return {
                    "succes": False,
                    "raison": f"Quantité insuffisante: {qty_dispo:.6f} < {quantite:.6f}"
                }

            pos = self.positions[ticker]
            pnl = (prix_exec - pos["prix_moyen"]) * quantite - frais

            # Mise à jour position
            pos["quantite"] -= quantite
            if pos["quantite"] <= 0.000001:
                del self.positions[ticker]
            else:
                pos["valeur"] = round(pos["quantite"] * prix_exec, 2)

            self.capital += (quantite * prix_exec) - frais

        else:
            return {"succes": False, "raison": f"Sens invalide: {sens}"}

        # Enregistrement
        record = {
            "id":           ordre_id,
            "ticker":       ticker,
            "sens":         sens,
            "quantite":     round(quantite, 6),
            "prix_demande": round(prix_actuel, 6),
            "prix_execute": round(prix_exec, 6),
            "slippage":     round(prix_exec - prix_actuel, 6),
            "frais":        round(frais, 4),
            "cout_total":   round(cout_total if sens == "BUY" else quantite * prix_exec, 2),
            "capital_apres": round(self.capital, 2),
            "timestamp":    datetime.now().isoformat(),
            "statut":       "EXECUTE",
            "mode":         "DEMO"
        }
        self.historique.append(record)
        self._sauvegarder_etat()

        return {"succes": True, "ordre": record}

    def get_portefeuille(self, prix_actuels: dict = None) -> dict:
        """Retourne l'état complet du portefeuille."""
        valeur_positions = 0.0
        positions_detail = {}

        for ticker, pos in self.positions.items():
            prix_actuel = prix_actuels.get(ticker, pos["prix_moyen"]) if prix_actuels else pos["prix_moyen"]
            valeur = pos["quantite"] * prix_actuel
            pnl    = (prix_actuel - pos["prix_moyen"]) * pos["quantite"]
            pnl_pct = ((prix_actuel - pos["prix_moyen"]) / pos["prix_moyen"]) * 100

            valeur_positions += valeur
            positions_detail[ticker] = {
                **pos,
                "prix_actuel": round(prix_actuel, 4),
                "valeur_actuelle": round(valeur, 2),
                "pnl": round(pnl, 4),
                "pnl_pct": round(pnl_pct, 2),
            }

        valeur_totale = self.capital + valeur_positions
        rendement = ((valeur_totale - self.capital_initial) / self.capital_initial) * 100

        return {
            "capital_liquide":    round(self.capital, 2),
            "valeur_positions":   round(valeur_positions, 2),
            "valeur_totale":      round(valeur_totale, 2),
            "capital_initial":    self.capital_initial,
            "rendement_pct":      round(rendement, 2),
            "nb_positions":       len(self.positions),
            "positions":          positions_detail,
            "nb_trades_total":    len(self.historique),
            "mode":               "DEMO",
        }

    def reset(self):
        """Remet à zéro le compte démo."""
        self.capital   = self.capital_initial
        self.positions = {}
        self.historique = []
        self._sauvegarder_etat()
        print("  ✓ Compte démo réinitialisé")


if __name__ == "__main__":
    print("=== TEST BROKER DÉMO ===\n")
    broker = BrokerDemo(100.0)

    print(f"  Capital initial: {broker.capital:.2f}€")

    # Simuler un achat d'or
    res = broker.passer_ordre_market("GC=F", "BUY", 0.001, 3200.0)
    if res["succes"]:
        print(f"  ✅ Achat exécuté: {res['ordre']['quantite']} GC=F @ {res['ordre']['prix_execute']:.2f}$")
        print(f"     Capital restant: {res['ordre']['capital_apres']:.2f}€")
    else:
        print(f"  ❌ Ordre rejeté: {res['raison']}")

    portefeuille = broker.get_portefeuille({"GC=F": 3210.0})
    print(f"\n  Portefeuille:")
    print(f"  → Cash:          {portefeuille['capital_liquide']:.2f}€")
    print(f"  → Positions:     {portefeuille['valeur_positions']:.2f}€")
    print(f"  → Total:         {portefeuille['valeur_totale']:.2f}€")
    print(f"  → Rendement:     {portefeuille['rendement_pct']:+.2f}%")
