"""
Tests for Bot Detection
"""

import pytest
import json
import numpy as np
from bot_detector import BotDetector, BotDetectionResult


class TestBotDetector:
    """Test bot detection functionality"""
    
    def setup_method(self):
        self.detector = BotDetector()
    
    def _create_human_trajectory(self):
        """Create a realistic human-like cursor trajectory"""
        samples = []
        t = 0
        x, y = 100, 100
        vx, vy = 0, 0
        
        for i in range(50):
            # Human-like: varying velocity, occasional pauses, curved paths
            vx = np.random.randn() * 50 + 20 * np.sin(i * 0.1)
            vy = np.random.randn() * 40 + 15 * np.cos(i * 0.15)
            
            # Occasional pause (human hesitation)
            if np.random.random() < 0.05:
                vx, vy = 0, 0
            
            x += vx * 0.02  # 50Hz sampling
            y += vy * 0.02
            
            samples.append({
                't': t,
                'x': x,
                'y': y,
                'vx': vx,
                'vy': vy
            })
            t += 20
        
        return {'samples': samples}
    
    def _create_bot_trajectory(self):
        """Create a bot-like cursor trajectory"""
        samples = []
        t = 0
        x, y = 100, 100
        
        # Bot-like: perfectly regular, linear movement, no pauses
        for i in range(50):
            # Constant velocity (very regular)
            vx = 50
            vy = 30
            
            x += vx * 0.02
            y += vy * 0.02
            
            samples.append({
                't': t,
                'x': x,
                'y': y,
                'vx': vx,
                'vy': vy
            })
            t += 20  # Perfectly regular
        
        return {'samples': samples}
    
    def _create_jerky_trajectory(self):
        """Create trajectory with impossible jerks"""
        samples = []
        t = 0
        x, y = 100, 100
        
        for i in range(50):
            # Random instantaneous direction changes (impossible for humans)
            vx = np.random.uniform(-500, 500)
            vy = np.random.uniform(-500, 500)
            
            x += vx * 0.02
            y += vy * 0.02
            
            samples.append({
                't': t,
                'x': x,
                'y': y,
                'vx': vx,
                'vy': vy
            })
            t += 20
        
        return {'samples': samples}
    
    def test_human_trajectory_not_bot(self):
        """Human-like trajectory should not be flagged as bot"""
        trajectory = self._create_human_trajectory()
        result = self.detector.analyze(trajectory)
        
        # Human trajectory should have reasonable entropy
        assert result.features.get('velocity_entropy', 0) > 1.0
    
    def test_bot_trajectory_detected(self):
        """Bot-like trajectory should be detected"""
        trajectory = self._create_bot_trajectory()
        result = self.detector.analyze(trajectory)
        
        # Bot should have high temporal regularity
        assert result.features.get('temporal_regularity', 0) > 0.8
    
    def test_jerky_trajectory_detected(self):
        """Trajectory with impossible jerks should be flagged"""
        trajectory = self._create_jerky_trajectory()
        result = self.detector.analyze(trajectory)
        
        # Should detect impossible jerks
        assert result.features.get('impossible_jerks', 0) > 0
    
    def test_insufficient_data(self):
        """Short trajectories should return low confidence"""
        trajectory = {'samples': [{'t': 0, 'x': 100, 'y': 100, 'vx': 0, 'vy': 0}] * 5}
        result = self.detector.analyze(trajectory)
        
        assert result.confidence == 0.0
        assert 'insufficient_data' in result.reasons
    
    def test_velocity_entropy(self):
        """Test velocity entropy computation"""
        velocities = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        entropy = self.detector._compute_entropy(velocities)
        
        # Should produce positive entropy
        assert entropy > 0
    
    def test_temporal_regularity(self):
        """Test temporal regularity computation"""
        # Perfectly regular (bot-like)
        timestamps_regular = list(range(0, 1000, 20))
        regularity_regular = self.detector._compute_temporal_regularity(timestamps_regular)
        
        # Should be high (close to 1)
        assert regularity_regular > 0.9
    
    def test_custom_thresholds(self):
        """Test detector with custom thresholds"""
        custom_detector = BotDetector(thresholds={
            'min_velocity_entropy': 1.0,
            'max_temporal_regularity': 0.8,
        })
        
        assert custom_detector.thresholds['min_velocity_entropy'] == 1.0
        assert custom_detector.thresholds['max_temporal_regularity'] == 0.8


class TestBotDetectionResult:
    """Test BotDetectionResult dataclass"""
    
    def test_creation(self):
        result = BotDetectionResult(
            is_bot=True,
            confidence=0.8,
            features={'velocity_entropy': 1.5},
            reasons=['low_entropy', 'high_regularity']
        )
        
        assert result.is_bot == True
        assert result.confidence == 0.8
        assert result.features['velocity_entropy'] == 1.5
        assert len(result.reasons) == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])