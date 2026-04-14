"""
Stage 2: Semantic Grounding Model

Fuses cursor trajectories with DOM structure to predict:
- Element attention (which elements user is focusing on)
- Click prediction (will user click this element)
- Intent classification (what is user trying to do)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from dataclasses import dataclass
from typing import Optional, Dict, Tuple, List
import math


@dataclass
class GroundingConfig:
    """Configuration for Semantic Grounding Model"""
    # Base model (Stage 1)
    d_model: int = 768
    n_heads: int = 12
    n_layers: int = 12
    
    # DOM encoding
    max_elements: int = 100
    dom_embed_dim: int = 256
    max_dom_depth: int = 20
    
    # Cross-attention
    cross_attn_layers: int = 4
    cross_attn_heads: int = 8
    
    # Output heads
    num_intents: int = 10  # browse, search, form_fill, click, scroll, etc.
    
    # Training
    learning_rate: float = 1e-4
    dropout: float = 0.1
    
    # Fine-tuning
    unfreeze_encoder_step: int = 100000


class DOMEncoder(nn.Module):
    """
    Encode DOM structure into embeddings.
    Creates hierarchical representation of page elements.
    """
    
    def __init__(self, config: GroundingConfig):
        super().__init__()
        self.config = config
        
        # Tag embeddings (div, button, input, etc.)
        self.tag_embed = nn.Embedding(50, config.dom_embed_dim)
        
        # Role embeddings (link, form, navigation, etc.)
        self.role_embed = nn.Embedding(20, config.dom_embed_dim)
        
        # Position encoding for elements
        self.pos_embed = nn.Parameter(torch.randn(1, config.max_elements, config.dom_embed_dim) * 0.02)
        
        # Element feature projection
        self.feature_proj = nn.Linear(config.dom_embed_dim * 3, config.d_model)
        
        self.dropout = nn.Dropout(config.dropout)
    
    def forward(self, dom_features: Dict) -> torch.Tensor:
        """
        Encode DOM features.
        
        Args:
            dom_features: Dict with keys:
                - tag_ids: [batch, num_elements] tag type IDs
                - role_ids: [batch, num_elements] role IDs  
                - bbox: [batch, num_elements, 4] bounding boxes
                - depth: [batch, num_elements] tree depth
                
        Returns:
            DOM embeddings: [batch, num_elements, d_model]
        """
        batch_size = dom_features['tag_ids'].shape[0]
        num_elements = dom_features['tag_ids'].shape[1]
        
        # Embed tags and roles
        tag_emb = self.tag_embed(dom_features['tag_ids'])  # [B, N, D]
        role_emb = self.role_embed(dom_features['role_ids'])  # [B, N, D]
        
        # Position features from bounding boxes
        bbox = dom_features['bbox']  # [B, N, 4] (x, y, w, h)
        # Normalize and encode positions
        bbox_norm = bbox / bbox.max() if bbox.max() > 0 else bbox
        pos_features = self._encode_bbox(bbox_norm)  # [B, N, D]
        
        # Depth encoding (as positional encoding)
        depth = dom_features['depth']  # [B, N]
        depth_emb = self._encode_depth(depth, self.config.dom_embed_dim)  # [B, N, D]
        
        # Combine all features
        combined = torch.cat([tag_emb, role_emb, pos_features, depth_emb], dim=-1)
        
        # Project to d_model
        dom_emb = self.feature_proj(combined)
        
        # Add positional embeddings
        if num_elements <= self.config.max_elements:
            dom_emb = dom_emb + self.pos_embed[:, :num_elements, :]
        
        return self.dropout(dom_emb)
    
    def _encode_bbox(self, bbox: torch.Tensor) -> torch.Tensor:
        """Encode bounding box as feature vector"""
        # Simple encoding: center x, center y, width, height
        x = bbox[..., 0:1]
        y = bbox[..., 1:2]
        w = bbox[..., 2:3]
        h = bbox[..., 3:4]
        
        # Encode as sinusoidal
        d = self.config.dom_embed_dim
        dim = d // 4
        
        # Use simple MLP instead of complex positional encoding
        return torch.cat([
            torch.tanh(x * 2),
            torch.tanh(y * 2),
            torch.tanh(w),
            torch.tanh(h)
        ], dim=-1).expand(-1, -1, -1, 4).reshape(bbox.shape[0], bbox.shape[1], d)
    
    def _encode_depth(self, depth: torch.Tensor, dim: int) -> torch.Tensor:
        """Encode tree depth"""
        depth_norm = depth.float() / self.config.max_dom_depth
        return depth_norm.unsqueeze(-1).expand(-1, -1, dim) * 0.1


class CrossAttentionLayer(nn.Module):
    """
    Cross-attention between cursor trajectory and DOM elements.
    Allows model to learn which elements the cursor is attending to.
    """
    
    def __init__(self, config: GroundingConfig):
        super().__init__()
        self.config = config
        
        # Query from cursor (Stage 1 output)
        self.cursor_proj = nn.Linear(config.d_model, config.d_model)
        
        # Key/Value from DOM
        self.dom_proj = nn.Linear(config.d_model, config.d_model)
        
        # Multi-head cross-attention
        self.attn = nn.MultiheadAttention(
            config.d_model, 
            config.cross_attn_heads,
            dropout=config.dropout,
            batch_first=True
        )
        
        # Feed-forward
        self.ff = nn.Sequential(
            nn.Linear(config.d_model, config.d_model * 4),
            nn.GELU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.d_model * 4, config.d_model)
        )
        
        self.norm1 = nn.LayerNorm(config.d_model)
        self.norm2 = nn.LayerNorm(config.d_model)
    
    def forward(
        self, 
        cursor_emb: torch.Tensor, 
        dom_emb: torch.Tensor,
        cursor_mask: Optional[torch.Tensor] = None,
        dom_mask: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Cross-attention forward.
        
        Args:
            cursor_emb: [batch, cursor_seq, d_model]
            dom_emb: [batch, num_elements, d_model]
            cursor_mask: [batch, cursor_seq]
            dom_mask: [batch, num_elements]
            
        Returns:
            cursor_out: [batch, cursor_seq, d_model]
            dom_out: [batch, num_elements, d_model]
        """
        # Project for attention
        q = self.cursor_proj(cursor_emb)
        k = self.dom_proj(dom_emb)
        v = self.dom_proj(dom_emb)
        
        # Cross-attention: cursor queries DOM
        attn_out, _ = self.attn(
            q, k, v,
            key_padding_mask=dom_mask,
            need_weights=False
        )
        
        # Residual and norm
        cursor_out = self.norm1(cursor_emb + attn_out)
        
        # Feed-forward on both
        ff_out = self.ff(cursor_out)
        cursor_out = self.norm2(cursor_out + ff_out)
        
        # Also update DOM from cursor perspective
        q_dom = self.cursor_proj(dom_emb)
        k_cursor = self.cursor_proj(cursor_emb)
        v_cursor = self.cursor_proj(cursor_emb)
        
        attn_dom, _ = self.attn(
            q_dom, k_cursor, v_cursor,
            key_padding_mask=cursor_mask,
            need_weights=False
        )
        
        dom_out = self.norm1(dom_emb + attn_dom)
        ff_dom = self.ff(dom_out)
        dom_out = self.norm2(dom_out + ff_dom)
        
        return cursor_out, dom_out


