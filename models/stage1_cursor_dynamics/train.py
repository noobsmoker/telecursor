"""
Training script for Stage 1 Cursor Dynamics Model
"""

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import yaml
import json
import argparse
from pathlib import Path
from tqdm import tqdm
import numpy as np
import logging

from model import CursorDynamicsModel, CursorConfig, CursorTokenizer, CursorDataset

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_config(config_path: str) -> dict:
    """Load configuration from YAML file"""
    with open(config_path) as f:
        return yaml.safe_load(f)


def load_trajectories(data_dir: Path, split: str = 'train'):
    """Load trajectories from JSONL files"""
    trajectories = []
    data_file = data_dir / f'{split}.jsonl'
    
    if not data_file.exists():
        logger.warning(f"Data file not found: {data_file}, using empty dataset")
        return trajectories
    
    with open(data_file) as f:
        for line in f:
            try:
                trajectory = json.loads(line)
                trajectories.append(trajectory)
            except json.JSONDecodeError:
                continue
    
    logger.info(f"Loaded {len(trajectories)} trajectories from {split}")
    return trajectories


def train_epoch(model, dataloader, optimizer, scheduler, config, device, use_checkpoint: bool = False):
    """Train for one epoch"""
    model.train()
    total_loss = 0
    total_position_loss = 0
    total_physics_loss = 0
    
    pbar = tqdm(dataloader, desc="Training")
    for batch_idx, (inputs, targets) in enumerate(pbar):
        inputs = inputs.to(device)
        targets = targets.to(device)
        
        optimizer.zero_grad()
        
        # Forward pass with gradient checkpointing if enabled
        outputs = model(inputs, use_checkpoint=use_checkpoint)
        loss_dict = model.compute_loss(outputs, targets, config)
        
        loss = loss_dict['total']
        loss.backward()
        
        # Gradient clipping
        torch.nn.utils.clip_grad_norm_(
            model.parameters(),
            config.get('gradient_clipping', 1.0)
        )
        
        optimizer.step()
        scheduler.step()
        
        # Logging
        total_loss += loss.item()
        total_position_loss += loss_dict['position'].item()
        total_physics_loss += loss_dict['physics'].item()
        
        pbar.set_postfix({
            'loss': f"{loss.item():.4f}",
            'pos': f"{loss_dict['position'].item():.4f}"
        })
    
    return {
        'loss': total_loss / len(dataloader),
        'position_loss': total_position_loss / len(dataloader),
        'physics_loss': total_physics_loss / len(dataloader)
    }


def validate(model, dataloader, config, device):
    """Validate the model"""
    model.eval()
    total_loss = 0
    total_position_loss = 0
    total_physics_loss = 0
    
    with torch.no_grad():
        for inputs, targets in tqdm(dataloader, desc="Validation"):
            inputs = inputs.to(device)
            targets = targets.to(device)
            
            outputs = model(inputs, use_checkpoint=False)
            loss_dict = model.compute_loss(outputs, targets, config)
            
            total_loss += loss_dict['total'].item()
            total_position_loss += loss_dict['position'].item()
            total_physics_loss += loss_dict['physics'].item()
    
    return {
        'loss': total_loss / len(dataloader),
        'position_loss': total_position_loss / len(dataloader),
        'physics_loss': total_physics_loss / len(dataloader)
    }


