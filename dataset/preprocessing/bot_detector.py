"""
Bot Detection for Cursor Trajectories
Distinguishes human cursor movement from automation
"""

import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Optional
import json


@dataclass
class BotDetectionResult:
    """Result of bot detection analysis"""
    is_bot: bool
    confidence: float  # 0-1
    features: Dict[str, float]
    reasons: List[str]


class BotDetector:
    """
    Detect automated cursor movement using multiple heuristics:
    
    1. Velocity entropy (bots are too smooth)
    2. Temporal regularity (bots are metronomic)
    3. Path curvature (bots move linearly)
    4. Pause patterns (humans hesitate)
    5. Impossible jerks (instantaneous direction changes)
    """
    
    def __init__(self, thresholds: Optional[Dict] = None):
        # Thresholds tuned on human baseline data
        self.thresholds = thresholds or {
            'min_velocity_entropy': 2.0,
            'max_temporal_regularity': 0.95,  # R² of timestamp linear fit
            'min_curvature_variance': 0.1,
            'min_pause_frequency': 0.05,  # Pauses per second
            'max_impossible_jerks': 3,
        }
    
    def analyze(self, trajectory: Dict) -> BotDetectionResult:
        """
        Analyze a trajectory and return bot detection result.
        
        Args:
            trajectory: Dict with 'samples' list of cursor samples
            
        Returns:
            BotDetectionResult with classification and details
        """
        samples = trajectory.get('samples', [])
        if len(samples) < 20:
            return BotDetectionResult(
                is_bot=False,
                confidence=0.0,
                features={},
                reasons=['insufficient_data']
            )
        
        features = {}
        reasons = []
        
        # Feature 1: Velocity entropy
        velocities = [np.hypot(s.get('vx', 0), s.get('vy', 0)) for s in samples]
        features['velocity_entropy'] = self._compute_entropy(velocities)
        if features['velocity_entropy'] < self.thresholds['min_velocity_entropy']:
            reasons.append(f"velocity_entropy ({features['velocity_entropy']:.2f}) too low")
        
        # Feature 2: Temporal regularity
        timestamps = [s.get('t', 0) for s in samples]
        features['temporal_regularity'] = self._compute_temporal_regularity(timestamps)
        if features['temporal_regularity'] > self.thresholds['max_temporal_regularity']:
            reasons.append(f"temporal_regularity ({features['temporal_regularity']:.2f}) too high")
        
        # Feature 3: Path curvature variance
        positions = [(s.get('x', 0), s.get('y', 0)) for s in samples]
        features['curvature_variance'] = self._compute_curvature_variance(positions)
        if features['curvature_variance'] < self.thresholds['min_curvature_variance']:
            reasons.append(f"curvature_variance ({features['curvature_variance']:.2f}) too low")
        
        # Feature 4: Pause frequency
        features['pause_frequency'] = self._compute_pause_frequency(velocities, timestamps)
        if features['pause_frequency'] < self.thresholds['min_pause_frequency']:
            reasons.append(f"pause_frequency ({features['pause_frequency']:.2f}) too low")
        
        # Feature 5: Impossible jerks
        features['impossible_jerks'] = self._count_impossible_jerks(samples)
        if features['impossible_jerks'] > self.thresholds['max_impossible_jerks']:
            reasons.append(f"impossible_jerks ({features['impossible_jerks']}) detected")
        
        # Calculate overall bot score
        bot_score = self._calculate_bot_score(features, reasons)
        is_bot = bot_score > 0.7 or len(reasons) >= 3
        
        return BotDetectionResult(
            is_bot=is_bot,
            confidence=bot_score,
            features=features,
            reasons=reasons
        )
    
    def _compute_entropy(self, values: List[float], bins: int = 50) -> float:
        """Compute Shannon entropy of velocity distribution"""
        if not values:
            return 0.0
        
        hist, _ = np.histogram(values, bins=bins, density=True)
        hist = hist[hist > 0]  # Remove zeros
        if len(hist) == 0:
            return 0.0
        return -np.sum(hist * np.log2(hist))
    
    def _compute_temporal_regularity(self, timestamps: List[float]) -> float:
        """Measure how regular the sampling intervals are (bots = very regular)"""
        if len(timestamps) < 2:
            return 0.0
        
        intervals = np.diff(timestamps)
        if len(intervals) < 2:
            return 0.0
        
        # Linear fit to intervals
        x = np.arange(len(intervals))
        try:
            coeffs = np.polyfit(x, intervals, 1)
            predicted = np.polyval(coeffs, x)
        except:
            return 0.0
        
        # R² score
        ss_res = np.sum((intervals - predicted) ** 2)
        ss_tot = np.sum((intervals - np.mean(intervals)) ** 2)
        
        if ss_tot == 0:
            return 1.0  # Perfectly regular
        
        r_squared = 1 - (ss_res / ss_tot)
        return max(0.0, min(1.0, r_squared))
    
    def _compute_curvature_variance(self, positions: List[tuple]) -> float:
        """Compute variance in path curvature"""
        if len(positions) < 3:
            return 0.0
        
        curvatures = []
        for i in range(1, len(positions) - 1):
            p1 = np.array(positions[i-1])
            p2 = np.array(positions[i])
            p3 = np.array(positions[i+1])
            
            # Vectors
            v1 = p2 - p1
            v2 = p3 - p2
            
            # Skip if no movement
            norm1 = np.linalg.norm(v1)
            norm2 = np.linalg.norm(v2)
            if norm1 == 0 or norm2 == 0:
                continue
            
            # Angle between vectors (curvature)
            cos_angle = np.dot(v1, v2) / (norm1 * norm2)
            angle = np.arccos(np.clip(cos_angle, -1, 1))
            curvatures.append(angle)
        
        return float(np.var(curvatures)) if curvatures else 0.0
    
    def _compute_pause_frequency(self, velocities: List[float], timestamps: List[float]) -> float:
        """Count pauses (velocity near zero) per second"""
        if not velocities or not timestamps:
            return 0.0
        
        duration = (timestamps[-1] - timestamps[0]) / 1000  # Convert to seconds
        if duration == 0:
            return 0.0
        
        # Count pauses (velocity < 10 px/s)
        pauses = sum(1 for v in velocities if v < 10)
        return pauses / duration
    
    def _count_impossible_jerks(self, samples: List[Dict]) -> int:
        """Count instantaneous direction changes impossible for humans"""
        impossible = 0
        
        for i in range(1, len(samples) - 1):
            s1, s2, s3 = samples[i-1], samples[i], samples[i+1]
            
            # Get velocities
            v1 = np.array([s1.get('vx', 0), s1.get('vy', 0)])
            v2 = np.array([s2.get('vx', 0), s2.get('vy', 0)])
            v3 = np.array([s3.get('vx', 0), s3.get('vy', 0)])
            
            # Skip if no velocity data
            if np.linalg.norm(v1) == 0 or np.linalg.norm(v2) == 0 or np.linalg.norm(v3) == 0:
                continue
            
            # Calculate jerk (change in acceleration)
            dt1 = s2.get('t', 0) - s1.get('t', 0)
            dt2 = s3.get('t', 0) - s2.get('t', 0)
            
            if dt1 == 0 or dt2 == 0:
                continue
            
            a1 = (v2 - v1) / dt1 * 1000  # px/s²
            a2 = (v3 - v2) / dt2 * 1000
            
            jerk = np.linalg.norm(a2 - a1) / ((dt1 + dt2) / 2) * 1000  # px/s³
            
            # Human limit for jerk is around 50,000 px/s³, bots can exceed 100k
            if jerk > 100000:
                impossible += 1
        
        return impossible
    
    def _calculate_bot_score(self, features: Dict, reasons: List[str]) -> float:
        """Calculate overall bot probability from features"""
        score = 0.0
        
        # Weight features
        if features.get('velocity_entropy', 10) < 2.0:
            score += 0.3
        if features.get('temporal_regularity', 0) > 0.95:
            score += 0.3
        if features.get('curvature_variance', 1) < 0.05:
            score += 0.2
        if features.get('pause_frequency', 0.1) < 0.01:
            score += 0.2
        
        # Boost for multiple reasons
        score += len(reasons) * 0.1
        
        return min(score, 1.0)


# CLI for testing
if __name__ == '__main__':
    import sys
    
    detector = BotDetector()
    
    # Load trajectory from file
    if len(sys.argv) < 2:
        print("Usage: python bot_detector.py <trajectory.json>")
        sys.exit(1)
    
    with open(sys.argv[1]) as f:
        trajectory = json.load(f)
    
    result = detector.analyze(trajectory)
    
    print(f"Bot Detection Result:")
    print(f"  Is Bot: {result.is_bot}")
    print(f"  Confidence: {result.confidence:.2%}")
    print(f"  Features:")
    for k, v in result.features.items():
        print(f"    {k}: {v:.4f}")
    print(f"  Reasons: {', '.join(result.reasons) if result.reasons else 'none'}")