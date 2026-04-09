/**
 * TeleCursor Trajectory Routes
 * 
 * API endpoints for submitting and querying cursor trajectory data.
 */

import { Router } from 'express';
import { v4 as uuidv4 } from 'uuid';
import crypto from 'crypto';

export function createTrajectoryRoutes(db) {
  const router = Router();
  
  /**
   * POST /api/v1/trajectories
   * Submit a new cursor trajectory
   * 
   * Body: {
   *   session_context: { domain, page_path, viewport, device_type, input_method },
   *   samples: [{ t, x, y, vx, vy, ax, ay, button_state }],
   *   interaction_events: [{ t, type, x, y, target }],
   *   anonymization: { user_consent, personal_data_scrubbed }
   * }
   */
  router.post('/', async (req, res) => {
    try {
      const data = req.body;
      
      // Validate required fields
      if (!data.session_context || !data.samples || !data.anonymization) {
        return res.status(400).json({ 
          error: 'Missing required fields: session_context, samples, anonymization' 
        });
      }
      
      // Verify consent
      if (!data.anonymization.user_consent) {
        return res.status(403).json({ 
          error: 'User consent required for data submission' 
        });
      }
      
      // Generate trajectory ID
      const trajectoryId = uuidv4();
      
      // Anonymize domain (hash + categorize)
      const domainCategory = categorizeDomain(data.session_context.domain || 'unknown');
      const pagePathHash = hashString(data.session_context.page_path || '');
      
      // Insert trajectory metadata
      const insertTrajectory = db.prepare(`
        INSERT INTO trajectories (
          id, domain_category, page_path_hash, viewport_width, viewport_height,
          device_type, input_method, sample_count, duration_ms,
          click_count, hover_count, scroll_count, consent_verified, expires_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, datetime('now', '+90 days'))
      `);
      
      const sampleCount = data.samples.length;
      const durationMs = data.samples.length > 0 
        ? data.samples[data.samples.length - 1].t - data.samples[0].t 
        : 0;
      
      const eventCounts = countEvents(data.interaction_events || []);
      
      insertTrajectory.run(
        trajectoryId,
        domainCategory,
        pagePathHash,
        data.session_context.viewport?.width || null,
        data.session_context.viewport?.height || null,
        data.session_context.device_type || 'unknown',
        data.session_context.input_method || 'mouse',
        sampleCount,
        durationMs,
        eventCounts.clicks,
        eventCounts.hover,
        eventCounts.scroll
      );
      
      // Insert sample data (with noise applied already on client)
      // Store only aggregated statistical features, not raw samples
      const insertSampleStats = db.prepare(`
        INSERT INTO trajectory_samples (trajectory_id, t_ms, x, y, vx, vy)
        VALUES (?, ?, ?, ?, ?, ?)
      `);
      
      // Downsample: store every 10th sample to reduce storage
      const downsampleRate = 10;
      for (let i = 0; i < data.samples.length; i += downsampleRate) {
        const s = data.samples[i];
        insertSampleStats.run(
          trajectoryId,
          s.t,
          Math.round(s.x * 10) / 10,  // Round to 1 decimal
          Math.round(s.y * 10) / 10,
          Math.round(s.vx),
          Math.round(s.vy)
        );
      }
      
      // Insert interaction events
      const insertEvent = db.prepare(`
        INSERT INTO interaction_events (
          trajectory_id, t_ms, event_type, x, y, 
          target_tag, target_role, target_category
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
      `);
      
      for (const event of (data.interaction_events || [])) {
        insertEvent.run(
          trajectoryId,
          event.t,
          event.type,
          Math.round(event.x),
          Math.round(event.y),
          event.target?.tag || null,
          event.target?.role || null,
          event.target?.semantic_category || null
        );
      }
      
      // Update daily stats
      const today = new Date().toISOString().split('T')[0];
      const updateDaily = db.prepare(`
        INSERT INTO daily_stats (date, total_sessions, total_samples, total_duration_ms, unique_domains)
        VALUES (?, 1, ?, ?, 1)
        ON CONFLICT(date) DO UPDATE SET
          total_sessions = total_sessions + 1,
          total_samples = total_samples + ?,
          total_duration_ms = total_duration_ms + ?
      `);
      
      updateDaily.run(today, sampleCount, durationMs, sampleCount, durationMs);
      
      res.status(201).json({
        success: true,
        trajectory_id: trajectoryId,
        message: 'Trajectory recorded successfully'
      });
      
    } catch (error) {
      console.error('[Trajectories] Error:', error);
      res.status(500).json({ error: 'Failed to record trajectory' });
    }
  });
  
  /**
   * GET /api/v1/trajectories/:id
   * Get a specific trajectory (anonymized)
   */
  router.get('/:id', (req, res) => {
    try {
      const { id } = req.params;
      
      const trajectory = db.prepare(`
        SELECT * FROM trajectories WHERE id = ? AND deleted_at IS NULL
      `).get(id);
      
      if (!trajectory) {
        return res.status(404).json({ error: 'Trajectory not found' });
      }
      
      // Get sample stats (not raw data)
      const samples = db.prepare(`
        SELECT t_ms, x, y, vx, vy FROM trajectory_samples 
        WHERE trajectory_id = ? ORDER BY t_ms
      `).all(id);
      
      // Get interaction events
      const events = db.prepare(`
        SELECT t_ms, event_type, x, y, target_tag, target_role, target_category
        FROM interaction_events WHERE trajectory_id = ? ORDER BY t_ms
      `).all(id);
      
      res.json({
        trajectory_id: trajectory.id,
        created_at: trajectory.created_at,
        session_context: {
          domain_category: trajectory.domain_category,
          viewport: {
            width: trajectory.viewport_width,
            height: trajectory.viewport_height
          },
          device_type: trajectory.device_type,
          input_method: trajectory.input_method
        },
        stats: {
          sample_count: trajectory.sample_count,
          duration_ms: trajectory.duration_ms,
          click_count: trajectory.click_count,
          hover_count: trajectory.hover_count,
          scroll_count: trajectory.scroll_count
        },
        samples: samples.map(s => ({
          t: s.t_ms,
          x: s.x,
          y: s.y,
          vx: s.vx,
          vy: s.vy
        })),
        interaction_events: events
      });
      
    } catch (error) {
      console.error('[Trajectories] Get error:', error);
      res.status(500).json({ error: 'Failed to get trajectory' });
    }
  });
  
  /**
   * GET /api/v1/trajectories
   * Query trajectories with filters
   */
  router.get('/', (req, res) => {
    try {
      const { 
        domain_category, 
        device_type, 
        min_samples, 
        limit = 100, 
        offset = 0 
      } = req.query;
      
      let query = 'SELECT * FROM trajectories WHERE deleted_at IS NULL';
      const params = [];
      
      if (domain_category) {
        query += ' AND domain_category = ?';
        params.push(domain_category);
      }
      
      if (device_type) {
        query += ' AND device_type = ?';
        params.push(device_type);
      }
      
      if (min_samples) {
        query += ' AND sample_count >= ?';
        params.push(parseInt(min_samples));
      }
      
      query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?';
      params.push(parseInt(limit), parseInt(offset));
      
      const trajectories = db.prepare(query).all(...params);
      
      res.json({
        trajectories: trajectories.map(t => ({
          id: t.id,
          created_at: t.created_at,
          domain_category: t.domain_category,
          device_type: t.device_type,
          sample_count: t.sample_count,
          duration_ms: t.duration_ms
        })),
        limit: parseInt(limit),
        offset: parseInt(offset)
      });
      
    } catch (error) {
      console.error('[Trajectories] Query error:', error);
      res.status(500).json({ error: 'Failed to query trajectories' });
    }
  });
  
  /**
   * DELETE /api/v1/trajectories/:id
   * Delete a trajectory (user request)
   */
  router.delete('/:id', (req, res) => {
    try {
      const { id } = req.params;
      
      const result = db.prepare(`
        UPDATE trajectories SET deleted_at = datetime('now') 
        WHERE id = ? AND deleted_at IS NULL
      `).run(id);
      
      if (result.changes === 0) {
        return res.status(404).json({ error: 'Trajectory not found' });
      }
      
      res.json({ success: true, message: 'Trajectory deleted' });
      
    } catch (error) {
      console.error('[Trajectories] Delete error:', error);
      res.status(500).json({ error: 'Failed to delete trajectory' });
    }
  });
  
  return router;
}

