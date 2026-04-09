/**
 * TeleCursor Data Collection Server
 * 
 * Receives and stores cursor trajectory data from the browser extension.
 * Applies privacy-preserving transformations before storage.
 * Optimized for production with compression and security headers.
 */

import express from 'express';
import compression from 'compression';
import helmet from 'helmet';
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

// Security middleware
app.use(helmet({
  contentSecurityPolicy: false, // Disable for API
  crossOriginEmbedderPolicy: false
}));

// Compression for responses
app.use(compression());

// Body parsing with size limits
app.use(express.json({ 
  limit: argv.maxBodySize,
  strict: false
}));
app.use(express.urlencoded({ 
  extended: true,
  limit: argv.maxBodySize
}));

// Request logging
app.use(loggingMiddleware);

// Rate limiting
app.use(rateLimitMiddleware(argv.rateLimit));

// CORS
app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', argv.corsOrigin);
  res.header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Telemetry-Consent');
  res.header('Access-Control-Max-Age', '86400');
  
  if (req.method === 'OPTIONS') {
    return res.sendStatus(204);
  }
  next();
});

// Health check with basic system info
app.get('/health', (req, res) => {
  res.json({ 
    status: 'ok', 
    timestamp: new Date().toISOString(),
    version: '0.1.0',
    uptime: process.uptime()
  });
});

// Initialize database
const db = initDatabase();

// API Routes
app.use('/api/v1/trajectories', createTrajectoryRoutes(db));
app.use('/api/v1/stats', createStatsRoutes(db));

// 404 handler
app.use((req, res) => {
  res.status(404).json({ error: 'Not found' });
});

// Global error handler
app.use((err, req, res, next) => {
  console.error('[TeleCursor Server] Error:', err.message);
  
  if (err.type === 'entity.parse.failed') {
    return res.status(400).json({ error: 'Invalid JSON in request body' });
  }
  
  if (err.code === 'LIMIT_FILE_SIZE') {
    return res.status(413).json({ error: 'Request body too large' });
  }
  
  // Don't leak error details in production
  res.status(500).json({ 
    error: 'Internal server error',
    requestId: req.headers['x-request-id'] || uuidv4()
  });
});

// Start server
const server = app.listen(argv.port, argv.host, () => {
  console.log(`[TeleCursor Server] Running on http://${argv.host}:${argv.port}`);
  console.log(`[TeleCursor Server] Rate limit: ${argv.rateLimit} req/min`);
  console.log(`[TeleCursor Server] Max body: ${argv.maxBodySize / 1024 / 1024}MB`);
});

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log('[TeleCursor Server] SIGTERM received, shutting down...');
  server.close(() => {
    console.log('[TeleCursor Server] HTTP server closed');
    process.exit(0);
  });
});

process.on('SIGINT', () => {
  console.log('[TeleCursor Server] SIGINT received, shutting down...');
  server.close(() => {
    console.log('[TeleCursor Server] HTTP server closed');
    process.exit(0);
  });
});

export default app;
