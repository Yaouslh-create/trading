const express = require('express');
const cors = require('cors');
const path = require('path');
const helmet = require('helmet');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 5000;
const NODE_ENV = process.env.NODE_ENV || 'development';
const LOG_LEVEL = process.env.LOG_LEVEL || 'info';

// ===== SECURITY MIDDLEWARE =====
app.use(helmet());
app.use(cors({
  origin: process.env.ALLOWED_ORIGINS || '*',
  credentials: true,
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization']
}));

// ===== BODY PARSING =====
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ limit: '10mb', extended: true }));

// ===== STATIC FILES =====
app.use(express.static('public', {
  maxAge: '1h',
  etag: false,
  setHeaders: (res, path) => {
    if (path.endsWith('.html')) {
      res.setHeader('Cache-Control', 'public, max-age=3600');
    }
  }
}));

// ===== LOGGING =====
const log = (level, message, data = {}) => {
  const timestamp = new Date().toISOString();
  const logEntry = { timestamp, level, message, ...data };
  if (level === 'error' || LOG_LEVEL === 'debug') {
    console.log(JSON.stringify(logEntry));
  }
};

// ===== REQUEST LOGGING =====
app.use((req, res, next) => {
  const start = Date.now();
  res.on('finish', () => {
    const duration = Date.now() - start;
    log('info', 'HTTP Request', {
      method: req.method,
      path: req.path,
      status: res.statusCode,
      duration: `${duration}ms`
    });
  });
  next();
});

// ===== MAIN ROUTES =====
app.get('/', (req, res) => {
  try {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
  } catch (error) {
    log('error', 'Failed to serve index.html', { error: error.message });
    res.status(500).json({ error: 'Failed to load dashboard' });
  }
});

// ===== HEALTH CHECK =====
app.get('/health', (req, res) => {
  res.status(200).json({
    status: 'OK',
    timestamp: new Date().toISOString(),
    environment: NODE_ENV,
    uptime: process.uptime()
  });
});

// ===== API: STATUS =====
app.get('/api/status', (req, res) => {
  res.json({
    status: 'running',
    version: '2.0.0',
    environment: NODE_ENV,
    timestamp: new Date().toISOString(),
    uptime: Math.floor(process.uptime()),
    server: 'Express',
    memory: process.memoryUsage()
  });
});

// ===== API: MARKET DATA =====
app.get('/api/market-data', (req, res) => {
  try {
    const basePrice = 45000;
    const volatility = 2000;
    const btcPrice = basePrice + (Math.random() * volatility - volatility / 2);
    const change24h = (Math.random() * 5 - 2.5).toFixed(2);

    res.json({
      symbol: 'BTCUSDT',
      price: parseFloat(btcPrice.toFixed(2)),
      change24h: parseFloat(change24h),
      high24h: 46500,
      low24h: 43500,
      volume24h: '28.5B',
      dominance: '45.2%',
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    log('error', 'Market data error', { error: error.message });
    res.status(500).json({ error: 'Failed to fetch market data' });
  }
});

// ===== API: SIGNALS =====
app.get('/api/signals', (req, res) => {
  try {
    const signals = [
      {
        id: 1,
        type: 'BUY',
        indicator: 'RSI Oversold',
        confidence: 85,
        timestamp: new Date().toISOString(),
        description: 'Strong oversold condition detected'
      },
      {
        id: 2,
        type: 'BUY',
        indicator: 'MACD Crossover',
        confidence: 72,
        timestamp: new Date(Date.now() - 60000).toISOString(),
        description: 'Bullish MACD crossover'
      },
      {
        id: 3,
        type: 'HOLD',
        indicator: 'Bollinger Bands',
        confidence: 55,
        timestamp: new Date(Date.now() - 120000).toISOString(),
        description: 'Price near upper band'
      }
    ];
    res.json({
      signals,
      generated_at: new Date().toISOString(),
      count: signals.length
    });
  } catch (error) {
    log('error', 'Signals error', { error: error.message });
    res.status(500).json({ error: 'Failed to fetch signals' });
  }
});

// ===== API: AGENTS =====
app.get('/api/agents', (req, res) => {
  try {
    const agents = [
      {
        id: 1,
        name: 'Agent Conservative',
        strategy: 'Conservative',
        status: 'active',
        trades: 12,
        wins: 9,
        losses: 3,
        winRate: 75,
        pnl: 245.50,
        roi: 24.55,
        maxDrawdown: -2.3,
        sharpeRatio: 1.85
      },
      {
        id: 2,
        name: 'Agent Balanced',
        strategy: 'Balanced',
        status: 'active',
        trades: 18,
        wins: 12,
        losses: 6,
        winRate: 68,
        pnl: 382.75,
        roi: 38.28,
        maxDrawdown: -3.5,
        sharpeRatio: 1.65
      },
      {
        id: 3,
        name: 'Agent Aggressive',
        strategy: 'Aggressive',
        status: 'active',
        trades: 25,
        wins: 15,
        losses: 10,
        winRate: 62,
        pnl: 128.30,
        roi: 12.83,
        maxDrawdown: -5.3,
        sharpeRatio: 1.42
      }
    ];
    res.json({
      agents,
      generated_at: new Date().toISOString(),
      total_agents: agents.length,
      active_agents: agents.filter(a => a.status === 'active').length
    });
  } catch (error) {
    log('error', 'Agents error', { error: error.message });
    res.status(500).json({ error: 'Failed to fetch agents' });
  }
});

// ===== API: POSITIONS =====
app.get('/api/positions', (req, res) => {
  try {
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
        status: 'open',
        agent: 'Agent #1',
        timestamp: new Date(Date.now() - 3600000).toISOString()
      }
    ];
    res.json({
      positions,
      generated_at: new Date().toISOString(),
      open_positions: positions.length,
      total_pnl: positions.reduce((sum, p) => sum + p.pnl, 0)
    });
  } catch (error) {
    log('error', 'Positions error', { error: error.message });
    res.status(500).json({ error: 'Failed to fetch positions' });
  }
});

