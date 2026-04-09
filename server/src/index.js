/**
 * TeleCursor Data Collection Server
 * 
 * Receives and stores cursor trajectory data from the browser extension.
 * Applies privacy-preserving transformations before storage.
 */

import express from 'express';
import { v4 as uuidv4 } from 'uuid';
import { initDatabase } from './db/database.js';
import { createTrajectoryRoutes } from './routes/trajectories.js';
import { createStatsRoutes } from './routes/stats.js';
import { consentMiddleware } from './middleware/consent.js';
import { rateLimitMiddleware } from './middleware/rateLimit.js';
import { loggingMiddleware } from './middleware/logging.js';
import yargs from 'yargs/yargs.js';

const argv = yargs(process.argv.slice(2))
  .option('port', {
    alias: 'p',
    type: 'number',
    default: 3000,
    description: 'Port to listen on'
  })
  .option('host', {
    alias: 'h',
    type: 'string',
    default: '0.0.0.0',
    description: 'Host to bind to'
  })
  .option('max-body-size', {
    type: 'number',
    default: 1048576,  // 1MB
    description: 'Max request body size in bytes'
  })
  .option('rate-limit', {
    type: 'number',
    default: 100,
    description: 'Rate limit per IP per minute'
  })
  .option('cors-origin', {
    type: 'string',
    default: '*',
    description: 'CORS origin'
  })
  .parse();

const app = express();

// Middleware
app.use(express.json({ limit: argv.maxBodySize }));
app.use(loggingMiddleware);
app.use(rateLimitMiddleware(argv.rateLimit));

// CORS
app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', argv.corsOrigin);
  res.header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.header('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  if (req.method === 'OPTIONS') {
    return res.sendStatus(200);
  }
  next();
});

// Health check
app.get('/health', (req, res) => {
  res.json({ 
    status: 'ok', 
    timestamp: new Date().toISOString(),
    version: '0.1.0'
  });
});

// Initialize database
const db = initDatabase();

// Routes
app.use('/api/v1/trajectories', createTrajectoryRoutes(db));
app.use('/api/v1/stats', createStatsRoutes(db));

// Error handling
app.use((err, req, res, next) => {
  console.error('[TeleCursor Server] Error:', err);
  
  if (err.type === 'entity.parse.failed') {
    return res.status(400).json({ error: 'Invalid JSON' });
  }
  
  if (err.code === 'LIMIT_FILE_SIZE') {
    return res.status(413).json({ error: 'Payload too large' });
  }
  
  res.status(500).json({ error: 'Internal server error' });
});

// Start server
app.listen(argv.port, argv.host, () => {
  console.log(`[TeleCursor Server] Running on http://${argv.host}:${argv.port}`);
  console.log(`[TeleCursor Server] Rate limit: ${argv.rateLimit} req/min`);
});

export default app;
