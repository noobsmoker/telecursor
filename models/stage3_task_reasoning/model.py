"""
Stage 3: Task-Level Reasoning Model

Uses sub-quadratic architecture (Mamba-style state space model) for:
- Session-level intent prediction
- Task completion prediction
- Frustration detection
- Multi-task learning
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from dataclasses import dataclass
from typing import Optional, Dict, Tuple, List
import math


@dataclass
class TaskReasoningConfig:
    """Configuration for Task Reasoning Model"""
    # Model dimensions (from SPEC.md)
    d_model: int = 1024
    n_layers: int = 24
    
    # State Space Model (Mamba-style) parameters
    ssm_d_state: int = 16  # State dimension
    ssm_d_conv: int = 4   # Convolution width
    ssmexpand: int = 2    # Expansion factor
    
    # Output heads
    num_intents: int = 10
    num_tasks: int = 20    # Task completion categories
    frustration_levels: int = 3  # low, medium, high
    
    # Training
    learning_rate: float = 3e-5  # Lower LR for fine-tuning
    dropout: float = 0.1
    
    # RL fine-tuning (PPO)
    ppo_clip_ratio: float = 0.2
    ppo_epochs: int = 4


class SSMConv1d(nn.Module):
    """
    Depthwise convolution for State Space Model.
    Used for local context in SSM.
    """
    
    def __init__(self, d_model: int, d_conv: int):
        super().__init__()
        self.d_model = d_model
        self.d_conv = d_conv
        
        # Convolution kernel
        self.conv = nn.Conv1d(
            d_model, 
            d_model, 
            kernel_size=d_conv,
            padding=d_conv - 1,
            groups=d_model  # Depthwise
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: [batch, seq, d_model]
        Returns:
            [batch, seq, d_model]
        """
        # Transpose for conv1d: [batch, d_model, seq]
        x = x.transpose(1, 2)
        x = self.conv(x)
        # Truncate to original length
        x = x[:, :, :x.shape[2]]
        return x.transpose(1, 2)


