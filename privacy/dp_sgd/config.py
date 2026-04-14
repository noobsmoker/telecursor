"""
DP-SGD Configuration

Defines hyperparameters for differentially private training.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class DPSGDConfig:
    """Configuration for DP-SGD training"""
    
    # Privacy budget (from SPEC.md)
    epsilon: float = 3.0       # Target privacy budget (ε ≤ 3.0)
    delta: float = 1e-5        # Failure probability
    
    # Gradient clipping
    max_grad_norm: float = 1.0  # Gradient clipping norm (C)
    clip_per_sample: bool = True  # Clip per-sample gradients
    
    # Noise
    noise_multiplier: float = 1.0  # σ = noise_multiplier * C
    
    # Training
    batch_size: int = 256
    learning_rate: float = 1e-3
    
    # Accounting
    accounting_mode: str = "rdp"  # "rdp" (Rényi) or "gdp" (Gaussian)
    
    # Secure aggregation
    use_secure_aggregation: bool = False
    aggregation_threshold: int = 3  # Min clients to aggregate
    
    # Validation
    verify_privacy: bool = True  # Run privacy verification tests
    
    # Logging
    log_privacy_every: int = 100  # Log privacy budget every N steps


# Preset configurations
PRESETS = {
    "high_privacy": DPSGDConfig(
        epsilon=1.0,
        delta=1e-6,
        max_grad_norm=0.5,
        noise_multiplier=2.0
    ),
    "balanced": DPSGDConfig(
        epsilon=3.0,
        delta=1e-5,
        max_grad_norm=1.0,
        noise_multiplier=1.0
    ),
    "low_privacy": DPSGDConfig(
        epsilon=10.0,
        delta=1e-4,
        max_grad_norm=2.0,
        noise_multiplier=0.5
    ),
    "debug": DPSGDConfig(
        epsilon=100.0,
        delta=1e-2,
        max_grad_norm=5.0,
        noise_multiplier=0.1
    )
}


def load_config(config_dict: dict) -> DPSGDConfig:
    """Load config from dictionary (e.g., YAML)"""
    return DPSGDConfig(**{
        k: v for k, v in config_dict.items()
        if k in DPSGDConfig.__dataclass_fields__
    })


def get_preset(name: str) -> DPSGDConfig:
    """Get a preset configuration"""
    if name not in PRESETS:
        raise ValueError(f"Unknown preset: {name}. Available: {list(PRESETS.keys())}")
    return PRESETS[name]


if __name__ == '__main__':
    # Print available presets
    print("Available DP-SGD presets:")
    for name, config in PRESETS.items():
        print(f"  {name}: ε={config.epsilon}, δ={config.delta}, C={config.max_grad_norm}")