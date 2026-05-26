"""
Filtre Halal - Critères AAOIFI / MSCI Islamic
Exclut automatiquement tout actif non-conforme charia
"""

SECTEURS_HARAM = [
    "alcohol", "tobacco", "weapons", "defense", "gambling",
    "adult entertainment", "pork", "banking", "insurance",
    "financial services", "interest", "riba", "brewery",
    "distillery", "casino", "lottery", "arms"
]

TICKERS_HARAM_CONNUS = {
    "BUD", "SAM", "STZ", "TAP",           # Alcool
    "MO",  "PM",  "BTI", "LO",             # Tabac
    "LVS", "WYNN","MGM", "CZR",            # Casinos
    "BA",  "LMT", "RTX", "NOC", "GD",      # Armement
    "JPM", "BAC", "WFC", "GS", "C",        # Banques (intérêts)
    "V",   "MA",  "AXP",                   # Services financiers basés sur intérêts
}

# Actifs halal validés — Matières premières + Actions conformes
ACTIFS_HALAL_VALIDES = {
    "matieres_premieres": {
        "GC=F":  "Or (Gold Futures)",
        "SI=F":  "Argent (Silver Futures)",
        "PL=F":  "Platine",
        "HG=F":  "Cuivre",
        "ZW=F":  "Blé",
        "ZC=F":  "Maïs",
        "ZS=F":  "Soja",
        "KC=F":  "Café",
        "CC=F":  "Cacao",
        "CT=F":  "Coton",
        "NG=F":  "Gaz Naturel",
        "CL=F":  "Pétrole brut (usage industriel uniquement)",
    },
    "actions_halal": {
        "AAPL":  "Apple (technologie)",
        "MSFT":  "Microsoft (cloud/logiciels)",
        "GOOGL": "Alphabet (technologie)",
        "AMZN":  "Amazon (e-commerce/cloud)",
        "NVDA":  "NVIDIA (semi-conducteurs)",
        "META":  "Meta (réseaux sociaux)",
        "TSM":   "TSMC (semi-conducteurs)",
        "TSLA":  "Tesla (véhicules électriques)",
        "AMD":   "AMD (semi-conducteurs)",
        "INTC":  "Intel (semi-conducteurs)",
        "QCOM":  "Qualcomm (télécoms)",
        "ADBE":  "Adobe (logiciels)",
        "CRM":   "Salesforce (logiciels)",
        "ORCL":  "Oracle (logiciels)",
        "SAP":   "SAP (logiciels entreprise)",
        "ASML":  "ASML (équipements semi-cond.)",
        "NOVO-B.CO": "Novo Nordisk (pharma)",
        "JNJ":   "Johnson & Johnson (santé)",
        "PFE":   "Pfizer (pharma)",
        "UNH":   "UnitedHealth (santé)",
        "NKE":   "Nike (équipement sportif)",
        "SBUX":  "Starbucks (alimentation/café)",
        "MCD":   "McDonald's (⚠ vérifier options halal)",
        "WMT":   "Walmart (distribution)",
        "COST":  "Costco (distribution)",
        "HD":    "Home Depot (bricolage)",
        "TM":    "Toyota (automobile)",
        "BABA":  "Alibaba (e-commerce)",
    },
    "etf_islamiques": {
        "ISWD":  "iShares MSCI World Islamic ETF",
        "ISUS":  "iShares MSCI USA Islamic ETF",
        "AMAGX": "Amana Growth Fund",
    }
}

def est_halal(ticker: str, secteur: str = "") -> dict:
    """
    Vérifie si un ticker est conforme charia.
    Retourne un dict avec statut et raison.
    """
    ticker = ticker.upper().strip()

    # Vérification liste noire explicite
    if ticker in TICKERS_HARAM_CONNUS:
        return {
            "halal": False,
            "ticker": ticker,
            "raison": "Présent dans la liste noire haram (secteur prohibé)",
            "confiance": "haute"
        }

    # Vérification du secteur
    secteur_lower = secteur.lower()
    for mot_haram in SECTEURS_HARAM:
        if mot_haram in secteur_lower:
            return {
                "halal": False,
                "ticker": ticker,
                "raison": f"Secteur interdit détecté : '{mot_haram}'",
                "confiance": "haute"
            }

    # Vérification liste blanche
    tous_halal = {}
    for categorie, actifs in ACTIFS_HALAL_VALIDES.items():
        tous_halal.update(actifs)

    if ticker in tous_halal:
        return {
            "halal": True,
            "ticker": ticker,
            "nom": tous_halal[ticker],
            "raison": "Présent dans la liste blanche halal validée",
            "confiance": "haute"
        }

    # Actif inconnu — prudence
    return {
        "halal": False,
        "ticker": ticker,
        "raison": "Actif non répertorié — vérification manuelle requise",
        "confiance": "basse"
    }

def filtrer_portefeuille(tickers: list) -> dict:
    """Filtre une liste de tickers et retourne les halal uniquement."""
    resultats = {"acceptes": [], "rejetes": [], "inconnus": []}

    for ticker in tickers:
        check = est_halal(ticker)
        if check["halal"] and check["confiance"] == "haute":
            resultats["acceptes"].append(check)
        elif not check["halal"] and check["confiance"] == "haute":
            resultats["rejetes"].append(check)
        else:
            resultats["inconnus"].append(check)

    return resultats

def get_univers_halal() -> list:
    """Retourne tous les tickers halal disponibles pour le trading."""
    univers = []
    for categorie, actifs in ACTIFS_HALAL_VALIDES.items():
        univers.extend(list(actifs.keys()))
    return univers

if __name__ == "__main__":
    print("=== TEST DU FILTRE HALAL ===\n")
    tests = ["AAPL", "JPM", "GC=F", "MO", "NVDA", "WYNN", "MSFT", "BAC"]
    for t in tests:
        r = est_halal(t)
        statut = "✅ HALAL" if r["halal"] else "❌ HARAM"
        print(f"{statut} | {t:8} | {r['raison']}")
