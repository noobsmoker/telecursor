/**
 * CursorTelemetry - Core Cursor Tracking Module
 * 
 * Captures cursor movement physics, interaction events, and DOM context.
 * Applies local differential privacy before any transmission.
 * Optimized with circular buffers for O(1) velocity calculations.
 * 
 * @version 0.2.0
 */

/**
 * Circular buffer for efficient velocity calculation
 * O(1) push/pop instead of O(n) array operations
 * OPTIMIZED: Uses TypedArray for memory efficiency
 */
class CircularVelocityBuffer {
  constructor(size = 5) {
    this.size = size;
    // Use TypedArrays for memory efficiency (Float64Array)
    this.timestamps = new Float64Array(size);
    this.vx = new Float64Array(size);
    this.vy = new Float64Array(size);
    this.index = 0;
    this.count = 0;
  }

  push(vx, vy, t) {
    this.vx[this.index] = vx;
    this.vy[this.index] = vy;
    this.timestamps[this.index] = t;
    this.index = (this.index + 1) % this.size;
    this.count = Math.min(this.count + 1, this.size);
  }

  getSmoothed() {
    if (this.count === 0) return { vx: 0, vy: 0 };
    let sumVx = 0, sumVy = 0;
    for (let i = 0; i < this.count; i++) {
      sumVx += this.vx[i];
      sumVy += this.vy[i];
    }
    return { vx: sumVx / this.count, vy: sumVy / this.count };
  }

  getAcceleration(prevVx, prevVy) {
    if (this.count < 2) return { ax: 0, ay: 0 };
    const currIdx = (this.index - 1 + this.size) % this.size;
    const currVx = this.vx[currIdx];
    const currVy = this.vy[currIdx];
    const currT = this.timestamps[currIdx];
    const dt = currT - this.timestamps[0];
    if (dt <= 0) return { ax: 0, ay: 0 };
    return {
      ax: (currVx - prevVx) / dt * 1000,
      ay: (currVy - prevVy) / dt * 1000
    };
  }

  clear() {
    this.timestamps = new Float64Array(this.size);
    this.vx = new Float64Array(this.size);
    this.vy = new Float64Array(this.size);
    this.index = 0;
    this.count = 0;
  }
}

class CursorTracker {
  constructor(config = {}) {
    this.config = {
      sampleRate: config.sampleRate || 50,
      maxSessionDuration: config.maxSessionDuration || 600000,
      minSessionDuration: config.minSessionDuration || 5000,
      includeVelocity: config.includeVelocity !== false,
      includeAcceleration: config.includeAcceleration !== false,
      includeDOMContext: config.includeDOMContext !== false,
      ...config
    };

    // State
    this.samples = [];
    this.interactionEvents = [];
    this.sessionStart = null;
    this.lastSample = null;
    this.isTracking = false;
    this.sessionId = this.generateUUID();
    
    // Circular buffer for O(1) velocity
    this.velocityBuffer = new CircularVelocityBuffer(5);
    this.prevVelocity = { vx: 0, vy: 0 };
    
    // Bind methods
    this.onMouseMove = this.onMouseMove.bind(this);
    this.onMouseDown = this.onMouseDown.bind(this);
    this.onMouseUp = this.onMouseUp.bind(this);
    this.onClick = this.onClick.bind(this);
    this.onScroll = this.onScroll.bind(this);
    this.onKeyDown = this.onKeyDown.bind(this);
    
    // Privacy filter
    this.privacyFilter = new LocalPrivacyFilter(config.epsilon || 3.0);
    
    // Consent manager
    this.consentManager = new ConsentManager();
    
    // DOM tracking for hover events
    this.hoverTarget = null;
    this.hoverTimer = null;
  }

