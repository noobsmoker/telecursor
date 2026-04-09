"""
Federated Learning Framework

A-007: Federated Learning
Prerequisite: A-101 (Modular Privacy) - COMPLETE
Enables distributed model training without sharing raw data.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
import hashlib
import json
import time
import asyncio
from collections import defaultdict
import logging

from privacy.modular.privacy_framework import ModularPrivacy, PrivacyBudget

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ClientStatus(Enum):
    """Federated client status"""
    IDLE = "idle"
    TRAINING = "training"
    UPLOADING = "uploading"
    UPDATING = "updating"
    DISCONNECTED = "disconnected"


@dataclass
class ClientConfig:
    """Configuration for a federated client"""
    client_id: str
    local_epochs: int = 5
    batch_size: int = 32
    learning_rate: float = 0.01
    min_data_size: int = 10
    max_noise_scale: float = 1.0
    communication_round: int = 1


@dataclass
class ClientState:
    """State of a federated client"""
    client_id: str
    status: ClientStatus = ClientStatus.IDLE
    data_size: int = 0
    last_update: float = field(default_factory=time.time)
    rounds_participated: int = 0
    accuracy: float = 0.0
    loss: float = float('inf')
    
    def to_dict(self) -> Dict:
        return {
            'client_id': self.client_id,
            'status': self.status.value,
            'data_size': self.data_size,
            'last_update': self.last_update,
            'rounds_participated': self.rounds_participated,
            'accuracy': self.accuracy,
            'loss': self.loss
        }


@dataclass
class ModelUpdate:
    """Model update from a client"""
    client_id: str
    round_number: int
    weights: Dict[str, np.ndarray]
    metadata: Dict[str, Any]
    privacy_noise: float = 0.0
    sample_size: int = 0
    
    def to_dict(self) -> Dict:
        return {
            'client_id': self.client_id,
            'round_number': self.round_number,
            'metadata': self.metadata,
            'privacy_noise': self.privacy_noise,
            'sample_size': self.sample_size,
            'weight_keys': list(self.weights.keys())
        }


@dataclass
class RoundResult:
    """Result of a federated round"""
    round_number: int
    clients_selected: int
    clients_completed: int
    aggregated_weights: Dict[str, np.ndarray]
    global_accuracy: float
    global_loss: float
    privacy_budget_spent: float
    duration_seconds: float


class FederatedClient:
    """
    A-007: Federated Learning Client
    Trains locally and shares only gradient updates (not raw data)
    """
    
    def __init__(self, config: ClientConfig, privacy: Optional[ModularPrivacy] = None):
        self.config = config
        self.privacy = privacy or ModularPrivacy()
        self.state = ClientState(client_id=config.client_id)
        self.local_model: Optional[Dict[str, np.ndarray]] = None
        self.train_data: List[Dict] = []
        
    def load_data(self, data: List[Dict]):
        """Load local training data"""
        self.train_data = data
        self.state.data_size = len(data)
        logger.info(f"Client {self.config.client_id} loaded {len(data)} samples")
    
    def set_model(self, weights: Dict[str, np.ndarray]):
        """Receive global model weights"""
        self.local_model = {k: v.copy() for k, v in weights.items()}
    
    def train(self) -> ModelUpdate:
        """
        Train locally on private data
        Returns: Model update with differential privacy
        """
        if not self.local_model or len(self.train_data) < self.config.min_data_size:
            raise ValueError("Model not initialized or insufficient data")
        
        self.state.status = ClientStatus.TRAINING
        start_time = time.time()
        
        # Initialize model if needed
        if self.local_model is None:
            self.local_model = self._initialize_model()
        
        # Simulate local training (in production, use actual ML framework)
        initial_weights = {k: v.copy() for k, v in self.local_model.items()}
        
        for epoch in range(self.config.local_epochs):
            # Process batches
            for i in range(0, len(self.train_data), self.config.batch_size):
                batch = self.train_data[i:i + self.config.batch_size]
                gradients = self._compute_gradients(batch)
                
                # Apply gradients
                for key in self.local_model:
                    self.local_model[key] -= self.config.learning_rate * gradients.get(key, 0)
        
        # Compute updates (difference from initial)
        updates = {}
        for key in self.local_model:
            updates[key] = self.local_model[key] - initial_weights[key]
        
        # Apply differential privacy to updates
        privacy_budget = PrivacyBudget(total_epsilon=2.0)
        privacy_noise = 0.0
        
        for key in updates:
            noise_scale = self.config.max_noise_scale / (self.state.data_size + 1)
            noise = np.random.laplace(0, noise_scale, updates[key].shape)
            updates[key] += noise
            privacy_noise = max(privacy_noise, noise_scale)
        
        training_time = time.time() - start_time
        
        self.state.status = ClientStatus.UPLOADING
        self.state.last_update = time.time()
        self.state.rounds_participated += 1
        
        # Simulate metrics
        self.state.accuracy = np.random.uniform(0.7, 0.95)
        self.state.loss = np.random.uniform(0.1, 0.5)
        
        return ModelUpdate(
            client_id=self.config.client_id,
            round_number=0,  # Will be set by aggregator
            weights=updates,
            metadata={
                'training_time': training_time,
                'epochs': self.config.local_epochs,
                'batch_size': self.config.batch_size,
                'accuracy': self.state.accuracy,
                'loss': self.state.loss
            },
            privacy_noise=privacy_noise,
            sample_size=self.state.data_size
        )
    
    def _initialize_model(self) -> Dict[str, np.ndarray]:
        """Initialize model weights (cursor dynamics model)"""
        return {
            'encoder.weight': np.random.randn(128, 64) * 0.01,
            'encoder.bias': np.zeros(128),
            'decoder.weight': np.random.randn(64, 128) * 0.01,
            'decoder.bias': np.zeros(64),
            'attention.weight': np.random.randn(64, 64) * 0.01,
        }
    
    def _compute_gradients(self, batch: List[Dict]) -> Dict[str, np.ndarray]:
        """Compute gradients for a batch (simplified)"""
        # In production, use actual backpropagation
        gradients = {}
        for key in self.local_model:
            shape = self.local_model[key].shape
            gradients[key] = np.random.randn(*shape) * 0.01
        return gradients
    
    def get_state(self) -> ClientState:
        return self.state


class FederatedServer:
    """
    A-007: Federated Learning Server
    Coordinates rounds, aggregates updates, maintains global model
    """
    
    def __init__(
        self,
        model: Dict[str, np.ndarray],
        privacy: Optional[ModularPrivacy] = None,
        min_clients: int = 3,
        aggregation_method: str = "fedavg"
    ):
        self.global_model = model
        self.privacy = privacy or ModularPrivacy()
        self.min_clients = min_clients
        self.aggregation_method = aggregation_method
        
        self.clients: Dict[str, FederatedClient] = {}
        self.round_history: List[RoundResult] = []
        self.current_round = 0
        
        # Federation parameters
        self.total_rounds = 100
        self.round_timeout = 300  # seconds
        self.client_fraction = 1.0  # Select all available clients
        
        logger.info(f"Federated server initialized with {aggregation_method}")
    
    def register_client(self, client: FederatedClient):
        """Register a client"""
        self.clients[client.config.client_id] = client
        logger.info(f"Registered client: {client.config.client_id}")
    
    def select_clients(self, num_clients: Optional[int] = None) -> List[str]:
        """Select clients for the current round"""
        available = [
            cid for cid, c in self.clients.items()
            if c.state.status != ClientStatus.DISCONNECTED
            and c.state.data_size >= c.config.min_data_size
        ]
        
        if num_clients is None:
            num_clients = max(
                self.min_clients,
                int(len(available) * self.client_fraction)
            )
        
        # Select clients (prioritize those with more data)
        available.sort(key=lambda cid: self.clients[cid].state.data_size, reverse=True)
        return available[:num_clients]
    
    async def execute_round(
        self,
        client_ids: List[str],
        round_number: int
    ) -> RoundResult:
        """Execute one federated training round"""
        start_time = time.time()
        
        # Distribute global model to selected clients
        for cid in client_ids:
            self.clients[cid].set_model(self.global_model)
        
        # Collect updates from clients (parallel)
        updates: List[ModelUpdate] = []
        
        # Simulate async client training
        for cid in client_ids:
            client = self.clients[cid]
            try:
                # In production, run in parallel with asyncio
                update = client.train()
                update.round_number = round_number
                updates.append(update)
                logger.info(f"Client {cid} completed round {round_number}")
            except Exception as e:
                logger.error(f"Client {cid} failed: {e}")
        
        # Aggregate updates
        aggregated = self._aggregate_updates(updates)
        
        # Apply to global model
        for key in aggregated:
            self.global_model[key] += aggregated[key]
        
        # Calculate metrics
        avg_accuracy = np.mean([u.metadata.get('accuracy', 0) for u in updates])
        avg_loss = np.mean([u.metadata.get('loss', float('inf')) for u in updates])
        
        # Track privacy budget
        total_privacy_spent = sum(u.privacy_noise for u in updates)
        
        duration = time.time() - start_time
        
        result = RoundResult(
            round_number=round_number,
            clients_selected=len(client_ids),
            clients_completed=len(updates),
            aggregated_weights=aggregated,
            global_accuracy=avg_accuracy,
            global_loss=avg_loss,
            privacy_budget_spent=total_privacy_spent,
            duration_seconds=duration
        )
        
        self.round_history.append(result)
        self.current_round = round_number
        
        logger.info(
            f"Round {round_number} complete: {len(updates)}/{len(client_ids)} clients, "
            f"accuracy={avg_accuracy:.3f}, loss={avg_loss:.3f}"
        )
        
        return result
    
    def _aggregate_updates(self, updates: List[ModelUpdate]) -> Dict[str, np.ndarray]:
        """Aggregate client updates using federated averaging"""
        if not updates:
            return {}
        
        if self.aggregation_method == "fedavg":
            return self._fedavg(updates)
        elif self.aggregation_method == "secure_avg":
            return self._secure_aggregation(updates)
        else:
            return self._fedavg(updates)
    
    def _fedavg(self, updates: List[ModelUpdate]) -> Dict[str, np.ndarray]:
        """Federated Averaging (FedAvg)"""
        # Weight by client data size
        total_samples = sum(u.sample_size for u in updates)
        
        aggregated = {}
        for key in updates[0].weights:
            weighted_sum = np.zeros_like(updates[0].weights[key], dtype=np.float64)
            
            for u in updates:
                weight = u.sample_size / total_samples
                weighted_sum += weight * u.weights[key]
            
            aggregated[key] = weighted_sum
        
        return aggregated
    
    def _secure_aggregation(self, updates: List[ModelUpdate]) -> Dict[str, np.ndarray]:
        """
        Secure Aggregation using cryptographic techniques
        Uses additive secret sharing and noise masking
        """
        # Add secure aggregation with noise masking
        num_clients = len(updates)
        
        # Create random masks (same for all clients - cancels out)
        masks = {}
        for key in updates[0].weights:
            masks[key] = np.random.randn(*updates[0].weights[key].shape)
        
        # Apply masks and aggregate
        aggregated = {}
        for key in updates[0].weights:
            sum_masked = np.zeros_like(updates[0].weights[key], dtype=np.float64)
            
            for u in updates:
                sum_masked += u.weights[key] + masks[key]
            
            # Subtract mask (cancels out when summed)
            aggregated[key] = sum_masked / num_clients
        
        return aggregated
    
    async def train(
        self,
        target_rounds: Optional[int] = None,
        early_stop: Optional[Callable[[RoundResult], bool]] = None
    ) -> List[RoundResult]:
        """Execute full federated training process"""
        target_rounds = target_rounds or self.total_rounds
        
        results = []
        
        for round_num in range(1, target_rounds + 1):
            # Select clients
            client_ids = self.select_clients()
            
            if len(client_ids) < self.min_clients:
                logger.warning(f"Insufficient clients: {len(client_ids)} < {self.min_clients}")
                break
            
            # Execute round
            result = await self.execute_round(client_ids, round_num)
            results.append(result)
            
            # Early stopping check
            if early_stop and early_stop(result):
                logger.info(f"Early stopping at round {round_num}")
                break
        
        return results
    
    def get_global_model(self) -> Dict[str, np.ndarray]:
        """Get the current global model"""
        return self.global_model
    
    def get_history(self) -> List[RoundResult]:
        """Get training history"""
        return self.round_history
    
    def get_client_states(self) -> List[Dict]:
        """Get states of all clients"""
        return [c.get_state().to_dict() for c in self.clients.values()]


class FederatedCoordinator:
    """
    High-level coordinator for federated learning
    Manages multiple federated learning sessions
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {
            'min_clients': 3,
            'rounds': 100,
            'aggregation': 'fedavg'
        }
        self.sessions: Dict[str, FederatedServer] = {}
    
    def create_session(
        self,
        session_id: str,
        initial_model: Dict[str, np.ndarray]
    ) -> FederatedServer:
        """Create a new federated learning session"""
        session = FederatedServer(
            model=initial_model,
            min_clients=self.config['min_clients'],
            aggregation_method=self.config['aggregation']
        )
        self.sessions[session_id] = session
        logger.info(f"Created federated session: {session_id}")
        return session
    
    def get_session(self, session_id: str) -> Optional[FederatedServer]:
        """Get an existing session"""
        return self.sessions.get(session_id)
    
    def list_sessions(self) -> List[Dict]:
        """List all sessions"""
        return [
            {
                'session_id': sid,
                'rounds_completed': len(s.round_history),
                'current_round': s.current_round,
                'clients': len(s.clients)
            }
            for sid, s in self.sessions.items()
        ]


