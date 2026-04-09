/**
 * TeleCursor Statistics Routes
 * 
 * Public API endpoints for aggregated statistics.
 */

import { Router } from 'express';

export function createStatsRoutes(db) {
  const router = Router();
  
  /**
   * GET /api/v1/stats
   * Get overall statistics
   */
  router.get('/', (req, res) => {
    try {
      // Get today's stats
      const today = new Date().toISOString().split('T')[0];
      const todayStats = db.prepare(`
        SELECT * FROM daily_stats WHERE date = ?
      `).get(today);
      
      // Get all-time totals
      const totals = db.prepare(`
        SELECT 
          COUNT(*) as total_sessions,
          SUM(sample_count) as total_samples,
          SUM(duration_ms) as total_duration,
          COUNT(DISTINCT domain_category) as unique_domains
        FROM trajectories WHERE deleted_at IS NULL
      `).get();
      
      // Get last 7 days trend
      const weeklyStats = db.prepare(`
        SELECT date, total_sessions, total_samples, total_duration_ms
        FROM daily_stats 
        WHERE date >= date('now', '-7 days')
        ORDER BY date ASC
      `).all();
      
      res.json({
        summary: {
          total_sessions: totals.total_sessions || 0,
          total_samples: totals.total_samples || 0,
          total_duration_hours: Math.round((totals.total_duration || 0) / 3600000),
          unique_domains: totals.unique_domains || 0
        },
        today: todayStats || { total_sessions: 0, total_samples: 0 },
        weekly: weeklyStats,
        updated_at: new Date().toISOString()
      });
      
    } catch (error) {
      console.error('[Stats] Error:', error);
      res.status(500).json({ error: 'Failed to get statistics' });
    }
  });
  
  /**
   * GET /api/v1/stats/domains
   * Get statistics by domain category
   */
  router.get('/domains', (req, res) => {
    try {
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
      
      res.json({
        domains: stats.map(d => ({
          category: d.domain_category,
          session_count: d.session_count,
          total_samples: d.total_samples,
          avg_samples: Math.round(d.avg_samples),
          total_duration_hours: Math.round(d.total_duration_ms / 3600000),
          avg_duration_ms: Math.round(d.avg_duration_ms)
        }))
      });
      
    } catch (error) {
      console.error('[Stats] Domains error:', error);
      res.status(500).json({ error: 'Failed to get domain stats' });
    }
  });
  
  /**
   * GET /api/v1/stats/devices
   * Get statistics by device type
   */
  router.get('/devices', (req, res) => {
    try {
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
      
      res.json({
        devices: stats.map(d => ({
          device_type: d.device_type,
          input_method: d.input_method,
          session_count: d.session_count,
          total_samples: d.total_samples
        }))
      });
      
    } catch (error) {
      console.error('[Stats] Devices error:', error);
      res.status(500).json({ error: 'Failed to get device stats' });
    }
  });
  
  /**
   * GET /api/v1/stats/leaderboard
   * Get top contributors (anonymized)
   */
  router.get('/leaderboard', (req, res) => {
    try {
      // Since we don't track individual users, show domain-level stats
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
      
      res.json({
        period: 'last_30_days',
        domains: topDomains.map((d, i) => ({
          rank: i + 1,
          category: d.domain_category,
          contribution_count: d.contribution_count,
          total_samples: d.total_samples,
          last_contribution: d.last_contribution
        }))
      });
      
    } catch (error) {
      console.error('[Stats] Leaderboard error:', error);
      res.status(500).json({ error: 'Failed to get leaderboard' });
    }
  });
  
  return router;
}
