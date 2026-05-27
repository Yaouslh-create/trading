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

// API Routes
app.get('/api/status', (req, res) => {
  res.json({
    status: 'running',
    version: '1.0.0',
    timestamp: new Date().toISOString()
  });
});

app.get('/api/market-data', (req, res) => {
  // Simulated market data
  res.json({
    symbol: 'BTCUSDT',
    price: 45000 + Math.random() * 1000,
    change24h: (Math.random() - 0.5) * 10,
    high24h: 46500,
    low24h: 43500
  });
});

// Error handling
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).json({ error: 'Something went wrong!' });
});

// 404 handler
app.use((req, res) => {
  res.status(404).json({ error: 'Route not found' });
});

app.listen(PORT, () => {
  console.log(`🚀 Halal Trading Bot Server running on port ${PORT}`);
  console.log(`📊 Dashboard available at http://localhost:${PORT}`);
});
