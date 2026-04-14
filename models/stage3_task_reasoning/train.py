"""
Stage 3: Task Reasoning Training Pipeline

Training script for Task Reasoning Model with:
- Mamba-style SSM architecture
- Multi-task learning (intent, task, frustration)
- PPO fine-tuning for task completion
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

from model import TaskReasoningModel, TaskReasoningConfig, PPOTrainer, load_config


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TaskReasoningDataset(Dataset):
    """
    Dataset for task reasoning training.
    Contains session-level trajectories with task labels.
    """
    
    def __init__(self, data_path: str, max_seq_len: int = 5000):
        self.data_path = data_path
        self.max_seq_len = max_seq_len
        self.data = self._load_data(data_path)
    
    def _load_data(self, path: str) -> List[Dict]:
        """Load training data"""
        if not Path(path).exists():
            logger.warning(f"Data file not found: {path}, using dummy data")
            return self._create_dummy_data(50)
        
        with open(path, 'r') as f:
            return json.load(f)
    
    def _create_dummy_data(self, size: int) -> List[Dict]:
        """Create dummy data for testing"""
        return [{
            'trajectory_emb': np.random.randn(500, 768).tolist(),  # 500 time steps
            'intent_label': np.random.randint(0, 10),
            'task_label': np.random.randint(0, 20),
            'frustration_label': np.random.randint(0, 3)
        } for _ in range(size)]
    
    def __len__(self):
        return len(self.data)
    
    def __getitem__(self, idx):
        item = self.data[idx]
        
        # Trajectory embedding
        trajectory_emb = torch.tensor(item['trajectory_emb'], dtype=torch.float32)
        
        # Truncate
        if trajectory_emb.shape[0] > self.max_seq_len:
            trajectory_emb = trajectory_emb[:self.max_seq_len]
        
        # Padding mask
        mask = torch.ones(trajectory_emb.shape[0], dtype=torch.float)
        
        # Labels
        intent_label = torch.tensor(item['intent_label'], dtype=torch.long)
        task_label = torch.tensor(item['task_label'], dtype=torch.long)
        frustration_label = torch.tensor(item['frustration_label'], dtype=torch.long)
        
        return {
            'trajectory_emb': trajectory_emb,
            'attention_mask': mask,
            'intent_labels': intent_label,
            'task_labels': task_label,
            'frustration_labels': frustration_label
        }


def train_epoch(
    model: TaskReasoningModel,
    dataloader: DataLoader,
    optimizer: torch.optim.Optimizer,
    scheduler: Optional[OneCycleLR],
    config: TaskReasoningConfig,
    device: str = 'cuda',
    step: int = 0
) -> Dict[str, float]:
    """Train for one epoch"""
    model.train()
    
    total_loss = 0
    losses = {'total': 0, 'intent': 0, 'task': 0, 'frustration': 0}
    num_batches = 0
    
    for batch in tqdm(dataloader, desc="Training"):
        # Move to device
        trajectory_emb = batch['trajectory_emb'].to(device)
        attention_mask = batch['attention_mask'].to(device) if 'attention_mask' in batch else None
        intent_labels = batch['intent_labels'].to(device)
        task_labels = batch['task_labels'].to(device)
        frustration_labels = batch['frustration_labels'].to(device)
        
        # Forward pass
        outputs = model(trajectory_emb, attention_mask)
        
        # Compute loss
        targets = {
            'intent_labels': intent_labels,
            'task_labels': task_labels,
            'frustration_labels': frustration_labels
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
        
        # Accumulate
        for k, v in batch_losses.items():
            losses[k] += v.item()
        total_loss += batch_losses['total'].item()
        num_batches += 1
        step += 1
    
    for k in losses:
        losses[k] /= num_batches
    
    return losses, step


def validate(
    model: TaskReasoningModel,
    dataloader: DataLoader,
    config: TaskReasoningConfig,
    device: str = 'cuda'
) -> Dict[str, float]:
    """Validate the model"""
    model.eval()
    
    total_loss = 0
    num_batches = 0
    
    with torch.no_grad():
        for batch in dataloader:
            trajectory_emb = batch['trajectory_emb'].to(device)
            attention_mask = batch.get('attention_mask', None)
            if attention_mask is not None:
                attention_mask = attention_mask.to(device)
            
            intent_labels = batch['intent_labels'].to(device)
            task_labels = batch['task_labels'].to(device)
            frustration_labels = batch['frustration_labels'].to(device)
            
            outputs = model(trajectory_emb, attention_mask)
            
            targets = {
                'intent_labels': intent_labels,
                'task_labels': task_labels,
                'frustration_labels': frustration_labels
            }
            batch_losses = model.compute_loss(outputs, targets, config)
            
            total_loss += batch_losses['total'].item()
            num_batches += 1
    
    return {'val_loss': total_loss / num_batches}


def save_checkpoint(
    model: nn.Module,
    optimizer: torch.optim.Optimizer,
    step: int,
    config: TaskReasoningConfig,
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
    
    path = Path(checkpoint_dir) / f'checkpoint-{step:08d}.pt'
    torch.save(checkpoint, path)
    logger.info(f"Saved checkpoint to {path}")
    
    # Keep only last 3
    checkpoints = sorted(Path(checkpoint_dir).glob('checkpoint-*.pt'))
    for old_ckpt in checkpoints[:-3]:
        old_ckpt.unlink()


def load_checkpoint(model: nn.Module, checkpoint_path: str, device: str = 'cuda') -> int:
    """Load checkpoint"""
    if not Path(checkpoint_path).exists():
        return 0
    
    checkpoint = torch.load(checkpoint_path, map_location=device)
    model.load_state_dict(checkpoint['model_state_dict'])
    return checkpoint.get('step', 0)


def main():
    """Main training entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Train Stage 3 Task Reasoning Model')
    parser.add_argument('--config', type=str, default='config.yaml')
    parser.add_argument('--data', type=str, default='data/train.json')
    parser.add_argument('--val-data', type=str, default='data/val.json')
    parser.add_argument('--batch-size', type=int, default=4)  # Smaller due to long sequences
    parser.add_argument('--epochs', type=int, default=10)
    parser.add_argument('--lr', type=float, default=3e-5)
    parser.add_argument('--device', type=str, default='cuda' if torch.cuda.is_available() else 'cpu')
    parser.add_argument('--checkpoint-dir', type=str, default='checkpoints')
    parser.add_argument('--resume', type=str, default=None)
    parser.add_argument('--use-ppo', action='store_true', help='Use PPO fine-tuning')
    
    args = parser.parse_args()
    
    # Load config
    if Path(args.config).exists():
        with open(args.config, 'r') as f:
            config_dict = yaml.safe_load(f)
        config = load_config(config_dict)
    else:
        config = TaskReasoningConfig()
    
    config.learning_rate = args.lr
    
    logger.info(f"Training config: {config}")
    
    # Create model
    model = TaskReasoningModel(config)
    model = model.to(args.device)
    
    # Create datasets
    train_dataset = TaskReasoningDataset(args.data)
    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=2
    )
    
    val_loader = None
    if Path(args.val_data).exists():
        val_dataset = TaskReasoningDataset(args.val_data)
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
    
    # PPO trainer (optional)
    ppo_trainer = None
    if args.use_ppo:
        ppo_trainer = PPOTrainer(model, config, args.lr)
    
    # Resume
    step = 0
    if args.resume:
        step = load_checkpoint(model, args.resume, args.device)
    
    # Training loop
    best_val_loss = float('inf')
    
    for epoch in range(args.epochs):
        logger.info(f"Epoch {epoch + 1}/{args.epochs}")
        
        train_losses, step = train_epoch(
            model, train_loader, optimizer, scheduler, config, args.device, step
        )
        
        logger.info(f"Train losses: {train_losses}")
        
        if val_loader:
            val_losses = validate(model, val_loader, config, args.device)
            logger.info(f"Val losses: {val_losses}")
            
            if val_losses['val_loss'] < best_val_loss:
                best_val_loss = val_losses['val_loss']
                save_checkpoint(model, optimizer, step, config, args.checkpoint_dir)
    
    logger.info("Training complete!")
    
    # Save final
    final_path = Path(args.checkpoint_dir) / 'final_model.pt'
    torch.save({
        'model_state_dict': model.state_dict(),
        'config': config.__dict__
    }, final_path)
    logger.info(f"Saved final model to {final_path}")


if __name__ == '__main__':
    main()