// ===== API: ANALYTICS =====
app.get('/api/analytics', (req, res) => {
  try {
    const analytics = {
      totalTrades: 55,
      winTrades: 37,
      lossTrades: 18,
      winRate: 68.2,
      avgWin: 85.50,
      avgLoss: -32.20,
      profitFactor: 2.65,
      maxDrawdown: -5.3,
      sharpeRatio: 1.82,
      sortinoRatio: 2.15,
      calmarRatio: 3.82,
      win_loss_ratio: 2.67,
      expectancy: 41.23
    };
    res.json({
      ...analytics,
      generated_at: new Date().toISOString()
    });
  } catch (error) {
    log('error', 'Analytics error', { error: error.message });
    res.status(500).json({ error: 'Failed to fetch analytics' });
  }
});

// ===== 404 HANDLER =====
app.use((req, res) => {
  log('warn', 'Route not found', { path: req.path, method: req.method });
  res.status(404).json({
    error: 'Route not found',
    path: req.path,
    available_endpoints: [
      'GET /',
      'GET /health',
      'GET /api/status',
      'GET /api/market-data',
      'GET /api/signals',
      'GET /api/agents',
      'GET /api/positions',
      'GET /api/analytics'
    ]
  });
});

// ===== ERROR HANDLER =====
app.use((err, req, res, next) => {
  log('error', 'Unhandled error', {
    error: err.message,
    stack: err.stack,
    path: req.path,
    method: req.method
  });
  res.status(500).json({
    error: 'Internal Server Error',
    message: NODE_ENV === 'development' ? err.message : 'An error occurred',
    timestamp: new Date().toISOString()
  });
});

// ===== SERVER START =====
const server = app.listen(PORT, () => {
  log('info', 'Halal Trading Bot Server Started', {
    version: '2.0.0',
    port: PORT,
    environment: NODE_ENV,
    timestamp: new Date().toISOString()
  });

  console.log(`
╔════════════════════════════════════════════════════╗`);
  console.log(`║  🤖 HALAL TRADING BOT PRO - v2.0.0            ║`);
  console.log(`╠════════════════════════════════════════════════════╣`);
  console.log(`║  ✅ Status: RUNNING                               ║`);
  console.log(`║  🌍 Environment: ${NODE_ENV.toUpperCase().padEnd(36)}║`);
  console.log(`║  🔌 Port: ${PORT.toString().padEnd(44)}║`);
  console.log(`║  🕐 Started: ${new Date().toLocaleString().padEnd(36)}║`);
  console.log(`╠════════════════════════════════════════════════════╣`);
  console.log(`║  📍 ENDPOINTS:                                    ║`);
  console.log(`║  - http://localhost:${PORT}                              ║`);
  console.log(`║  - http://localhost:${PORT}/health                      ║`);
  console.log(`║  - http://localhost:${PORT}/api/status                  ║`);
  console.log(`║  - http://localhost:${PORT}/api/market-data             ║`);
  console.log(`║  - http://localhost:${PORT}/api/signals                 ║`);
  console.log(`║  - http://localhost:${PORT}/api/agents                  ║`);
  console.log(`║  - http://localhost:${PORT}/api/positions               ║`);
  console.log(`║  - http://localhost:${PORT}/api/analytics               ║`);
  console.log(`╚════════════════════════════════════════════════════╝
`);
});

// ===== GRACEFUL SHUTDOWN =====
process.on('SIGTERM', () => {
  log('info', 'SIGTERM received - shutting down gracefully');
  server.close(() => {
    log('info', 'Server closed');
    process.exit(0);
  });
});

process.on('SIGINT', () => {
  log('info', 'SIGINT received - shutting down gracefully');
  server.close(() => {
    log('info', 'Server closed');
    process.exit(0);
  });
});

module.exports = app;
