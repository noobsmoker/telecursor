"""
Adaptive Quantization for Cursor Trajectories

Dynamically adjusts token granularity based on trajectory complexity
and velocity patterns to improve model performance.

O-101: Unblocks model deployment
"""

import torch
import torch.nn as nn
import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class QuantizationConfig:
    """Configuration for adaptive quantization"""
    # Base bins (minimum resolution)
    position_bins_min: int = 256
    position_bins_max: int = 2048
    velocity_bins_min: int = 128
    velocity_bins_max: int = 1024
    acceleration_bins_min: int = 64
    acceleration_bins_max: int = 512
    
    # Complexity thresholds
    high_velocity_threshold: float = 500  # px/s
    high_curvature_threshold: float = 0.5  # radians
    low_complexity_threshold: float = 0.1
    
    # Adaptation rates
    learning_rate: float = 0.01
    smoothing_factor: float = 0.9


class ComplexityAnalyzer:
    """Analyze trajectory complexity for adaptive quantization"""
    
    def __init__(self, config: QuantizationConfig):
        self.config = config
        self.bin_counts = {
            'x': config.position_bins_min,
            'y': config.position_bins_min,
            'vx': config.velocity_bins_min,
            'vy': config.velocity_bins_min,
            'ax': config.acceleration_bins_min,
            'ay': config.acceleration_bins_min
        }
        
    def analyze(self, samples: List[Dict]) -> Dict[str, float]:
        """
        Analyze trajectory complexity and return complexity scores.
        
        Returns:
            Dict with complexity scores for each dimension (0-1 range)
        """
        if len(samples) < 10:
            return {k: 0.5 for k in self.bin_counts.keys()}
        
        # Extract arrays
        x = np.array([s.get('x', 0) for s in samples])
        y = np.array([s.get('y', 0) for s in samples])
        vx = np.array([s.get('vx', 0) for s in samples])
        vy = np.array([s.get('vy', 0) for s in samples])
        
        # Compute velocity magnitude
        velocity = np.sqrt(vx ** 2 + vy ** 2)
        
        # Compute curvature (change in direction)
        dx = np.diff(x)
        dy = np.diff(y)
        angle = np.arctan2(dy, dx)
        curvature = np.abs(np.diff(angle))
        
        # Compute complexity scores
        complexity = {}
        
        # Position complexity (spatial spread)
        x_range = np.max(x) - np.min(x)
        y_range = np.max(y) - np.min(y)
        position_complexity = (x_range + y_range) / 4000  # Normalize by typical viewport
        complexity['x'] = min(position_complexity, 1.0)
        complexity['y'] = min(position_complexity, 1.0)
        
        # Velocity complexity
        v_mean = np.mean(velocity)
        v_std = np.std(velocity)
        velocity_complexity = min((v_mean + v_std) / 1000, 1.0)
        complexity['vx'] = velocity_complexity
        complexity['vy'] = velocity_complexity
        
        # Acceleration complexity (derived from velocity changes)
        ax = np.diff(velocity)
        a_mean = np.mean(np.abs(ax))
        accel_complexity = min(a_mean / 100, 1.0)
        complexity['ax'] = accel_complexity
        complexity['ay'] = accel_complexity
        
        return complexity
    
    def compute_bin_counts(self, complexity: Dict[str, float]) -> Dict[str, int]:
        """
        Compute optimal bin counts based on complexity scores.
        
        Uses linear interpolation between min and max bins.
        """
        bin_counts = {}
        
        # Position bins
        for dim in ['x', 'y']:
            c = complexity.get(dim, 0.5)
            min_bins = self.config.position_bins_min
            max_bins = self.config.position_bins_max
            bin_counts[dim] = int(min_bins + c * (max_bins - min_bins))
        
        # Velocity bins
        for dim in ['vx', 'vy']:
            c = complexity.get(dim, 0.5)
            min_bins = self.config.velocity_bins_min
            max_bins = self.config.velocity_bins_max
            bin_counts[dim] = int(min_bins + c * (max_bins - min_bins))
        
        # Acceleration bins
        for dim in ['ax', 'ay']:
            c = complexity.get(dim, 0.5)
            min_bins = self.config.acceleration_bins_min
            max_bins = self.config.acceleration_bins_max
            bin_counts[dim] = int(min_bins + c * (max_bins - min_bins))
        
        return bin_counts
    
    def update_bins(self, bin_counts: Dict[str, int]):
        """Update bin counts with exponential smoothing"""
        for dim, new_count in bin_counts.items():
            old_count = self.bin_counts.get(dim, self.config.position_bins_min)
            smoothed = self.config.smoothing_factor * old_count + \
                      (1 - self.config.smoothing_factor) * new_count
            self.bin_counts[dim] = int(smoothed)
    
    def get_current_bins(self) -> Dict[str, int]:
        """Get current bin counts"""
        return self.bin_counts.copy()


