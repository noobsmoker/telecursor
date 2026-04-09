/**
 * TeleCursor Trajectory Routes
 * 
 * API endpoints for submitting and querying cursor trajectory data.
 * Optimized for performance with batch inserts and transactions.
 * B-002: Fixed SQL injection vulnerabilities with parameterized queries
 */

import { Router } from 'express';
import { v4 as uuidv4 } from 'uuid';
import crypto from 'crypto';

// B-002: Input validation schemas
const VALIDATION = {
  trajectory: {
    required: ['session_context', 'samples', 'anonymization'],
    session_context: {
      domain: { type: 'string', maxLength: 253 },
      page_path: { type: 'string', maxLength: 2048 },
      viewport: { type: 'object' },
      device_type: { type: 'string', enum: ['desktop', 'mobile', 'tablet'] },
      input_method: { type: 'string', enum: ['mouse', 'touch', 'trackpad'] }
    },
    samples: { type: 'array', minLength: 10, maxLength: 10000 },
    anonymization: {
      user_consent: { type: 'boolean' },
      epsilon: { type: 'number', min: 0.1, max: 10 }
    }
  }
};

/**
 * B-002: Validate input data to prevent injection attacks
 */
function validateInput(data, schema) {
  const errors = [];
  
  // Check required fields
  for (const field of schema.required || []) {
    if (!data[field]) {
      errors.push(`Missing required field: ${field}`);
    }
  }
  
  // Validate session context
  if (data.session_context) {
    const sc = data.session_context;
    
    if (sc.domain && typeof sc.domain !== 'string') {
      errors.push('domain must be string');
    }
    if (sc.device_type && !['desktop', 'mobile', 'tablet'].includes(sc.device_type)) {
      errors.push('invalid device_type');
    }
    if (sc.input_method && !['mouse', 'touch', 'trackpad'].includes(sc.input_method)) {
      errors.push('invalid input_method');
    }
  }
  
  // Validate samples array
  if (data.samples) {
    if (!Array.isArray(data.samples)) {
      errors.push('samples must be array');
    } else if (data.samples.length < 10) {
      errors.push('samples too short (min 10)');
    } else if (data.samples.length > 10000) {
      errors.push('samples too long (max 10000)');
    } else {
      // Validate sample structure
      for (let i = 0; i < Math.min(data.samples.length, 100); i++) {
        const s = data.samples[i];
        if (typeof s.x !== 'number' || typeof s.y !== 'number') {
          errors.push(`sample ${i}: invalid x/y`);
          break;
        }
      }
    }
  }
  
  return errors;
}