  /**
   * Start tracking cursor movement
   */
  start() {
    if (this.isTracking) return;
    
    this.sessionId = this.generateUUID();
    this.sessionStart = Date.now();
    this.samples = [];
    this.interactionEvents = [];
    this.lastSample = null;
    this.velocityBuffer.clear();
    this.prevVelocity = { vx: 0, vy: 0 };
    this.isTracking = true;
    
    // Attach event listeners
    document.addEventListener('mousemove', this.onMouseMove, { passive: true });
    document.addEventListener('mousedown', this.onMouseDown, { passive: true });
    document.addEventListener('mouseup', this.onMouseUp, { passive: true });
    document.addEventListener('click', this.onClick, { passive: true });
    document.addEventListener('keydown', this.onKeyDown, { passive: true });
    
    // Scroll tracking with throttling
    this.lastScrollTime = 0;
    document.addEventListener('scroll', this.onScroll, { passive: true });
    
    // Initialize hover tracking
    this.initHoverTracking();
    
    console.log('[CursorTelemetry] Tracking started:', this.sessionId);
  }

  /**
   * Stop tracking and return collected data
   */
  stop() {
    if (!this.isTracking) return null;
    
    this.isTracking = false;
    
    // Remove event listeners
    document.removeEventListener('mousemove', this.onMouseMove);
    document.removeEventListener('mousedown', this.onMouseDown);
    document.removeEventListener('mouseup', this.onMouseUp);
    document.removeEventListener('click', this.onClick);
    document.removeEventListener('scroll', this.onScroll);
    document.removeEventListener('keydown', this.onKeyDown);
    
    // Clear hover timer
    if (this.hoverTimer) {
      clearTimeout(this.hoverTimer);
      this.hoverTimer = null;
    }
    
    const sessionDuration = Date.now() - this.sessionStart;
    
    if (sessionDuration < this.config.minSessionDuration) {
      console.log('[CursorTelemetry] Session too short, discarded');
      return null;
    }
    
    const sessionData = this.buildSessionData(sessionDuration);
    console.log('[CursorTelemetry] Session ended:', {
      sessionId: this.sessionId,
      duration: sessionDuration,
      samples: sessionData.samples.length,
      events: sessionData.interaction_events.length
    });
    
    return sessionData;
  }

  /**
   * Handle mouse move events - captures cursor physics
   * Optimized with circular buffer
   */
  onMouseMove(event) {
    if (!this.isTracking) return;
    
    const now = performance.now();
    const t = now - this.sessionStart;
    
    // Calculate raw velocity from position delta
    let rawVx = 0, rawVy = 0;
    if (this.lastSample) {
      const dt = t - this.lastSample.t;
      if (dt > 0) {
        rawVx = (event.clientX - this.lastSample.x) / dt * 1000;
        rawVy = (event.clientY - this.lastSample.y) / dt * 1000;
      }
    }
    
    // Clamp velocity to human limits
    const maxVelocity = 5000;
    rawVx = Math.max(-maxVelocity, Math.min(maxVelocity, rawVx));
    rawVy = Math.max(-maxVelocity, Math.min(maxVelocity, rawVy));
    
    // Add to circular buffer for smoothed velocity
    this.velocityBuffer.push(rawVx, rawVy, t);
    const smoothed = this.velocityBuffer.getSmoothed();
    const acceleration = this.velocityBuffer.getAcceleration(this.prevVelocity.vx, this.prevVelocity.vy);
    
    this.prevVelocity = { vx: smoothed.vx, vy: smoothed.vy };
    
    const sample = {
      t: Math.round(t * 100) / 100,
      x: event.clientX,
      y: event.clientY,
      vx: Math.round(smoothed.vx * 100) / 100,
      vy: Math.round(smoothed.vy * 100) / 100,
      ax: Math.round(acceleration.ax * 100) / 100,
      ay: Math.round(acceleration.ay * 100) / 100,
      pressure: event.pressure || 1.0,
      button_state: this.getButtonState(event)
    };
    
    // Apply local DP noise
    const sanitized = this.privacyFilter.addSpatialNoise([sample])[0];
    
    this.samples.push(sanitized);
    this.lastSample = sanitized;
    
    if (t > this.config.maxSessionDuration) {
      return this.stop();
    }
  }