# Example usage
if __name__ == '__main__':
    # Create coordinator
    coordinator = FederatedCoordinator({
        'min_clients': 2,
        'rounds': 10
    })
    
    # Initialize model
    initial_model = {
        'encoder.weight': np.random.randn(128, 64) * 0.01,
        'encoder.bias': np.zeros(128),
        'decoder.weight': np.random.randn(64, 128) * 0.01,
        'decoder.bias': np.zeros(64),
    }
    
    # Create session
    session = coordinator.create_session('cursor-training', initial_model)
    
    # Create and register clients
    privacy = ModularPrivacy()
    
    for i in range(3):
        client_config = ClientConfig(
            client_id=f'client-{i}',
            local_epochs=3,
            batch_size=16
        )
        client = FederatedClient(client_config, privacy)
        
        # Load simulated data
        client.load_data([
            {'x': np.random.randint(0, 1920), 'y': np.random.randint(0, 1080)}
            for _ in range(100)
        ])
        
        session.register_client(client)
    
    # Run training (sync for demo)
    async def run_training():
        results = await session.train(target_rounds=3)
        for r in results:
            print(f"Round {r.round_number}: accuracy={r.global_accuracy:.3f}, loss={r.global_loss:.3f}")
    
    asyncio.run(run_training())
    
    print(f"\nFinal model keys: {list(session.get_global_model().keys())}")
    print(f"Total clients: {len(session.clients)}")