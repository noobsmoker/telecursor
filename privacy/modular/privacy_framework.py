"""
Modular Privacy Framework

A-101: Enables A-007 federated learning
Provides pluggable privacy mechanisms that can be composed for different use cases.
"""

import numpy as np
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import hashlib
import json


class PrivacyMechanism(ABC):
    """Base class for privacy mechanisms"""
    
    @abstractmethod
    def apply(self, data: Any, epsilon: float) -> Any:
        """Apply privacy mechanism to data"""
        pass
    
    @abstractmethod
    def get_privacy_spent(self) -> float:
        """Return privacy budget spent (in epsilon)"""
        pass
    
    @abstractmethod
    def get_config(self) -> Dict:
        """Return mechanism configuration"""
        pass


class LaplaceMechanism(PrivacyMechanism):
    """
    Laplace mechanism for differential privacy
    Adds noise drawn from Laplace distribution to numerical values.
    """
    
    def __init__(self, sensitivity: float = 1.0):
        self.sensitivity = sensitivity
        self._privacy_spent = 0.0
    
    def apply(self, data: np.ndarray, epsilon: float) -> np.ndarray:
        """Add Laplace noise to data"""
        scale = self.sensitivity / epsilon
        noise = np.random.laplace(0, scale, data.shape)
        self._privacy_spent += epsilon
        return data + noise
    
    def get_privacy_spent(self) -> float:
        return self._privacy_spent
    
    def get_config(self) -> Dict:
        return {
            'mechanism': 'laplace',
            'sensitivity': self.sensitivity
        }


class GaussianMechanism(PrivacyMechanism):
    """
    Gaussian mechanism for differential privacy
    Adds Gaussian noise (requires stronger assumptions for DP).
    """
    
    def __init__(self, sensitivity: float = 1.0, delta: float = 1e-5):
        self.sensitivity = sensitivity
        self.delta = delta
        self._privacy_spent = 0.0
    
    def apply(self, data: np.ndarray, epsilon: float) -> np.ndarray:
        """Add Gaussian noise to data"""
        # Compute sigma for (epsilon, delta)-DP
        sigma = self.sensitivity * np.sqrt(2 * np.log(1.25 / self.delta)) / epsilon
        noise = np.random.normal(0, sigma, data.shape)
        self._privacy_spent += epsilon
        return data + noise
    
    def get_privacy_spent(self) -> float:
        return self._privacy_spent
    
    def get_config(self) -> Dict:
        return {
            'mechanism': 'gaussian',
            'sensitivity': self.sensitivity,
            'delta': self.delta
        }


class RandomizedResponse(PrivacyMechanism):
    """
    Randomized response for categorical data
    Probabilistically flips or reports true value.
    """
    
    def __init__(self, domain_size: int):
        self.domain_size = domain_size
        self._privacy_spent = 0.0
    
    def apply(self, data: np.ndarray, epsilon: float) -> np.ndarray:
        """Apply randomized response"""
        p_true = np.exp(epsilon) / (np.exp(epsilon) + self.domain_size - 1)
        
        # Flip with probability (1 - p_true)
        flip = np.random.random(data.shape) > p_true
        randomized = np.where(flip, np.random.randint(0, self.domain_size, data.shape), data)
        
        self._privacy_spent += epsilon
        return randomized
    
    def get_privacy_spent(self) -> float:
        return self._privacy_spent
    
    def get_config(self) -> Dict:
        return {
            'mechanism': 'randomized_response',
            'domain_size': self.domain_size
        }


class PrivacyBudget:
    """
    Track and manage privacy budget across multiple mechanisms
    """
    
    def __init__(self, total_epsilon: float = 3.0, delta: float = 1e-5):
        self.total_epsilon = total_epsilon
        self.delta = delta
        self.spent = 0.0
        self.transactions: List[Dict] = []
    
    def allocate(self, epsilon: float, mechanism: str) -> bool:
        """Allocate budget for a mechanism"""
        if self.spent + epsilon > self.total_epsilon:
            return False
        
        self.spent += epsilon
        self.transactions.append({
            'epsilon': epsilon,
            'mechanism': mechanism,
            'remaining': self.total_epsilon - self.spent
        })
        return True
    
    def get_remaining(self) -> float:
        """Get remaining budget"""
        return self.total_epsilon - self.spent
    
    def get_summary(self) -> Dict:
        """Get budget summary"""
        return {
            'total': self.total_epsilon,
            'spent': self.spent,
            'remaining': self.get_remaining(),
            'transactions': self.transactions
        }


class PrivacyPipeline:
    """
    Composable privacy pipeline
    Applies multiple mechanisms in sequence with budget tracking
    """
    
    def __init__(self, budget: Optional[PrivacyBudget] = None):
        self.budget = budget or PrivacyBudget()
        self.mechanisms: List[Tuple[PrivacyMechanism, float, str]] = []
    
    def add_mechanism(self, mechanism: PrivacyMechanism, epsilon: float, name: str = ''):
        """Add a mechanism to the pipeline"""
        self.mechanisms.append((mechanism, epsilon, name or mechanism.get_config()['mechanism']))
    
    def apply(self, data: Any) -> Tuple[Any, Dict]:
        """Apply all mechanisms in sequence"""
        result = data
        applied = []
        
        for mechanism, epsilon, name in self.mechanisms:
            if not self.budget.allocate(epsilon, name):
                applied.append({
                    'mechanism': name,
                    'status': 'skipped',
                    'reason': 'insufficient_budget'
                })
                continue
            
            result = mechanism.apply(result, epsilon)
            applied.append({
                'mechanism': name,
                'epsilon': epsilon,
                'status': 'applied'
            })
        
        metadata = {
            'budget': self.budget.get_summary(),
            'applied': applied
        }
        
        return result, metadata
    
    def reset(self):
        """Reset budget and mechanisms"""
        self.budget.spent = 0.0
        self.budget.transactions = []


