"""
Model Poisoning Defense

Implements detection and filtering mechanisms to protect training pipeline
from adversarial data injection attacks.

S-003: Critical for data integrity
"""

import torch
import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict
import hashlib
import json


@dataclass
class PoisoningConfig:
    """Configuration for poisoning detection"""
    # Detection thresholds
    anomaly_score_threshold: float = 0.8
    max_gradient_norm: float = 10.0
    suspicious_pattern_threshold: float = 0.95
    
    # Statistical bounds (based on human movement)
    max_velocity: float = 5000  # px/s
    max_acceleration: float = 100000  # px/s²
    max_jerk: float = 500000  # px/s³
    
    # Filtering options
    enable_statistical_filter: bool = True
    enable_gradient_filter: bool = True
    enable_pattern_filter: bool = True
    
    # Attribution
    enable_attribution: bool = True
    attribution_window: int = 1000  # samples


class PoisonDetector:
    """Detect potential poisoned samples in training data"""
    
    def __init__(self, config: PoisoningConfig = None):
        self.config = config or PoisoningConfig()
        self.statistics = defaultdict(list)
        self.suspicious_hashes: Set[str] = set()
        self.anomaly_scores = []
        
    def analyze_sample(self, sample: Dict) -> Tuple[bool, float, List[str]]:
        """
        Analyze a single sample for poisoning indicators.
        
        Returns:
            (is_poisoned, anomaly_score, reasons)
        """
        reasons = []
        anomaly_score = 0.0
        
        # Check 1: Statistical anomalies (impossible physics)
        if self.config.enable_statistical_filter:
            vx, vy = sample.get('vx', 0), sample.get('vy', 0)
            ax, ay = sample.get('ax', 0), sample.get('ay', 0)
            
            velocity = np.sqrt(vx ** 2 + vy ** 2)
            if velocity > self.config.max_velocity:
                anomaly_score += 0.4
                reasons.append(f"impossible_velocity({velocity:.0f})")
            
            accel = np.sqrt(ax ** 2 + ay ** 2)
            if accel > self.config.max_acceleration:
                anomaly_score += 0.3
                reasons.append(f"impossible_acceleration({accel:.0f})")
        
        # Check 2: Suspicious patterns
        if self.config.enable_pattern_filter:
            # Check for repeated patterns (potential backdoor)
            sample_hash = self._hash_sample(sample)
            
            if sample_hash in self.suspicious_hashes:
                anomaly_score += 0.5
                reasons.append("suspicious_hash")
            
            # Check for perfect periodicity (bot-like)
            if self._is_suspiciously_periodic(sample):
                anomaly_score += 0.3
                reasons.append("periodic_pattern")
        
        # Check 3: Unusual entropy
        if self._has_low_entropy(sample):
            anomaly_score += 0.2
            reasons.append("low_entropy")
        
        is_poisoned = anomaly_score >= self.config.anomaly_score_threshold
        
        return is_poisoned, min(anomaly_score, 1.0), reasons
    
    def analyze_trajectory(self, samples: List[Dict]) -> Tuple[List[bool], float]:
        """
        Analyze an entire trajectory for poisoning.
        
        Returns:
            (is_poisoned_per_sample, trajectory_anomaly_score)
        """
        if len(samples) < 10:
            return [False] * len(samples), 0.0
        
        results = []
        scores = []
        
        for sample in samples:
            is_poisoned, score, _ = self.analyze_sample(sample)
            results.append(is_poisoned)
            scores.append(score)
        
        # Trajectory-level analysis
        trajectory_score = np.mean(scores)
        
        # Check for coordinated anomalies (multiple suspicious samples)
        poisoned_count = sum(results)
        if poisoned_count / len(samples) > 0.3:
            trajectory_score += 0.2
            reasons.append("coordinated_anomalies")
        
        return results, min(trajectory_score, 1.0)
    
    def _hash_sample(self, sample: Dict) -> str:
        """Create hash of sample for pattern detection"""
        key_fields = ['x', 'y', 'vx', 'vy', 'ax', 'ay', 'button_state']
        values = [str(sample.get(k, 0)) for k in key_fields]
        return hashlib.sha256('|'.join(values).encode()).hexdigest()[:16]
    
    def _is_suspiciously_periodic(self, sample: Dict) -> bool:
        """Detect suspiciously regular patterns (bot indicator)"""
        # Check if velocity is perfectly constant
        vx = sample.get('vx', 0)
        vy = sample.get('vy', 0)
        
        # Bot-like: exactly constant velocity
        if abs(vx) > 0 and abs(vx - round(vx)) < 0.01:
            if abs(vy) > 0 and abs(vy - round(vy)) < 0.01:
                return True
        
        return False
    
    def _has_low_entropy(self, sample: Dict) -> bool:
        """Detect samples with suspiciously low entropy"""
        # Count how many values are identical/rounded
        values = [
            sample.get('x', 0),
            sample.get('y', 0),
            sample.get('vx', 0),
            sample.get('vy', 0)
        ]
        
        # If all positions are integers (no noise), suspicious
        if all(v == round(v) for v in values if v != 0):
            return True
        
        return False
    
    def update_statistics(self, sample: Dict, is_poisoned: bool):
        """Update tracking statistics for attribution"""
        if self.config.enable_attribution:
            sample_hash = self._hash_sample(sample)
            
            if is_poisoned:
                self.suspicious_hashes.add(sample_hash)
            
            # Track anomaly scores
            _, score, _ = self.analyze_sample(sample)
            self.anomaly_scores.append(score)
            
            # Keep window bounded
            if len(self.anomaly_scores) > self.config.attribution_window:
                self.anomaly_scores = self.anomaly_scores[-self.config.attribution_window:]


