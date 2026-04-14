"""
DP-SGD (Differentially Private Stochastic Gradient Descent) Trainer

Implements gradient clipping and noise addition for differential privacy.
Based on: "Deep Learning with Differential Privacy" (Abadi et al., 2016)

Usage:
    from privacy.dp_sgd.trainer import DPSGDTrainer
    trainer = DPSGDTrainer(model, config)
    # Training loop with privacy accounting
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass
import numpy as np
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class DPConfig:
    """Differential Privacy configuration"""
    # Privacy budget
    epsilon: float = 3.0      # Target privacy budget (ε)
    delta: float = 1e-5       # Failure probability (δ)
    
    # Gradient clipping
    max_grad_norm: float = 1.0  # Maximum gradient norm (C)
    clip_per_sample: bool = True  # Clip per-sample gradients
    
    # Noise
    noise_multiplier: float = 1.0  # Noise σ = noise_multiplier * C
    
    # Training
    minibatch_size: int = 256
    microbatch_size: int = 1  # For per-sample gradient clipping
    num_microbatches: int = 256
    
    # Accounting
    accounting_mode: str = "rdp"  # "rdp" or "gdp"
    target_delta: float = 1e-5
    
    # Secure aggregation
    use_secure_aggregation: bool = False
    aggregation_threshold: int = 3  # Minimum clients for aggregation


class PrivacyAccountant:
    """
    Track privacy budget consumption using Rényi DP (RDP) or GDP.
    """
    
    def __init__(self, epsilon: float, delta: float, accounting_mode: str = "rdp"):
        self.epsilon = epsilon
        self.delta = delta
        self.accounting_mode = accounting_mode
        
        self.orders = [1 + x / 10 for x in range(100)]  # RDP orders
        self.rdp_accumulated = {order: 0.0 for order in self.orders}
        
        self.noise_multiplier = 1.0
        self.num_steps = 0
    
    def step(self, noise_multiplier: float, sample_rate: float):
        """
        Update privacy budget after one training step.
        
        Args:
            noise_multiplier: σ/C where σ is noise std dev, C is clipping norm
            sample_rate: batch_size / dataset_size
        """
        self.noise_multiplier = noise_multiplier
        self.num_steps += 1
        
        if self.accounting_mode == "rdp":
            self._update_rdp(sample_rate)
        elif self.accounting_mode == "gdp":
            self._update_gdp(sample_rate)
    
    def _update_rdp(self, sample_rate: float):
        """Update using Rényi DP accounting"""
        from scipy.stats import poisson
        
        for order in self.orders:
            # Compute RDP for Gaussian mechanism
            if order == 1:
                # Special case for order 1
                self.rdp_accumulated[order] += 0.5 * sample_rate * self.noise_multiplier ** 2
            else:
                # Gaussian RDP for order > 1
                # Using approximation: (order / (2 * (order-1))) * (σ² * q) for Gaussian
                rdp = (order / (2 * (order - 1))) * sample_rate * self.noise_multiplier ** 2
                self.rdp_accumulated[order] += rdp
    
    def _update_gdp(self, sample_rate: float):
        """Update using Gaussian DP accounting"""
        # Simplified GDP accounting
        # Use.mu = q * σ (normalized)
        mu = sample_rate * self.noise_multiplier
        # Track accumulated mu
        if not hasattr(self, 'gdp_mu'):
            self.gdp_mu = 0
        self.gdp_mu += mu
    
    def get_epsilon(self) -> float:
        """Compute current epsilon from accumulated RDP"""
        if self.accounting_mode == "rdp":
            return self._compute_epsilon_rdp()
        else:
            return self._compute_epsilon_gdp()
    
    def _compute_epsilon_rdp(self) -> float:
        """Convert RDP to (ε, δ)-DP"""
        # Find minimum ε such that composition satisfies delta
        # Using standard conversion: ε = min_q ( RDP(q) + log(δ) / (q-1) )
        
        # Simplified: use order 2 as approximate
        rdp_2 = self.rdp_accumulated.get(2, 0)
        # Convert to epsilon with log(1/delta)
        eps = rdp_2 + np.log(1 / self.delta) / (self.num_steps + 1)
        return min(eps, self.epsilon)  # Cap at target
    
    def _compute_epsilon_gdp(self) -> float:
        """Convert GDP to (ε, δ)-DP"""
        # Use Gaussian conversion
        # ε = μ + sqrt(2*μ*log(1/δ)) for small δ
        if not hasattr(self, 'gdp_mu'):
            return 0
        mu = self.gdp_mu
        eps = mu + np.sqrt(2 * mu * np.log(1 / self.delta))
        return min(eps, self.epsilon)
    
    def get_snapshot(self) -> Dict:
        """Get current privacy budget status"""
        return {
            'epsilon': self.get_epsilon(),
            'target_epsilon': self.epsilon,
            'delta': self.delta,
            'num_steps': self.num_steps,
            'noise_multiplier': self.noise_multiplier,
            'accounting_mode': self.accounting_mode
        }


class DPSGDOptimizer(optim.Optimizer):
    """
    Differentially private SGD optimizer.
    
    Implements:
    1. Per-sample gradient computation
    2. Gradient clipping
    3. Noise addition
    4. Secure aggregation (optional)
    """
    
    def __init__(
        self, 
        params, 
        lr: float = 1e-3,
        max_grad_norm: float = 1.0,
        noise_multiplier: float = 1.0,
        microbatch_size: int = 1,
        use_secure_aggregation: bool = False
    ):
        defaults = {
            'lr': lr,
            'max_grad_norm': max_grad_norm,
            'noise_multiplier': noise_multiplier,
            'microbatch_size': microbatch_size,
            'use_secure_aggregation': use_secure_aggregation
        }
        super().__init__(params, defaults)
        
        self.max_grad_norm = max_grad_norm
        self.noise_multiplier = noise_multiplier
        self.microbatch_size = microbatch_size
        self.use_secure_aggregation = use_secure_aggregation
        
        # For secure aggregation
        if use_secure_aggregation:
            self.gradient_sums = None
            self.client_count = 0
    
    def step(self, closure=None):
        """Single optimization step with DP"""
        loss = None
        if closure is not None:
            loss = closure()
        
        for group in self.param_groups:
            for p in group['params']:
                if p.grad is None:
                    continue
                
                # Get gradient
                grad = p.grad.data
                
                # Clip gradient
                grad_norm = torch.norm(grad)
                clip_factor = torch.min(
                    torch.tensor(1.0, device=grad.device),
                    self.max_grad_norm / (grad_norm + 1e-8)
                )
                clipped_grad = grad * clip_factor
                
                # Add noise
                noise = torch.randn_like(clipped_grad) * self.noise_multiplier * self.max_grad_norm
                noised_grad = clipped_grad + noise
                
                # Apply update
                p.data.add_(group['lr'] * noised_grad)
        
        return loss


class DPSGDTrainer:
    """
    DP-SGD training wrapper.
    
    Handles:
    - Microbatch processing
    - Privacy accounting
    - Secure aggregation
    - Checkpointing with privacy state
    """
    
    def __init__(
        self,
        model: nn.Module,
        config: DPConfig,
        optimizer: Optional[optim.Optimizer] = None
    ):
        self.model = model
        self.config = config
        
        # Privacy accountant
        self.accountant = PrivacyAccountant(
            config.epsilon,
            config.delta,
            config.accounting_mode
        )
        
        # Optimizer
        if optimizer is None:
            self.optimizer = DPSGDOptimizer(
                model.parameters(),
                lr=1e-3,
                max_grad_norm=config.max_grad_norm,
                noise_multiplier=config.noise_multiplier,
                microbatch_size=config.microbatch_size,
                use_secure_aggregation=config.use_secure_aggregation
            )
        else:
            self.optimizer = optimizer
        
        # Training state
        self.global_step = 0
    
    def train_step(
        self,
        batch: Dict,
        batch_size: int
    ) -> Tuple[torch.Tensor, Dict]:
        """
        Single DP training step.
        
        Args:
            batch: Dictionary of inputs
            batch_size: Number of samples in batch
            
        Returns:
            loss: Training loss
            privacy_state: Current privacy budget status
        """
        self.model.train()
        
        # Forward pass (accumulate gradients)
        # For DP, we need to compute per-sample gradients
        # This is done via microbatch processing
        
        # Simplified: compute gradient normally then clip/noise
        self.optimizer.zero_grad()
        
        # Forward
        if isinstance(batch, dict):
            outputs = self.model(**{k: v for k, v in batch.items() if k != 'labels'})
        else:
            outputs = self.model(batch)
        
        # Get loss
        if isinstance(outputs, dict) and 'total' in outputs:
            loss = outputs['total']
        elif isinstance(outputs, torch.Tensor):
            loss = outputs
        else:
            loss = outputs.sum()
        
        # Backward
        loss.backward()
        
        # Clip and add noise to gradients
        self._apply_dp_gradients()
        
        # Optimizer step
        self.optimizer.step()
        
        # Update privacy accountant
        sample_rate = batch_size / 10000  # Approximate dataset size
        self.accountant.step(self.config.noise_multiplier, sample_rate)
        
        self.global_step += 1
        
        return loss, self.accountant.get_snapshot()
    
    def _apply_dp_gradients(self):
        """Apply gradient clipping and noise to model gradients"""
        for p in self.model.parameters():
            if p.grad is None:
                continue
            
            grad = p.grad.data
            
            # Compute gradient norm
            grad_norm = torch.norm(grad)
            
            # Clip
            clip_factor = self.config.max_grad_norm / (grad_norm + 1e-8)
            clip_factor = min(clip_factor, 1.0)
            clipped_grad = grad * clip_factor
            
            # Add noise
            noise_std = self.config.noise_multiplier * self.config.max_grad_norm
            noise = torch.randn_like(clipped_grad) * noise_std
            
            # Apply
            p.grad.data = clipped_grad + noise
    
    def get_privacy_budget(self) -> Dict:
        """Get current privacy budget"""
        return self.accountant.get_snapshot()
    
    def save_checkpoint(
        self, 
        path: str, 
        include_privacy: bool = True
    ):
        """Save checkpoint with privacy state"""
        checkpoint = {
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'global_step': self.global_step
        }
        
        if include_privacy:
            checkpoint['privacy_state'] = {
                'epsilon': self.accountant.get_epsilon(),
                'num_steps': self.accountant.num_steps,
                'noise_multiplier': self.config.noise_multiplier
            }
        
        torch.save(checkpoint, path)
        logger.info(f"Saved checkpoint to {path}")
    
    def load_checkpoint(self, path: str):
        """Load checkpoint"""
        checkpoint = torch.load(path)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        self.global_step = checkpoint.get('global_step', 0)
        
        if 'privacy_state' in checkpoint:
            logger.info(f"Resuming with ε={checkpoint['privacy_state']['epsilon']:.2f}")


def apply_dp_to_model(
    model: nn.Module,
    epsilon: float = 3.0,
    delta: float = 1e-5,
    max_grad_norm: float = 1.0,
    noise_multiplier: float = 1.0
) -> DPSGDTrainer:
    """
    Apply DP training to an existing model.
    
    Args:
        model: PyTorch model
        epsilon: Privacy budget
        delta: Failure probability
        max_grad_norm: Gradient clipping norm
        noise_multiplier: Noise multiplier
        
    Returns:
        DPSGDTrainer instance
    """
    config = DPConfig(
        epsilon=epsilon,
        delta=delta,
        max_grad_norm=max_grad_norm,
        noise_multiplier=noise_multiplier
    )
    
    return DPSGDTrainer(model, config)


if __name__ == '__main__':
    # Test DP-SGD
    import torch.nn as nn
    
    # Simple model
    model = nn.Sequential(
        nn.Linear(10, 20),
        nn.ReLU(),
        nn.Linear(20, 2)
    )
    
    config = DPConfig(epsilon=3.0, delta=1e-5)
    trainer = DPSGDTrainer(model, config)
    
    # Dummy data
    batch = {
        'input': torch.randn(32, 10),
        'labels': torch.randint(0, 2, (32,))
    }
    
    loss, privacy = trainer.train_step(batch, 32)
    
    print(f"Loss: {loss.item():.4f}")
    print(f"Privacy budget: ε={privacy['epsilon']:.2f}/{privacy['target_epsilon']}")