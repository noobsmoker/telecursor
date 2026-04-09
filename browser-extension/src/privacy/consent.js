/**
 * CursorTelemetry - Consent Management
 * 
 * Handles granular, revocable consent for data collection.
 * Implements transparent consent flow.
 * 
 * @version 0.1.0
 */

class ConsentManager {
  constructor() {
    this.defaultPolicy = {
      collected: [
        'Cursor position and movement speed',
        'Page structure (DOM) at interaction points',
        'Anonymized site category (e.g., e-commerce)',
        'Interaction timing patterns',
        'Viewport size and device type'
      ],
      notCollected: [
        'Typed text or form inputs',
        'Passwords or authentication data',
        'Personal identifiers (name, email, etc.)',
        'Full page content',
        'Browsing history outside current session'
      ],
      usage: [
        'Open research on web interaction patterns',
        'Improving accessibility tools',
        'Training open-source UI/UX models',
        'Academic publications (anonymized)'
      ]
    };
    
    this.consentState = this.loadConsentState();
  }

  /**
   * Load saved consent state
   */
  loadConsentState() {
    try {
      const stored = localStorage.getItem('telemetry_consent');
      if (stored) {
        return JSON.parse(stored);
      }
    } catch (e) {
      console.error('[ConsentManager] Failed to load consent:', e);
    }
    
    // Default: no consent given
    return {
      globalOptIn: false,
      siteSpecific: {},  // domain -> boolean
      dataRetention: '90_days',
      downloadMyData: true,
      lastUpdated: null
    };
  }

  /**
   * Save consent state
   */
  saveConsentState() {
    this.consentState.lastUpdated = Date.now();
    localStorage.setItem('telemetry_consent', JSON.stringify(this.consentState));
  }

  /**
   * Request global consent
   */
  requestGlobalConsent() {
    return {
      ...this.defaultPolicy,
      userChoice: this.consentState.globalOptIn,
      dataRetention: this.consentState.dataRetention
    };
  }

  /**
   * Grant global consent
   */
  grantGlobalConsent(optIn = true, retention = '90_days') {
    this.consentState.globalOptIn = optIn;
    this.consentState.dataRetention = retention;
    this.saveConsentState();
    
    return {
      granted: optIn,
      timestamp: this.consentState.lastUpdated,
      retention: retention
    };
  }

  /**
   * Set consent for specific site
   */
  setSiteConsent(domain, optIn) {
    this.consentState.siteSpecific[domain] = optIn;
    this.saveConsentState();
    
    return {
      domain: domain,
      optedIn: optIn,
      timestamp: this.consentState.lastUpdated
    };
  }

  /**
   * Get effective consent for current site
   */
  hasConsent(domain = window.location.hostname) {
    // Check site-specific setting first
    if (domain in this.consentState.siteSpecific) {
      return this.consentState.siteSpecific[domain];
    }
    
    // Fall back to global setting
    return this.consentState.globalOptIn;
  }

  /**
   * Check if user can export their data
   */
  canExportData() {
    return this.consentState.downloadMyData;
  }

  /**
   * Export all user's collected data
   */
  exportUserData(storedData) {
    if (!this.canExportData()) {
      return { error: 'User has not enabled data export' };
    }
    
    const exportData = {
      exportDate: new Date().toISOString(),
      consentHistory: this.consentState,
      sessions: storedData,
      policy: this.defaultPolicy
    };
    
    return {
      data: exportData,
      filename: `cursor-telemetry-export-${Date.now()}.json`
    };
  }

  /**
   * Revoke all consent and delete data
   */
  revokeAllConsent() {
    // Clear all data
    const keys = Object.keys(localStorage).filter(k => k.startsWith('session_'));
    keys.forEach(key => localStorage.removeItem(key));
    
    // Reset consent state
    this.consentState = {
      globalOptIn: false,
      siteSpecific: {},
      dataRetention: '90_days',
      downloadMyData: true,
      lastUpdated: Date.now()
    };
    this.saveConsentState();
    
    return { revoked: true, timestamp: this.consentState.lastUpdated };
  }

  /**
   * Get consent summary for display
   */
  getConsentSummary() {
    return {
      globalOptIn: this.consentState.globalOptIn,
      siteSpecificCount: Object.keys(this.consentState.siteSpecific).length,
      optedInSites: Object.entries(this.consentState.siteSpecific)
        .filter(([_, optIn]) => optIn).length,
      optedOutSites: Object.entries(this.consentState.siteSpecific)
        .filter(([_, optIn]) => !optIn).length,
      dataRetention: this.consentState.dataRetention,
      lastUpdated: this.consentState.lastUpdated
    };
  }

  /**
   * Render consent UI
   */
  renderConsentUI(container) {
    const summary = this.getConsentSummary();
    
    const html = `
      <div class="consent-panel">
        <h3>CursorTelemetry Consent</h3>
        
        <div class="consent-status">
          <p>Status: <strong>${summary.globalOptIn ? 'Enabled' : 'Disabled'}</strong></p>
          ${summary.lastUpdated ? 
            `<p>Last updated: ${new Date(summary.lastUpdated).toLocaleDateString()}</p>` : ''}
        </div>
        
        <div class="consent-toggle">
          <label>
            <input type="checkbox" id="global-consent" ${summary.globalOptIn ? 'checked' : ''}>
            Enable global tracking
          </label>
        </div>
        
        <div class="consent-info">
          <h4>What we collect:</h4>
          <ul>
            ${this.defaultPolicy.collected.map(item => `<li>${item}</li>`).join('')}
          </ul>
          
          <h4>What we never collect:</h4>
          <ul class="never-collect">
            ${this.defaultPolicy.notCollected.map(item => `<li>${item}</li>`).join('')}
          </ul>
        </div>
        
        <div class="consent-actions">
          <button id="save-consent">Save Settings</button>
          <button id="export-data" ${!this.canExportData() ? 'disabled' : ''}>Export My Data</button>
          <button id="revoke-all" class="danger">Delete All Data</button>
        </div>
        
        <p class="consent-footer">
          Data is processed with differential privacy. Individual cursor paths
          are anonymized before storage or transmission.
        </p>
      </div>
    `;
    
    container.innerHTML = html;
    
    // Attach handlers
    container.querySelector('#save-consent')?.addEventListener('click', () => {
      const enabled = container.querySelector('#global-consent').checked;
      this.grantGlobalConsent(enabled);
      this.renderConsentUI(container);
    });
    
    container.querySelector('#export-data')?.addEventListener('click', () => {
      this.downloadExportedData();
    });
    
    container.querySelector('#revoke-all')?.addEventListener('click', () => {
      if (confirm('This will delete all your collected data. Are you sure?')) {
        this.revokeAllConsent();
        this.renderConsentUI(container);
      }
    });
  }

  /**
   * Download exported data
   */
  async downloadExportedData() {
    const sessions = await chrome.storage.local.get(null);
    const sessionData = Object.entries(sessions)
      .filter(([key]) => key.startsWith('session_'))
      .reduce((acc, [key, value]) => ({ ...acc, [key]: value }), {});
    
    const { data, filename } = this.exportUserData(sessionData);
    
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    
    URL.revokeObjectURL(url);
  }
}

// Export
window.ConsentManager = ConsentManager;
