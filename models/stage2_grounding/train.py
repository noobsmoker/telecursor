"""
Stage 2: Semantic Grounding Training Pipeline

Training script for the Semantic Grounding Model with:
- Cross-attention between cursor and DOM
- Element attention, click prediction, intent classification heads
- Progressive unfreezing of Stage 1 encoder
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torch.optim.lr_scheduler import OneCycleLR
import yaml
import json
from pathlib import Path
from typing import Dict, Optional, List
import numpy as np
from tqdm import tqdm
import logging

from model import SemanticGroundingModel, GroundingConfig, load_config


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GroundingDataset(Dataset):
    """
    Dataset for semantic grounding training.
    Contains cursor trajectories with DOM context and labels.
    """
    
    def __init__(
        self, 
        data_path: str,
        max_seq_len: int = 2048,
        max_elements: int = 100
    ):
        self.data_path = data_path
        self.max_seq_len = max_seq_len
        self.max_elements = max_elements
        
        # Load data
        self.data = self._load_data(data_path)
    
    def _load_data(self, path: str) -> List[Dict]:
        """Load training data from JSON file"""
        if not Path(path).exists():
            logger.warning(f"Data file not found: {path}, using dummy data")
            return self._create_dummy_data(100)
        
        with open(path, 'r') as f:
            return json.load(f)
    
    def _create_dummy_data(self, size: int) -> List[Dict]:
        """Create dummy data for testing"""
        return [{
            'cursor_tokens': np.random.randint(0, 100, (100, 11)).tolist(),
            'dom_features': {
                'tag_ids': np.random.randint(0, 20, (50,)).tolist(),
                'role_ids': np.random.randint(0, 10, (50,)).tolist(),
                'bbox': np.random.rand(50, 4).tolist(),
                'depth': np.random.randint(0, 10, (50,)).tolist()
            },
            'element_labels': np.random.randint(0, 2, (50,)).tolist(),
            'click_labels': np.random.randint(0, 2, (50,)).tolist(),
            'intent_labels': np.random.randint(0, 10)
        } for _ in range(size)]
    
    def __len__(self):
        return len(self.data)
    
    def __getitem__(self, idx):
        item = self.data[idx]
        
        # Parse cursor tokens
        cursor_tokens = torch.tensor(item['cursor_tokens'], dtype=torch.long)
        
        # Pad or truncate
        if cursor_tokens.shape[0] > self.max_seq_len:
            cursor_tokens = cursor_tokens[:self.max_seq_len]
        elif cursor_tokens.shape[0] < self.max_seq_len:
            padding = torch.zeros(self.max_seq_len - cursor_tokens.shape[0], 11, dtype=torch.long)
            cursor_tokens = torch.cat([padding, cursor_tokens], dim=0)
        
        # Parse DOM features
        dom_features = {
            'tag_ids': torch.tensor(item['dom_features']['tag_ids'][:self.max_elements], dtype=torch.long),
            'role_ids': torch.tensor(item['dom_features']['role_ids'][:self.max_elements], dtype=torch.long),
            'bbox': torch.tensor(item['dom_features']['bbox'][:self.max_elements], dtype=torch.float),
            'depth': torch.tensor(item['dom_features']['depth'][:self.max_elements], dtype=torch.long)
        }
        
        # Pad DOM features
        num_elements = dom_features['tag_ids'].shape[0]
        if num_elements < self.max_elements:
            pad_size = self.max_elements - num_elements
            for key in dom_features:
                if key == 'bbox':
                    pad = torch.zeros(pad_size, 4)
                else:
                    pad = torch.zeros(pad_size, dtype=torch.long)
                dom_features[key] = torch.cat([dom_features[key], pad], dim=0)
        
        # Labels
        element_labels = torch.tensor(item['element_labels'][:self.max_elements], dtype=torch.float)
        click_labels = torch.tensor(item['click_labels'][:self.max_elements], dtype=torch.float)
        intent_label = torch.tensor(item['intent_labels'], dtype=torch.long)
        
        # Pad labels
        if element_labels.shape[0] < self.max_elements:
            pad = torch.zeros(self.max_elements - element_labels.shape[0], dtype=torch.float)
            element_labels = torch.cat([element_labels, pad], dim=0)
            click_labels = torch.cat([click_labels, pad], dim=0)
        
        return {
            'cursor_tokens': cursor_tokens,
            'dom_features': dom_features,
            'element_labels': element_labels,
            'click_labels': click_labels,
            'intent_labels': intent_label
        }


def train_epoch(
    model: SemanticGroundingModel,
    dataloader: DataLoader,
    optimizer: torch.optim.Optimizer,
    scheduler: Optional[OneCycleLR],
    config: GroundingConfig,
    device: str = 'cuda',
    step: int = 0
) -> Dict[str, float]:
    """Train for one epoch"""
    model.train()
    
    total_loss = 0
    losses = {
        'total': 0,
        'element_attention': 0,
        'click': 0,
        'intent': 0
    }
    num_batches = 0
    
    for batch in tqdm(dataloader, desc="Training"):
        # Move to device
        cursor_tokens = batch['cursor_tokens'].to(device)
        dom_features = {k: v.to(device) for k, v in batch['dom_features'].items()}
        element_labels = batch['element_labels'].to(device)
        click_labels = batch['click_labels'].to(device)
        intent_labels = batch['intent_labels'].to(device)
        
        # Forward pass
        outputs = model(cursor_tokens, dom_features)
        
        # Compute loss
        targets = {
            'element_labels': element_labels,
            'click_labels': click_labels,
            'intent_labels': intent_labels
        }
        batch_losses = model.compute_loss(outputs, targets, config)
        
        # Backward
        optimizer.zero_grad()
        batch_losses['total'].backward()
        
        # Gradient clipping
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        
        optimizer.step()
        if scheduler:
            scheduler.step()
        
        # Accumulate losses
        for k, v in batch_losses.items():
            losses[k] += v.item()
        total_loss += batch_losses['total'].item()
        num_batches += 1
        
        step += 1
        
        # Check for encoder unfreezing
        if step >= config.unfreeze_encoder_step and model.stage1_frozen:
            logger.info(f"Unfreezing Stage 1 encoder at step {step}")
            model.stage1.requires_grad_(True)
            model.stage1_frozen = False
    
    # Average losses
    for k in losses:
        losses[k] /= num_batches
    
    return losses, step


def validate(
    model: SemanticGroundingModel,
    dataloader: DataLoader,
    config: GroundingConfig,
    device: str = 'cuda'
) -> Dict[str, float]:
    """Validate the model"""
    model.eval()
    
    total_loss = 0
    num_batches = 0
    
    with torch.no_grad():
        for batch in dataloader:
            cursor_tokens = batch['cursor_tokens'].to(device)
            dom_features = {k: v.to(device) for k, v in batch['dom_features'].items()}
            element_labels = batch['element_labels'].to(device)
            click_labels = batch['click_labels'].to(device)
            intent_labels = batch['intent_labels'].to(device)
            
            outputs = model(cursor_tokens, dom_features)
            
            targets = {
                'element_labels': element_labels,
                'click_labels': click_labels,
                'intent_labels': intent_labels
            }
            batch_losses = model.compute_loss(outputs, targets, config)
            
            total_loss += batch_losses['total'].item()
            num_batches += 1
    
    return {'val_loss': total_loss / num_batches}


def load_checkpoint(model: nn.Module, checkpoint_path: str, device: str = 'cuda') -> int:
    """Load model checkpoint"""
    if not Path(checkpoint_path).exists():
        logger.info(f"No checkpoint found at {checkpoint_path}")
        return 0
    
    checkpoint = torch.load(checkpoint_path, map_location=device)
    model.load_state_dict(checkpoint['model_state_dict'])
    logger.info(f"Loaded checkpoint from {checkpoint_path}")
    
    return checkpoint.get('step', 0)


def save_checkpoint(
    model: nn.Module,
    optimizer: torch.optim.Optimizer,
    scheduler: Optional[OneCycleLR],
    step: int,
    config: GroundingConfig,
    checkpoint_dir: str
):
    """Save model checkpoint"""
    Path(checkpoint_dir).mkdir(parents=True, exist_ok=True)
    
    checkpoint = {
        'step': step,
        'model_state_dict': model.state_dict(),
        'optimizer_state_dict': optimizer.state_dict(),
        'config': config.__dict__
    }
    if scheduler:
        checkpoint['scheduler_state_dict'] = scheduler.state_dict()
    
    path = Path(checkpoint_dir) / f'checkpoint-{step:08d}.pt'
    torch.save(checkpoint, path)
    logger.info(f"Saved checkpoint to {path}")
    
    # Keep only last 3 checkpoints
    checkpoints = sorted(Path(checkpoint_dir).glob('checkpoint-*.pt'))
    for old_ckpt in checkpoints[:-3]:
        old_ckpt.unlink()


def main():
    """Main training entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Train Stage 2 Semantic Grounding Model')
    parser.add_argument('--config', type=str, default='config.yaml', help='Path to config file')
    parser.add_argument('--data', type=str, default='data/train.json', help='Path to training data')
    parser.add_argument('--val-data', type=str, default='data/val.json', help='Path to validation data')
    parser.add_argument('--batch-size', type=int, default=16, help='Batch size')
    parser.add_argument('--epochs', type=int, default=10, help='Number of epochs')
    parser.add_argument('--lr', type=float, default=1e-4, help='Learning rate')
    parser.add_argument('--device', type=str, default='cuda' if torch.cuda.is_available() else 'cpu')
    parser.add_argument('--checkpoint-dir', type=str, default='checkpoints')
    parser.add_argument('--resume', type=str, default=None, help='Resume from checkpoint')
    
    args = parser.parse_args()
    
    # Load config
    if Path(args.config).exists():
        with open(args.config, 'r') as f:
            config_dict = yaml.safe_load(f)
        config = load_config(config_dict)
    else:
        config = GroundingConfig()
    
    # Override with command line args
    config.learning_rate = args.lr
    
    logger.info(f"Training config: {config}")
    
    # Create model
    model = SemanticGroundingModel(config)
    model = model.to(args.device)
    
    # Freeze Stage 1 initially
    for param in model.stage1.parameters():
        param.requires_grad = False
    model.stage1_frozen = True
    
    # Create datasets
    train_dataset = GroundingDataset(args.data)
    train_loader = DataLoader(
        train_dataset, 
        batch_size=args.batch_size, 
        shuffle=True,
        num_workers=4
    )
    
    val_loader = None
    if Path(args.val_data).exists():
        val_dataset = GroundingDataset(args.val_data)
        val_loader = DataLoader(val_dataset, batch_size=args.batch_size)
    
    # Optimizer
    optimizer = optim.AdamW(
        model.parameters(),
        lr=config.learning_rate,
        weight_decay=0.01
    )
    
    # Scheduler
    total_steps = len(train_loader) * args.epochs
    scheduler = OneCycleLR(
        optimizer,
        max_lr=config.learning_rate,
        total_steps=total_steps
    )
    
    # Resume if needed
    step = 0
    if args.resume:
        step = load_checkpoint(model, args.resume, args.device)
    
    # Training loop
    best_val_loss = float('inf')
    
    for epoch in range(args.epochs):
        logger.info(f"Epoch {epoch + 1}/{args.epochs}")
        
        # Train
        train_losses, step = train_epoch(
            model, train_loader, optimizer, scheduler, config, args.device, step
        )
        
        logger.info(f"Train losses: {train_losses}")
        
        # Validate
        if val_loader:
            val_losses = validate(model, val_loader, config, args.device)
            logger.info(f"Val losses: {val_losses}")
            
            if val_losses['val_loss'] < best_val_loss:
                best_val_loss = val_losses['val_loss']
                save_checkpoint(model, optimizer, scheduler, step, config, args.checkpoint_dir)
        
        # Save periodic checkpoint
        if (epoch + 1) % 5 == 0:
            save_checkpoint(model, optimizer, scheduler, step, config, args.checkpoint_dir)
    
    logger.info("Training complete!")
    
    # Save final model
    final_path = Path(args.checkpoint_dir) / 'final_model.pt'
    torch.save({
        'model_state_dict': model.state_dict(),
        'config': config.__dict__
    }, final_path)
    logger.info(f"Saved final model to {final_path}")


if __name__ == '__main__':
    main()