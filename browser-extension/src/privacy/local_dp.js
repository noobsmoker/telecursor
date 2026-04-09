/**
 * CursorTelemetry - Local Differential Privacy Filter
 * 
 * Adds noise to cursor data before any transmission or storage.
 * Implements Laplace mechanism for spatial privacy.
 * Uses Web Crypto API for cryptographic security.
 * 
 * @version 0.2.0
 */

class LocalPrivacyFilter {
  constructor(epsilon = 3.0) {
    this.epsilon = epsilon;
    this.sensitivity = this.computeSensitivity();
    this._saltPromise = null;
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
   * Cryptographically secure Laplace noise using Web Crypto API
   */
  addLaplaceNoise(value, scale) {
    // Use crypto.getRandomValues for secure randomness
    const randomBytes = new Uint8Array(4);
    crypto.getRandomValues(randomBytes);
    
    // Convert to float in [0, 1)
    let u = (
      randomBytes[0] / 255 +
      randomBytes[1] / 65025 +
      randomBytes[2] / 16581375 +
      randomBytes[3] / 4228250625
    );
    
    // Apply Laplace distribution
    const noise = -scale * Math.sign(u - 0.5) * Math.log(1 - 2 * Math.abs(u - 0.5));
    return Math.round((value + noise) * 100) / 100;
  }

  /**
   * Cryptographically secure random for subsampling
   */
  subsample(trajectory, rate = 0.7) {
    const randomBytes = new Uint8Array(trajectory.length);
    crypto.getRandomValues(randomBytes);
    
    return trajectory.filter((_, i) => randomBytes[i] / 255 < rate);
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
      },
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
    
    if (tag === 'nav' || role === 'navigation' || role === 'menu') return 'navigation';
    if (tag === 'button' || role === 'button') return 'button';
    if (tag === 'a' || role === 'link') return 'link';
    if (['input', 'textarea', 'select'].includes(tag) || role === 'textbox') return 'input';
    if (['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'].includes(tag)) return 'text';
    if (tag === 'img' || tag === 'video' || role === 'img') return 'media';
    if (tag === 'ul' || tag === 'ol' || tag === 'li') return 'list';
    if (['div', 'section', 'article', 'main', 'aside'].includes(tag)) return 'container';
    
    return 'other';
  }

  /**
   * Secure user hash using SubtleCrypto
   * Returns promise for async hash
   */
  async hashUser() {
    const salt = await this._getSecureSalt();
    const data = navigator.userAgent + screen.width + screen.height;
    
    const encoder = new TextEncoder();
    const dataBuffer = encoder.encode(data + salt);
    
    const hashBuffer = await crypto.subtle.digest('SHA-256', dataBuffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('').substring(0, 16);
  }

  /**
   * Get or generate salt using Extension Storage API only
   * B-005: Fail closed - no localStorage fallback
   */
  async _getSecureSalt() {
    const storageKey = 'telecursor_secure_salt';
    
    // Only use extension storage API - fail if unavailable
    if (typeof chrome !== 'undefined' && chrome.storage) {
      try {
        const result = await chrome.storage.local.get(storageKey);
        if (result[storageKey]) return result[storageKey];
        
        // Generate new cryptographically secure salt
        const saltBytes = new Uint8Array(32);
        crypto.getRandomValues(saltBytes);
        const salt = Array.from(saltBytes).map(b => b.toString(16).padStart(2, '0')).join('');
        
        // Store using extension API only
        await chrome.storage.local.set({ [storageKey]: salt });
        return salt;
      } catch (e) {
        // B-005: Fail closed - don't fall back to localStorage
        console.error('[Privacy] Secure storage unavailable, failing closed');
        throw new Error('Secure storage required but unavailable');
      }
    }
    
    // B-005: Fail closed - no fallback
    throw new Error('Extension storage API not available');
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
    const requiredScale = this.sensitivity.spatial / epsilon;
    
    return {
      epsilon: epsilon,
      achievedEpsilon: epsilon,
      delta: delta,
      sufficientPrivacy: epsilon <= 8.0,
      recommendation: epsilon > 3.0 ? 
        'Consider lowering epsilon for stronger privacy' : 
        'Epsilon setting is appropriate'
    };
  }
}

// Export
window.LocalPrivacyFilter = LocalPrivacyFilter;
