/**
 * TeleCursor ClickHouse Integration
 * 
 * O-001: Analytics requirement - ClickHouse for high-performance analytics
 * Handles analytical queries, aggregations, and time-series data
 * 
 * @version 0.1.0
 */

import ClickHouse from 'clickhouse';
import crypto from 'crypto';


/**
 * ClickHouse client configuration
 */
const DEFAULT_CONFIG = {
  host: process.env.CLICKHOUSE_HOST || 'http://localhost',
  port: parseInt(process.env.CLICKHOUSE_PORT || '8124'),
  database: process.env.CLICKHOUSE_DB || 'telecursor',
  user: process.env.CLICKHOUSE_USER || 'default',
  password: process.env.CLICKHOUSE_PASSWORD || '',
  debug: process.env.NODE_ENV !== 'production',
  basicAuth: process.env.CLICKHOUSE_PASSWORD ? {
    username: process.env.CLICKHOUSE_USER || 'default',
    password: process.env.CLICKHOUSE_PASSWORD
  } : null
};

/**
 * Initialize ClickHouse client
 */
export function createClickHouseClient(config = {}) {
  const cfg = { ...DEFAULT_CONFIG, ...config };
  
  const ch = new ClickHouse({
    host: cfg.host,
    port: cfg.port,
    database: cfg.database,
    basicAuth: cfg.basicAuth,
    debug: cfg.debug
  });
  
  return ch;
}


/**
 * ClickHouse database manager
 */
export class ClickHouseManager {
  constructor(config = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.client = createClickHouseClient(config);
    this.isConnected = false;
  }
  
  /**
   * Initialize database and tables
   */
  async initialize() {
    try {
      // Create database if not exists
      await this.client.query(`
        CREATE DATABASE IF NOT EXISTS ${this.config.database}
      `).toPromise();
      
      // Create trajectories table (time-series optimized)
      await this.client.query(`
        CREATE TABLE IF NOT EXISTS ${this.config.database}.trajectories (
          trajectory_id UUID,
          created_at DateTime,
          domain String,
          page_path String,
          viewport_width UInt16,
          viewport_height UInt16,
          device_type String,
          input_method String,
          sample_count UInt32,
          duration_ms UInt32,
          click_count UInt16,
          hover_count UInt16,
          scroll_count UInt16,
          bot_score Float32,
          privacy_epsilon Float32,
          -- Denormalized for analytics
          domain_category Enum8('' = 0, 'search' = 1, 'social' = 2, 'shopping' = 3, 
                               'news' = 4, 'video' = 5, 'developer' = 6, 'email' = 7, 
                               'education' = 8, 'other' = 9),
          hour_of_day UInt8,
          day_of_week UInt8,
          is_weekend Bool
        )
        ENGINE = MergeTree()
        PARTITION BY toYYYYMM(created_at)
        ORDER BY (domain, created_at)
        TTL created_at + INTERVAL 90 DAY
        SETTINGS index_granularity = 8192
      `).toPromise();
      
      // Create samples table (granular analytics)
      await this.client.query(`
        CREATE TABLE IF NOT EXISTS ${this.config.database}.samples (
          trajectory_id UUID,
          t_ms UInt32,
          x Float32,
          y Float32,
          vx Float32,
          vy Float32,
          ax Float32,
          ay Float32,
          button_state UInt8,
          created_at DateTime
        )
        ENGINE = MergeTree()
        PARTITION BY toYYYYMM(created_at)
        ORDER BY (trajectory_id, t_ms)
        SAMPLE BY t_ms
        SETTINGS index_granularity = 1024
      `).toPromise();
      
      // Create daily aggregates (materialized view alternative)
      await this.client.query(`
        CREATE TABLE IF NOT EXISTS ${this.config.database}.daily_aggregates (
          date Date,
          domain_category String,
          device_type String,
          sessions UInt32,
          total_samples UInt64,
          total_duration_ms UInt64,
          avg_session_duration Float32,
          avg_samples_per_session Float32,
          unique_domains UInt32,
          bot_rate Float32,
          updated_at DateTime DEFAULT now()
        )
        ENGINE = SummingMergeTree()
        ORDER BY (date, domain_category, device_type)
      `).toPromise();
      
      // Create index for domain queries
      await this.client.query(`
        ALTER TABLE ${this.config.database}.trajectories
        ADD INDEX idx_domain domain TYPE bloom_filter GRANULARITY 1
      `).toPromise();
      
      this.isConnected = true;
      console.log('[ClickHouse] Database initialized');
      
    } catch (error) {
      console.error('[ClickHouse] Initialization error:', error.message);
      throw error;
    }
  }
  
