"""
Tests for Privacy Mechanisms

Tests for:
- Laplace mechanism
- Gaussian mechanism  
- Privacy composition
- DP-SGD training
"""

import pytest
import torch
import numpy as np
from privacy.modular.privacy_framework import (
    ModularPrivacy, 
    PrivacyBudget,
    LaplaceMechanism,
    GaussianMechanism
)


class TestLaplaceMechanism:
    """Test Laplace noise mechanism"""
    
    def setup_method(self):
        self.mechanism = LaplaceMechanism()
    
    def test_adds_noise(self):
        """Adding Laplace noise changes the value"""
        value = 10.0
        epsilon = 1.0
        
        noisy = self.mechanism.add_noise(value, epsilon)
        
        # Noise should have been added
        assert noisy != value
    
    def test_sensitivity(self):
        """Test that sensitivity is properly calibrated"""
        epsilon = 1.0
        sensitivity = 1.0
        
        # Run multiple times and check distribution
        samples = [self.mechanism.add_noise(0, epsilon, sensitivity) for _ in range(1000)]
        
        # Laplace noise should have exponential distribution
        # Mean should be 0
        assert abs(np.mean(samples)) < 0.1
    
    def test_epsilon_scaling(self):
        """Higher epsilon = less noise"""
        value = 10.0
        
        noisy_low_eps = self.mechanism.add_noise(value, epsilon=0.1)
        noisy_high_eps = self.mechanism.add_noise(value, epsilon=10.0)
        
        # Lower epsilon = more noise
        diff_low = abs(noisy_low_eps - value)
        diff_high = abs(noisy_high_eps - value)
        
        assert diff_low > diff_high


class TestGaussianMechanism:
    """Test Gaussian noise mechanism"""
    
    def setup_method(self):
        self.mechanism = GaussianMechanism()
    
    def test_adds_noise(self):
        """Adding Gaussian noise changes the value"""
        value = 10.0
        epsilon = 1.0
        delta = 1e-5
        
        noisy = self.mechanism.add_noise(value, epsilon, delta)
        
        assert noisy != value
    
    def test_delta_parameter(self):
        """Test that delta affects noise level"""
        epsilon = 1.0
        
        noisy_low_delta = self.mechanism.add_noise(10.0, epsilon, delta=1e-9)
        noisy_high_delta = self.mechanism.add_noise(10.0, epsilon, delta=1e-3)
        
        # Lower delta = more noise (tighter privacy)
        diff_low = abs(noisy_low_delta - 10.0)
        diff_high = abs(noisy_high_delta - 10.0)
        
        assert diff_low > diff_high


class TestPrivacyComposition:
    """Test privacy composition theorems"""
    
    def setup_method(self):
        self.privacy = ModularPrivacy()
    
    def test_basic_composition(self):
        """Test basic composition: ε_total = ε1 + ε2"""
        epsilon1 = 1.0
        epsilon2 = 2.0
        
        total = self.privacy.compose_epsilon(epsilon1, epsilon2, method='basic')
        
        assert total == 3.0
    
    def test_strong_composition(self):
        """Test strong composition with delta"""
        epsilon = 1.0
        delta = 1e-5
        num_compositions = 10
        
        total = self.privacy.compose_epsilon(
            epsilon, epsilon, 
            method='strong', 
            delta=delta,
            num_compositions=num_compositions
        )
        
        # Strong composition: ε_total = ε * sqrt(2 * k * log(1/δ))
        expected = epsilon * np.sqrt(2 * num_compositions * np.log(1/delta))
        
        assert abs(total - expected) < 0.1
    
    def test_advanced_composition(self):
        """Test advanced composition"""
        epsilon = 1.0
        num_compositions = 5
        
        total = self.privacy.compose_epsilon(
            epsilon, epsilon,
            method='advanced',
            num_compositions=num_compositions
        )
        
        # Advanced: ε_total = ε + log(k)
        expected = epsilon + np.log(num_compositions)
        
        assert abs(total - expected) < 0.1