  /**
   * Get current button state as bitmask
   */
  getButtonState(event) {
    let state = 0;
    if (event.buttons & 1) state |= 1;
    if (event.buttons & 2) state |= 2;
    if (event.buttons & 4) state |= 4;
    return state;
  }

  /**
   * Track mouse down events
   */
  onMouseDown(event) {
    if (!this.isTracking) return;
    this.recordInteraction('mousedown', event);
  }

  /**
   * Track mouse up events
   */
  onMouseUp(event) {
    if (!this.isTracking) return;
    this.recordInteraction('mouseup', event);
  }

  /**
   * Track click events with DOM context
   */
  onClick(event) {
    if (!this.isTracking) return;
    this.recordInteraction('click', event);
  }

  /**
   * Track key presses
   */
  onKeyDown(event) {
    if (!this.isTracking) return;
    if (event.target.tagName === 'INPUT' || 
        event.target.tagName === 'TEXTAREA' ||
        event.target.contentEditable === 'true') {
      this.recordInteraction('typing', event, { hasInput: true });
      return;
    }
    this.recordInteraction('keydown', event);
  }

  /**
   * Track scroll events (debounced for performance)
   */
  onScroll(event) {
    if (!this.isTracking) return;
    
    const now = Date.now();
    if (now - this.lastScrollTime < 150) return;  // Debounce at 150ms
    this.lastScrollTime = now;
    
    // Use requestIdleCallback for non-critical work
    if ('requestIdleCallback' in window) {
      requestIdleCallback(() => {
        this.recordInteraction('scroll', event, {
          scrollX: window.scrollX,
          scrollY: window.scrollY,
          scrollDeltaX: event.deltaX || 0,
          scrollDeltaY: event.deltaY || 0
        });
      }, { timeout: 100 });
    } else {
      this.recordInteraction('scroll', event, {
        scrollX: window.scrollX,
        scrollY: window.scrollY,
        scrollDeltaX: event.deltaX || 0,
        scrollDeltaY: event.deltaY || 0
      });
    }
  }

  /**
   * Initialize hover tracking using mouseover/mouseout
   */
  initHoverTracking() {
    document.addEventListener('mouseover', (event) => {
      if (!this.isTracking) return;
      
      const target = event.target;
      if (target === this.hoverTarget) return;
      
      if (this.hoverTimer) clearTimeout(this.hoverTimer);
      
      this.hoverTimer = setTimeout(() => {
        this.hoverTarget = target;
        this.recordInteraction('hover_start', event);
      }, 300);
    }, true);
    
    document.addEventListener('mouseout', (event) => {
      if (!this.isTracking) return;
      
      if (this.hoverTimer) {
        clearTimeout(this.hoverTimer);
        this.hoverTimer = null;
      }
      
      if (this.hoverTarget) {
        this.recordInteraction('hover_end', event);
        this.hoverTarget = null;
      }
    }, true);
  }

  /**
   * Record an interaction event with DOM context
   */
  recordInteraction(type, event, extra = {}) {
    const t = performance.now() - this.sessionStart;
    const target = event.target;
    
    let domContext = null;
    if (this.config.includeDOMContext && target) {
      domContext = this.snapshotDOM(target);
    }
    
    const interactionEvent = {
      t: Math.round(t),
      type: type,
      x: event.clientX || 0,
      y: event.clientY || 0,
      target: domContext,
      ...extra
    };
    
    if (domContext) {
      interactionEvent.target = this.privacyFilter.generalizeContext(interactionEvent);
    }
    
    this.interactionEvents.push(interactionEvent);
  }