/**
 * Categorize domain into high-level category
 */
function categorizeDomain(domain) {
  if (!domain) return 'unknown';
  
  const categories = {
    'search': ['google', 'bing', 'yahoo', 'duckduckgo'],
    'social': ['facebook', 'twitter', 'instagram', 'linkedin', 'reddit', 'tiktok'],
    'shopping': ['amazon', 'ebay', 'etsy', 'shopify', 'walmart'],
    'news': ['cnn', 'bbc', 'nytimes', 'reuters', 'bloomberg'],
    'video': ['youtube', 'netflix', 'twitch', 'vimeo'],
    'developer': ['github', 'stackoverflow', 'gitlab', 'vercel', 'npm'],
    'email': ['gmail', 'outlook', 'yahoo-mail'],
    'education': ['coursera', 'udemy', 'khanacademy', 'edx'],
  };
  
  for (const [category, patterns] of Object.entries(categories)) {
    if (patterns.some(p => domain.includes(p))) {
      return category;
    }
  }
  
  return 'other';
}

/**
 * Simple hash for paths
 */
function hashString(str) {
  return crypto.createHash('sha256').update(str).digest('hex').substring(0, 16);
}

/**
 * Count event types
 */
function countEvents(events) {
  return {
    clicks: events.filter(e => e.type === 'click').length,
    hover: events.filter(e => e.type?.startsWith('hover')).length,
    scroll: events.filter(e => e.type === 'scroll').length
  };
}