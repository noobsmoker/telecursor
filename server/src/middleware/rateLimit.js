/**
 * Tiered Rate Limit Middleware
 * 
 * Different limits for read vs write operations.
 * Write: 30 req/min (POST, PUT, DELETE)
 * Read: 100 req/min (GET)
 */

import crypto from 'crypto';

export function rateLimitMiddleware(options = {}) {
  const {
    writeLimit = 30,
    readLimit = 100,
    windowMs = 60 * 1000
  } = options;

  const cache = new Map();
  
  // Cleanup old entries periodically
  const cleanupInterval = setInterval(() => {
    const now = Date.now();
    for (const [key, value] of cache.entries()) {
      if (now - value.windowStart > windowMs) {
        cache.delete(key);
      }
    }
  }, windowMs);
  
  // Cleanup on module unload
  process.on('SIGTERM', () => clearInterval(cleanupInterval));
  process.on('SIGINT', () => clearInterval(cleanupInterval));
  
  return (req, res, next) => {
    const ip = getClientIp(req);
    const key = crypto.createHash('sha256').update(ip).digest('hex').substring(0, 16);
    
    // Determine limit based on HTTP method
    const method = req.method.toUpperCase();
    const isWrite = ['POST', 'PUT', 'DELETE', 'PATCH'].includes(method);
    const limit = isWrite ? writeLimit : readLimit;
    
    let record = cache.get(key);
    const now = Date.now();
    
    if (!record || now - record.windowStart > windowMs) {
      record = {
        count: 0,
        windowStart: now,
        writeCount: 0,
        readCount: 0
      };
      cache.set(key, record);
    }
    
    // Track separately for write vs read
    if (isWrite) {
      record.writeCount++;
    } else {
      record.readCount++;
    }
    record.count++;
    record.lastRequest = now;
    
    // Set rate limit headers with dynamic limits
    res.set('X-RateLimit-Limit', limit);
    res.set('X-RateLimit-Remaining', Math.max(0, limit - (isWrite ? record.writeCount : record.readCount)));
    res.set('X-RateLimit-Reset', Math.ceil((record.windowStart + windowMs) / 1000));
    res.set('X-RateLimit-Scope', isWrite ? 'write' : 'read');
    
    // Check limit
    const currentCount = isWrite ? record.writeCount : record.readCount;
    if (currentCount > limit) {
      return res.status(429).json({
        error: 'Rate limit exceeded',
        limit: limit,
        scope: isWrite ? 'write' : 'read',
        retry_after: Math.ceil((record.windowStart + windowMs - now) / 1000)
      });
    }
    
    next();
  };
}

function getClientIp(req) {
  return req.headers['x-forwarded-for']?.split(',')[0]?.trim()
    || req.headers['x-real-ip']
    || req.socket?.remoteAddress
    || 'unknown';
}