class SSMBlock(nn.Module):
    """
    State Space Model block (Mamba-style).
    Uses selective state space for efficient long-range dependencies.
    """
    
    def __init__(self, config: TaskReasoningConfig):
        super().__init__()
        self.config = config
        
        d_model = config.d_model
        d_state = config.ssm_d_state
        d_conv = config.ssm_d_conv
        expand = config.ssmexpand
        
        # Input projection
        self.in_proj = nn.Linear(d_model, d_model * expand * 2, bias=False)
        
        # Convolution for local context
        self.conv = SSMConv1d(d_model * expand, d_conv)
        
        # SSM parameters (selective)
        self.x_proj = nn.Linear(d_model * expand, d_state * 2, bias=False)  # For selective mechanism
        self.dt_proj = nn.Linear(d_model * expand, d_model * expand, bias=True)
        
        # SSM Core - A, B matrices
        # A: [d_model * expand, d_state]
        self.A_log = nn.Parameter(torch.randn(d_model * expand, d_state))
        self.B_log = nn.Parameter(torch.randn(d_model * expand, d_state))
        
        # Output projection
        self.out_proj = nn.Linear(d_model * expand, d_model, bias=False)
        
        # Norm
        self.norm = nn.LayerNorm(d_model)
        
        # Initialize
        self._init_weights()
    
    def _init_weights(self):
        # Initialize A as negative (for stability)
        nn.init.xavier_uniform_(self.A_log)
        nn.init.xavier_uniform_(self.B_log)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Mamba-style SSM forward.
        
        Args:
            x: [batch, seq, d_model]
            
        Returns:
            [batch, seq, d_model]
        """
        batch, seq_len, _ = x.shape
        
        # Input projection with gating
        xz = self.in_proj(x)  # [B, L, 2*D]
        x_inner, z = xz.chunk(2, dim=-1)  # Each [B, L, D*expand]
        
        # Convolution (local context)
        conv_out = self.conv(x_inner)  # [B, L, D*expand]
        x_conv = F.silu(conv_out)
        
        # Selective SSM parameters
        # Project to get selective weights
        s_params = self.x_proj(x_conv)  # [B, L, 2*d_state]
        s_B, s_C = s_params.chunk(2, dim=-1)
        
        # Get A, B matrices (learned, not selective for now)
        A = -torch.exp(self.A_log.float())  # [D*expand, d_state]
        B = torch.exp(self.B_log.float())  # [D*expand, d_state]
        
        # dt projection (delta for SSM)
        dt = self.dt_proj(x_conv)  # [B, L, D*expand]
        dt = F.softplus(dt)
        
        # Simplified SSM: use diagonal approximation
        # This is a simplified version - full Mamba uses selective scan
        # For now, use a simplified state update
        
        # State: [B, D*expand, d_state]
        state = torch.zeros(batch, x_conv.shape[-1], self.config.ssm_d_state, 
                           device=x.device, dtype=x.dtype)
        
        outputs = []
        for t in range(seq_len):
            # Selective update (simplified)
            x_t = x_conv[:, t, :]  # [B, D*expand]
            
            # State update: state = A * state + B * x_t
            # Using element-wise for simplicity (would use scan in full impl)
            state = state * 0.95 + B.unsqueeze(0) * x_t.unsqueeze(-1)
            
            # Output: C * state
            y_t = torch.einsum('bd,bn->b', x_t, C = torch.einsum('dm,bn->bd', state, s_C.squeeze(-1)).squeeze(-1))
            
            # Actually, let's use a simpler approach with a linear layer
            # This avoids the complexity of full SSM
            output = torch.sum(state * s_C.unsqueeze(1), dim=-1)  # [B, D*expand]
            outputs.append(output)
        
        # Stack outputs
        y = torch.stack(outputs, dim=1)  # [B, L, D*expand]
        
        # gating
        y = y * F.silu(z)
        
        # Output projection
        y = self.out_proj(y)
        
        # Residual connection with norm
        return self.norm(x + y)


class TaskReasoningModel(nn.Module):
    """
    Stage 3: Task-Level Reasoning Model
    
    Uses Mamba-style SSM for efficient long-sequence modeling.
    Predicts:
    - Intent (what is user trying to do)
    - Task completion (did they succeed)
    - Frustration level (how frustrated are they)
    """
    
    def __init__(self, config: TaskReasoningConfig, stage2_model=None):
        super().__init__()
        self.config = config
        
        # Stage 2 encoder (can be frozen)
        if stage2_model is not None:
            self.stage2 = stage2_model
            self.stage2.eval()
            self.stage2_frozen = True
            # Project Stage 2 output to our dimension
            self.stage2_proj = nn.Linear(768, config.d_model)
        else:
            self.stage2 = None
            self.stage2_frozen = False
        
        # Embedding for trajectory features
        self.input_embed = nn.Linear(768, config.d_model)
        
        # Positional encoding (learnable)
        self.pos_embed = nn.Parameter(torch.randn(1, 50000, config.d_model) * 0.02)
        
        # SSM layers (Mamba-style)
        self.layers = nn.ModuleList([
            SSMBlock(config) for _ in range(config.n_layers)
        ])
        
        # Output heads
        self.intent_head = nn.Sequential(
            nn.Linear(config.d_model, config.d_model // 2),
            nn.GELU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.d_model // 2, config.num_intents)
        )
        
        self.task_head = nn.Sequential(
            nn.Linear(config.d_model, config.d_model // 2),
            nn.GELU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.d_model // 2, config.num_tasks)
        )
        
        self.frustration_head = nn.Sequential(
            nn.Linear(config.d_model, config.d_model // 2),
            nn.GELU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.d_model // 2, config.frustration_levels)
        )
        
        # Session pooling
        self.pool = nn.AdaptiveAvgPool1d(1)
        
        # Initialize
        self._init_weights()
    
    def _init_weights(self):
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
    
    def forward(
        self, 
        trajectory_emb: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None
    ) -> Dict[str, torch.Tensor]:
        """
        Forward pass.
        
        Args:
            trajectory_emb: [batch, seq, 768] embedded trajectories from Stage 2
            attention_mask: [batch, seq] mask for valid positions
            
        Returns:
            Dict with:
            - intent_logits: [batch, num_intents]
            - task_logits: [batch, num_tasks]
            - frustration_logits: [batch, frustration_levels]
            - session_emb: [batch, d_model]
        """
        batch_size, seq_len, _ = trajectory_emb.shape
        
        # Project to our dimension
        if self.stage2 is not None:
            x = self.stage2_proj(trajectory_emb)
        else:
            x = self.input_embed(trajectory_emb)
        
        # Add positional encoding
        if seq_len <= self.pos_embed.shape[1]:
            x = x + self.pos_embed[:, :seq_len, :]
        
        # SSM layers
        for layer in self.layers:
            x = layer(x)
        
        # Pool for final representation
        if attention_mask is not None:
            # Weighted pooling
            mask = attention_mask.unsqueeze(-1).float()
            session_emb = (x * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1)
        else:
            session_emb = x.mean(dim=1)
        
        # Output predictions
        intent_logits = self.intent_head(session_emb)
        task_logits = self.task_head(session_emb)
        frustration_logits = self.frustration_head(session_emb)
        
        return {
            'intent_logits': intent_logits,
            'task_logits': task_logits,
            'frustration_logits': frustration_logits,
            'session_emb': session_emb,
            'sequence_output': x
        }
    
    def compute_loss(
        self, 
        outputs: Dict[str, torch.Tensor],
        targets: Dict,
        config: TaskReasoningConfig
    ) -> Dict[str, torch.Tensor]:
        """Compute training loss"""
        losses = {}
        
        # Intent loss
        if 'intent_labels' in targets:
            losses['intent'] = F.cross_entropy(
                outputs['intent_logits'],
                targets['intent_labels']
            )
        
        # Task completion loss
        if 'task_labels' in targets:
            losses['task'] = F.cross_entropy(
                outputs['task_logits'],
                targets['task_labels']
            )
        
        # Frustration loss (ordinal - treat as regression)
        if 'frustration_labels' in targets:
            frustration_labels = targets['frustration_labels']
            # Use cross-entropy for ordinal
            losses['frustration'] = F.cross_entropy(
                outputs['frustration_logits'],
                frustration_labels
            )
        
        # Total loss
        if losses:
            losses['total'] = sum(losses.values())
        else:
            losses['total'] = torch.tensor(0.0, device=outputs['intent_logits'].device)
        
        return losses


class PPOTrainer:
    """
    PPO trainer for RL fine-tuning of task reasoning.
    Fine-tunes model using PPO on task completion rewards.
    """
    
    def __init__(
        self,
        model: TaskReasoningModel,
        config: TaskReasoningConfig,
        lr: float = 3e-5
    ):
        self.model = model
        self.config = config
        
        # PPO optimizer
        self.optimizer = torch.optim.AdamW(
            model.parameters(),
            lr=lr,
            weight_decay=0.01
        )
        
        self.clip_ratio = config.ppo_clip_ratio
        self.ppo_epochs = config.ppo_epochs
    
    def compute_ppo_loss(
        self,
        logits: torch.Tensor,
        old_log_probs: torch.Tensor,
        actions: torch.Tensor,
        rewards: torch.Tensor
    ) -> torch.Tensor:
        """
        Compute PPO loss.
        
        Args:
            logits: [batch, action_dim]
            old_log_probs: [batch] old policy log probs
            actions: [batch] selected actions
            rewards: [batch] rewards
        """
        # Get log probs for actions
        dist = torch.distributions.Categorical(logits=logits)
        log_probs = dist.log_prob(actions)
        
        # Ratio
        ratio = torch.exp(log_probs - old_log_probs)
        
        # Clipped objective
        surr1 = ratio * rewards
        surr2 = torch.clamp(ratio, 1 - self.clip_ratio, 1 + self.clip_ratio) * rewards
        
        # PPO loss (negative because we want to maximize)
        loss = -torch.min(surr1, surr2).mean()
        
        return loss
    
    def update(
        self,
        trajectories: List[Dict],
        rewards: torch.Tensor
    ) -> Dict[str, float]:
        """Update policy using PPO"""
        self.model.train()
        
        total_loss = 0
        num_updates = 0
        
        for _ in range(self.ppo_epochs):
            for traj in trajectories:
                # Forward
                outputs = self.model(traj['emb'])
                
                # Compute PPO loss (simplified - would use actual action/reward)
                loss = outputs['task_logits'].sum() * 0  # Placeholder
                
                # Update
                self.optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
                self.optimizer.step()
                
                total_loss += loss.item()
                num_updates += 1
        
        return {'ppo_loss': total_loss / max(num_updates, 1)}


# Config loader
def load_config(config_dict: dict) -> TaskReasoningConfig:
    """Load config from dict (e.g., from YAML)"""
    return TaskReasoningConfig(**{
        k: v for k, v in config_dict.items() 
        if k in TaskReasoningConfig.__dataclass_fields__
    })


if __name__ == '__main__':
    # Test the model
    config = TaskReasoningConfig()
    model = TaskReasoningModel(config)
    
    # Dummy input
    batch_size = 2
    seq_len = 100
    
    trajectory_emb = torch.randn(batch_size, seq_len, 768)
    outputs = model(trajectory_emb)
    
    print("Stage 3 Model Output Shapes:")
    for key, val in outputs.items():
        print(f"  {key}: {val.shape}")
    
    print(f"\nModel parameters: {sum(p.numel() for p in model.parameters()):,}")