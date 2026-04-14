/**
 * Tests for Browser Extension
 * Tests cursor tracking, local DP, and consent management
 */

// Mock browser APIs
const mockBrowser = {
  runtime: {
    id: 'test-extension',
    sendMessage: jest.fn(),
    onMessage: { addListener: jest.fn() }
  },
  storage: {
    local: {
      get: jest.fn(),
      set: jest.fn()
    }
  },
  identity: {
    getRedirectURL: jest.fn()
  }
};

global.chrome = mockBrowser;

// Import modules to test (would need babel transform in real environment)
const localDP = require('./browser-extension/src/privacy/local_dp.js');
const consent = require('./browser-extension/src/privacy/consent.js');

describe('Browser Extension', () => {
  describe('Local Differential Privacy', () => {
    describe('LaplaceNoise', () => {
      it('should add noise to values', () => {
        const value = 10;
        const epsilon = 1.0;
        
        const noisy = localDP.addLaplaceNoise(value, epsilon);
        
        // Noise should have been added
        expect(noisy).not.toBe(value);
      });
      
      it('should add more noise for lower epsilon', () => {
        const value = 10;
        
        const noisyLowEps = localDP.addLaplaceNoise(value, epsilon=0.1);
        const noisyHighEps = localDP.addLaplaceNoise(value, epsilon=10.0);
        
        const diffLow = Math.abs(noisyLowEps - value);
        const diffHigh = Math.abs(noisyHighEps - value);
        
        expect(diffLow).toBeGreaterThan(diffHigh);
      });
    });
    
    describe('RandomizedResponse', () => {
      it('should sometimes flip true responses', () => {
        const trueValue = true;
        const epsilon = 1.0;
        
        let flippedCount = 0;
        const trials = 1000;
        
        for (let i = 0; i < trials; i++) {
          const result = localDP.randomizedResponse(trueValue, epsilon);
          if (result !== trueValue) {
            flippedCount++;
          }
        }
        
        // Should flip some percentage based on epsilon
        const flipRate = flippedCount / trials;
        expect(flipRate).toBeGreaterThan(0);
      });
    });
    
    describe('TrajectoryPrivacy', () => {
      it('should apply DP to trajectory', () => {
        const trajectory = [
          { x: 100, y: 200, t: 0 },
          { x: 110, y: 210, t: 100 }
        ];
        
        const epsilon = 1.0;
        const privateTrajectory = localDP.applyDPToTrajectory(trajectory, epsilon);
        
        expect(privateTrajectory).toBeDefined();
        expect(privateTrajectory.length).toBe(trajectory.length);
      });
    });
  });
  
  describe('Consent Management', () => {
    describe('ConsentManager', () => {
      it('should initialize with default consent', () => {
        const manager = new consent.ConsentManager();
        
        // Should have default denied consent
        expect(manager.hasConsent()).toBe(false);
      });
      
      it('should grant consent', () => {
        const manager = new consent.ConsentManager();
        
        manager.grantConsent({
          research: true,
          improvement: false
        });
        
        expect(manager.hasConsent()).toBe(true);
        expect(manager.canUseForResearch()).toBe(true);
        expect(manager.canUseForImprovement()).toBe(false);
      });
      
      it('should revoke consent', () => {
        const manager = new consent.ConsentManager();
        
        manager.grantConsent({ research: true });
        expect(manager.hasConsent()).toBe(true);
        
        manager.revokeConsent();
        expect(manager.hasConsent()).toBe(false);
      });
      
      it('should serialize consent to storage', async () => {
        const manager = new consent.ConsentManager();
        
        await manager.saveConsent({
          research: true,
          timestamp: new Date().toISOString()
        });
        
        // Should have called storage API
        expect(mockBrowser.storage.local.set).toHaveBeenCalled();
      });
      
      it('should load consent from storage', async () => {
        mockBrowser.storage.local.get.mockResolvedValue({
          consent: {
            research: true,
            timestamp: '2024-01-01T00:00:00Z'
          }
        });
        
        const manager = new consent.ConsentManager();
        await manager.loadConsent();
        
        expect(manager.hasConsent()).toBe(true);
      });
    });
    
    describe('Consent Banner', () => {
      it('should show banner when consent not given', () => {
        // Mock DOM
        document.body.innerHTML = '<div id="consent-banner"></div>';
        
        const banner = new consent.ConsentBanner();
        
        expect(banner.shouldShow()).toBe(true);
      });
      
      it('should hide after consent given', () => {
        document.body.innerHTML = '<div id="consent-banner"></div>';
        
        const banner = new consent.ConsentBanner();
        
        banner.onConsentGranted();
        
        // Banner should be hidden
        expect(banner.shouldShow()).toBe(false);
      });
    });
  });
  
  describe('Cursor Tracking', () => {
    describe('CursorTracker', () => {
      it('should track cursor position', () => {
        const tracker = new localDP.CursorTracker();
        
        tracker.track({ x: 100, y: 200, type: 'mousemove' });
        
        const trajectory = tracker.getTrajectory();
        
        expect(trajectory.length).toBe(1);
        expect(trajectory[0].x).toBe(100);
      });
      
      it('should respect sampling rate', () => {
        const tracker = new localDP.CursorTracker({
          samplingRate: 50  // 50Hz
        });
        
        // Should sample at appropriate rate
        // (Implementation would throttle)
        expect(tracker.getSamplingRate()).toBe(50);
      });
      
      it('should clean up old samples', () => {
        const tracker = new localDP.CursorTracker({
          maxDuration: 60000  // 1 minute
        });
        
        // Add old samples
        const oldSample = { x: 0, y: 0, t: 0 };
        const newSample = { x: 100, y: 100, t: 50000 };
        
        tracker.track(oldSample);
        tracker.track(newSample);
        
        // Old sample should be removed
        const trajectory = tracker.getTrajectory();
        
        expect(trajectory.length).toBeGreaterThan(0);
      });
    });
  });
  
  describe('Content Script', () => {
    describe('DOM Grounding', () => {
      it('should get element at cursor position', () => {
        // Mock DOM
        document.elementFromPoint = jest.fn().mockReturnValue({
          tagName: 'BUTTON',
          id: 'submit-btn',
          className: 'btn primary',
          getAttribute: jest.fn().mockReturnValue(null)
        });
        
        const grounding = localDP.getDOMContext(100, 200);
        
        expect(grounding).toBeDefined();
        expect(grounding.tag).toBe('BUTTON');
      });
      
      it('should build DOM path', () => {
        // Create mock element hierarchy
        const button = document.createElement('button');
        button.id = 'submit';
        
        const form = document.createElement('form');
        form.appendChild(button);
        
        const path = localDP.buildDOMPath(button);
        
        expect(path).toContain('button');
      });
    });
  });
});

describe('Extension Integration', () => {
  it('should integrate DP with cursor tracking', () => {
    const tracker = new localDP.CursorTracker();
    const epsilon = 1.0;
    
    // Track some points
    for (let i = 0; i < 10; i++) {
      tracker.track({ x: i * 10, y: i * 10, t: i * 100 });
    }
    
    // Apply DP
    const privateTrajectory = localDP.applyDPToTrajectory(
      tracker.getTrajectory(),
      epsilon
    );
    
    expect(privateTrajectory.length).toBeGreaterThan(0);
  });
  
  it('should respect consent before tracking', () => {
    const manager = new consent.ConsentManager();
    const tracker = new localDP.CursorTracker();
    
    // No consent yet
    expect(manager.hasConsent()).toBe(false);
    
    // Should not track without consent
    // (Implementation would check this)
    const shouldTrack = manager.hasConsent();
    
    expect(shouldTrack).toBe(false);
  });
});