class GradientMonitor:
    """Monitor training gradients for poisoning indicators"""
    
    def __init__(self, config: PoisoningConfig = None):
        self.config = config or PoisoningConfig()
        self.gradient_history = []
        self.suspicious_batches: List[int] = []
    
    def analyze_batch(self, batch_idx: int, gradients: Dict[str, torch.Tensor]) -> Tuple[bool, float]:
        """
        Analyze a batch of gradients for poisoning indicators.
        
        Returns:
            (is_suspicious, anomaly_score)
        """
        total_norm = 0.0
        max_single = 0.0
        
        for name, grad in gradients.items():
            if grad is None:
                continue
            
            # Compute norms
            param_norm = grad.norm().item()
            total_norm += param_norm ** 2
            
            # Track largest single gradient
            max_single = max(max_single, param_norm.abs().item())
        
        total_norm = total_norm ** 0.5
        
        # Check against threshold
        if total_norm > self.config.max_gradient_norm:
            anomaly_score = min(total_norm / self.config.max_gradient_norm, 2.0)
            if anomaly_score > 1.0:
                self.suspicious_batches.append(batch_idx)
            return True, anomaly_score
        
        return False, 0.0
    
    def get_statistics(self) -> Dict:
        """Get gradient monitoring statistics"""
        return {
            'suspicious_batches': len(self.suspicious_batches),
            'total_batches': len(self.gradient_history),
            'suspicious_indices': self.suspicious_batches[-10:]  # Last 10
        }


class DataAttributor:
    """Attribute suspicious samples to potential sources"""
    
    def __init__(self):
        self.source_tracking: Dict[str, int] = defaultdict(int)
        self.domain_stats: Dict[str, Dict] = {}
    
    def track_source(self, trajectory: Dict, is_poisoned: bool):
        """Track potential source of suspicious data"""
        if not is_poisoned:
            return
        
        domain = trajectory.get('session_context', {}).get('domain', 'unknown')
        self.source_tracking[domain] += 1
        
    def get_top_suspicious_sources(self, n: int = 10) -> List[Tuple[str, int]]:
        """Get top N most suspicious data sources"""
        sorted_sources = sorted(
            self.source_tracking.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_sources[:n]
    
    def reset(self):
        """Reset attribution tracking"""
        self.source_tracking.clear()
        self.domain_stats.clear()


def filter_poisoned_data(
    trajectories: List[Dict],
    config: Optional[PoisoningConfig] = None
) -> Tuple[List[Dict], Dict]:
    """
    Filter poisoned samples from training data.
    
    Returns:
        (filtered_trajectories, filtering_report)
    """
    cfg = config or PoisoningConfig()
    detector = PoisonDetector(cfg)
    attributor = DataAttributor()
    
    filtered = []
    total_samples = 0
    removed_samples = 0
    
    for traj in trajectories:
        samples = traj.get('samples', [])
        if len(samples) < 10:
            filtered.append(traj)
            continue
        
        # Analyze trajectory
        is_poisoned_per_sample, trajectory_score = detector.analyze_trajectory(samples)
        
        # Track source
        attributor.track_source(traj, trajectory_score > cfg.anomaly_score_threshold)
        
        # Filter poisoned samples
        clean_samples = [
            s for s, is_p in zip(samples, is_poisoned_per_sample) 
            if not is_p
        ]
        
        # Update statistics
        total_samples += len(samples)
        removed_samples += len(samples) - len(clean_samples)
        
        # Keep trajectory if enough samples remain
        if len(clean_samples) >= 10:
            filtered_traj = traj.copy()
            filtered_traj['samples'] = clean_samples
            filtered_traj['poisoning_score'] = trajectory_score
            filtered.append(filtered_traj)
        else:
            removed_samples += len(clean_samples)  # Count removed trajectory
    
    report = {
        'input_trajectories': len(trajectories),
        'output_trajectories': len(filtered),
        'total_samples': total_samples,
        'removed_samples': removed_samples,
        'removal_rate': removed_samples / max(total_samples, 1),
        'top_suspicious_sources': attributor.get_top_suspicious_sources()
    }
    
    return filtered, report


# Example usage
if __name__ == '__main__':
    # Test with sample data
    trajectories = [
        {
            'trajectory_id': 'test-1',
            'session_context': {'domain': 'example.com'},
            'samples': [
                {'x': 100 + i, 'y': 200 + i, 'vx': 50, 'vy': 30, 'ax': 10, 'ay': 5, 'button_state': 0}
                for i in range(50)
            ]
        },
        {
            'trajectory_id': 'test-2',
            'session_context': {'domain': 'suspicious.com'},
            'samples': [
                {'x': i * 100, 'y': i * 100, 'vx': 100, 'vy': 100, 'ax': 0, 'ay': 0, 'button_state': 0}
                for i in range(50)
            ]
        }
    ]
    
    # Run filtering
    filtered, report = filter_poisoned_data(trajectories)
    
    print("Filtering Report:")
    print(f"  Input: {report['input_trajectories']} trajectories")
    print(f"  Output: {report['output_trajectories']} trajectories")
    print(f"  Removed: {report['removed_samples']} samples ({report['removal_rate']:.1%})")
    print(f"  Top suspicious sources: {report['top_suspicious_sources']}")