class ElementAttentionHead(nn.Module):
    """Predict which DOM elements the cursor is attending to"""
    
    def __init__(self, config: GroundingConfig):
        super().__init__()
        self.d_model = config.d_model
        self.num_elements = config.max_elements
        
        self.attention = nn.Linear(config.d_model, 1)
    
    def forward(
        self, 
        cursor_emb: torch.Tensor, 
        dom_emb: torch.Tensor
    ) -> torch.Tensor:
        """
        Compute element attention scores.
        
        Args:
            cursor_emb: [batch, seq, d_model]
            dom_emb: [batch, num_elements, d_model]
            
        Returns:
            attention: [batch, num_elements]
        """
        # Compute similarity between cursor states and DOM elements
        # Take mean of cursor sequence
        cursor_mean = cursor_emb.mean(dim=1)  # [batch, d_model]
        
        # Dot product with each element
        scores = torch.einsum('bd,bn->bn', cursor_mean, dom_emb.mean(dim=1))
        
        return scores


class ClickPredictionHead(nn.Module):
    """Predict whether user will click on an element"""
    
    def __init__(self, config: GroundingConfig):
        super().__init__()
        
        self.predictor = nn.Sequential(
            nn.Linear(config.d_model * 2, config.d_model),
            nn.GELU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.d_model, 1)
        )
    
    def forward(
        self, 
        cursor_state: torch.Tensor, 
        element_emb: torch.Tensor
    ) -> torch.Tensor:
        """
        Predict click probability for each element.
        
        Args:
            cursor_state: [batch, d_model] current cursor state
            element_emb: [batch, num_elements, d_model]
            
        Returns:
            click_probs: [batch, num_elements]
        """
        # Expand cursor state
        cursor_expanded = cursor_state.unsqueeze(1).expand(-1, element_emb.shape[1], -1)
        
        # Concatenate
        combined = torch.cat([cursor_expanded, element_emb], dim=-1)
        
        # Predict
        logits = self.predictor(combined).squeeze(-1)
        
        return torch.sigmoid(logits)


