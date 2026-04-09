/**
 * TeleCursor Database Module
 * 
 * SQLite-based storage for cursor trajectory data.
 * Schema designed for privacy and efficient queries.
 * Optimized with WAL mode and proper indexing.
 */

import Database from 'better-sqlite3';
import path from 'path';
import { fileURLToPath } from 'url';
import fs from 'fs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const dbPath = process.env.TELECURSOR_DB_PATH || path.join(__dirname, '../../data/telecursor.db');

// Ensure data directory exists
const dataDir = path.dirname(dbPath);
if (!fs.existsSync(dataDir)) {
  fs.mkdirSync(dataDir, { recursive: true });
}

let db = null;

export function initDatabase() {
  db = new Database(dbPath);
  
  // Performance optimizations
  db.pragma('journal_mode = WAL');           // Better concurrent writes
  db.pragma('synchronous = NORMAL');          // Balanced durability/speed
  db.pragma('cache_size = -64000');          // 64MB cache
  db.pragma('temp_store = MEMORY');          // Temp tables in memory
  db.pragma('mmap_size = 268435456');         // 256MB memory-mapped I/O
  db.pragma('busy_timeout = 5000');          // Wait 5s for locks
  
  // Create tables
  createTables();
  
  console.log('[TeleCursor DB] Initialized at:', dbPath);
  
  return db;
}

function createTables() {
  // Trajectories table - main storage
  db.exec(`
    CREATE TABLE IF NOT EXISTS trajectories (
      id TEXT PRIMARY KEY,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      
      -- Session context (anonymized)
      domain_category TEXT,
      page_path_hash TEXT,
      viewport_width INTEGER,
      viewport_height INTEGER,
      device_type TEXT,
      input_method TEXT,
      
      -- Statistics (pre-aggregated, no raw data stored long-term)
      sample_count INTEGER DEFAULT 0,
      duration_ms INTEGER DEFAULT 0,
      
      -- Interaction summary
      click_count INTEGER DEFAULT 0,
      hover_count INTEGER DEFAULT 0,
      scroll_count INTEGER DEFAULT 0,
      
      -- Privacy flags
      consent_verified INTEGER DEFAULT 0,
      anonymized_at TEXT,
      
      -- Data retention
      expires_at TEXT,
      deleted_at TEXT
    )
  `);
  
  // Trajectory samples - stored briefly, then aggregated
  db.exec(`
    CREATE TABLE IF NOT EXISTS trajectory_samples (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      trajectory_id TEXT NOT NULL,
      t_ms INTEGER NOT NULL,
      x REAL NOT NULL,
      y REAL NOT NULL,
      vx REAL,
      vy REAL,
      button_state INTEGER,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      
      FOREIGN KEY (trajectory_id) REFERENCES trajectories(id) ON DELETE CASCADE
    )
  `);
  
  // Interaction events
  db.exec(`
    CREATE TABLE IF NOT EXISTS interaction_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      trajectory_id TEXT NOT NULL,
      t_ms INTEGER NOT NULL,
      event_type TEXT NOT NULL,
      x REAL,
      y REAL,
      target_tag TEXT,
      target_role TEXT,
      target_category TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      
      FOREIGN KEY (trajectory_id) REFERENCES trajectories(id) ON DELETE CASCADE
    )
  `);
  
  // Aggregate statistics (for public API)
  db.exec(`
    CREATE TABLE IF NOT EXISTS daily_stats (
      date TEXT PRIMARY KEY,
      total_sessions INTEGER DEFAULT 0,
      total_samples INTEGER DEFAULT 0,
      total_duration_ms INTEGER DEFAULT 0,
      unique_domains INTEGER DEFAULT 0,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
  `);
  
  // Rate limit tracking
  db.exec(`
    CREATE TABLE IF NOT EXISTS rate_limits (
      ip_hash TEXT PRIMARY KEY,
      request_count INTEGER DEFAULT 0,
      window_start TEXT NOT NULL,
      last_request TEXT NOT NULL
    )
  `);
  
  // Create indexes for common queries
  db.exec(`
    CREATE INDEX IF NOT EXISTS idx_trajectories_created ON trajectories(created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_trajectories_domain ON trajectories(domain_category);
    CREATE INDEX IF NOT EXISTS idx_trajectories_device ON trajectories(device_type);
    CREATE INDEX IF NOT EXISTS idx_trajectories_deleted ON trajectories(deleted_at);
    CREATE INDEX IF NOT EXISTS idx_trajectories_consent ON trajectories(consent_verified);
    CREATE INDEX IF NOT EXISTS idx_trajectories_samples ON trajectories(sample_count);
    
    CREATE INDEX IF NOT EXISTS idx_samples_trajectory ON trajectory_samples(trajectory_id);
    CREATE INDEX IF NOT EXISTS idx_samples_time ON trajectory_samples(trajectory_id, t_ms);
    
    CREATE INDEX IF NOT EXISTS idx_events_trajectory ON interaction_events(trajectory_id);
    CREATE INDEX IF NOT EXISTS idx_events_type ON interaction_events(event_type);
    
    CREATE INDEX IF NOT EXISTS idx_daily_stats_date ON daily_stats(date DESC);
  `);
  
  // Data retention policy - auto-delete after 90 days
  db.exec(`
    CREATE TRIGGER IF NOT EXISTS auto_delete_old_trajectories
    AFTER INSERT ON trajectories
    BEGIN
      DELETE FROM trajectories 
      WHERE created_at < datetime('now', '-90 days') 
      AND deleted_at IS NULL;
    END
  `);
  
  // Cascade delete for samples/events when trajectory deleted
  db.exec(`
    CREATE TRIGGER IF NOT EXISTS delete_trajectory_samples
    AFTER DELETE ON trajectories
    BEGIN
      DELETE FROM trajectory_samples WHERE trajectory_id = OLD.id;
      DELETE FROM interaction_events WHERE trajectory_id = OLD.id;
    END
  `);
}

export function getDatabase() {
  if (!db) {
    throw new Error('Database not initialized. Call initDatabase() first.');
  }
  return db;
}

export function closeDatabase() {
  if (db) {
    // Checkpoint WAL before closing
    db.pragma('wal_checkpoint(TRUNCATE)');
    db.close();
    db = null;
    console.log('[TeleCursor DB] Closed');
  }
}

// Export for debugging
export function getDbStats() {
  if (!db) return null;
  
  return db.prepare(`
    SELECT 
      (SELECT COUNT(*) FROM trajectories WHERE deleted_at IS NULL) as trajectories,
      (SELECT COUNT(*) FROM trajectory_samples) as samples,
      (SELECT COUNT(*) FROM interaction_events) as events,
      (SELECT page_count * page_size as bytes_used FROM pragma_page_count(), pragma_page_size()) as db_size
  `).get();
}

export default { initDatabase, getDatabase, closeDatabase, getDbStats };