  /**
   * Insert trajectory data
   */
  async insertTrajectory(data) {
    const now = new Date();
    const hour = now.getHours();
    const dayOfWeek = now.getDay();
    
    const query = `
      INSERT INTO ${this.config.database}.trajectories (
        trajectory_id, created_at, domain, page_path,
        viewport_width, viewport_height, device_type, input_method,
        sample_count, duration_ms, click_count, hover_count, scroll_count,
        bot_score, privacy_epsilon, domain_category,
        hour_of_day, day_of_week, is_weekend
      ) VALUES
    `;
    
    const values = [
      data.trajectory_id,
      data.timestamp || new Date().toISOString(),
      data.session_context?.domain || '',
      data.session_context?.page_path || '',
      data.session_context?.viewport?.width || 0,
      data.session_context?.viewport?.height || 0,
      data.session_context?.device_type || 'desktop',
      data.session_context?.input_method || 'mouse',
      data.samples?.length || 0,
      data.duration_ms || 0,
      data.interaction_events?.filter(e => e.type === 'click').length || 0,
      data.interaction_events?.filter(e => e.type?.startsWith('hover')).length || 0,
      data.interaction_events?.filter(e => e.type === 'scroll').length || 0,
      data.bot_score || 0,
      data.anonymization?.epsilon || 3.0,
      this.categorizeDomain(data.session_context?.domain || ''),
      hour,
      dayOfWeek,
      dayOfWeek === 0 || dayOfWeek === 6
    ];
    
    return this.client.insert(query, [values]).toPromise();
  }
  
  /**
   * Insert batch of samples
   */
  async insertSamples(trajectoryId, samples) {
    if (!samples || samples.length === 0) return;
    
    // Downsample for storage efficiency (every 10th sample)
    const downsampled = samples.filter((_, i) => i % 10 === 0);
    
    const query = `
      INSERT INTO ${this.config.database}.samples (
        trajectory_id, t_ms, x, y, vx, vy, ax, ay, button_state, created_at
      ) VALUES
    `;
    
    const values = downsampled.map(s => [
      trajectoryId,
      Math.round(s.t),
      Math.round(s.x * 10) / 10,
      Math.round(s.y * 10) / 10,
      Math.round(s.vx * 10) / 10,
      Math.round(s.vy * 10) / 10,
      Math.round(s.ax * 10) / 10,
      Math.round(s.ay * 10) / 10,
      s.button_state || 0,
      new Date().toISOString()
    ]);
    
    return this.client.insert(query, values).toPromise();
  }
  
  /**
   * Analytics: Get domain statistics
   */
  async getDomainStats(days = 7) {
    const query = `
      SELECT
        domain_category,
        count() as sessions,
        sum(sample_count) as total_samples,
        avg(sample_count) as avg_samples,
        sum(duration_ms) as total_duration_ms,
        avg(duration_ms) as avg_duration_ms,
        avg(bot_score) as avg_bot_rate
      FROM ${this.config.database}.trajectories
      WHERE created_at >= now() - INTERVAL ${days} DAY
      GROUP BY domain_category
      ORDER BY sessions DESC
    `;
    
    return this.client.query(query).toPromise();
  }
  
  /**
   * Analytics: Get time-series data
   */
  async getTimeSeries(metric = 'sessions', interval = 'hour', days = 7) {
    const groupBy = interval === 'day' ? 'toDate(created_at)' : 
                    interval === 'hour' ? 'toHour(created_at)' :
                    'toStartOfDay(created_at)';
    
    const query = `
      SELECT
        ${groupBy} as timestamp,
        count() as sessions,
        sum(sample_count) as samples,
        sum(duration_ms) as duration
      FROM ${this.config.database}.trajectories
      WHERE created_at >= now() - INTERVAL ${days} DAY
      GROUP BY ${groupBy}
      ORDER BY timestamp
    `;
    
    return this.client.query(query).toPromise();
  }
  
  /**
   * Analytics: Get device breakdown
   */
  async getDeviceStats(days = 30) {
    const query = `
      SELECT
        device_type,
        input_method,
        count() as sessions,
        sum(sample_count) as total_samples,
        avg(sample_count) as avg_samples
      FROM ${this.config.database}.trajectories
      WHERE created_at >= now() - INTERVAL ${days} DAY
      GROUP BY device_type, input_method
      ORDER BY sessions DESC
    `;
    
    return this.client.query(query).toPromise();
  }
  
