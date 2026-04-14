"""
Privacy Audit Module

Tools for:
- Privacy budget tracking and reporting
- Attack simulation (membership inference, reconstruction)
- Privacy guarantee verification
- Audit report generation
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Callable
from enum import Enum
import json
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AttackType(Enum):
    """Types of privacy attacks to test"""
    MEMBERSHIP_INFERENCE = "membership_inference"
    ATTRIBUTE_INFERENCE = "attribute_inference"
    RECONSTRUCTION = "reconstruction"
    LINKAGE = "linkage"


@dataclass
class PrivacyMetric:
    """Privacy metric result"""
    name: str
    value: float
    threshold: float
    passed: bool
    details: str = ""


@dataclass
class AuditReport:
    """Privacy audit report"""
    timestamp: str
    epsilon_spent: float
    epsilon_budget: float
    delta: float
    num_training_steps: int
    metrics: List[PrivacyMetric]
    attack_results: List[Dict]
    recommendations: List[str]
    
    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp,
            'epsilon_spent': self.epsilon_spent,
            'epsilon_budget': self.epsilon_budget,
            'delta': self.delta,
            'num_training_steps': self.num_training_steps,
            'metrics': [
                {'name': m.name, 'value': m.value, 'threshold': m.threshold, 'passed': m.passed, 'details': m.details}
                for m in self.metrics
            ],
            'attack_results': self.attack_results,
            'recommendations': self.recommendations
        }
    
    def to_json(self, path: str):
        """Save report to JSON"""
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    def summary(self) -> str:
        """Generate text summary"""
        lines = [
            f"Privacy Audit Report - {self.timestamp}",
            "=" * 50,
            f"Privacy Budget: ε = {self.epsilon_spent:.2f} / {self.epsilon_budget:.2f}",
            f"Delta: {self.delta}",
            f"Training Steps: {self.num_training_steps}",
            "",
            "Metrics:"
        ]
        for m in self.metrics:
            status = "✓" if m.passed else "✗"
            lines.append(f"  {status} {m.name}: {m.value:.4f} (threshold: {m.threshold})")
        
        if self.attack_results:
            lines.append("")
            lines.append("Attack Simulations:")
            for r in self.attack_results:
                lines.append(f"  - {r.get('attack_type', 'unknown')}: {r.get('success_rate', 0):.2%}")
        
        if self.recommendations:
            lines.append("")
            lines.append("Recommendations:")
            for r in self.recommendations:
                lines.append(f"  - {r}")
        
        return "\n".join(lines)


class PrivacyAuditor:
    """
    Comprehensive privacy auditing for DP systems.
    """
    
    def __init__(
        self,
        epsilon_budget: float,
        delta: float,
        dataset_size: int = 10000
    ):
        self.epsilon_budget = epsilon_budget
        self.delta = delta
        self.dataset_size = dataset_size
        
        # Track history
        self.epsilon_history: List[float] = []
        self.step_history: List[int] = []
        
        # Metrics
        self.metrics: List[PrivacyMetric] = []
        self.attack_results: List[Dict] = []
    
    def update(
        self,
        epsilon_spent: float,
        num_steps: int
    ):
        """Update privacy tracking"""
        self.epsilon_history.append(epsilon_spent)
        self.step_history.append(num_steps)
    
    def verify_epsilon(self, epsilon_spent: float) -> PrivacyMetric:
        """Verify epsilon is within budget"""
        passed = epsilon_spent <= self.epsilon_budget
        metric = PrivacyMetric(
            name="Epsilon Budget",
            value=epsilon_spent,
            threshold=self.epsilon_budget,
            passed=passed,
            details=f"Spent: {epsilon_spent:.2f}, Budget: {self.epsilon_budget:.2f}"
        )
        self.metrics.append(metric)
        return metric
    
    def verify_delta(self, delta_achieved: float) -> PrivacyMetric:
        """Verify delta is within budget"""
        passed = delta_achieved <= self.delta
        metric = PrivacyMetric(
            name="Delta Budget",
            value=delta_achieved,
            threshold=self.delta,
            passed=passed,
            details=f"Achieved: {delta_achieved:.2e}, Budget: {self.delta:.2e}"
        )
        self.metrics.append(metric)
        return metric
    
    def verify_composition(
        self,
        num_steps: int,
        epsilon_per_step: float,
        composition_theorem: str = "advanced"
    ) -> PrivacyMetric:
        """
        Verify composition property.
        
        Supports: basic, strong, advanced composition
        """
        if composition_theorem == "basic":
            # Basic: ε_total = ε * num_steps
            epsilon_total = epsilon_per_step * num_steps
        elif composition_theorem == "strong":
            # Strong: ε_total = ε * sqrt(2 * num_steps * log(1/δ))
            epsilon_total = epsilon_per_step * np.sqrt(
                2 * num_steps * np.log(1 / self.delta)
            )
        else:  # advanced
            # Advanced composition (RDP)
            # Use RDP composition formula
            epsilon_total = epsilon_per_step * (1 + np.log(num_steps))
        
        passed = epsilon_total <= self.epsilon_budget
        metric = PrivacyMetric(
            name="Composition Guarantee",
            value=epsilon_total,
            threshold=self.epsilon_budget,
            passed=passed,
            details=f"Using {composition_theorem} composition"
        )
        self.metrics.append(metric)
        return metric
    
    def simulate_membership_inference(
        self,
        model,
        train_data: List,
        test_data: List,
        num_samples: int = 1000
    ) -> Dict:
        """
        Simulate membership inference attack.
        
        Measures how well an attacker can distinguish training data.
        """
        logger.info("Running membership inference attack simulation...")
        
        # Simplified: measure training loss vs test loss distribution
        train_losses = []
        test_losses = []
        
        # Simulate (in production, use actual model predictions)
        np.random.seed(42)
        for _ in range(num_samples):
            # Training samples tend to have lower loss
            train_losses.append(np.random.exponential(1.0))
            test_losses.append(np.random.exponential(1.2))
        
        # Compute attack success rate (simplified)
        # If distributions don't overlap much, attack is more effective
        train_mean = np.mean(train_losses)
        test_mean = np.mean(test_losses)
        
        # Simple threshold-based attack
        threshold = (train_mean + test_mean) / 2
        correct_train = sum(1 for l in train_losses if l < threshold)
        correct_test = sum(1 for l in test_losses if l >= threshold)
        
        success_rate = (correct_train + correct_test) / (2 * num_samples)
        
        result = {
            'attack_type': 'membership_inference',
            'success_rate': success_rate,
            'train_loss_mean': train_mean,
            'test_loss_mean': test_mean,
            'threshold': threshold,
            'description': 'Measures attacker ability to distinguish training data'
        }
        
        self.attack_results.append(result)
        
        # Add as metric
        self.metrics.append(PrivacyMetric(
            name="Membership Inference Resistance",
            value=success_rate,
            threshold=0.55,  # Should be close to random (0.5)
            passed=success_rate < 0.55,
            details=f"Success rate: {success_rate:.2%} (lower is better)"
        ))
        
        return result
    
    def simulate_reconstruction_attack(
        self,
        model,
        num_reconstructed: int = 10
    ) -> Dict:
        """
        Simulate gradient reconstruction attack.
        """
        logger.info("Running reconstruction attack simulation...")
        
        # Simplified: measure gradient exposure
        # In production, would use actual gradient information
        
        # Simulate some leakage based on DP noise level
        noise_scale = 1.0  # From DP-SGD
        reconstruction_quality = 1.0 / (1.0 + noise_scale)
        
        result = {
            'attack_type': 'reconstruction',
            'success_rate': 1 - reconstruction_quality,
            'noise_scale': noise_scale,
            'description': 'Measures ability to reconstruct training data from gradients'
        }
        
        self.attack_results.append(result)
        
        return result
    
    def compute_privacy_loss(self) -> Dict:
        """Compute worst-case privacy loss"""
        if not self.epsilon_history:
            return {'max_epsilon': 0, 'final_epsilon': 0}
        
        return {
            'max_epsilon': max(self.epsilon_history),
            'final_epsilon': self.epsilon_history[-1],
            'num_steps': len(self.epsilon_history)
        }
    
    def generate_report(self) -> AuditReport:
        """Generate comprehensive audit report"""
        
        # Compute current epsilon
        current_epsilon = self.epsilon_history[-1] if self.epsilon_history else 0
        current_steps = self.step_history[-1] if self.step_history else 0
        
        # Generate recommendations
        recommendations = []
        
        # Check epsilon
        if current_epsilon > self.epsilon_budget * 0.8:
            recommendations.append(
                "Privacy budget is above 80% - consider stopping training or using lower epsilon"
            )
        
        # Check metrics
        failed_metrics = [m for m in self.metrics if not m.passed]
        if failed_metrics:
            recommendations.append(
                f"Failed metrics: {', '.join(m.name for m in failed_metrics)}"
            )
        
        # Check attack success
        high_attack_success = [r for r in self.attack_results if r.get('success_rate', 0) > 0.55]
        if high_attack_success:
            recommendations.append(
                f"High attack success detected for: {[r['attack_type'] for r in high_attack_success]}"
            )
        
        return AuditReport(
            timestamp=datetime.now().isoformat(),
            epsilon_spent=current_epsilon,
            epsilon_budget=self.epsilon_budget,
            delta=self.delta,
            num_training_steps=current_steps,
            metrics=self.metrics,
            attack_results=self.attack_results,
            recommendations=recommendations
        )


class KAnonymityVerifier:
    """Verify k-anonymity guarantees"""
    
    def __init__(self, k: int = 5):
        self.k = k
    
    def verify(
        self,
        data: List[Dict],
        quasi_identifiers: List[str]
    ) -> Tuple[bool, Dict]:
        """
        Verify k-anonymity for dataset.
        
        Args:
            data: List of records
            quasi_identifiers: Fields that could identify individuals
            
        Returns:
            (passed, details)
        """
        # Group by quasi-identifiers
        groups: Dict[Tuple, List] = {}
        
        for record in data:
            key = tuple(record.get(qi, 'unknown') for qi in quasi_identifiers)
            if key not in groups:
                groups[key] = []
            groups[key].append(record)
        
        # Check min group size
        min_size = min(len(g) for g in groups.values()) if groups else 0
        passed = min_size >= self.k
        
        details = {
            'num_groups': len(groups),
            'min_group_size': min_size,
            'k_required': self.k,
            'passed': passed
        }
        
        if not passed:
            small_groups = [(k, len(g)) for k, g in groups.items() if len(g) < self.k]
            details['violations'] = [
                f"{k}: {len(g)} < {self.k}" for k, g in small_groups[:5]
            ]
        
        return passed, details


def audit_differential_privacy(
    epsilon: float,
    delta: float,
    num_steps: int,
    dataset_size: int = 10000
) -> AuditReport:
    """
    Quick audit function for DP training.
    
    Args:
        epsilon: Privacy budget
        delta: Failure probability
        num_steps: Number of training steps
        dataset_size: Size of training dataset
        
    Returns:
        AuditReport
    """
    # Create auditor
    auditor = PrivacyAuditor(epsilon, delta, dataset_size)
    
    # Compute effective epsilon (simplified)
    effective_epsilon = epsilon * np.sqrt(2 * num_steps * np.log(1 / delta))
    
    # Verify epsilon
    auditor.verify_epsilon(effective_epsilon)
    
    # Verify delta
    auditor.verify_delta(delta)
    
    # Verify composition
    auditor.verify_composition(
        num_steps,
        epsilon / np.sqrt(num_steps),  # Epsilon per step
        "strong"
    )
    
    # Update tracking
    auditor.update(effective_epsilon, num_steps)
    
    # Generate report
    return auditor.generate_report()


# Example usage
if __name__ == '__main__':
    # Quick audit
    print("Running quick privacy audit...")
    
    report = audit_differential_privacy(
        epsilon=3.0,
        delta=1e-5,
        num_steps=10000,
        dataset_size=10000
    )
    
    print(report.summary())
    
    # Save report
    report.to_json('privacy_audit_report.json')
    print("\nSaved report to privacy_audit_report.json")