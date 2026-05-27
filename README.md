# Halal Trading Bot Pro Dashboard

Dashboard de trading avancé avec intégration TradingView en temps réel.

## 🚀 Fonctionnalités

- 📊 Graphique TradingView live (Bitcoin/USDT)
- 🤖 Bot de trading automatisé avec simulation
- 💼 Gestion de portefeuille en temps réel
- 📈 Performance et statistiques
- 🎨 Interface dark mode professionnelle
- 📱 Design responsive

## 📋 Prérequis

- Node.js 18.x ou supérieur
- npm ou yarn

## 🔧 Installation

```bash
# Cloner le repository
git clone https://github.com/Yaouslh-create/trading.git
cd trading

# Installer les dépendances
npm install

# Démarrer le serveur local
npm start
```

Le dashboard sera accessible sur `http://localhost:5000`

## 🌐 Déploiement sur Render

### Méthode 1: Configuration automatique (Recommandé)

1. Allez sur [render.com](https://render.com)
2. Cliquez sur "New +" → "Web Service"
3. Connectez votre repository GitHub `Yaouslh-create/trading`
4. Render détectera automatiquement le `render.yml`
5. Cliquez sur "Deploy"
6. Votre application sera en ligne en quelques minutes ✅

### Méthode 2: Configuration manuelle

1. Allez sur [render.com](https://render.com)
2. Cliquez sur "New +" → "Web Service"
3. Connectez votre repository GitHub
4. Configurez:
   - **Name**: halal-trading-bot
   - **Environment**: Node
   - **Build Command**: `npm install`
   - **Start Command**: `npm start`
   - **Port**: 5000
5. Cliquez sur "Create Web Service"

## 📝 Structure du projet

```
trading/
├── server.js              # Serveur Express
├── package.json           # Dépendances
├── render.yml             # Configuration Render
├── .env                   # Variables d'environnement
├── .gitignore             # Fichiers à ignorer
├── README.md              # Documentation
└── public/
    └── index.html         # Dashboard complet
```

## 🎮 Utilisation du Dashboard

### Contrôles du Bot

- **▶️ Démarrer**: Lance la simulation de trading automatique
- **⏹️ Arrêter**: Arrête le bot
- **📈 Acheter**: Achat manuel de BTC
- **📉 Vendre**: Vente manuelle de BTC

### Paramètres Configurables

- **Prix Cible**: Prix d'achat/vente par défaut (en $)
- **Stop Loss**: Pourcentage de perte acceptable

## 📊 Éléments du Dashboard

Le dashboard affiche en temps réel:

- **Graphique TradingView**: Données live BTC/USDT 5-min
- **Solde**: Liquidités disponibles en $
- **Holdings**: Nombre de BTC en portefeuille
- **Valeur Totale**: Solde + (Holdings × Prix)
- **Performance**: Gain/Perte en pourcentage
- **Journal**: Historique des 50 dernières transactions
- **État du Bot**: Actif/Arrêté
- **Compteur de Trades**: Total des transactions exécutées

## 🔗 API Endpoints

- `GET /` - Dashboard HTML principal
- `GET /api/status` - État du serveur
- `GET /api/market-data` - Données de marché simulées

## 🛠️ Technologies Utilisées

- **Frontend**: HTML5, CSS3, JavaScript (Vanille)
- **Backend**: Node.js, Express.js
- **Charts**: TradingView Lightweight Charts API
- **Icons**: Font Awesome 6.4
- **Deployment**: Render
- **Version Control**: Git & GitHub

## 📄 Licence

MIT License

## 👨‍💻 Auteur

Yaouslh - Halal Trading Bot Pro

---

### 🌍 Accès au Dashboard Déployé

Après le déploiement sur Render:

```
https://halal-trading-bot.onrender.com
```

**Note**: Render peut mettre jusqu'à 2-3 minutes pour déployer la première fois.

### 📌 Statut

- ✅ Dashboard HTML complet
- ✅ Serveur Express configuré
- ✅ TradingView intégré
- ✅ Prêt pour Render
- ✅ Mode sombre professionnel