  /**
   * Analytics: User engagement funnel
   */
  async getEngagementFunnel(days = 7) {
    const query = `
      SELECT
        count() as total_sessions,
        countIf(click_count > 0) as with_clicks,
        countIf(hover_count > 10) as with_hover,
        countIf(scroll_count > 0) as with_scroll,
        countIf(duration_ms > 30000) as long_sessions,
        countIf(sample_count > 100) as high_samples
      FROM ${this.config.database}.trajectories
      WHERE created_at >= now() - INTERVAL ${days} DAY
    `;
    
    return this.client.query(query).toPromise();
  }
  
  /**
   * Analytics: Cohort analysis
   */
  async getCohortAnalysis(cohortBy = 'day_of_week', days = 30) {
    const query = `
      SELECT
        ${cohortBy},
        count() as sessions,
        avg(sample_count) as avg_samples,
        avg(duration_ms) as avg_duration,
        avg(bot_score) as avg_bot_rate
      FROM ${this.config.database}.trajectories
      WHERE created_at >= now() - INTERVAL ${days} DAY
      GROUP BY ${cohortBy}
      ORDER BY ${cohortBy}
    `;
    
    return this.client.query(query).toPromise();
  }
  
  /**
   * Helper: Categorize domain
   */
  categorizeDomain(domain) {
    if (!domain) return '';
    
    const lower = domain.toLowerCase();
    const categories = {
      'search': ['google', 'bing', 'yahoo', 'duckduckgo'],
      'social': ['facebook', 'twitter', 'instagram', 'linkedin', 'reddit'],
      'shopping': ['amazon', 'ebay', 'etsy', 'shopify'],
      'news': ['cnn', 'bbc', 'nytimes', 'reuters'],
      'video': ['youtube', 'netflix', 'twitch'],
      'developer': ['github', 'stackoverflow', 'gitlab'],
      'email': ['gmail', 'outlook'],
      'education': ['coursera', 'udemy', 'khanacademy']
    };
    
    for (const [cat, patterns] of Object.entries(categories)) {
      if (patterns.some(p => lower.includes(p))) return cat;
    }
    
    return 'other';
  }
  
  /**
   * Health check
   */
  async healthCheck() {
    try {
      await this.client.query('SELECT 1').toPromise();
      return { connected: true };
    } catch (error) {
      return { connected: false, error: error.message };
    }
  }
}


/**
 * O-104: Delta encoding for bandwidth reduction
 */
export class DeltaEncoder {
  /**
   * Encode samples using delta encoding
   */
  static encode(samples) {
    if (!samples || samples.length === 0) return samples;
    
    const encoded = [samples[0]];  // First sample is absolute
    
    for (let i = 1; i < samples.length; i++) {
      const curr = samples[i];
      const prev = samples[i - 1];
      
      encoded.push({
        t: curr.t - prev.t,  // Delta time
        x: curr.x - prev.x,  // Delta position
        y: curr.y - prev.y,
        vx: curr.vx - prev.vx,
        vy: curr.vy - prev.vy,
        ax: curr.ax - prev.ax,
        ay: curr.ay - prev.ay,
        button_state: curr.button_state
      });
    }
    
    return encoded;
  }
  
  /**
   * Decode delta-encoded samples
   */
  static decode(encoded) {
    if (!encoded || encoded.length === 0) return [];
    
    const decoded = [encoded[0]];
    let lastT = encoded[0].t || 0;
    let lastX = encoded[0].x || 0;
    let lastY = encoded[0].y || 0;
    let lastVx = encoded[0].vx || 0;
    let lastVy = encoded[0].vy || 0;
    let lastAx = encoded[0].ax || 0;
    let lastAy = encoded[0].ay || 0;
    
    for (let i = 1; i < encoded.length; i++) {
      const curr = encoded[i];
      
      decoded.push({
        t: lastT + (curr.t || 0),
        x: lastX + (curr.x || 0),
        y: lastY + (curr.y || 0),
        vx: lastVx + (curr.vx || 0),
        vy: lastVy + (curr.vy || 0),
        ax: lastAx + (curr.ax || 0),
        ay: lastAy + (curr.ay || 0),
        button_state: curr.button_state
      });
      
      // Update last values
      lastT = decoded[decoded.length - 1].t;
      lastX = decoded[decoded.length - 1].x;
      lastY = decoded[decoded.length - 1].y;
      lastVx = decoded[decoded.length - 1].vx;
      lastVy = decoded[decoded.length - 1].vy;
      lastAx = decoded[decoded.length - 1].ax;
      lastAy = decoded[decoded.length - 1].ay;
    }
    
    return decoded;
  }
  
  /**
   * Calculate compression ratio
   */
  static getCompressionRatio(original, encoded) {
    const origSize = JSON.stringify(original).length;
    const encSize = JSON.stringify(encoded).length;
    return origSize / encSize;
  }
}


export default { ClickHouseManager, DeltaEncoder, createClickHouseClient };