def main():
    parser = argparse.ArgumentParser(description='Train Stage 1 Cursor Dynamics Model')
    parser.add_argument('--config', type=str, default='config.yaml',
                        help='Path to config file')
    parser.add_argument('--data-dir', type=str, required=True,
                        help='Path to data directory')
    parser.add_argument('--output-dir', type=str, default='checkpoints',
                        help='Output directory for checkpoints')
    parser.add_argument('--resume', type=str, default=None,
                        help='Resume from checkpoint')
    parser.add_argument('--epochs', type=int, default=10,
                        help='Number of epochs')
    parser.add_argument('--batch-size', type=int, default=32,
                        help='Batch size')
    parser.add_argument('--lr', type=float, default=None,
                        help='Learning rate (overrides config)')
    args = parser.parse_args()
    
    # Load config
    config_dict = load_config(args.config)
    
    # Extract model config
    model_config_dict = config_dict.get('model', {})
    training_config = config_dict.get('training', {})
    
    # Create CursorConfig
    config = CursorConfig(
        d_model=model_config_dict.get('d_model', 768),
        n_layers=model_config_dict.get('n_layers', 12),
        n_heads=model_config_dict.get('n_heads', 12),
        d_ff=model_config_dict.get('d_ff', 3072),
        dropout=model_config_dict.get('dropout', 0.1),
        max_seq_len=model_config_dict.get('max_seq_len', 4096),
        learning_rate=args.lr or training_config.get('lr', 3e-4),
        weight_decay=training_config.get('weight_decay', 0.1),
        gradient_checkpointing=training_config.get('gradient_checkpointing', True),
    )
    
    # Add physics constraints from config
    physics = model_config_dict.get('physics_constraints', {})
    config.max_velocity = physics.get('max_velocity', 5000)
    config.max_acceleration = physics.get('max_acceleration', 50000)
    config.jerk_penalty_weight = physics.get('jerk_penalty_weight', 0.1)
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    logger.info(f"Using device: {device}")
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Model
    model = CursorDynamicsModel(config).to(device)
    logger.info(f"Model parameters: {sum(p.numel() for p in model.parameters()):,}")
    
    # Compile for performance (PyTorch 2.0+)
    if hasattr(torch, 'compile'):
        logger.info("Compiling model with torch.compile()")
        model = torch.compile(model)
    
    # Optimizer
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=config.learning_rate,
        weight_decay=config.weight_decay,
        betas=tuple(training_config.get('betas', [0.9, 0.95])),
        eps=training_config.get('eps', 1e-8)
    )
    
    # Learning rate scheduler
    warmup_steps = training_config.get('warmup_steps', 2000)
    total_steps = training_config.get('stable_steps', 480000) + training_config.get('decay_steps', 20000)
    
    def lr_lambda(step):
        if step < warmup_steps:
            return step / warmup_steps
        elif step < warmup_steps + training_config.get('stable_steps', 480000):
            return 1.0
        else:
            decay_steps = step - warmup_steps - training_config.get('stable_steps', 480000)
            min_lr_ratio = training_config.get('min_lr_ratio', 0.1)
            return max(min_lr_ratio, 1 - decay_steps / training_config.get('decay_steps', 20000))
    
    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)
    
    # Resume from checkpoint
    start_epoch = 0
    if args.resume:
        checkpoint = torch.load(args.resume)
        model.load_state_dict(checkpoint['model_state'])
        optimizer.load_state_dict(checkpoint['optimizer_state'])
        scheduler.load_state_dict(checkpoint['scheduler_state'])
        start_epoch = checkpoint.get('epoch', 0)
        logger.info(f"Resumed from epoch {start_epoch}")
    
    # Data
    train_trajectories = load_trajectories(Path(args.data_dir), 'train')
    val_trajectories = load_trajectories(Path(args.data_dir), 'val')
    
    tokenizer = CursorTokenizer(config)
    sequence_length = training_config.get('sequence_length', 2048)
    
    train_dataset = CursorDataset(train_trajectories, tokenizer, context_length=sequence_length)
    val_dataset = CursorDataset(val_trajectories, tokenizer, context_length=sequence_length)
    
    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=4,
        pin_memory=True
    )
    
    val_loader = DataLoader(
        val_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=4
    )
    
    logger.info(f"Train batches: {len(train_loader)}, Val batches: {len(val_loader)}")
    
    # Training loop
    best_val_loss = float('inf')
    use_checkpoint = config.gradient_checkpointing
    
    for epoch in range(start_epoch, args.epochs):
        logger.info(f"Epoch {epoch + 1}/{args.epochs}")
        
        train_metrics = train_epoch(
            model, train_loader, optimizer, scheduler,
            config, device, use_checkpoint=use_checkpoint
        )
        
        logger.info(f"Train - Loss: {train_metrics['loss']:.4f}, "
                   f"Position: {train_metrics['position_loss']:.4f}, "
                   f"Physics: {train_metrics['physics_loss']:.4f}")
        
        # Validation
        if len(val_loader) > 0:
            val_metrics = validate(model, val_loader, config, device)
            logger.info(f"Val - Loss: {val_metrics['loss']:.4f}, "
                       f"Position: {val_metrics['position_loss']:.4f}, "
                       f"Physics: {val_metrics['physics_loss']:.4f}")
            
            # Save best model
            if val_metrics['loss'] < best_val_loss:
                best_val_loss = val_metrics['loss']
                torch.save({
                    'epoch': epoch,
                    'model_state': model.state_dict(),
                    'config': config_dict,
                    'val_loss': val_metrics['loss']
                }, output_dir / 'best_model.pt')
                logger.info(f"Saved best model with val_loss: {val_metrics['loss']:.4f}")
        
        # Regular checkpoint
        if (epoch + 1) % 5 == 0:
            torch.save({
                'epoch': epoch,
                'model_state': model.state_dict(),
                'optimizer_state': optimizer.state_dict(),
                'scheduler_state': scheduler.state_dict(),
                'config': config_dict
            }, output_dir / f'checkpoint_epoch_{epoch}.pt')
            logger.info(f"Saved checkpoint at epoch {epoch}")
    
    logger.info("Training complete!")
    
    # Save final model
    torch.save({
        'epoch': args.epochs,
        'model_state': model.state_dict(),
        'config': config_dict
    }, output_dir / 'final_model.pt')


if __name__ == '__main__':
    main()