class AdaptiveTokenizer:
    """Tokenizer with adaptive bin sizing"""
    
    def __init__(self, base_config: 'CursorConfig', quant_config: Optional[QuantizationConfig] = None):
        self.base_config = base_config
        self.quant_config = quant_config or QuantizationConfig()
        self.analyzer = ComplexityAnalyzer(self.quant_config)
        
        # Initialize with base config bins
        self.bin_mappings = {
            'x': self._create_bin_mapping(base_config.position_bins),
            'y': self._create_bin_mapping(base_config.position_bins),
            'vx': self._create_log_bin_mapping(base_config.velocity_bins, 2000),
            'vy': self._create_log_bin_mapping(base_config.velocity_bins, 2000),
            'ax': self._create_log_bin_mapping(base_config.acceleration_bins, 10000),
            'ay': self._create_log_bin_mapping(base_config.acceleration_bins, 10000),
        }
    
    def _create_bin_mapping(self, num_bins: int) -> np.ndarray:
        """Create linear bin edges"""
        return np.linspace(0, 1920, num_bins + 1)
    
    def _create_log_bin_mapping(self, num_bins: int, max_val: float) -> np.ndarray:
        """Create log-spaced bin edges"""
        return np.logspace(0, np.log10(max_val), num_bins + 1)
    
    def tokenize(self, sample: Dict, bin_counts: Optional[Dict[str, int]] = None) -> Dict:
        """
        Tokenize a sample with adaptive bin counts.
        
        Args:
            sample: Raw cursor sample
            bin_counts: Optional overrides for bin counts
            
        Returns:
            Token IDs
        """
        bins = bin_counts or self.analyzer.get_current_bins()
        
        # Ensure bin mappings are updated
        self._ensure_bin_mappings(bins)
        
        # Tokenize each dimension
        tokens = {}
        
        # Position (linear bins)
        tokens['x'] = min(int(np.digitize(sample.get('x', 0), self.bin_mappings['x']) - 1), bins['x'] - 1)
        tokens['y'] = min(int(np.digitize(sample.get('y', 0), self.bin_mappings['y']) - 1), bins['y'] - 1)
        
        # Velocity (log bins)
        tokens['vx'] = min(int(np.digitize(abs(sample.get('vx', 0)), self.bin_mappings['vx']) - 1), bins['vx'] - 1)
        tokens['vy'] = min(int(np.digitize(abs(sample.get('vy', 0)), self.bin_mappings['vy']) - 1), bins['vy'] - 1)
        tokens['vx_sign'] = 1 if sample.get('vx', 0) >= 0 else 0
        tokens['vy_sign'] = 1 if sample.get('vy', 0) >= 0 else 0
        
        # Acceleration (log bins)
        tokens['ax'] = min(int(np.digitize(abs(sample.get('ax', 0)), self.bin_mappings['ax']) - 1), bins['ax'] - 1)
        tokens['ay'] = min(int(np.digitize(abs(sample.get('ay', 0)), self.bin_mappings['ay']) - 1), bins['ay'] - 1)
        tokens['ax_sign'] = 1 if sample.get('ax', 0) >= 0 else 0
        tokens['ay_sign'] = 1 if sample.get('ay', 0) >= 0 else 0
        
        # Button state
        tokens['button'] = sample.get('button_state', 0)
        
        return tokens
    
    def _ensure_bin_mappings(self, bin_counts: Dict[str, int]):
        """Ensure bin mappings are updated for current bin counts"""
        if bin_counts.get('x') != len(self.bin_mappings['x']) - 1:
            self.bin_mappings['x'] = self._create_bin_mapping(bin_counts['x'])
        if bin_counts.get('y') != len(self.bin_mappings['y']) - 1:
            self.bin_mappings['y'] = self._create_bin_mapping(bin_counts['y'])
        if bin_counts.get('vx') != len(self.bin_mappings['vx']) - 1:
            self.bin_mappings['vx'] = self._create_log_bin_mapping(bin_counts['vx'], 2000)
        if bin_counts.get('vy') != len(self.bin_mappings['vy']) - 1:
            self.bin_mappings['vy'] = self._create_log_bin_mapping(bin_counts['vy'], 2000)
        if bin_counts.get('ax') != len(self.bin_mappings['ax']) - 1:
            self.bin_mappings['ax'] = self._create_log_bin_mapping(bin_counts['ax'], 10000)
        if bin_counts.get('ay') != len(self.bin_mappings['ay']) - 1:
            self.bin_mappings['ay'] = self._create_log_bin_mapping(bin_counts['ay'], 10000)
    
    def process_trajectory(self, samples: List[Dict]) -> Tuple[List[Dict], Dict[str, int]]:
        """
        Process a full trajectory with adaptive quantization.
        
        Returns:
            (tokenized_samples, bin_counts_used)
        """
        # Analyze complexity
        complexity = self.analyzer.analyze(samples)
        
        # Compute optimal bins
        bin_counts = self.analyzer.compute_bin_counts(ComplexityAnalyzer(self.quant_config).analyze(samples))
        
        # Update analyzer
        self.analyzer.update_bins(bin_counts)
        
        # Tokenize each sample
        tokens = [self.tokenize(s, bin_counts) for s in samples]
        
        return tokens, bin_counts


# Example usage
if __name__ == '__main__':
    from dataclasses import asdict
    
    # Create sample trajectory
    samples = [
        {'x': 100 + i * 2, 'y': 200 + i, 'vx': 50 + i, 'vy': 30, 'ax': 10, 'ay': 5, 'button_state': 0}
        for i in range(100)
    ]
    
    # Initialize adaptive tokenizer
    config = QuantizationConfig()
    tokenizer = AdaptiveTokenizer(None, config)
    
    # Process trajectory
    tokens, bins = tokenizer.process_trajectory(samples)
    
    print(f"Trajectory processed:")
    print(f"  Samples: {len(tokens)}")
    print(f"  Bin counts: {bins}")
    print(f"  First token: {tokens[0]}")