  /**
   * Snapshot DOM element context at interaction point
   */
  snapshotDOM(element) {
    try {
      const rect = element.getBoundingClientRect();
      let selector = this.buildSelector(element);
      const computedStyle = window.getComputedStyle(element);
      
      return {
        selector: selector,
        tag: element.tagName.toLowerCase(),
        role: element.getAttribute('role') || this.inferRole(element),
        text_content: this.extractTextContent(element),
        bounding_box: {
          x: Math.round(rect.x),
          y: Math.round(rect.y),
          w: Math.round(rect.width),
          h: Math.round(rect.height)
        },
        visual_features: {
          color: computedStyle.color,
          background_color: computedStyle.backgroundColor,
          font_size: computedStyle.fontSize,
          font_weight: computedStyle.fontWeight,
          is_in_viewport: this.isInViewport(rect),
          distance_from_previous: this.lastSample ? 
            Math.sqrt(Math.pow(element.clientX - this.lastSample.x, 2) + 
                     Math.pow(element.clientY - this.lastSample.y, 2)) : 0
        }
      };
    } catch (e) {
      return { error: 'snapshot_failed' };
    }
  }

  /**
   * Build minimal CSS selector path
   */
  buildSelector(element) {
    const path = [];
    let current = element;
    
    while (current && current !== document.body && current !== document.documentElement) {
      let selector = current.tagName.toLowerCase();
      
      if (current.id) {
        selector += `#${current.id}`;
        path.unshift(selector);
        break;
      } else if (current.className && typeof current.className === 'string') {
        const classes = current.className.trim().split(/\s+/).slice(0, 2);
        if (classes[0]) selector += `.${classes.join('.')}`;
      }
      
      path.unshift(selector);
      current = current.parentElement;
    }
    
    return path.join(' > ');
  }

  /**
   * Extract text content (truncated for privacy)
   */
  extractTextContent(element) {
    const text = element.textContent || '';
    return text.trim().substring(0, 50);
  }

  /**
   * Infer ARIA role from element type
   */
  inferRole(element) {
    const tag = element.tagName.toLowerCase();
    const roleMap = {
      'a': 'link', 'button': 'button', 'input': 'textbox',
      'select': 'combobox', 'textarea': 'textbox', 'nav': 'navigation',
      'header': 'banner', 'footer': 'contentinfo', 'main': 'main',
      'aside': 'complementary', 'form': 'form'
    };
    return roleMap[tag] || 'unknown';
  }

  /**
   * Check if element is in viewport
   */
  isInViewport(rect) {
    return (
      rect.top >= 0 && rect.left >= 0 &&
      rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
      rect.right <= (window.innerWidth || document.documentElement.clientWidth)
    );
  }

  /**
   * Build final session data structure
   */
  buildSessionData(duration) {
    const domain = window.location.hostname;
    const path = window.location.pathname;
    
    let samples = this.samples;
    if (this.config.subsampleRate && this.config.subsampleRate < 1) {
      samples = this.privacyFilter.subsample(samples, this.config.subsampleRate);
    }
    
    return {
      trajectory_id: this.sessionId,
      timestamp: new Date(this.sessionStart).toISOString(),
      session_context: {
        domain: domain,
        page_path: path,
        viewport: {
          width: window.innerWidth,
          height: window.innerHeight
        },
        device_type: this.detectDeviceType(),
        input_method: this.detectInputMethod()
      },
      samples: samples,
      interaction_events: this.interactionEvents,
      task: {
        stated_goal: null,
        inferred_intent: null,
        completion_status: null
      },
      anonymization: {
        user_consent: this.consentManager.hasConsent(),
        personal_data_scrubbed: true,
        local_dp_applied: true,
        hash_id: this.privacyFilter.hashUser()
      }
    };
  }

  /**
   * Detect device type from user agent
   */
  detectDeviceType() {
    const ua = navigator.userAgent;
    if (/Mobi|Android/i.test(ua)) return 'mobile';
    if (/Tablet|iPad/i.test(ua)) return 'tablet';
    return 'desktop';
  }

