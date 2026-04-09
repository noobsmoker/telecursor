/**
 * CursorTelemetry - Popup UI Controller
 */

document.addEventListener('DOMContentLoaded', async () => {
  // Elements
  const trackingToggle = document.getElementById('tracking-toggle');
  const statusText = document.getElementById('status-text');
  const privacyLevel = document.getElementById('privacy-level');
  const statSessions = document.getElementById('stat-sessions');
  const statSamples = document.getElementById('stat-samples');
  const statHours = document.getElementById('stat-hours');
  const btnSettings = document.getElementById('btn-settings');
  const btnExport = document.getElementById('btn-export');
  const btnClear = document.getElementById('btn-clear');
  const openConsent = document.getElementById('open-consent');
  
  // State
  let isTracking = false;
  let settings = {};
  
  // Initialize
  await loadStatus();
  await loadStats();
  
  // Event handlers
  trackingToggle.addEventListener('click', toggleTracking);
  btnSettings.addEventListener('click', openSettings);
  btnExport.addEventListener('click', exportData);
  btnClear.addEventListener('click', clearData);
  openConsent.addEventListener('click', openConsentPage);
  
  // Load status from background
  async function loadStatus() {
    try {
      const response = await chrome.runtime.sendMessage({ type: 'GET_STATUS' });
      isTracking = response.isTracking;
      settings = response.settings || {};
      
      updateStatusUI();
      updatePrivacyUI();
    } catch (err) {
      console.error('Failed to load status:', err);
    }
  }
  
  // Load stats
  async function loadStats() {
    try {
      const stats = await chrome.runtime.sendMessage({ type: 'GET_STATS' });
      
      statSessions.textContent = stats.totalSessions || 0;
      statSamples.textContent = formatNumber(stats.totalSamples || 0);
      statHours.textContent = formatDuration(stats.totalDuration || 0);
    } catch (err) {
      console.error('Failed to load stats:', err);
    }
  }
  
  // Toggle tracking
  async function toggleTracking() {
    try {
      if (isTracking) {
        await chrome.runtime.sendMessage({ type: 'STOP_TRACKING' });
        isTracking = false;
      } else {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        await chrome.runtime.sendMessage({ type: 'START_TRACKING', tabId: tab.id });
        isTracking = true;
      }
      updateStatusUI();
    } catch (err) {
      console.error('Failed to toggle tracking:', err);
    }
  }
  
  // Update UI based on status
  function updateStatusUI() {
    if (isTracking) {
      trackingToggle.classList.add('active');
      statusText.textContent = 'Active';
      statusText.className = 'status-value active';
    } else {
      trackingToggle.classList.remove('active');
      statusText.textContent = 'Inactive';
      statusText.className = 'status-value inactive';
    }
  }
  
  // Update privacy level display
  function updatePrivacyUI() {
    const epsilon = settings.epsilon || 3.0;
    privacyLevel.textContent = `ε = ${epsilon}`;
  }
  
  // Open settings page
  function openSettings() {
    chrome.runtime.openOptionsPage();
  }
  
  // Export data
  async function exportData() {
    const consentManager = new ConsentManager();
    
    try {
      // Get all session data
      const allData = await chrome.storage.local.get(null);
      const sessions = Object.entries(allData)
        .filter(([key]) => key.startsWith('session_'))
        .reduce((acc, [key, value]) => ({ ...acc, [key]: value }), {});
      
      const exportResult = consentManager.exportUserData(sessions);
      
      if (exportResult.error) {
        alert(exportResult.error);
        return;
      }
      
      // Download
      const blob = new Blob([JSON.stringify(exportResult.data, null, 2)], { 
        type: 'application/json' 
      });
      const url = URL.createObjectURL(blob);
      
      const a = document.createElement('a');
      a.href = url;
      a.download = exportResult.filename;
      a.click();
      
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Export failed:', err);
      alert('Export failed. Please try again.');
    }
  }
  
  // Clear all data
  async function clearData() {
    if (!confirm('This will delete all your collected data. This cannot be undone. Continue?')) {
      return;
    }
    
    const consentManager = new ConsentManager();
    consentManager.revokeAllConsent();
    
    // Clear storage
    await chrome.storage.local.clear();
    
    // Reset UI
    await loadStats();
    alert('All data has been deleted.');
  }
  
  // Open consent page
  function openConsentPage() {
    chrome.runtime.openOptionsPage();
  }
  
  // Format large numbers
  function formatNumber(num) {
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toString();
  }
  
  // Format duration
  function formatDuration(ms) {
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    
    if (hours > 0) return hours + 'h';
    if (minutes > 0) return minutes + 'm';
    return seconds + 's';
  }
});