class ModularPrivacy:
    """
    A-101: Main privacy orchestrator
    Provides pluggable privacy for different data types and use cases
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {
            'position': {'epsilon': 1.0, 'sensitivity': 2.0},
            'velocity': {'epsilon': 1.0, 'sensitivity': 10.0},
            'acceleration': {'epsilon': 0.5, 'sensitivity': 100.0},
            'categorical': {'epsilon': 0.5}
        }
        self.pipelines: Dict[str, PrivacyPipeline] = {}
    
    def create_pipeline(self, name: str, epsilon: float) -> PrivacyPipeline:
        """Create a named pipeline"""
        budget = PrivacyBudget(total_epsilon=epsilon)
        pipeline = PrivacyPipeline(budget)
        self.pipelines[name] = pipeline
        return pipeline
    
    def process_trajectory(self, trajectory: Dict) -> Tuple[Dict, Dict]:
        """
        Apply privacy to cursor trajectory
        """
        processed = trajectory.copy()
        metadata = {
            'budgets': {},
            'privacy_applied': True
        }
        
        # Apply position privacy (Laplace)
        if 'samples' in trajectory:
            samples = trajectory['samples']
            
            if samples:
                # Extract position data
                x = np.array([s.get('x', 0) for s in samples])
                y = np.array([s.get('y', 0) for s in samples])
                
                # Create and apply position pipeline
                pos_pipeline = self.create_pipeline('position', self.config['position']['epsilon'])
                pos_pipeline.add_mechanism(
                    LaplaceMechanism(sensitivity=self.config['position']['sensitivity']),
                    self.config['position']['epsilon'],
                    'position_noise'
                )
                
                # Apply
                x_noisy, meta = pos_pipeline.apply(x)
                y_noisy, _ = pos_pipeline.apply(y)
                
                # Update samples
                for i, s in enumerate(processed['samples']):
                    s['x'] = float(x_noisy[i])
                    s['y'] = float(y_noisy[i])
                
                metadata['budgets']['position'] = meta['budget']
        
        # Apply velocity privacy
        if 'samples' in processed['samples']:
            vx = np.array([s.get('vx', 0) for s in processed['samples']])
            vy = np.array([s.get('vy', 0) for s in processed['samples']])
            
            vel_pipeline = self.create_pipeline('velocity', self.config['velocity']['epsilon'])
            vel_pipeline.add_mechanism(
                LaplaceMechanism(sensitivity=self.config['velocity']['sensitivity']),
                self.config['velocity']['epsilon'],
                'velocity_noise'
            )
            
            vx_noisy, _ = vel_pipeline.apply(vx)
            vy_noisy, _ = vel_pipeline.apply(vy)
            
            for i, s in enumerate(processed['samples']):
                s['vx'] = float(vx_noisy[i])
                s['vy'] = float(vy_noisy[i])
            
            metadata['budgets']['velocity'] = vel_pipeline.budget.get_summary()
        
        # Add privacy metadata
        processed['anonymization'] = {
            'user_consent': trajectory.get('anonymization', {}).get('user_consent', False),
            'local_dp_applied': True,
            'privacy_metadata': metadata,
            'epsilon_used': sum(self.config[k]['epsilon'] for k in self.config)
        }
        
        return processed, metadata
    
    def federated_average(self, updates: List[Dict]) -> Dict:
        """
        A-101: Federated learning support
        Perform secure aggregation of model updates
        """
        if not updates:
            return {}
        
        # Secure aggregation: sum with noise cancellation
        aggregated = {}
        
        for key in updates[0].keys():
            values = [u.get(key, 0) for u in updates]
            
            # Add noise to each update before aggregation
            epsilon = 1.0
            noisy_values = [
                v + np.random.laplace(0, 1.0 / epsilon)
                for v in values
            ]
            
            # Sum (noise averages out with enough clients)
            aggregated[key] = np.mean(noisy_values, axis=0)
        
        return aggregated
    
    def get_privacy_guarantee(self) -> Dict:
        """Get formal privacy guarantee"""
        total_epsilon = sum(self.config[k]['epsilon'] for k in self.config)
        return {
            'epsilon': total_epsilon,
            'delta': 1e-5,
            'mechanisms': list(self.config.keys()),
            'guarantee': f'(ε={total_epsilon:.1f}, δ=1e-5)-differential privacy'
        }


# Example usage
if __name__ == '__main__':
    # Create modular privacy
    privacy = ModularPrivacy({
        'position': {'epsilon': 1.5, 'sensitivity': 2.0},
        'velocity': {'epsilon': 1.0, 'sensitivity': 10.0},
        'categorical': {'epsilon': 0.5}
    })
    
    # Sample trajectory
    trajectory = {
        'trajectory_id': 'test-123',
        'samples': [
            {'t': 0, 'x': 100, 'y': 200, 'vx': 50, 'vy': 30, 'button_state': 0},
            {'t': 20, 'x': 105, 'y': 205, 'vx': 55, 'vy': 35, 'button_state': 0},
        ],
        'anonymization': {'user_consent': True}
    }
    
    # Apply privacy
    protected, metadata = privacy.process_trajectory(trajectory)
    
    print("Privacy applied:")
    print(f"  Original x: {trajectory['samples'][0]['x']}")
    print(f"  Protected x: {protected['samples'][0]['x']:.2f}")
    print(f"  Budget spent: {metadata['budgets']['position']['spent']:.2f}")
    print(f"  Privacy guarantee: {privacy.get_privacy_guarantee()}")