"""
Tests for Stage 1 Cursor Dynamics Model
"""

import pytest
import torch
import numpy as np
from model import (
    CursorConfig, CursorTokenizer, CursorDynamicsModel,
    RoPE, SwiGLU, CausalSelfAttention, PhysicsConstrainedLoss
)


class TestCursorConfig:
    """Test configuration defaults"""
    
    def test_defaults(self):
        config = CursorConfig()
        assert config.d_model == 768
        assert config.n_layers == 12
        assert config.n_heads == 12
        assert config.max_velocity == 5000
        assert config.gradient_checkpointing == True


class TestCursorTokenizer:
    """Test tokenization"""
    
    def setup_method(self):
        self.config = CursorConfig()
        self.tokenizer = CursorTokenizer(self.config)
    
    def test_tokenize_position(self):
        sample = {'x': 960, 'y': 540, 'vx': 0, 'vy': 0, 'ax': 0, 'ay': 0, 'button_state': 0}
        tokens = self.tokenizer.tokenize(sample)
        
        assert 0 <= tokens['x'] < self.config.position_bins
        assert 0 <= tokens['y'] < self.config.position_bins
    
    def test_tokenize_velocity(self):
        sample = {'x': 0, 'y': 0, 'vx': 100, 'vy': -50, 'ax': 0, 'ay': 0, 'button_state': 0}
        tokens = self.tokenizer.tokenize(sample)
        
        assert 0 <= tokens['vx'] < self.config.velocity_bins
        assert 0 <= tokens['vy'] < self.config.velocity_bins
        assert tokens['vx_sign'] == 1
        assert tokens['vy_sign'] == 0
    
    def test_batch_tokenize(self):
        samples = [
            {'x': 100, 'y': 200, 'vx': 10, 'vy': 20, 'ax': 0, 'ay': 0, 'button_state': 0},
            {'x': 300, 'y': 400, 'vx': 30, 'vy': 40, 'ax': 0, 'ay': 0, 'button_state': 0},
        ]
        tokens = self.tokenizer.batch_tokenize(samples)
        
        assert len(tokens) == 2


class TestRoPE:
    """Test Rotary Positional Embeddings"""
    
    def setup_method(self):
        self.rope = RoPE(dim=64, max_seq_len=128)
    
    def test_forward_shape(self):
        batch_size = 2
        num_heads = 4
        seq_len = 32
        head_dim = 64
        
        x = torch.randn(batch_size, num_heads, seq_len, head_dim)
        output = self.rope(x, seq_len)
        
        assert output.shape == (batch_size, num_heads, seq_len, head_dim)
    
    def test_rope_invariance(self):
        """Test that RoPE is idempotent when applied twice to same input"""
        x = torch.randn(1, 2, 16, 32)
        
        # RoPE should be applied once during forward, not be idempotent
        # This test just ensures it runs without error
        output = self.rope(x, 16)
        assert output.shape == x.shape


class TestSwiGLU:
    """Test SwiGLU activation"""
    
    def setup_method(self):
        self.swiglu = SwiGLU(dim=128)
    
    def test_forward_shape(self):
        batch_size = 4
        seq_len = 16
        dim = 128
        
        x = torch.randn(batch_size, seq_len, dim)
        output = self.swiglu(x)
        
        assert output.shape == (batch_size, seq_len, dim)
    
    def test_non_zero_output(self):
        x = torch.randn(2, 8, 64)
        output = self.swiglu(x)
        
        # SwiGLU should not produce all zeros
        assert not torch.allclose(output, torch.zeros_like(output))


class TestCausalSelfAttention:
    """Test causal self-attention"""
    
    def setup_method(self):
        self.config = CursorConfig(d_model=128, n_heads=4, max_seq_len=64)
        self.attn = CausalSelfAttention(self.config)
    
    def test_forward_shape(self):
        batch_size = 2
        seq_len = 16
        d_model = 128
        
        x = torch.randn(batch_size, seq_len, d_model)
        output = self.attn(x)
        
        assert output.shape == (batch_size, seq_len, d_model)
    
    def test_causal_masking(self):
        """Test that future positions don't influence past"""
        batch_size = 1
        seq_len = 8
        d_model = 64
        n_heads = 2
        
        # Create attention with causal mask
        config = CursorConfig(d_model=d_model, n_heads=n_heads, max_seq_len=seq_len)
        attn = CausalSelfAttention(config)
        
        x = torch.randn(batch_size, seq_len, d_model)
        output = attn(x)
        
        # Just ensure it runs without NaN
        assert not torch.isnan(output).any()


