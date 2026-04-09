/**
 * CursorTelemetry - Background Service Worker
 * 
 * Manages extension lifecycle, stores data, handles sync, uploads to server.
 * 
 * @version 0.2.0
 */

// Configuration
const CONFIG = {
  serverUrl: 'http://localhost:3000/api/v1/trajectories',
  batchSize: 10,  // Trajectories per batch upload
  uploadInterval: 60000,  // 1 minute
  maxRetries: 3,
  retryDelay: 5000
};

// State
let currentTracker = null;
let isEnabled = false;
let uploadQueue = [];
let isUploading = false;
let settings = {
  sampleRate: 50,
  epsilon: 3.0,
  maxSessionDuration: 600000,
  includeDOMContext: true,
  siteAllowlist: [],
  siteBlocklist: [],
  serverUrl: null
};

// Initialize
chrome.runtime.onInstalled.addListener(() => {
  console.log('[CursorTelemetry] Extension installed');
  loadSettings();
  
  // Schedule periodic upload
  chrome.alarms.create('upload-trajectories', {
    periodInMinutes: 1
  });
});

chrome.runtime.onStartup.addListener(() => {
  console.log('[CursorTelemetry] Extension started');
  loadSettings();
});

// Alarm handler for periodic upload
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === 'upload-trajectories') {
    processUploadQueue();
  }
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
  
  // Validate data
  if (!validateTrajectory(data)) {
    console.error('[CursorTelemetry] Invalid trajectory data');
    return;
  }
  
  // Store locally as backup
  const storageKey = `session_${data.trajectory_id}`;
  await chrome.storage.local.set({ [storageKey]: data });
  
  // Update stats
  const stats = await getStats();
  stats.totalSessions += 1;
  stats.totalSamples += data.samples.length;
  stats.totalDuration += (data.samples[data.samples.length - 1]?.t || 0);
  stats.lastUpdated = Date.now();
  
  await chrome.storage.local.set({ stats });
  
  // Check consent before adding to upload queue
  if (!data.anonymization?.user_consent) {
    console.log('[CursorTelemetry] No consent, storing locally only');
    return;
  }
  
  // Add to upload queue
  uploadQueue.push({
    data: data,
    retries: 0,
    timestamp: Date.now()
  });
  
  console.log('[CursorTelemetry] Added to upload queue, queue size:', uploadQueue.length);
  
  // Try immediate upload if queue is large enough
  if (uploadQueue.length >= CONFIG.batchSize) {
    await processUploadQueue();
  }
}

function validateTrajectory(data) {
  // Basic validation
  if (!data.trajectory_id || !data.samples || data.samples.length < 10) {
    return false;
  }
  
  // Check for required fields
  if (!data.session_context || !data.anonymization) {
    return false;
  }
  
  return true;
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

// Process upload queue - batch upload to server
async function processUploadQueue() {
  if (isUploading || uploadQueue.length === 0) {
    return;
  }
  
  // Get server URL from settings
  const { settings: storedSettings } = await chrome.storage.local.get('settings');
  const serverUrl = (storedSettings && storedSettings.serverUrl) || CONFIG.serverUrl;
  
  if (!serverUrl) {
    console.log('[CursorTelemetry] No server configured, skipping upload');
    return;
  }
  
  isUploading = true;
  console.log('[CursorTelemetry] Processing upload queue, size:', uploadQueue.length);
  
  // Get batch to upload
  const batch = uploadQueue.splice(0, CONFIG.batchSize);
  
  try {
    const response = await uploadBatch(batch, serverUrl);
    
    if (response.ok) {
      console.log(`[CursorTelemetry] Successfully uploaded ${batch.length} trajectories`);
      
      // Clear uploaded from local storage
      for (const item of batch) {
        await chrome.storage.local.remove(`session_${item.data.trajectory_id}`);
      }
      
      // Update upload stats
      const stats = await getStats();
      stats.totalUploaded = (stats.totalUploaded || 0) + batch.length;
      await chrome.storage.local.set({ stats });
    } else {
      // Re-queue on failure
      console.error('[CursorTelemetry] Upload failed with status:', response.status);
      requeueBatch(batch);
    }
  } catch (error) {
    console.error('[CursorTelemetry] Upload error:', error);
    // Re-queue all on error
    requeueBatch(batch);
  }
  
  isUploading = false;
}

function requeueBatch(batch) {
  for (const item of batch) {
    if (item.retries < CONFIG.maxRetries) {
      item.retries++;
      item.timestamp = Date.now();
      uploadQueue.push(item);
      console.log('[CursorTelemetry] Re-queued item, retry:', item.retries);
    } else {
      console.log('[CursorTelemetry] Dropped item after max retries');
    }
  }
}

async function uploadBatch(batch, serverUrl) {
  const trajectories = batch.map(item => item.data);
  
  return fetch(serverUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Telemetry-Consent': 'true',
      'X-Client-Version': chrome.runtime.getManifest().version
    },
    body: JSON.stringify({ trajectories })
  });
}

// Debug helper
function debugUploadQueue() {
  console.log('Upload queue:', uploadQueue);
  console.log('Queue length:', uploadQueue.length);
  console.log('Is uploading:', isUploading);
}

// Expose for debugging
window.debugUploadQueue = debugUploadQueue;

console.log('[CursorTelemetry] Background service worker loaded v0.2.0');