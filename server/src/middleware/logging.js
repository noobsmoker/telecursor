/**
 * Logging Middleware
 * 
 * Request/response logging with structured output.
 */

export function loggingMiddleware(req, res, next) {
  const start = Date.now();
  
  res.on('finish', () => {
    const duration = Date.now() - start;
    
    const log = {
      timestamp: new Date().toISOString(),
      method: req.method,
      path: req.path,
      status: res.statusCode,
      duration_ms: duration,
      ip: req.headers['x-forwarded-for']?.split(',')[0] || req.socket?.remoteAddress,
      user_agent: req.headers['user-agent']?.substring(0, 100)
    };
    
    // Log to console (in production, would send to logging service)
    const level = res.statusCode >= 400 ? 'ERROR' : 'INFO';
    console.log(`[TeleCursor] ${level}:`, JSON.stringify(log));
  });
  
  next();
}
