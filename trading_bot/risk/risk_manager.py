"""
Gestionnaire de risque — La règle d'or de Simons :
"Survivre d'abord, gagner ensuite."
Conçu pour 100€ de capital initial.
"""

from dataclasses import dataclass, field
from datetime import datetime
import json, os


@dataclass
class PositionSizingResult:
    taille_position: float      # montant en euros à investir
    nb_unites:        float      # nombre de parts/contrats
    risque_euros:     float      # perte max acceptée en euros
    risque_pct:       float      # % du capital risqué
    levier:           float      # levier utilisé (1.0 = pas de levier)
    autorise:         bool
    raison:           str


class GestionnaireRisque:
    """
    Gestionnaire de risque inspiré de Renaissance Technologies.
    Adapté pour petit capital (100€).
    """

    def __init__(self, capital_initial: float = 100.0):
        self.capital_initial   = capital_initial
        self.capital_actuel    = capital_initial
        self.capital_max       = capital_initial  # pour drawdown

        # Paramètres de risque (style Simons — très conservateur)
        self.risque_par_trade_pct = 0.02    # max 2% du capital par trade
        self.max_positions_ouvertes = 3     # max 3 trades simultanés
        self.max_drawdown_pct   = 0.15      # stop trading si -15% du capital max
        self.max_perte_journaliere_pct = 0.05  # stop si -5% en une journée

        # État
        self.positions_ouvertes  = {}
        self.historique_trades   = []
        self.perte_jour_actuel   = 0.0
        self.date_debut_journee  = datetime.now().date()

        # Statistiques
        self.nb_trades_gagnants  = 0
        self.nb_trades_perdants  = 0
        self.gain_total          = 0.0
        self.perte_totale        = 0.0

    def reset_journee(self):
        """Remet à zéro les limites quotidiennes."""
        aujourd_hui = datetime.now().date()
        if aujourd_hui != self.date_debut_journee:
            self.perte_jour_actuel = 0.0
            self.date_debut_journee = aujourd_hui

    def peut_trader(self) -> tuple[bool, str]:
        """Vérifie si le bot peut ouvrir de nouveaux trades."""
        self.reset_journee()

        # Vérification drawdown maximum
        drawdown = (self.capital_max - self.capital_actuel) / self.capital_max
        if drawdown >= self.max_drawdown_pct:
            return False, f"DRAWDOWN MAX ATTEINT: -{drawdown:.1%} (limite: -{self.max_drawdown_pct:.1%})"

        # Vérification perte journalière
        if self.perte_jour_actuel >= self.capital_actuel * self.max_perte_journaliere_pct:
            return False, f"LIMITE JOURNALIÈRE ATTEINTE: -{self.perte_jour_actuel:.2f}€"

        # Vérification nombre de positions
        if len(self.positions_ouvertes) >= self.max_positions_ouvertes:
            return False, f"MAX POSITIONS ATTEINT: {len(self.positions_ouvertes)}/{self.max_positions_ouvertes}"

        # Capital minimum
        if self.capital_actuel < 10.0:
            return False, "CAPITAL INSUFFISANT (< 10€)"

        return True, "OK"

    def calculer_taille_position(
        self,
        ticker: str,
        prix_entree: float,
        stop_loss: float,
        force_signal: float = 0.5
    ) -> PositionSizingResult:
        """
        Calcule la taille optimale d'une position.
        Méthode Kelly partielle (utilisée par Simons).
        """
        peut, raison = self.peut_trader()
        if not peut:
            return PositionSizingResult(0, 0, 0, 0, 1.0, False, raison)

        if prix_entree <= 0 or stop_loss <= 0:
            return PositionSizingResult(0, 0, 0, 0, 1.0, False, "Prix invalide")

        # Risque par unité
        risque_par_unite = abs(prix_entree - stop_loss)
        if risque_par_unite == 0:
            return PositionSizingResult(0, 0, 0, 0, 1.0, False, "Stop-loss identique au prix d'entrée")

        # Montant max risqué (2% du capital)
        risque_max_euros = self.capital_actuel * self.risque_par_trade_pct

        # Ajustement selon la force du signal (Kelly partiel)
        kelly_fraction = 0.25 + (force_signal * 0.50)  # entre 25% et 75% du Kelly
        risque_ajuste  = risque_max_euros * kelly_fraction

        # Nombre d'unités
        nb_unites = risque_ajuste / risque_par_unite

        # Valeur totale de la position
        valeur_position = nb_unites * prix_entree

        # Plafond : jamais plus de 35% du capital sur un seul trade
        plafond = self.capital_actuel * 0.35
        if valeur_position > plafond:
            valeur_position = plafond
            nb_unites = valeur_position / prix_entree
            risque_ajuste = nb_unites * risque_par_unite

        return PositionSizingResult(
            taille_position = round(valeur_position, 2),
            nb_unites        = round(nb_unites, 6),
            risque_euros     = round(risque_ajuste, 2),
            risque_pct       = round((risque_ajuste / self.capital_actuel) * 100, 2),
            levier           = 1.0,
            autorise         = True,
            raison           = f"Kelly {kelly_fraction:.0%} — Signal force {force_signal:.0%}"
        )

    def ouvrir_position(self, ticker: str, signal) -> dict:
        """Enregistre l'ouverture d'un trade (compte démo)."""
        sizing = self.calculer_taille_position(
            ticker, signal.prix_entree, signal.stop_loss, signal.force
        )

        if not sizing.autorise:
            return {"succes": False, "raison": sizing.raison}

        trade = {
            "id":           f"{ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "ticker":       ticker,
            "action":       signal.action,
            "prix_entree":  signal.prix_entree,
            "stop_loss":    signal.stop_loss,
            "take_profit":  signal.take_profit,
            "nb_unites":    sizing.nb_unites,
            "montant":      sizing.taille_position,
            "risque_euros": sizing.risque_euros,
            "ouverture":    datetime.now().isoformat(),
            "statut":       "OUVERT",
        }

        self.positions_ouvertes[trade["id"]] = trade
        return {"succes": True, "trade": trade, "sizing": sizing}

    def fermer_position(self, trade_id: str, prix_cloture: float) -> dict:
        """Clôture un trade et met à jour le capital."""
        if trade_id not in self.positions_ouvertes:
            return {"succes": False, "raison": "Trade introuvable"}

        trade = self.positions_ouvertes.pop(trade_id)
        nb    = trade["nb_unites"]
        sens  = 1 if trade["action"] == "ACHETER" else -1

        pnl = (prix_cloture - trade["prix_entree"]) * nb * sens

        self.capital_actuel += pnl
        if self.capital_actuel > self.capital_max:
            self.capital_max = self.capital_actuel

        if pnl >= 0:
            self.nb_trades_gagnants += 1
            self.gain_total += pnl
        else:
            self.nb_trades_perdants += 1
            self.perte_totale += abs(pnl)
            self.perte_jour_actuel += abs(pnl)

        trade.update({
            "prix_cloture": prix_cloture,
            "pnl":          round(pnl, 4),
            "pnl_pct":      round((pnl / trade["montant"]) * 100, 2),
            "fermeture":    datetime.now().isoformat(),
            "statut":       "FERME",
        })
        self.historique_trades.append(trade)

        return {"succes": True, "trade": trade, "pnl": round(pnl, 4)}

    def statistiques(self) -> dict:
        """Tableau de bord des performances — style Simons."""
        total_trades = self.nb_trades_gagnants + self.nb_trades_perdants
        win_rate = (self.nb_trades_gagnants / total_trades * 100) if total_trades > 0 else 0.0
        profit_factor = (self.gain_total / self.perte_totale) if self.perte_totale > 0 else float("inf")
        rendement = ((self.capital_actuel - self.capital_initial) / self.capital_initial) * 100
        drawdown  = ((self.capital_max - self.capital_actuel) / self.capital_max) * 100

        return {
            "capital_initial":    round(self.capital_initial, 2),
            "capital_actuel":     round(self.capital_actuel, 2),
            "rendement_total":    round(rendement, 2),
            "drawdown_actuel":    round(drawdown, 2),
            "nb_trades":          total_trades,
            "win_rate":           round(win_rate, 1),
            "profit_factor":      round(profit_factor, 2) if profit_factor != float("inf") else "∞",
            "gain_total":         round(self.gain_total, 2),
            "perte_totale":       round(self.perte_totale, 2),
            "positions_ouvertes": len(self.positions_ouvertes),
        }


if __name__ == "__main__":
    print("=== TEST GESTION DU RISQUE (100€) ===\n")
    gm = GestionnaireRisque(capital_initial=100.0)

    print(f"  Capital: {gm.capital_actuel}€")
    print(f"  Peut trader? {gm.peut_trader()}")

    sizing = gm.calculer_taille_position("GC=F", 3200.0, 3168.0, force_signal=0.7)
    print(f"\n  Sizing pour GC=F (Or):")
    print(f"  → Montant investi : {sizing.taille_position}€")
    print(f"  → Risque max      : {sizing.risque_euros}€ ({sizing.risque_pct}%)")
    print(f"  → Autorisé        : {sizing.autorise}")
    print(f"  → Raison          : {sizing.raison}")