class IntentClassifier(nn.Module):
    """Classify user intent from trajectory + DOM context"""
    
    def __init__(self, config: GroundingConfig):
        super().__init__()
        
        self.classifier = nn.Sequential(
            nn.Linear(config.d_model, config.d_model // 2),
            nn.GELU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.d_model // 2, config.num_intents)
        )
    
    def forward(self, trajectory_emb: torch.Tensor) -> torch.Tensor:
        """
        Classify intent from trajectory embedding.
        
        Args:
            trajectory_emb: [batch, d_model]
            
        Returns:
            logits: [batch, num_intents]
        """
        return self.classifier(trajectory_emb)


class SemanticGroundingModel(nn.Module):
    """
    Stage 2: Semantic Grounding Model
    
    Combines:
    - Stage 1 cursor dynamics encoder (frozen, loaded from checkpoint)
    - DOM encoder for page structure
    - Cross-attention for grounding
    - Output heads for element attention, click prediction, intent
    """
    
    def __init__(self, config: GroundingConfig, stage1_model=None):
        super().__init__()
        self.config = config
        
        # Stage 1 encoder (can be frozen)
        if stage1_model is not None:
            self.stage1 = stage1_model
            self.stage1.eval()
            # We'll use the Stage 1 model as feature extractor
            self.stage1_frozen = True
        else:
            # Create a simple encoder if no Stage 1 provided
            from models.stage1_cursor_dynamics.model import CursorDynamicsModel
            self.stage1 = CursorDynamicsModel(CursorConfig())
            self.stage1_frozen = False
        
        # Project Stage 1 output to config dimensions
        self.stage1_proj = nn.Linear(768, config.d_model)
        
        # DOM encoder
        self.dom_encoder = DOMEncoder(config)
        
        # Cross-attention layers
        self.cross_attn_layers = nn.ModuleList([
            CrossAttentionLayer(config) for _ in range(config.cross_attn_layers)
        ])
        
        # Output heads
        self.element_attention = ElementAttentionHead(config)
        self.click_prediction = ClickPredictionHead(config)
        self.intent_classifier = IntentClassifier(config)
        
        # Pooling for final trajectory representation
        self.pool = nn.AdaptiveAvgPool1d(1)
    
    def forward(
        self, 
        cursor_tokens: torch.Tensor,
        dom_features: Dict,
        element_masks: Optional[torch.Tensor] = None
    ) -> Dict[str, torch.Tensor]:
        """
        Forward pass.
        
        Args:
            cursor_tokens: [batch, seq, 11] tokenized cursor trajectory
            dom_features: Dict with DOM element features
            element_masks: [batch, num_elements] mask for valid elements
            
        Returns:
            Dict with:
            - element_attention: [batch, num_elements]
            - click_probs: [batch, num_elements]  
            - intent_logits: [batch, num_intents]
            - trajectory_emb: [batch, d_model]
        """
        batch_size = cursor_tokens.shape[0]
        
        # Get Stage 1 embeddings
        with torch.no_grad() if self.stage1_frozen else torch.enable_grad():
            stage1_output = self.stage1.forward(cursor_tokens, use_checkpoint=False)
            # Use position logits as embeddings (mean pooled)
            cursor_emb = self.stage1_proj(stage1_output.get('x_logits', stage1_output.get('physics_pred', torch.zeros(batch_size, cursor_tokens.shape[1], 768))))
            # Actually, let's use a simpler approach - embed the tokens directly
            cursor_emb = self.stage1_proj(cursor_tokens.float().mean(dim=-1))
        
        # Encode DOM
        dom_emb = self.dom_encoder(dom_features)  # [B, N, D]
        
        # Cross-attention
        for layer in self.cross_attn_layers:
            cursor_emb, dom_emb = layer(cursor_emb, dom_emb)
        
        # Pool trajectory for final representation
        trajectory_emb = cursor_emb.mean(dim=1)  # [B, D]
        
        # Output predictions
        element_attn = self.element_attention(cursor_emb, dom_emb)
        
        click_probs = self.click_prediction(
            trajectory_emb.unsqueeze(1).expand(-1, dom_emb.shape[1], -1),
            dom_emb
        )
        
        intent_logits = self.intent_classifier(trajectory_emb)
        
        return {
            'element_attention': element_attn,
            'click_probs': click_probs,
            'intent_logits': intent_logits,
            'trajectory_emb': trajectory_emb,
            'dom_emb': dom_emb
        }
    
    def compute_loss(
        self, 
        outputs: Dict, 
        targets: Dict,
        config: GroundingConfig
    ) -> Dict[str, torch.Tensor]:
        """
        Compute training loss.
        
        Args:
            outputs: model outputs
            targets: Dict with:
                - element_labels: [batch, num_elements] which elements cursor attended
                - click_labels: [batch, num_elements] which elements were clicked
                - intent_labels: [batch] intent class
                
        Returns:
            Dict with losses
        """
        losses = {}
        
        # Element attention loss (binary classification per element)
        if 'element_labels' in targets:
            element_labels = targets['element_labels']
            element_loss = F.binary_cross_entropy_with_logits(
                outputs['element_attention'],
                element_labels.float(),
                reduction='mean'
            )
            losses['element_attention'] = element_loss
        
        # Click prediction loss
        if 'click_labels' in targets:
            click_loss = F.binary_cross_entropy_with_logits(
                outputs['click_probs'],
                targets['click_labels'].float(),
                reduction='mean'
            )
            losses['click'] = click_loss
        
        # Intent classification loss
        if 'intent_labels' in targets:
            intent_loss = F.cross_entropy(
                outputs['intent_logits'],
                targets['intent_labels']
            )
            losses['intent'] = intent_loss
        
        # Total loss
        if losses:
            losses['total'] = sum(losses.values())
        else:
            losses['total'] = torch.tensor(0.0, device=outputs['intent_logits'].device)
        
        return losses


# Helper to create config from dict (for YAML loading)
def load_config(config_dict: dict) -> GroundingConfig:
    """Load config from dict (e.g., from YAML)"""
    return GroundingConfig(**{k: v for k, v in config_dict.items() if k in GroundingConfig.__dataclass_fields__})


if __name__ == '__main__':
    # Test the model
    config = GroundingConfig()
    model = SemanticGroundingModel(config)
    
    # Dummy inputs
    batch_size = 2
    seq_len = 100
    num_elements = 50
    
    cursor_tokens = torch.randint(0, 100, (batch_size, seq_len, 11))
    dom_features = {
        'tag_ids': torch.randint(0, 20, (batch_size, num_elements)),
        'role_ids': torch.randint(0, 10, (batch_size, num_elements)),
        'bbox': torch.rand(batch_size, num_elements, 4),
        'depth': torch.randint(0, 10, (batch_size, num_elements))
    }
    
    outputs = model(cursor_tokens, dom_features)
    
    print("Stage 2 Model Output Shapes:")
    for key, val in outputs.items():
        print(f"  {key}: {val.shape}")
    
    print(f"\nModel parameters: {sum(p.numel() for p in model.parameters()):,}")