/**
 * TeleCursor Statistics Routes
 * 
 * Public API endpoints for aggregated statistics.
 * Optimized with in-memory caching.
 */

import { Router } from 'express';

export function createStatsRoutes(db) {
  const router = Router();
  
  // In-memory cache with TTL
  const cache = new Map();
  const CACHE_TTL = 60000; // 60 seconds
  
  function getCached(key, fetchFn) {
    const now = Date.now();
    const entry = cache.get(key);
    
    if (entry && (now - entry.timestamp) < CACHE_TTL) {
      return entry.data;
    }
    
    const data = fetchFn();
    cache.set(key, { timestamp: now, data });
    return data;
  }
  
  /**
   * GET /api/v1/stats
   * Get overall statistics
   */
  router.get('/', (req, res) => {
    try {
      const cacheKey = 'stats:overview';
      
      const data = getCached(cacheKey, () => {
        const today = new Date().toISOString().split('T')[0];
        
        // Single optimized query for all stats
        const stats = db.prepare(`
          SELECT 
            (SELECT COUNT(*) FROM trajectories WHERE deleted_at IS NULL) as total_sessions,
            (SELECT SUM(sample_count) FROM trajectories WHERE deleted_at IS NULL) as total_samples,
            (SELECT SUM(duration_ms) FROM trajectories WHERE deleted_at IS NULL) as total_duration,
            (SELECT COUNT(DISTINCT domain_category) FROM trajectories WHERE deleted_at IS NULL) as unique_domains,
            (SELECT * FROM daily_stats WHERE date = ?) as today_stats,
            (SELECT date, total_sessions, total_samples, total_duration_ms 
             FROM daily_stats WHERE date >= date('now', '-7 days') ORDER BY date ASC) as weekly
        `).get(today);
        
        return {
          summary: {
            total_sessions: stats.total_sessions || 0,
            total_samples: stats.total_samples || 0,
            total_duration_hours: Math.round((stats.total_duration || 0) / 3600000),
            unique_domains: stats.unique_domains || 0
          },
          today: stats.today_stats || { total_sessions: 0, total_samples: 0 },
          weekly: stats.weekly || [],
          updated_at: new Date().toISOString()
        };
      });
      
      res.json(data);
      
    } catch (error) {
      console.error('[Stats] Error:', error.message);
      res.status(500).json({ error: 'Failed to get statistics' });
    }
  });
  
  /**
   * GET /api/v1/stats/domains
   * Get statistics by domain category (cached)
   */
  router.get('/domains', (req, res) => {
    try {
      const cacheKey = 'stats:domains';
      
      const data = getCached(cacheKey, () => {
        const stats = db.prepare(`
          SELECT 
            domain_category,
            COUNT(*) as session_count,
            SUM(sample_count) as total_samples,
            AVG(sample_count) as avg_samples,
            SUM(duration_ms) as total_duration_ms,
            AVG(duration_ms) as avg_duration_ms
          FROM trajectories 
          WHERE deleted_at IS NULL
          GROUP BY domain_category
          ORDER BY session_count DESC
        `).all();
        
        return {
          domains: stats.map(d => ({
            category: d.domain_category,
            session_count: d.session_count,
            total_samples: d.total_samples,
            avg_samples: Math.round(d.avg_samples),
            total_duration_hours: Math.round((d.total_duration_ms || 0) / 3600000),
            avg_duration_ms: Math.round(d.avg_duration_ms)
          }))
        };
      });
      
      res.json(data);
      
    } catch (error) {
      console.error('[Stats] Domains error:', error.message);
      res.status(500).json({ error: 'Failed to get domain stats' });
    }
  });
  
  /**
   * GET /api/v1/stats/devices
   * Get statistics by device type (cached)
   */
  router.get('/devices', (req, res) => {
    try {
      const cacheKey = 'stats:devices';
      
      const data = getCached(cacheKey, () => {
        const stats = db.prepare(`
          SELECT 
            device_type,
            input_method,
            COUNT(*) as session_count,
            SUM(sample_count) as total_samples
          FROM trajectories 
          WHERE deleted_at IS NULL
          GROUP BY device_type, input_method
          ORDER BY session_count DESC
        `).all();
        
        return {
          devices: stats.map(d => ({
            device_type: d.device_type,
            input_method: d.input_method,
            session_count: d.session_count,
            total_samples: d.total_samples
          }))
        };
      });
      
      res.json(data);
      
    } catch (error) {
      console.error('[Stats] Devices error:', error.message);
      res.status(500).json({ error: 'Failed to get device stats' });
    }
  });
  
  /**
   * GET /api/v1/stats/leaderboard
   * Get top contributing domains (cached)
   */
  router.get('/leaderboard', (req, res) => {
    try {
      const cacheKey = 'stats:leaderboard';
      
      const data = getCached(cacheKey, () => {
        const topDomains = db.prepare(`
          SELECT 
            domain_category,
            COUNT(*) as contribution_count,
            SUM(sample_count) as total_samples,
            MAX(created_at) as last_contribution
          FROM trajectories 
          WHERE deleted_at IS NULL
          AND created_at >= date('now', '-30 days')
          GROUP BY domain_category
          ORDER BY contribution_count DESC
          LIMIT 20
        `).all();
        
        return {
          period: 'last_30_days',
          domains: topDomains.map((d, i) => ({
            rank: i + 1,
            category: d.domain_category,
            contribution_count: d.contribution_count,
            total_samples: d.total_samples,
            last_contribution: d.last_contribution
          }))
        };
      });
      
      res.json(data);
      
    } catch (error) {
      console.error('[Stats] Leaderboard error:', error.message);
      res.status(500).json({ error: 'Failed to get leaderboard' });
    }
  });
  
  /**
   * POST /api/v1/stats/invalidate-cache
   * Invalidate cache (for admin/debugging)
   */
  router.post('/invalidate-cache', (req, res) => {
    const { secret } = req.query;
    if (secret !== process.env.ADMIN_SECRET) {
      return res.status(401).json({ error: 'Unauthorized' });
    }
    
    cache.clear();
    res.json({ success: true, message: 'Cache cleared' });
  });
  
  return router;
}
