/**
 * CursorTelemetry - Background Service Worker
 * 
 * Manages extension lifecycle, stores data, handles sync.
 * 
 * @version 0.1.0
 */

// State
let currentTracker = null;
let isEnabled = false;
let settings = {
  sampleRate: 50,
  epsilon: 3.0,
  maxSessionDuration: 600000,
  includeDOMContext: true,
  siteAllowlist: [],
  siteBlocklist: []
};

// Initialize
chrome.runtime.onInstalled.addListener(() => {
  console.log('[CursorTelemetry] Extension installed');
  loadSettings();
});

chrome.runtime.onStartup.addListener(() => {
  console.log('[CursorTelemetry] Extension started');
  loadSettings();
});

// Load settings from storage
async function loadSettings() {
  const stored = await chrome.storage.local.get(['settings', 'stats']);
  if (stored.settings) {
    settings = { ...settings, ...stored.settings };
  }
  console.log('[CursorTelemetry] Settings loaded:', settings);
}

// Handle messages from content script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  console.log('[CursorTelemetry] Message:', message.type);
  
  switch (message.type) {
    case 'START_TRACKING':
      startTracking(sender.tab.id);
      sendResponse({ success: true });
      break;
      
    case 'STOP_TRACKING':
      const data = stopTracking();
      sendResponse({ success: true, data });
      break;
      
    case 'GET_STATUS':
      sendResponse({ 
        isTracking: isEnabled, 
        settings: settings,
        currentSession: currentTracker ? {
          sessionId: currentTracker.sessionId,
          startTime: currentTracker.sessionStart
        } : null
      });
      break;
      
    case 'UPDATE_SETTINGS':
      Object.assign(settings, message.settings);
      chrome.storage.local.set({ settings });
      sendResponse({ success: true });
      break;
      
    case 'GET_STATS':
      getStats().then(stats => sendResponse(stats));
      return true;  // Async response
      
    default:
      sendResponse({ error: 'Unknown message type' });
  }
  
  return true;
});

// Tab visibility handling
chrome.tabs.onActivated.addListener((activeInfo) => {
  // Pause on tab switch
  if (currentTracker && isEnabled) {
    // Could implement pause/resume here
  }
});

chrome.tabs.onRemoved.addListener((tabId) => {
  // Clean up if tracking tab is closed
});

// Start tracking for a tab
function startTracking(tabId) {
  isEnabled = true;
  
  chrome.tabs.sendMessage(tabId, { type: 'INIT_TRACKING', settings: settings })
    .then(response => {
      console.log('[CursorTelemetry] Tracking initialized:', response);
    })
    .catch(err => {
      console.error('[CursorTelemetry] Failed to init tracking:', err);
    });
}

// Stop tracking and collect data
function stopTracking() {
  isEnabled = false;
  
  // The content script will handle the actual stop and send data back
  return { stopped: true, timestamp: Date.now() };
}

// Receive session data from content script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'SESSION_DATA') {
    handleSessionData(message.data);
    sendResponse({ received: true });
  }
  return true;
});

// Handle completed session data
async function handleSessionData(data) {
  console.log('[CursorTelemetry] Session data received:', {
    sessionId: data.trajectory_id,
    samples: data.samples.length,
    events: data.interaction_events.length
  });
  
  // Store locally
  const storageKey = `session_${data.trajectory_id}`;
  await chrome.storage.local.set({ [storageKey]: data });
  
  // Update stats
  const stats = await getStats();
  stats.totalSessions += 1;
  stats.totalSamples += data.samples.length;
  stats.totalDuration += (data.samples[data.samples.length - 1]?.t || 0);
  
  await chrome.storage.local.set({ stats });
  
  // In future: upload to server (with user consent)
  // await uploadSession(data);
}

// Get aggregated stats
async function getStats() {
  const stored = await chrome.storage.local.get('stats');
  return stored.stats || {
    totalSessions: 0,
    totalSamples: 0,
    totalDuration: 0,
    lastUpdated: Date.now()
  };
}

// Upload session to server (future)
async function uploadSession(data) {
  // Server endpoint would be configured in settings
  const serverUrl = settings.serverUrl;
  if (!serverUrl) return;
  
  // Check consent
  if (!data.anonymization.user_consent) {
    console.log('[CursorTelemetry] No consent, skipping upload');
    return;
  }
  
  try {
    const response = await fetch(serverUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(data)
    });
    
    console.log('[CursorTelemetry] Upload response:', response.status);
  } catch (err) {
    console.error('[CursorTelemetry] Upload failed:', err);
  }
}

console.log('[CursorTelemetry] Background service worker loaded');