export function createTrajectoryRoutes(db) {
  const router = Router();
  
  // Prepared statements for performance
  const insertTrajectory = db.prepare(`
    INSERT INTO trajectories (
      id, domain_category, page_path_hash, viewport_width, viewport_height,
      device_type, input_method, sample_count, duration_ms,
      click_count, hover_count, scroll_count, consent_verified, expires_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, datetime('now', '+90 days'))
  `);

  const insertSampleBatch = db.prepare(`
    INSERT INTO trajectory_samples (trajectory_id, t_ms, x, y, vx, vy)
    VALUES (?, ?, ?, ?, ?, ?)
  `);

  const insertEventBatch = db.prepare(`
    INSERT INTO interaction_events (
      trajectory_id, t_ms, event_type, x, y, 
      target_tag, target_role, target_category
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
  `);

  const updateDailyStats = db.prepare(`
    INSERT INTO daily_stats (date, total_sessions, total_samples, total_duration_ms, unique_domains)
    VALUES (?, 1, ?, ?, 1)
    ON CONFLICT(date) DO UPDATE SET
      total_sessions = total_sessions + 1,
      total_samples = total_samples + ?,
      total_duration_ms = total_duration_ms + ?
  `);

  /**
   * POST /api/v1/trajectories
   * Submit a new cursor trajectory (single)
   * B-002: Added input validation
   */
  router.post('/', (req, res) => {
    try {
      const data = req.body;
      
      // B-002: Validate input to prevent injection attacks
      const validationErrors = validateInput(data, VALIDATION.trajectory);
      if (validationErrors.length > 0) {
        console.error('[Trajectories] Validation failed:', validationErrors);
        return res.status(400).json({ 
          error: 'Validation failed',
          details: validationErrors
        });
      }
      
      // Handle batch submission
      if (data.trajectories && Array.isArray(data.trajectories)) {
        return handleBatchSubmit(data.trajectories, db, res);
      }
      
      // Single trajectory submission (existing code)
      const result = insertTrajectoryData(data, db);
      if (result.error) {
        return res.status(400).json({ error: result.error });
      }
      
      res.status(201).json({
        success: true,
        trajectory_id: result.trajectory_id,
        message: 'Trajectory recorded'
      });
      
    } catch (error) {
      console.error('[Trajectories] Error:', error.message);
      res.status(500).json({ error: 'Failed to record trajectory' });
    }
  });

  /**
   * POST /api/v1/trajectories/batch
   * Submit multiple cursor trajectories at once
   */
  router.post('/batch', (req, res) => {
    try {
      const { trajectories } = req.body;
      
      if (!Array.isArray(trajectories) || trajectories.length === 0) {
        return res.status(400).json({ 
          error: 'Missing or invalid trajectories array' 
        });
      }
      
      const results = handleBatchSubmit(trajectories, db, res);
      return results;
      
    } catch (error) {
      console.error('[Trajectories] Batch error:', error.message);
      res.status(500).json({ error: 'Failed to record trajectories' });
    }
  });
  
  /**
   * Handle batch trajectory submission
   */
  function handleBatchSubmit(trajectories, db, res) {
    const results = [];
    let successCount = 0;
    let errorCount = 0;
    
    for (const data of trajectories) {
      try {
        // Validate required fields
        if (!data.session_context || !data.samples?.length || !data.anonymization) {
          results.push({ error: 'Missing required fields' });
          errorCount++;
          continue;
        }

        // Verify consent
        if (!data.anonymization.user_consent) {
          results.push({ error: 'User consent required' });
          errorCount++;
          continue;
        }
        
        const result = insertTrajectoryData(data, db);
        if (result.error) {
          results.push({ error: result.error });
          errorCount++;
        } else {
          results.push({ trajectory_id: result.trajectory_id, success: true });
          successCount++;
        }
      } catch (e) {
        results.push({ error: e.message });
        errorCount++;
      }
    }
    
    res.status(201).json({
      success: true,
      total: trajectories.length,
      succeeded: successCount,
      failed: errorCount,
      results: results
    });
  }
  
  /**
   * Insert trajectory data (single)
   */
  function insertTrajectoryData(data, db) {
    // Validate required fields
    if (!data.session_context || !data.samples?.length || !data.anonymization) {
      return { error: 'Missing required fields: session_context, samples, anonymization' };
    }

    // Verify consent
    if (!data.anonymization.user_consent) {
      return { error: 'User consent required for data submission' };
    }

    // Sanitize inputs
    const trajectoryId = uuidv4();
    const domainCategory = categorizeDomain(data.session_context.domain || '');
    const pagePathHash = hashString(data.session_context.page_path || '');
    const samples = Array.isArray(data.samples) ? data.samples : [];
    const events = Array.isArray(data.interaction_events) ? data.interaction_events : [];

    // Calculate stats
    const sampleCount = samples.length;
    const durationMs = sampleCount > 0 
      ? samples[sampleCount - 1].t - samples[0].t 
      : 0;
    
    const eventCounts = countEvents(events);

    // Use transaction for atomicity
    const insertTransaction = db.transaction(() => {
      // Insert trajectory metadata
      insertTrajectory.run(
        trajectoryId,
        domainCategory,
        pagePathHash,
        Math.min(Math.max(data.session_context.viewport?.width || 0, 0), 10000),
        Math.min(Math.max(data.session_context.viewport?.height || 0, 0), 10000),
        sanitizeString(data.session_context.device_type, 20),
        sanitizeString(data.session_context.input_method, 20),
        sampleCount,
        Math.min(durationMs, 600000), // Cap at 10 min
        eventCounts.clicks,
        eventCounts.hover,
        eventCounts.scroll
      );

      // Batch insert samples (every 10th for storage efficiency)
      const downsampleRate = 10;
      for (let i = 0; i < samples.length; i += downsampleRate) {
        const s = samples[i];
        insertSampleBatch.run(
          trajectoryId,
          Math.round(s.t),
          Math.round(s.x * 10) / 10,
          Math.round(s.y * 10) / 10,
          Math.round(Math.max(-5000, Math.min(5000, s.vx || 0))),
          Math.round(Math.max(-5000, Math.min(5000, s.vy || 0)))
        );
      }

      // Batch insert events
      for (const event of events) {
        insertEventBatch.run(
          trajectoryId,
          Math.round(event.t || 0),
          sanitizeString(event.type, 30),
          Math.round(event.x || 0),
          Math.round(event.y || 0),
          sanitizeString(event.target?.tag, 10),
          sanitizeString(event.target?.role, 30),
          sanitizeString(event.target?.semantic_category, 20)
        );
      }

      // Update daily stats
      const today = new Date().toISOString().split('T')[0];
      updateDailyStats.run(today, sampleCount, durationMs, sampleCount, durationMs);
    });

    insertTransaction();
    
    return { trajectory_id: trajectoryId };
  }
  
  /**
   * GET /api/v1/trajectories/:id
   * Get a specific trajectory (anonymized)
   */
  router.get('/:id', (req, res) => {
    try {
      const { id } = req.params;
      
      // Validate ID format
      if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id)) {
        return res.status(400).json({ error: 'Invalid trajectory ID format' });
      }
      
      const trajectory = db.prepare(`
        SELECT id, created_at, domain_category, viewport_width, viewport_height,
               device_type, input_method, sample_count, duration_ms,
               click_count, hover_count, scroll_count
        FROM trajectories WHERE id = ? AND deleted_at IS NULL
      `).get(id);
      
      if (!trajectory) {
        return res.status(404).json({ error: 'Trajectory not found' });
      }

      // Parallel fetch samples and events
      const [samples, events] = Promise.all([
        db.prepare(`
          SELECT t_ms, x, y, vx, vy FROM trajectory_samples 
          WHERE trajectory_id = ? ORDER BY t_ms
        `).all(id),
        db.prepare(`
          SELECT t_ms, event_type, x, y, target_tag, target_role, target_category
          FROM interaction_events WHERE trajectory_id = ? ORDER BY t_ms
        `).all(id)
      ]);

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
          t: s.t_ms, x: s.x, y: s.y, vx: s.vx, vy: s.vy
        })),
        interaction_events: events
      });
      
    } catch (error) {
      console.error('[Trajectories] Get error:', error.message);
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
      
      // Validate and clamp pagination
      const safeLimit = Math.min(Math.max(parseInt(limit) || 100, 1), 1000);
      const safeOffset = Math.max(parseInt(offset) || 0, 0);
      
      let query = 'SELECT id, created_at, domain_category, device_type, sample_count, duration_ms FROM trajectories WHERE deleted_at IS NULL';
      const params = [];
      
      if (domain_category) {
        const safeCategory = sanitizeString(domain_category, 20);
        if (safeCategory) {
          query += ' AND domain_category = ?';
          params.push(safeCategory);
        }
      }
      
      if (device_type) {
        const safeDevice = sanitizeString(device_type, 20);
        if (safeDevice) {
          query += ' AND device_type = ?';
          params.push(safeDevice);
        }
      }
      
      if (min_samples) {
        const safeMin = parseInt(min_samples);
        if (safeMin > 0) {
          query += ' AND sample_count >= ?';
          params.push(safeMin);
        }
      }
      
      query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?';
      params.push(safeLimit, safeOffset);
      
      const trajectories = db.prepare(query).all(...params);
      
      res.json({
        trajectories: trajectories,
        limit: safeLimit,
        offset: safeOffset
      });
      
    } catch (error) {
      console.error('[Trajectories] Query error:', error.message);
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
      
      // Validate ID format
      if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id)) {
        return res.status(400).json({ error: 'Invalid trajectory ID format' });
      }
      
      const result = db.prepare(`
        UPDATE trajectories SET deleted_at = datetime('now') 
        WHERE id = ? AND deleted_at IS NULL
      `).run(id);
      
      if (result.changes === 0) {
        return res.status(404).json({ error: 'Trajectory not found' });
      }
      
      res.json({ success: true, message: 'Trajectory deleted' });
      
    } catch (error) {
      console.error('[Trajectories] Delete error:', error.message);
      res.status(500).json({ error: 'Failed to delete trajectory' });
    }
  });
  
  return router;
}

/**
 * Sanitize string input - prevents injection and limits length
 */
function sanitizeString(str, maxLength = 100) {
  if (!str || typeof str !== 'string') return '';
  return str.slice(0, maxLength).replace(/[<>'";]/g, '');
}

/**
 * Categorize domain into high-level category
 */
function categorizeDomain(domain = '') {
  if (!domain) return 'unknown';
  
  const lowerDomain = domain.toLowerCase();
  
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
    if (patterns.some(p => lowerDomain.includes(p))) {
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
  if (!Array.isArray(events)) return { clicks: 0, hover: 0, scroll: 0 };
  
  let clicks = 0, hover = 0, scroll = 0;
  
  for (const event of events) {
    const type = event?.type;
    if (type === 'click') clicks++;
    else if (type?.startsWith('hover')) hover++;
    else if (type === 'scroll') scroll++;
  }
  
  return { clicks, hover, scroll };
}