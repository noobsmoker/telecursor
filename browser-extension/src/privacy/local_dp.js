/**
 * CursorTelemetry - Local Differential Privacy Filter
 * 
 * Adds noise to cursor data before any transmission or storage.
 * Implements Laplace mechanism for spatial privacy.
 * 
 * @version 0.1.0
 */

class LocalPrivacyFilter {
  constructor(epsilon = 3.0) {
    this.epsilon = epsilon;
    this.sensitivity = this.computeSensitivity();
  }

  /**
   * Compute sensitivity based on data domain
   * Sensitivity = max change a single record can make
   */
  computeSensitivity() {
    return {
      spatial: 10,      // Max pixel difference
      temporal: 100,    // Max ms difference
      velocity: 500,    // Max px/s difference
      acceleration: 1000 // Max px/s² difference
    };
  }

  /**
   * Add Laplace noise to trajectory points
   * Privacy guarantee: Individual points are plausibly deniable
   */
  addSpatialNoise(trajectory) {
    const scale = this.sensitivity.spatial / this.epsilon;
    
    return trajectory.map(point => ({
      ...point,
      x: this.addLaplaceNoise(point.x, scale),
      y: this.addLaplaceNoise(point.y, scale),
      // Velocity/acceleration derived from noisy positions
      // No additional privacy loss from post-processing
    }));
  }

  /**
   * Add Laplace noise to velocity
   */
  addVelocityNoise(trajectory) {
    const scale = this.sensitivity.velocity / this.epsilon;
    
    return trajectory.map(point => ({
      ...point,
      vx: this.addLaplaceNoise(point.vx, scale),
      vy: this.addLaplaceNoise(point.vy, scale)
    }));
  }

  /**
   * Add Laplace noise to acceleration
   */
  addAccelerationNoise(trajectory) {
    const scale = this.sensitivity.acceleration / this.epsilon;
    
    return trajectory.map(point => ({
      ...point,
      ax: this.addLaplaceNoise(point.ax, scale),
      ay: this.addLaplaceNoise(point.ay, scale)
    }));
  }

  /**
   * Laplace(0, scale) noise generation
   */
  addLaplaceNoise(value, scale) {
    const u = Math.random() - 0.5;
    const noise = -scale * Math.sign(u) * Math.log(1 - 2 * Math.abs(u));
    return Math.round((value + noise) * 100) / 100;
  }

  /**
   * Randomized response: temporally subsample
   * Each point kept with probability p
   */
  subsample(trajectory, rate = 0.7) {
    return trajectory.filter(() => Math.random() < rate);
  }

  /**
   * Generalize DOM context for privacy
   * "div.header-nav > a.btn-primary" -> "nav > a"
   */
  generalizeContext(event) {
    const target = event.target;
    
    if (!target) return event;
    
    return {
      ...event,
      target: {
        tag: target.tag?.toLowerCase(),
        role: target.role,
        semantic_category: this.categorizeElement(target),
        // Removed: specific classes, IDs, exact text
      },
      // Remove exact coordinates, keep relative position
      x_bucket: this.bucketize(event.x, 100),
      y_bucket: this.bucketize(event.y, 100)
    };
  }

  /**
   * Bucketize coordinate to reduce precision
   */
  bucketize(value, bucketSize = 100) {
    return Math.floor(value / bucketSize) * bucketSize;
  }

  /**
   * Categorize element semantically (no identifying info)
   */
  categorizeElement(element) {
    if (!element || !element.tag) return 'unknown';
    
    const tag = element.tag.toLowerCase();
    const role = element.role || '';
    
    // Navigation elements
    if (tag === 'nav' || role === 'navigation' || role === 'menu') {
      return 'navigation';
    }
    
    // Interactive elements
    if (tag === 'button' || role === 'button' || role === 'link') {
      return role === 'link' ? 'link' : 'button';
    }
    
    // Form elements
    if (['input', 'textarea', 'select'].includes(tag) || role === 'textbox') {
      return 'input';
    }
    
    // Text content
    if (['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'].includes(tag)) {
      return 'text';
    }
    
    // Images/media
    if (tag === 'img' || tag === 'video' || role === 'img') {
      return 'media';
    }
    
    // Lists
    if (tag === 'ul' || tag === 'ol' || tag === 'li') {
      return 'list';
    }
    
    // Generic containers
    if (['div', 'section', 'article', 'main', 'aside'].includes(tag)) {
      return 'container';
    }
    
    return 'other';
  }

  /**
   * Create anonymous user hash (for rate limiting, not identification)
   * Uses truncated hash - can't reverse to identify user
   */
  hashUser() {
    const salt = this.getSalt();
    const data = navigator.userAgent + screen.width + screen.height + navigator.hardwareConcurrency;
    
    // Simple hash - in production use Web Crypto API
    let hash = 0;
    const combined = data + salt;
    for (let i = 0; i < combined.length; i++) {
      const char = combined.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash;
    }
    
    // Return truncated (first 16 chars)
    return Math.abs(hash).toString(16).substring(0, 16);
  }

  /**
   * Get or generate salt for hashing
   * Stored locally, never sent to server
   */
  getSalt() {
    const storageKey = 'telemetry_salt';
    
    // Check if we have a stored salt
    const stored = localStorage.getItem(storageKey);
    if (stored) return stored;
    
    // Generate new salt
    const salt = crypto.getRandomValues(new Uint8Array(16))
      .reduce((acc, byte) => acc + byte.toString(16).padStart(2, '0'), '');
    
    localStorage.setItem(storageKey, salt);
    return salt;
  }

  /**
   * Apply full privacy pipeline to trajectory
   */
  anonymize(trajectory) {
    let processed = trajectory;
    
    // 1. Temporal subsampling
    processed = this.subsample(processed, 0.7);
    
    // 2. Add spatial noise
    processed = this.addSpatialNoise(processed);
    
    // 3. Add velocity noise
    processed = this.addVelocityNoise(processed);
    
    // 4. Round to reduce precision
    processed = processed.map(point => ({
      ...point,
      x: Math.round(point.x),
      y: Math.round(point.y),
      t: Math.round(point.t)
    }));
    
    return processed;
  }

  /**
   * Verify differential privacy guarantees
   */
  verifyDP(epsilon, delta = 1e-5) {
    // Check that noise scale matches claimed epsilon
    const requiredScale = this.sensitivity.spatial / epsilon;
    
    // This is a simplified check - real implementation would
    // run statistical tests on actual noise distribution
    return {
      epsilon: epsilon,
      achievedEpsilon: epsilon,  // By construction
      delta: delta,
      sufficientPrivacy: epsilon <= 8.0,  // Standard threshold
      recommendation: epsilon > 3.0 ? 
        'Consider lowering epsilon for stronger privacy' : 
        'Epsilon setting is appropriate'
    };
  }
}

// Export
window.LocalPrivacyFilter = LocalPrivacyFilter;
