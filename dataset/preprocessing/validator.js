/**
 * Dataset Validator
 * Validates cursor trajectory data against JSON schema
 */

const fs = require('fs');
const path = require('path');

class TrajectoryValidator {
  constructor(schemaPath) {
    this.schema = JSON.parse(fs.readFileSync(schemaPath, 'utf-8'));
    this.errors = [];
  }

  validate(trajectory) {
    this.errors = [];
    
    // Required fields
    this._checkRequired(trajectory);
    
    // Validate session_id format (SHA-256 hash)
    if (trajectory.session_id && !/^[a-f0-9]{32}$/.test(trajectory.session_id)) {
      this.errors.push('Invalid session_id format (expected 32-char hex)');
    }
    
    // Validate trajectory_id format (UUID)
    if (trajectory.trajectory_id && !this._isUUID(trajectory.trajectory_id)) {
      this.errors.push('Invalid trajectory_id format (expected UUID)');
    }
    
    // Validate timestamp format
    if (trajectory.timestamp && !this._isISODate(trajectory.timestamp)) {
      this.errors.push('Invalid timestamp format (expected ISO 8601)');
    }
    
    // Validate duration_ms
    if (trajectory.duration_ms !== undefined) {
      if (trajectory.duration_ms < 0 || trajectory.duration_ms > 600000) {
        this.errors.push('duration_ms must be between 0 and 600000');
      }
    }
    
    // Validate samples array
    this._validateSamples(trajectory.samples);
    
    // Validate privacy section
    this._validatePrivacy(trajectory.privacy);
    
    // Validate consent section
    this._validateConsent(trajectory.consent);
    
    return {
      valid: this.errors.length === 0,
      errors: this.errors
    };
  }

  _checkRequired(trajectory) {
    const required = ['session_id', 'trajectory_id', 'timestamp', 'samples'];
    for (const field of required) {
      if (!trajectory[field]) {
        this.errors.push(`Missing required field: ${field}`);
      }
    }
  }

  _isUUID(str) {
    return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(str);
  }

  _isISODate(str) {
    return !isNaN(Date.parse(str));
  }

  _validateSamples(samples) {
    if (!samples || !Array.isArray(samples)) {
      this.errors.push('samples must be a non-empty array');
      return;
    }
    
    if (samples.length === 0) {
      this.errors.push('samples array cannot be empty');
      return;
    }
    
    if (samples.length > 60000) {
      this.errors.push('samples array exceeds maximum of 60000');
    }
    
    // Validate each sample
    for (let i = 0; i < samples.length; i++) {
      const sample = samples[i];
      
      // Required fields in sample
      if (sample.t === undefined || sample.t === null) {
        this.errors.push(`Sample ${i}: missing required field 't'`);
      }
      if (sample.x === undefined || sample.x === null) {
        this.errors.push(`Sample ${i}: missing required field 'x'`);
      }
      if (sample.y === undefined || sample.y === null) {
        this.errors.push(`Sample ${i}: missing required field 'y'`);
      }
      
      // Validate ranges
      if (sample.x !== undefined && (sample.x < 0 || sample.x > 7680)) {
        this.errors.push(`Sample ${i}: x out of range (0-7680)`);
      }
      if (sample.y !== undefined && (sample.y < 0 || sample.y > 4320)) {
        this.errors.push(`Sample ${i}: y out of range (0-4320)`);
      }
      
      // Validate button state if present
      if (sample.button !== undefined) {
        const validButtons = [0, 1, 2, 4, 8, 16];
        if (!validButtons.includes(sample.button)) {
          this.errors.push(`Sample ${i}: invalid button state`);
        }
      }
    }
    
    // Check temporal ordering
    let prevT = -1;
    for (let i = 0; i < samples.length; i++) {
      if (samples[i].t < prevT) {
        this.errors.push(`Samples are not temporally ordered at index ${i}`);
        break;
      }
      prevT = samples[i].t;
    }
  }

  _validatePrivacy(privacy) {
    if (!privacy) return;
    
    if (privacy.epsilon !== undefined) {
      if (privacy.epsilon < 0 || privacy.epsilon > 10) {
        this.errors.push('privacy.epsilon must be between 0 and 10');
      }
    }
    
    if (privacy.noise_mechanism) {
      const valid = ['none', 'laplace', 'gaussian'];
      if (!valid.includes(privacy.noise_mechanism)) {
        this.errors.push(`Invalid noise_mechanism: ${privacy.noise_mechanism}`);
      }
    }
  }

  _validateConsent(consent) {
    if (!consent) return;
    
    if (consent.research_consent !== undefined && typeof consent.research_consent !== 'boolean') {
      this.errors.push('consent.research_consent must be boolean');
    }
    
    if (consent.data_usage) {
      const valid = ['research_only', 'research_and_improvement', 'any'];
      if (!valid.includes(consent.data_usage)) {
        this.errors.push(`Invalid data_usage: ${consent.data_usage}`);
      }
    }
  }

  /**
   * Validate a batch of trajectories
   */
  validateBatch(trajectories) {
    const results = [];
    for (let i = 0; i < trajectories.length; i++) {
      const result = this.validate(trajectories[i]);
      results.push({
        index: i,
        trajectory_id: trajectories[i].trajectory_id,
        ...result
      });
    }
    return results;
  }
}

// CLI usage
if (require.main === module) {
  const schemaPath = path.join(__dirname, '../schema/trajectory.schema.json');
  const validator = new TrajectoryValidator(schemaPath);
  
  // Read from stdin or file
  const input = process.argv[2] 
    ? JSON.parse(fs.readFileSync(process.argv[2], 'utf-8'))
    : JSON.parse(fs.readFileSync(0, 'utf-8'));
  
  const result = validator.validate(input);
  console.log(JSON.stringify(result, null, 2));
  
  process.exit(result.valid ? 0 : 1);
}

module.exports = { TrajectoryValidator };