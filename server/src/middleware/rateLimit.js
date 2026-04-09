/**
 * Rate Limit Middleware
 * 
 * Simple IP-based rate limiting to prevent abuse.
 */

import crypto from 'crypto';

export function rateLimitMiddleware(requestsPerMinute = 100) {
  const windowMs = 60 * 1000; // 1 minute
  const cache = new Map();
  
  // Cleanup old entries periodically
  setInterval(() => {
    const now = Date.now();
    for (const [key, value] of cache.entries()) {
      if (now - value.windowStart > windowMs) {
        cache.delete(key);
      }
    }
  }, windowMs);
  
  return (req, res, next) => {
    const ip = getClientIp(req);
    const key = crypto.createHash('sha256').update(ip).digest('hex').substring(0, 16);
    
    let record = cache.get(key);
    const now = Date.now();
    
    if (!record || now - record.windowStart > windowMs) {
      record = {
        count: 0,
        windowStart: now
      };
      cache.set(key, record);
    }
    
    record.count++;
    record.lastRequest = now;
    
    // Set rate limit headers
    res.set('X-RateLimit-Limit', requestsPerMinute);
    res.set('X-RateLimit-Remaining', Math.max(0, requestsPerMinute - record.count));
    res.set('X-RateLimit-Reset', Math.ceil((record.windowStart + windowMs) / 1000));
    
    if (record.count > requestsPerMinute) {
      return res.status(429).json({
        error: 'Rate limit exceeded',
        retry_after: Math.ceil((record.windowStart + windowMs - now) / 1000)
      });
    }
    
    next();
  };
}

function getClientIp(req) {
  // Check various headers for client IP
  return req.headers['x-forwarded-for']?.split(',')[0]?.trim()
    || req.headers['x-real-ip']
    || req.socket?.remoteAddress
    || 'unknown';
}
