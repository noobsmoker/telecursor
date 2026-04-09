/**
 * TeleCursor Database Module
 * 
 * SQLite-based storage for cursor trajectory data.
 * Schema designed for privacy and efficient queries.
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
  
  // Enable WAL mode for better concurrent performance
  db.pragma('journal_mode = WAL');
  db.pragma('synchronous = NORMAL');
  
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
      sample_count INTEGER,
      duration_ms INTEGER,
      
      -- Interaction summary
      click_count INTEGER,
      hover_count INTEGER,
      scroll_count INTEGER,
      
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
      ax REAL,
      ay REAL,
      button_state INTEGER,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      
      FOREIGN KEY (trajectory_id) REFERENCES trajectories(id)
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
      target_selector TEXT,
      target_category TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      
      FOREIGN KEY (trajectory_id) REFERENCES trajectories(id)
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
  
  // Create indexes
  db.exec(`
    CREATE INDEX IF NOT EXISTS idx_trajectories_created ON trajectories(created_at);
    CREATE INDEX IF NOT EXISTS idx_trajectories_domain ON trajectories(domain_category);
    CREATE INDEX IF NOT EXISTS idx_trajectory_samples_trajectory ON trajectory_samples(trajectory_id);
    CREATE INDEX IF NOT EXISTS idx_interaction_events_trajectory ON interaction_events(trajectory_id);
    CREATE INDEX IF NOT EXISTS idx_daily_stats_date ON daily_stats(date);
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
}

export function getDatabase() {
  if (!db) {
    throw new Error('Database not initialized. Call initDatabase() first.');
  }
  return db;
}

export function closeDatabase() {
  if (db) {
    db.close();
    db = null;
    console.log('[TeleCursor DB] Closed');
  }
}

export default { initDatabase, getDatabase, closeDatabase };
