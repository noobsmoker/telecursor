"""
CursorTelemetry - Stage 1: Cursor Dynamics Foundation Model

Architecture: Transformer over cursor trajectories
Objective: Next-position prediction (like language modeling)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
import numpy as np
from dataclasses import dataclass
from typing import Optional


@dataclass
class CursorConfig:
    """Configuration for Cursor Dynamics Model"""
    # Tokenization
    position_bins: int = 1024      # 0-1920 mapped to bins
    velocity_bins: int = 512       # Log-scaled velocity
    acceleration_bins: int = 256  # Jerk detection
    
    # Transformer core
    d_model: int = 768
    n_layers: int = 12
    n_heads: int = 12
    d_ff: int = 3072               # 4x d_model
    dropout: float = 0.1
    max_seq_len: int = 4096       # ~80 seconds at 50Hz
    
    # Training
    learning_rate: float = 3e-4
    weight_decay: float = 0.1
    warmup_steps: int = 10000


class CursorTokenizer:
    """
    Tokenize cursor physics into discrete tokens.
    Similar to how text is tokenized for LLMs.
    """
    
    def __init__(self, config: CursorConfig):
        self.config = config
        
        # Position bins: 0-1920 mapped linearly
        self.x_bins = config.position_bins
        self.y_bins = config.position_bins
        
        # Velocity bins: log-spaced from 0 to max velocity
        max_velocity = 2000  # px/s
        self.velocity_bins = self._log_bins(0, max_velocity, config.velocity_bins)
        
        # Acceleration bins: log-spaced
        max_acceleration = 10000  # px/s²
        self.acceleration_bins = self._log_bins(0, max_acceleration, config.acceleration_bins)
        
        # Button states: 8 combinations
        self.button_states = 8
        
        # Total vocab size
        self.vocab_size = (
            self.x_bins * self.y_bins * 
            config.velocity_bins * config.velocity_bins * 
            config.acceleration_bins * config.acceleration_bins *
            self.button_states
        )
        
    def _log_bins(self, min_val, max_val, num_bins):
        """Create log-spaced bin edges"""
        return np.logspace(0, np.log10(max_val), num_bins + 1)
    
    def _digitize(self, value, bins):
        """Map continuous value to bin index"""
        return np.digitize(value, bins) - 1
    
    def tokenize(self, sample):
        """
        Convert raw cursor sample to token IDs.
        
        Args:
            sample: dict with x, y, vx, vy, ax, ay, button_state
            
        Returns:
            token_ids: list of discrete token IDs
        """
        # Quantize position
        x_token = int(np.clip(sample['x'] / 1920 * self.config.position_bins, 
                              0, self.config.position_bins - 1))
        y_token = int(np.clip(sample['y'] / 1080 * self.config.position_bins, 
                              0, self.config.position_bins - 1))
        
        # Quantize velocity (use absolute value, sign separately)
        vx_sign = 1 if sample['vx'] >= 0 else 0
        vy_sign = 1 if sample['vy'] >= 0 else 0
        vx_mag = min(abs(sample['vx']), 2000)
        vy_mag = min(abs(sample['vy']), 2000)
        vx_token = self._digitize(vx_mag, self.velocity_bins)
        vy_token = self._digitize(vy_mag, self.velocity_bins)
        
        # Quantize acceleration
        ax_sign = 1 if sample['ax'] >= 0 else 0
        ay_sign = 1 if sample['ay'] >= 0 else 0
        ax_mag = min(abs(sample['ax']), 10000)
        ay_mag = min(abs(sample['ay']), 10000)
        ax_token = self._digitize(ax_mag, self.acceleration_bins)
        ay_token = self._digitize(ay_mag, self.acceleration_bins)
        
        # Button state
        button_token = sample.get('button_state', 0)
        
        # Combine into single token ID (for embedding lookup)
        # In practice, use separate embeddings and concat
        return {
            'x': x_token,
            'y': y_token,
            'vx': vx_token,
            'vy': vy_token,
            'vx_sign': vx_sign,
            'vy_sign': vy_sign,
            'ax': ax_token,
            'ay': ay_token,
            'ax_sign': ax_sign,
            'ay_sign': ay_sign,
            'button': button_token
        }
    
    def batch_tokenize(self, samples):
        """Tokenize a batch of samples"""
        return [self.tokenize(s) for s in samples]


class CursorDynamicsModel(nn.Module):
    """
    Transformer model for cursor dynamics.
    Predicts next cursor position given trajectory history.
    """
    
    def __init__(self, config: CursorConfig):
        super().__init__()
        self.config = config
        
        # Separate embeddings for each dimension
        self.x_embed = nn.Embedding(config.position_bins, config.d_model // 8)
        self.y_embed = nn.Embedding(config.position_bins, config.d_model // 8)
        self.vx_embed = nn.Embedding(config.velocity_bins, config.d_model // 8)
        self.vy_embed = nn.Embedding(config.velocity_bins, config.d_model // 8)
        self.ax_embed = nn.Embedding(config.acceleration_bins, config.d_model // 8)
        self.ay_embed = nn.Embedding(config.acceleration_bins, config.d_model // 8)
        self.button_embed = nn.Embedding(8, config.d_model // 8)
        
        # Combined embedding dimension
        embed_dim = config.d_model
        
        # Positional encoding (learnable)
        self.pos_embed = nn.Embedding(config.max_seq_len, embed_dim)
        
        # Transformer decoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=embed_dim,
            nhead=config.n_heads,
            dim_feedforward=config.d_ff,
            dropout=config.dropout,
            activation='gelu',
            batch_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=config.n_layers)
        
        # Output heads
        self.x_head = nn.Linear(embed_dim, config.position_bins)
        self.y_head = nn.Linear(embed_dim, config.position_bins)
        
        # Physics consistency head (predict velocity for regularization)
        self.velocity_head = nn.Linear(embed_dim, 2)
        
        self.dropout = nn.Dropout(config.dropout)
        self.layer_norm = nn.LayerNorm(embed_dim)
        
    def forward(self, trajectory_tokens, mask=None):
        """
        Forward pass.
        
        Args:
            trajectory_tokens: [batch, seq_len, 11] token IDs
            mask: [batch, seq_len] attention mask
            
        Returns:
            x_logits: [batch, seq_len, position_bins]
            y_logits: [batch, seq_len, position_bins]
        """
        batch_size, seq_len, _ = trajectory_tokens.shape
        
        # Extract individual token dimensions
        x_tokens = trajectory_tokens[:, :, 0]  # [batch, seq]
        y_tokens = trajectory_tokens[:, :, 1]
        vx_tokens = trajectory_tokens[:, :, 2]
        vy_tokens = trajectory_tokens[:, :, 3]
        vx_signs = trajectory_tokens[:, :, 4]
        vy_signs = trajectory_tokens[:, :, 5]
        ax_tokens = trajectory_tokens[:, :, 6]
        ay_tokens = trajectory_tokens[:, :, 7]
        ax_signs = trajectory_tokens[:, :, 8]
        ay_signs = trajectory_tokens[:, :, 9]
        button_tokens = trajectory_tokens[:, :, 10]
        
        # Embed each dimension
        x_emb = self.x_embed(x_tokens)
        y_emb = self.y_embed(y_tokens)
        vx_emb = self.vx_embed(vx_tokens)
        vy_emb = self.vy_embed(vy_tokens)
        ax_emb = self.ax_embed(ax_tokens)
        ay_emb = self.ay_embed(ay_tokens)
        button_emb = self.button_embed(button_tokens)
        
        # Combine embeddings
        hidden = torch.cat([
            x_emb, y_emb, vx_emb, vy_emb, 
            ax_emb, ay_emb, button_emb
        ], dim=-1)
        
        hidden = self.layer_norm(hidden)
        hidden = self.dropout(hidden)
        
        # Add positional encoding
        positions = torch.arange(seq_len, device=hidden.device).unsqueeze(0).expand(batch_size, -1)
        pos_emb = self.pos_embed(positions)
        hidden = hidden + pos_emb
        
        # Transformer
        if mask is not None:
            # Convert mask to transformer format
            attn_mask = mask.logical_not().float()
            hidden = self.transformer(hidden, src_key_padding_mask=attn_mask)
        else:
            hidden = self.transformer(hidden)
        
        # Output predictions
        x_logits = self.x_head(hidden)
        y_logits = self.y_head(hidden)
        
        # Velocity prediction for physics consistency
        velocity_pred = self.velocity_head(hidden)
        
        return {
            'x_logits': x_logits,
            'y_logits': y_logits,
            'velocity_pred': velocity_pred
        }
    
    def generate(self, seed_trajectory, max_length=100, temperature=1.0):
        """
        Autoregressively generate cursor trajectory.
        
        Args:
            seed_trajectory: Initial trajectory tokens
            max_length: Maximum length to generate
            temperature: Sampling temperature
            
        Returns:
            Generated trajectory tokens
        """
        self.eval()
        with torch.no_grad():
            generated = seed_trajectory.clone()
            
            for _ in range(max_length):
                outputs = self.forward(generated)
                
                # Sample next position
                x_logits = outputs['x_logits'][:, -1] / temperature
                y_logits = outputs['y_logits'][:, -1] / temperature
                
                x_probs = F.softmax(x_logits, dim=-1)
                y_probs = F.softmax(y_logits, dim=-1)
                
                x_next = torch.multinomial(x_probs, 1)
                y_next = torch.multinomial(y_probs, 1)
                
                # Build next token (simplified)
                next_token = torch.cat([x_next, y_next], dim=-1)
                generated = torch.cat([generated, next_token.unsqueeze(1)], dim=1)
                
                if generated.size(1) >= self.config.max_seq_len:
                    break
                    
        return generated


class CursorDataset(Dataset):
    """
    Dataset for cursor trajectory data.
    Loads from processed trajectory files.
    """
    
    def __init__(self, trajectories, tokenizer, context_length=2048):
        self.trajectories = trajectories
        self.tokenizer = tokenizer
        self.context_length = context_length
        
    def __len__(self):
        return len(self.trajectories)
    
    def __getitem__(self, idx):
        trajectory = self.trajectories[idx]
        
        # Extract samples
        samples = trajectory.get('samples', [])
        
        if len(samples) < 10:
            # Skip very short trajectories
            return self.__getitem__((idx + 1) % len(self))
        
        # Tokenize
        tokens = self.tokenizer.batch_tokenize(samples)
        
        # Convert to tensor
        token_array = np.zeros((len(tokens), 11), dtype=np.int64)
        for i, t in enumerate(tokens):
            token_array[i, 0] = t['x']
            token_array[i, 1] = t['y']
            token_array[i, 2] = t['vx']
            token_array[i, 3] = t['vy']
            token_array[i, 4] = t['vx_sign']
            token_array[i, 5] = t['vy_sign']
            token_array[i, 6] = t['ax']
            token_array[i, 7] = t['ay']
            token_array[i, 8] = t['ax_sign']
            token_array[i, 9] = t['ay_sign']
            token_array[i, 10] = t['button']
        
        # Pad or truncate to context length
        if token_array.shape[0] < self.context_length:
            padding = np.zeros((self.context_length - token_array.shape[0], 11), dtype=np.int64)
            token_array = np.vstack([padding, token_array])
        else:
            token_array = token_array[:self.context_length]
        
        return torch.from_numpy(token_array)


def compute_loss(outputs, targets, config):
    """
    Compute training loss.
    
    Combines:
    - Cross-entropy for position prediction
    - Physics consistency loss
    """
    # Position loss
    x_loss = F.cross_entropy(
        outputs['x_logits'].view(-1, config.position_bins),
        targets[:, 1:, 0].view(-1)  # Predict next position
    )
    y_loss = F.cross_entropy(
        outputs['y_logits'].view(-1, config.position_bins),
        targets[:, 1:, 1].view(-1)
    )
    
    position_loss = (x_loss + y_loss) / 2
    
    # Physics loss (velocity consistency)
    # This encourages predicted velocities to match actual
    physics_loss = 0.0
    
    return {
        'total': position_loss + 0.1 * physics_loss,
        'position': position_loss,
        'physics': physics_loss
    }


# Example training loop
def train_stage1():
    """Example training loop for Stage 1"""
    config = CursorConfig()
    
    model = CursorDynamicsModel(config)
    tokenizer = CursorTokenizer(config)
    
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=config.learning_rate,
        weight_decay=config.weight_decay
    )
    
    # Learning rate scheduler
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, 
        T_max=500000,
        eta_min=config.learning_rate * 0.1
    )
    
    # Example: would load from dataset
    # dataset = CursorDataset(trajectories, tokenizer)
    # dataloader = DataLoader(dataset, batch_size=32)
    
    print(f"Model parameters: {sum(p.numel() for p in model.parameters()):,}")
    print(f"Vocab size: {tokenizer.vocab_size:,}")
    
    return model, tokenizer, optimizer, scheduler


if __name__ == '__main__':
    model, tokenizer, optimizer, scheduler = train_stage1()
    print("Stage 1 model initialized")