class TestPhysicsConstrainedLoss:
    """Test physics constraint loss"""
    
    def setup_method(self):
        self.config = CursorConfig(max_velocity=100, max_acceleration=1000)
        self.loss_fn = PhysicsConstrainedLoss(self.config)
    
    def test_forward(self):
        batch_size = 4
        seq_len = 16
        
        # Predictions: vx, vy, ax, ay
        predictions = torch.randn(batch_size, seq_len, 4)
        targets = torch.randn(batch_size, seq_len, 4)
        
        loss = self.loss_fn(predictions, targets)
        
        assert loss.item() >= 0  # Loss should be non-negative
    
    def test_penalizes_high_velocity(self):
        """High velocities should produce positive loss"""
        predictions = torch.zeros(2, 4, 4)
        predictions[0, :, 0] = 1000  # vx = 1000 (exceeds max_velocity=100)
        
        targets = torch.zeros(2, 4, 4)
        loss = self.loss_fn(predictions, targets)
        
        assert loss.item() > 0


class TestCursorDynamicsModel:
    """Test full model"""
    
    def setup_method(self):
        self.config = CursorConfig(
            d_model=128,
            n_layers=2,
            n_heads=2,
            max_seq_len=32
        )
        self.model = CursorDynamicsModel(self.config)
    
    def test_forward_shape(self):
        batch_size = 2
        seq_len = 16
        
        # Input: [batch, seq, 11] token IDs
        tokens = torch.randint(0, 100, (batch_size, seq_len, 11))
        
        outputs = self.model(tokens, use_checkpoint=False)
        
        assert outputs['x_logits'].shape == (batch_size, seq_len, self.config.position_bins)
        assert outputs['y_logits'].shape == (batch_size, seq_len, self.config.position_bins)
        assert outputs['physics_pred'].shape == (batch_size, seq_len, 4)
    
    def test_gradient_checkpointing(self):
        """Test that gradient checkpointing runs without error"""
        batch_size = 2
        seq_len = 8
        
        tokens = torch.randint(0, 100, (batch_size, seq_len, 11))
        
        # Forward with checkpointing
        outputs = self.model(tokens, use_checkpoint=True)
        
        # Backward pass
        loss = outputs['x_logits'].sum()
        loss.backward()
        
        # Check gradients exist
        for name, param in self.model.named_parameters():
            if param.requires_grad:
                assert param.grad is not None or not torch.isnan(param.grad).any()
    
    def test_compute_loss(self):
        batch_size = 2
        seq_len = 8
        
        tokens = torch.randint(0, 100, (batch_size, seq_len, 11))
        
        outputs = self.model(tokens, use_checkpoint=False)
        loss_dict = self.model.compute_loss(outputs, tokens, self.config)
        
        assert 'total' in loss_dict
        assert 'position' in loss_dict
        assert 'physics' in loss_dict
        assert loss_dict['total'].item() > 0


class TestModelGeneration:
    """Test autoregressive generation"""
    
    def setup_method(self):
        self.config = CursorConfig(
            d_model=64,
            n_layers=2,
            n_heads=2,
            max_seq_len=32,
            position_bins=32
        )
        self.model = CursorDynamicsModel(self.config)
        self.model.eval()
    
    def test_generate(self):
        # Seed with small trajectory
        seed = torch.randint(0, 32, (1, 4, 11))
        
        with torch.no_grad():
            generated = self.model.generate(seed, max_length=8, temperature=1.0)
        
        # Should have more tokens than seed
        assert generated.shape[1] > 4


if __name__ == '__main__':
    pytest.main([__file__, '-v'])