  /**
   * Detect input method (mouse vs touch vs trackpad)
   */
  detectInputMethod() {
    if ('ontouchstart' in window || navigator.maxTouchPoints > 0) {
      return 'touch';
    }
    return 'mouse';
  }

  /**
   * Generate UUID v4
   */
  generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = Math.random() * 16 | 0;
      const v = c === 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
  }
}

// Export for use in content script
window.CursorTracker = CursorTracker;
window.CircularVelocityBuffer = CircularVelocityBuffer;
    
    // Clean up hover tracking
    if (this.hoverTimer) {
      clearTimeout(this.hoverTimer);
      this.hoverTimer = null;
    }
    
    const sessionDuration = Date.now() - this.sessionStart;
    
    // Only return if minimum duration met
    if (sessionDuration < this.config.minSessionDuration) {
      console.log('[CursorTelemetry] Session too short, discarded');
      return null;
    }
    
    const sessionData = this.buildSessionData(sessionDuration);
    console.log('[CursorTelemetry] Session ended:', {
      sessionId: this.sessionId,
      duration: sessionDuration,
      samples: sessionData.samples.length,
      events: sessionData.interaction_events.length
    });
    
    return sessionData;
  }

  /**
   * Handle mouse move events - captures cursor physics
   */
  onMouseMove(event) {
    if (!this.isTracking) return;
    
    const now = performance.now();
    const t = now - this.sessionStart;
    
    // Calculate velocity from position delta
    let vx = 0, vy = 0;
    if (this.lastSample) {
      const dt = t - this.lastSample.t;
      if (dt > 0) {
        vx = (event.clientX - this.lastSample.x) / dt * 1000;  // px/s
        vy = (event.clientY - this.lastSample.y) / dt * 1000;
      }
    }
    
    // Smooth velocity
    this.velocityHistory.push({ vx, vy, t });
    if (this.velocityHistory.length > this.velocityWindowSize) {
      this.velocityHistory.shift();
    }
    
    const smoothedVx = this.velocityHistory.reduce((a, b) => a + b.vx, 0) / this.velocityHistory.length;
    const smoothedVy = this.velocityHistory.reduce((a, b) => a + b.vy, 0) / this.velocityHistory.length;
    
    // Calculate acceleration
    let ax = 0, ay = 0;
    if (this.velocityHistory.length >= 2) {
      const prev = this.velocityHistory[this.velocityHistory.length - 2];
      const dt = t - prev.t;
      if (dt > 0) {
        ax = (smoothedVx - prev.vx) / dt * 1000;
        ay = (smoothedVy - prev.vy) / dt * 1000;
      }
    }
    
    const sample = {
      t: Math.round(t * 100) / 100,  // ms with 2 decimal precision
      x: event.clientX,
      y: event.clientY,
      vx: Math.round(smoothedVx * 100) / 100,
      vy: Math.round(smoothedVy * 100) / 100,
      ax: Math.round(ax * 100) / 100,
      ay: Math.round(ay * 100) / 100,
      pressure: event.pressure || 1.0,
      button_state: this.getButtonState(event)
    };
    
    // Apply local DP noise to spatial coordinates
    const sanitized = this.privacyFilter.addSpatialNoise([sample])[0];
    
    this.samples.push(sanitized);
    this.lastSample = sanitized;
    
    // Check session duration
    if (t > this.config.maxSessionDuration) {
      return this.stop();
    }
  }

  /**
   * Get current button state as bitmask
   */
  getButtonState(event) {
    let state = 0;
    if (event.buttons & 1) state |= 1;  // left
    if (event.buttons & 2) state |= 2;  // right
    if (event.buttons & 4) state |= 4;  // middle
    return state;
  }

  /**
   * Track mouse down events
   */
  onMouseDown(event) {
    if (!this.isTracking) return;
    this.recordInteraction('mousedown', event);
  }

  /**
   * Track mouse up events
   */
  onMouseUp(event) {
    if (!this.isTracking) return;
    this.recordInteraction('mouseup', event);
  }

  /**
   * Track click events with DOM context
   */
  onClick(event) {
    if (!this.isTracking) return;
    this.recordInteraction('click', event);
  }

  /**
   * Track key presses
   */
  onKeyDown(event) {
    if (!this.isTracking) return;
    // Don't capture sensitive keys
    if (event.target.tagName === 'INPUT' || 
        event.target.tagName === 'TEXTAREA' ||
        event.target.contentEditable === 'true') {
      // Only record that typing happened, not what
      this.recordInteraction('typing', event, { hasInput: true });
      return;
    }
    this.recordInteraction('keydown', event);
  }

  /**
   * Track scroll events (throttled)
   */
  onScroll(event) {
    if (!this.isTracking) return;
    
    const now = Date.now();
    if (now - this.lastScrollTime < 500) return;  // throttle to 2Hz
    this.lastScrollTime = now;
    
    this.recordInteraction('scroll', event, {
      scrollX: window.scrollX,
      scrollY: window.scrollY,
      scrollDeltaX: event.deltaX || 0,
      scrollDeltaY: event.deltaY || 0
    });
  }

  /**
   * Initialize hover tracking using mouseover/mouseout
   */
  initHoverTracking() {
    let hoverTimeout = null;
    
    document.addEventListener('mouseover', (event) => {
      if (!this.isTracking) return;
      
      const target = event.target;
      if (target === this.hoverTarget) return;
      
      // Clear previous hover timer
      if (hoverTimeout) clearTimeout(hoverTimeout);
      
      // Start hover timer (300ms before recording)
      hoverTimeout = setTimeout(() => {
        this.hoverTarget = target;
        this.recordInteraction('hover_start', event);
      }, 300);
    }, true);
    
    document.addEventListener('mouseout', (event) => {
      if (!this.isTracking) return;
      
      if (hoverTimeout) {
        clearTimeout(hoverTimeout);
        hoverTimeout = null;
      }
      
      if (this.hoverTarget) {
        this.recordInteraction('hover_end', event);
        this.hoverTarget = null;
      }
    }, true);
  }

  /**
   * Record an interaction event with DOM context
   */
  recordInteraction(type, event, extra = {}) {
    const t = performance.now() - this.sessionStart;
    const target = event.target;
    
    let domContext = null;
    if (this.config.includeDOMContext && target) {
      domContext = this.snapshotDOM(target);
    }
    
    const interactionEvent = {
      t: Math.round(t),
      type: type,
      x: event.clientX || 0,
      y: event.clientY || 0,
      target: domContext,
      ...extra
    };
    
    // Generalize DOM selectors for privacy
    if (domContext) {
      interactionEvent.target = this.privacyFilter.generalizeContext(interactionEvent);
    }
    
    this.interactionEvents.push(interactionEvent);
  }

  /**
   * Snapshot DOM element context at interaction point
   */
  snapshotDOM(element) {
    try {
      const rect = element.getBoundingClientRect();
      
      // Build selector path
      let selector = this.buildSelector(element);
      
      // Get computed styles (privacy-preserving subset)
      const computedStyle = window.getComputedStyle(element);
      
      return {
        selector: selector,
        tag: element.tagName.toLowerCase(),
        role: element.getAttribute('role') || this.inferRole(element),
        text_content: this.extractTextContent(element),
        bounding_box: {
          x: Math.round(rect.x),
          y: Math.round(rect.y),
          w: Math.round(rect.width),
          h: Math.round(rect.height)
        },
        visual_features: {
          color: computedStyle.color,
          background_color: computedStyle.backgroundColor,
          font_size: computedStyle.fontSize,
          font_weight: computedStyle.fontWeight,
          is_in_viewport: this.isInViewport(rect),
          distance_from_previous: this.lastSample ? 
            Math.sqrt(Math.pow(element.clientX - this.lastSample.x, 2) + 
                     Math.pow(element.clientY - this.lastSample.y, 2)) : 0
        }
      };
    } catch (e) {
      return { error: 'snapshot_failed' };
    }
  }

  /**
   * Build minimal CSS selector path
   */
  buildSelector(element) {
    const path = [];
    let current = element;
    
    while (current && current !== document.body && current !== document.documentElement) {
      let selector = current.tagName.toLowerCase();
      
      if (current.id) {
        selector += `#${current.id}`;
        path.unshift(selector);
        break;
      } else if (current.className && typeof current.className === 'string') {
        const classes = current.className.trim().split(/\s+/).slice(0, 2);
        if (classes[0]) {
          selector += `.${classes.join('.')}`;
        }
      }
      
      path.unshift(selector);
      current = current.parentElement;
    }
    
    return path.join(' > ');
  }

  /**
   * Extract text content (truncated for privacy)
   */
  extractTextContent(element) {
    const text = element.textContent || '';
    return text.trim().substring(0, 50);  // First 50 chars
  }

  /**
   * Infer ARIA role from element type
   */
  inferRole(element) {
    const tag = element.tagName.toLowerCase();
    const roleMap = {
      'a': 'link',
      'button': 'button',
      'input': 'textbox',
      'select': 'combobox',
      'textarea': 'textbox',
      'nav': 'navigation',
      'header': 'banner',
      'footer': 'contentinfo',
      'main': 'main',
      'aside': 'complementary',
      'form': 'form'
    };
    return roleMap[tag] || 'unknown';
  }

  /**
   * Check if element is in viewport
   */
  isInViewport(rect) {
    return (
      rect.top >= 0 &&
      rect.left >= 0 &&
      rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
      rect.right <= (window.innerWidth || document.documentElement.clientWidth)
    );
  }

  /**
   * Build final session data structure
   */
  buildSessionData(duration) {
    const domain = window.location.hostname;
    const path = window.location.pathname;
    
    // Apply temporal subsampling
    let samples = this.samples;
    if (this.config.subsampleRate && this.config.subsampleRate < 1) {
      samples = this.privacyFilter.subsample(samples, this.config.subsampleRate);
    }
    
    return {
      trajectory_id: this.sessionId,
      timestamp: new Date(this.sessionStart).toISOString(),
      session_context: {
        domain: domain,
        page_path: path,
        viewport: {
          width: window.innerWidth,
          height: window.innerHeight
        },
        device_type: this.detectDeviceType(),
        input_method: this.detectInputMethod()
      },
      samples: samples,
      interaction_events: this.interactionEvents,
      task: {
        stated_goal: null,  // User can fill in
        inferred_intent: null,  // Model prediction
        completion_status: null
      },
      anonymization: {
        user_consent: this.consentManager.hasConsent(),
        personal_data_scrubbed: true,
        local_dp_applied: true,
        hash_id: this.privacyFilter.hashUser()
      }
    };
  }

  /**
   * Detect device type from user agent
   */
  detectDeviceType() {
    const ua = navigator.userAgent;
    if (/Mobi|Android/i.test(ua)) return 'mobile';
    if (/Tablet|iPad/i.test(ua)) return 'tablet';
    return 'desktop';
  }

  /**
   * Detect input method (mouse vs touch vs trackpad)
   */
  detectInputMethod() {
    // Check for touch support
    if ('ontouchstart' in window || navigator.maxTouchPoints > 0) {
      return 'touch';
    }
    // Trackpad typically shows different mouse events
    // For now, default to mouse
    return 'mouse';
  }

  /**
   * Generate UUID v4
   */
  generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = Math.random() * 16 | 0;
      const v = c === 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
  }
}

// Export for use in content script
window.CursorTracker = CursorTracker;
