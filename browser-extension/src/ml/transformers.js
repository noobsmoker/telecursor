/**
 * TeleCursor Client-Side ML with Transformers.js
 * 
 * A-001: Eliminate server costs - Run model inference in browser
 * Uses Transformers.js for WebGPU/WebAssembly inference
 * 
 * @version 0.1.0
 */

// Configuration
const ML_CONFIG = {
  modelPath: './models/',
  maxSeqLen: 2048,
  device: 'webgpu',  // 'webgpu', 'wasm', 'cpu'
  dtype: 'q4',       // 'q4', 'q8', 'f16', 'f32'
  numThreads: 4
};

/**
 * Initialize Transformers.js pipeline
 */
class ClientMLManager {
  constructor(config = {}) {
    this.config = { ...ML_CONFIG, ...config };
    this.pipeline = null;
    this.isLoaded = false;
    this.isLoading = false;
  }

  /**
   * Load model and tokenizer
   */
  async load() {
    if (this.isLoaded || this.isLoading) {
      return;
    }

    this.isLoading = true;
    console.log('[ML] Loading Transformers.js model...');

    try {
      // Dynamic import to avoid loading if not needed
      const { pipeline, env } = await import('@xenova/transformers');

      // Configure for browser
      env.allowLocalModels = false;
      env.useBrowserCache = true;
      env.backends.onnx.wasm.numThreads = this.config.numThreads;

      // Create pipeline for sequence classification (cursor state prediction)
      this.pipeline = await pipeline(
        'text-classification',
        this.config.modelPath,
        {
          dtype: this.config.dtype,
          device: this.config.device
        }
      );

      this.isLoaded = true;
      console.log('[ML] Model loaded successfully');
    } catch (error) {
      console.error('[ML] Failed to load model:', error);
      this.isLoading = false;
      throw error;
    }
  }

  /**
   * Predict cursor state from trajectory context
   */
  async predict(trajectoryContext) {
    if (!this.isLoaded) {
      await this.load();
    }

    try {
      // Convert trajectory to text-like input for the model
      const input = this.formatInput(trajectoryContext);

      // Run inference
      const result = await this.pipeline(input, {
        max_length: this.config.maxSeqLen,
        return_dict: true
      });

      return this.parseOutput(result);
    } catch (error) {
      console.error('[ML] Prediction error:', error);
      return { error: error.message };
    }
  }

  /**
   * Format trajectory as model input
   */
  formatInput(context) {
    // Convert trajectory features to a structured text representation
    const { samples, domain, viewport } = context;
    
    // Sample last N points for context
    const recent = samples.slice(-20);
    
    // Create movement pattern description
    const velocities = recent.map(s => Math.round(s.vx) + ',' + Math.round(s.vy));
    const positions = recent.map(s => Math.round(s.x) + ',' + Math.round(s.y));
    
    return `Cursor on ${domain} (${viewport.width}x${viewport.height}): ` +
      `velocities [${velocities.join(';')}], positions [${positions.join(';')}]`;
  }

  /**
   * Parse model output
   */
  parseOutput(output) {
    // Transform model output to predictions
    return {
      predictions: output,
      confidence: output[0]?.score || 0,
      timestamp: Date.now()
    };
  }

  /**
   * Check if WebGPU is available
   */
  static async checkWebGPU() {
    if (!navigator.gpu) {
      return { available: false, reason: 'WebGPU not supported' };
    }

    try {
      const adapter = await navigator.gpu.requestAdapter();
      if (!adapter) {
        return { available: false, reason: 'No GPU adapter' };
      }

      const device = await adapter.requestDevice();
      return { 
        available: true, 
        device: device.name,
        adapter: adapter
      };
    } catch (error) {
      return { available: false, reason: error.message };
    }
  }

  /**
   * Get memory usage estimate
   */
  getMemoryUsage() {
    // Estimate based on dtype and model size
    const sizes = {
      'q4': '~200MB',
      'q8': '~400MB',
      'f16': '~800MB',
      'f32': '~1.6GB'
    };
    return sizes[this.config.dtype] || 'unknown';
  }

  /**
   * Unload model to free memory
   */
  async unload() {
    if (this.pipeline) {
      // Release pipeline resources
      this.pipeline = null;
      this.isLoaded = false;
      console.log('[ML] Model unloaded');
    }
  }
}

/**
 * Cursor state prediction using Transformers.js
 */
class CursorPredictor {
  constructor() {
    this.mlManager = new ClientMLManager();
    this.predictionCache = new Map();
    this.lastPredictionTime = 0;
    this.predictionInterval = 1000;  // 1 second between predictions
  }

  /**
   * Predict next cursor position/state
   */
  async predictNextState(trajectory, currentState) {
    const now = Date.now();
    
    // Rate limit predictions
    if (now - this.lastPredictionTime < this.predictionInterval) {
      return this.predictionCache.get('latest') || null;
    }

    try {
      const context = {
        samples: trajectory.samples,
        domain: trajectory.session_context?.domain || 'unknown',
        viewport: trajectory.session_context?.viewport || { width: 1920, height: 1080 }
      };

      const result = await this.mlManager.predict(context);
      
      this.lastPredictionTime = now;
      this.predictionCache.set('latest', result);
      
      return result;
    } catch (error) {
      console.error('[Predictor] Error:', error);
      return null;
    }
  }

  /**
   * Batch predict for multiple trajectories
   */
  async batchPredict(trajectories) {
    const results = await Promise.allSettled(
      trajectories.map(t => this.predictNextState(t, null))
    );
    
    return results.map((r, i) => ({
      trajectory: trajectories[i],
      result: r.status === 'fulfilled' ? r.value : { error: r.reason }
    }));
  }

  /**
   * Initialize ML capabilities
   */
  async initialize() {
    const webGPU = await ClientMLManager.checkWebGPU();
    console.log('[Predictor] WebGPU status:', webGPU);
    
    if (!webGPU.available) {
      console.warn('[Predictor] WebGPU not available, falling back to WASM');
      this.mlManager.config.device = 'wasm';
    }
    
    // Pre-load model (optional, can lazy load)
    await this.mlManager.load();
  }
}

/**
 * Export for use in extension
 */
export { ClientMLManager, CursorPredictor };
export default { ClientMLManager, CursorPredictor };