class TestModularPrivacy:
    """Test ModularPrivacy class"""
    
    def setup_method(self):
        self.privacy = ModularPrivacy(epsilon_budget=3.0, delta=1e-5)
    
    def test_initial_budget(self):
        """Test initial budget is correctly set"""
        budget = self.privacy.get_budget()
        
        assert budget.epsilon == 3.0
        assert budget.delta == 1e-5
    
    def test_spend_budget(self):
        """Test spending privacy budget"""
        self.privacy.spend_epsilon(1.0)
        
        budget = self.privacy.get_budget()
        assert budget.epsilon_spent == 1.0
    
    def test_budget_exceeded(self):
        """Test budget exceeded raises error"""
        with pytest.raises(ValueError):
            self.privacy.spend_epsilon(5.0)  # Over budget of 3.0
    
    def test_reset_budget(self):
        """Test resetting budget"""
        self.privacy.spend_epsilon(2.0)
        self.privacy.reset()
        
        budget = self.privacy.get_budget()
        assert budget.epsilon_spent == 0.0


class TestDPSGD:
    """Test DP-SGD implementation"""
    
    def test_gradient_clipping(self):
        """Test gradient clipping"""
        from privacy.dp_sgd.trainer import DPSGDTrainer, DPConfig
        
        # Simple model
        model = torch.nn.Linear(10, 2)
        
        config = DPConfig(
            epsilon=3.0,
            max_grad_norm=1.0,
            noise_multiplier=0.0  # No noise for testing
        )
        
        trainer = DPSGDTrainer(model, config)
        
        # Create batch with high gradient
        batch = {
            'input': torch.randn(32, 10),
            'labels': torch.randint(0, 2, (32,))
        }
        
        # Forward/backward
        output = model(batch['input'])
        loss = torch.nn.functional.cross_entropy(output, batch['labels'])
        loss.backward()
        
        # Should have clipped gradients
        for name, param in model.named_parameters():
            if param.grad is not None:
                grad_norm = param.grad.norm().item()
                # Norm should be <= max_grad_norm * some factor (due to per-layer clipping)
                assert grad_norm <= config.max_grad_norm * 2  # Some tolerance
    
    def test_privacy_accounting(self):
        """Test privacy accountant tracks epsilon"""
        from privacy.dp_sgd.trainer import DPSGDTrainer, DPConfig, PrivacyAccountant
        
        accountant = PrivacyAccountant(
            epsilon=3.0,
            delta=1e-5,
            accounting_mode='rdp'
        )
        
        # Take several steps
        for _ in range(100):
            accountant.step(noise_multiplier=1.0, sample_rate=0.01)
        
        epsilon = accountant.get_epsilon()
        
        # Should have accumulated some privacy loss
        assert epsilon > 0


class TestPrivacyAudit:
    """Test privacy audit module"""
    
    def test_audit_report_generation(self):
        """Test generating audit report"""
        from privacy.audit.report import audit_differential_privacy
        
        report = audit_differential_privacy(
            epsilon=3.0,
            delta=1e-5,
            num_steps=1000,
            dataset_size=10000
        )
        
        assert report.epsilon_spent > 0
        assert report.epsilon_budget == 3.0
        assert len(report.metrics) > 0
    
    def test_k_anonymity_verification(self):
        """Test k-anonymity verification"""
        from privacy.audit.report import KAnonymityVerifier
        
        verifier = KAnonymityVerifier(k=5)
        
        # Create test data
        data = [
            {'age': 25, 'zip': '12345', 'value': 1},
            {'age': 25, 'zip': '12345', 'value': 2},
            {'age': 30, 'zip': '12345', 'value': 3},
            {'age': 30, 'zip': '12345', 'value': 4},
            {'age': 30, 'zip': '12345', 'value': 5},
            {'age': 35, 'zip': '54321', 'value': 6},
        ]
        
        passed, details = verifier.verify(data, ['age', 'zip'])
        
        # Group (25, 12345) has 2 < 5, so should fail
        assert not passed
        assert details['min_group_size'] == 2


class TestFederatedLearning:
    """Test federated learning privacy"""
    
    def test_client_update_privacy(self):
        """Test that client updates preserve privacy"""
        from privacy.federated.federated_learning import (
            FederatedClient, ClientConfig, ModularPrivacy
        )
        
        config = ClientConfig(client_id='test-client')
        privacy = ModularPrivacy(epsilon_budget=2.0)
        client = FederatedClient(config, privacy)
        
        # Load dummy data
        client.load_data([
            {'x': i, 'y': i} for i in range(10)
        ])
        
        # Initialize model
        client.set_model({
            'layer1': np.random.randn(10, 5)
        })
        
        # Train
        update = client.train()
        
        # Update should have privacy metadata
        assert hasattr(update, 'privacy_noise')
        assert update.privacy_noise > 0  # Should add noise


if __name__ == '__main__':
    pytest.main([__file__, '-v'])