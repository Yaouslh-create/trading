const express = require('express');
const cors = require('cors');
const path = require('path');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 5000;

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.static('public'));

// Routes
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// API Routes - Market Data
app.get('/api/status', (req, res) => {
  res.json({
    status: 'running',
    version: '2.0.0',
    timestamp: new Date().toISOString(),
    uptime: process.uptime()
  });
});

app.get('/api/market-data', (req, res) => {
  const btcPrice = 45000 + Math.random() * 2000 - 1000;
  res.json({
    symbol: 'BTCUSDT',
    price: btcPrice.toFixed(2),
    change24h: (Math.random() * 5 - 2.5).toFixed(2),
    high24h: 46500,
    low24h: 43500,
    volume24h: '28.5B',
    timestamp: new Date().toISOString()
  });
});

// API Routes - Trading Signals
app.get('/api/signals', (req, res) => {
  const signals = [
    { id: 1, type: 'BUY', indicator: 'RSI Oversold', confidence: 85, timestamp: new Date().toISOString() },
    { id: 2, type: 'BUY', indicator: 'MACD Crossover', confidence: 72, timestamp: new Date(Date.now() - 60000).toISOString() },
    { id: 3, type: 'HOLD', indicator: 'Bollinger Bands', confidence: 55, timestamp: new Date(Date.now() - 120000).toISOString() }
  ];
  res.json(signals);
});

// API Routes - Agent Data
app.get('/api/agents', (req, res) => {
  const agents = [
    {
      id: 1,
      name: 'Agent Conservative',
      strategy: 'Conservative',
      status: 'active',
      trades: 12,
      winRate: 75,
      pnl: 245.50,
      roi: 24.55
    },
    {
      id: 2,
      name: 'Agent Balanced',
      strategy: 'Balanced',
      status: 'active',
      trades: 18,
      winRate: 68,
      pnl: 382.75,
      roi: 38.28
    },
    {
      id: 3,
      name: 'Agent Aggressive',
      strategy: 'Aggressive',
      status: 'active',
      trades: 25,
      winRate: 62,
      pnl: 128.30,
      roi: 12.83
    }
  ];
  res.json(agents);
});

// API Routes - Trading Positions
app.get('/api/positions', (req, res) => {
  const positions = [
    {
      id: 1,
      symbol: 'BTC/USDT',
      type: 'LONG',
      quantity: 0.5,
      entryPrice: 44500,
      currentPrice: 45000,
      pnl: 250,
      pnlPercent: 0.56,
      agent: 'Agent #1'
    }
  ];
  res.json(positions);
});

// API Routes - Analytics
app.get('/api/analytics', (req, res) => {
  res.json({
    totalTrades: 55,
    winRate: 68.2,
    avgWin: 85.50,
    avgLoss: -32.20,
    maxDrawdown: -5.3,
    profitFactor: 2.65,
    sharpeRatio: 1.82
  });
});

// Health Check
app.get('/health', (req, res) => {
  res.json({ status: 'OK', timestamp: new Date().toISOString() });
});

// Error handling
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).json({ error: 'Internal Server Error', message: err.message });
});

// 404 handler
app.use((req, res) => {
  res.status(404).json({ error: 'Route not found' });
});

app.listen(PORT, () => {
  console.log(`✅ Halal Trading Bot Server v2.0 running on port ${PORT}`);
  console.log(`📊 Dashboard available at http://localhost:${PORT}`);
  console.log(`🔗 API endpoints:`)
  console.log(`   - /api/status`);
  console.log(`   - /api/market-data`);
  console.log(`   - /api/signals`);
  console.log(`   - /api/agents`);
  console.log(`   - /api/positions`);
  console.log(`   - /api/analytics`);
});