/**
 * WebRTC P2P Module
 * 
 * O-011: WebRTC P2P
 * Prerequisite: A-007 (Federated Learning) successful
 * Enables peer-to-peer communication between clients for distributed inference.
 */

import { EventEmitter } from 'events';
import { v4 as uuidv4 } from 'uuid';

/**
 * WebRTC Configuration for P2P
 */
const ICE_SERVERS = [
  { urls: 'stun:stun.l.google.com:19302' },
  { urls: 'stun:stun1.l.google.com:19302' }
];

/**
 * Peer Connection State
 */
const PeerState = {
  NEW: 'new',
  CONNECTING: 'connecting',
  CONNECTED: 'connected',
  DISCONNECTED: 'disconnected',
  FAILED: 'failed'
};

/**
 * Message Types
 */
const MessageType = {
  OFFER: 'offer',
  ANSWER: 'answer',
  ICE_CANDIDATE: 'ice-candidate',
  DATA: 'data',
  SIGNAL: 'signal',
  HEARTBEAT: 'heartbeat',
  SYNC: 'sync'
};

/**
 * P2P Peer Connection
 */
class PeerConnection extends EventEmitter {
  constructor(peerId, config = {}) {
    super();
    this.peerId = peerId;
    this.config = {
      iceServers: config.iceServers || ICE_SERVERS,
      ...config
    };
    
    this.connection = null;
    this.dataChannel = null;
    this.state = PeerState.NEW;
    this.metadata = {};
    this.createdAt = Date.now();
  }
  
  /**
   * Create RTCPeerConnection
   */
  async createConnection() {
    this.connection = new RTCPeerConnection({
      iceServers: this.config.iceServers
    });
    
    // ICE candidate handler
    this.connection.onicecandidate = (event) => {
      if (event.candidate) {
        this.emit('ice-candidate', {
          candidate: event.candidate,
          peerId: this.peerId
        });
      }
    };
    
    // Connection state handler
    this.connection.onconnectionstatechange = () => {
      this.state = this.connection.connectionState;
      this.emit('state-change', this.state);
    };
    
    // Data channel handler
    this.connection.ondatachannel = (event) => {
      this._setupDataChannel(event.channel);
    };
    
    return this.connection;
  }
  
  /**
   * Create data channel for messaging
   */
  createDataChannel(label = 'telecursor-p2p') {
    if (!this.connection) {
      throw new Error('Connection not initialized');
    }
    
    const channel = this.connection.createDataChannel(label, {
      ordered: true,
      maxRetransmits: 30
    });
    
    this._setupDataChannel(channel);
    return channel;
  }
  
  /**
   * Setup data channel event handlers
   */
  _setupDataChannel(channel) {
    this.dataChannel = channel;
    
    channel.onopen = () => {
      this.emit('open');
    };
    
    channel.onclose = () => {
      this.emit('close');
    };
    
    channel.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this.emit('message', data);
      } catch (e) {
        this.emit('message', event.data);
      }
    };
    
    channel.onerror = (error) => {
      this.emit('error', error);
    };
  }
  
  /**
   * Create SDP offer (caller)
   */
  async createOffer() {
    if (!this.connection) {
      await this.createConnection();
    }
    
    if (!this.dataChannel) {
      this.createDataChannel();
    }
    
    const offer = await this.connection.createOffer();
    await this.connection.setLocalDescription(offer);
    
    return offer;
  }
  
  /**
   * Create SDP answer (callee)
   */
  async createAnswer(offer) {
    if (!this.connection) {
      await this.createConnection();
    }
    
    await this.connection.setRemoteDescription(new RTCSessionDescription(offer));
    
    const answer = await this.connection.createAnswer();
    await this.connection.setLocalDescription(answer);
    
    return answer;
  }
  
  /**
   * Apply remote description (answer)
   */
  async applyAnswer(answer) {
    await this.connection.setRemoteDescription(new RTCSessionDescription(answer));
  }
  
  /**
   * Add ICE candidate
   */
  async addIceCandidate(candidate) {
    if (this.connection) {
      await this.connection.addIceCandidate(new RTCIceCandidate(candidate));
    }
  }
  
  /**
   * Send message to peer
   */
  send(data) {
    if (this.dataChannel && this.dataChannel.readyState === 'open') {
      this.dataChannel.send(typeof data === 'string' ? data : JSON.stringify(data));
      return true;
    }
    return false;
  }
  
  /**
   * Close connection
   */
  close() {
    if (this.dataChannel) {
      this.dataChannel.close();
    }
    if (this.connection) {
      this.connection.close();
    }
    this.state = PeerState.DISCONNECTED;
  }
  
  getState() {
    return this.state;
  }
}

/**
 * P2P Mesh Network Manager
 */
class P2PMesh extends EventEmitter {
  constructor(config = {}) {
    super();
    
    this.config = {
      maxPeers: config.maxPeers || 10,
      heartbeatInterval: config.heartbeatInterval || 5000,
      reconnectAttempts: config.reconnectAttempts || 3,
      signalingServer: config.signalingServer || null,
      iceServers: config.iceServers || ICE_SERVERS
    };
    
    this.peerId = config.peerId || uuidv4();
    this.peers = new Map(); // peerId -> PeerConnection
    this.pendingOffers = new Map(); // offerId -> {offer, from}
    this.messageQueue = [];
    
    this._heartbeatTimer = null;
    this._cleanupTimer = null;
    
    console.log(`[P2P] Initialized with peer ID: ${this.peerId}`);
  }
  
  /**
   * Initialize P2P mesh
   */
  async initialize() {
    this._startHeartbeat();
    this._startCleanup();
    this.emit('initialized', { peerId: this.peerId });
  }
  
  /**
   * Connect to a peer
   */
  async connect(peerId, signalCallback) {
    if (this.peers.size >= this.config.maxPeers) {
      throw new Error('Max peers reached');
    }
    
    if (this.peers.has(peerId)) {
      console.log(`[P2P] Already connected to ${peerId}`);
      return this.peers.get(peerId);
    }
    
    const peer = new PeerConnection(peerId, {
      iceServers: this.config.iceServers
    });
    
    peer.on('ice-candidate', async (event) => {
      if (signalCallback) {
        await signalCallback({
          type: MessageType.ICE_CANDIDATE,
          from: this.peerId,
          to: peerId,
          candidate: event.candidate
        });
      }
    });
    
    peer.on('message', (data) => {
      this.emit('message', { peerId, data });
    });
    
    peer.on('state-change', (state) => {
      if (state === PeerState.CONNECTED) {
        this.emit('peer-connected', peerId);
      } else if (state === PeerState.DISCONNECTED || state === PeerState.FAILED) {
        this._handlePeerDisconnect(peerId);
      }
    });
    
    // Create offer
    const offer = await peer.createOffer();
    
    // Store pending offer
    this.pendingOffers.set(peerId, { offer, peer });
    
    // Send offer via signaling
    if (signalCallback) {
      await signalCallback({
        type: MessageType.OFFER,
        from: this.peerId,
        to: peerId,
        offer: offer
      });
    }
    
    this.peers.set(peerId, peer);
    return peer;
  }
  
  /**
   * Handle incoming offer (callee)
   */
  async handleOffer(offer, fromPeerId, signalCallback) {
    let peer = this.peers.get(fromPeerId);
    
    if (!peer) {
      peer = new PeerConnection(fromPeerId, {
        iceServers: this.config.iceServers
      });
      
      peer.on('ice-candidate', async (event) => {
        if (signalCallback) {
          await signalCallback({
            type: MessageType.ICE_CANDIDATE,
            from: this.peerId,
            to: fromPeerId,
            candidate: event.candidate
          });
        }
      });
      
      peer.on('message', (data) => {
        this.emit('message', { peerId: fromPeerId, data });
      });
      
      peer.on('state-change', (state) => {
        if (state === PeerState.DISCONNECTED || state === PeerState.FAILED) {
          this._handlePeerDisconnect(fromPeerId);
        }
      });
      
      this.peers.set(fromPeerId, peer);
    }
    
    // Create and send answer
    const answer = await peer.createAnswer(offer);
    
    if (signalCallback) {
      await signalCallback({
        type: MessageType.ANSWER,
        from: this.peerId,
        to: fromPeerId,
        answer: answer
      });
    }
    
    return peer;
  }
  
  /**
   * Handle incoming answer (caller)
   */
  async handleAnswer(answer, fromPeerId) {
    const pending = this.pendingOffers.get(fromPeerId);
    if (pending && pending.peer) {
      await pending.peer.applyAnswer(answer);
      this.pendingOffers.delete(fromPeerId);
    }
  }
  
  /**
   * Handle ICE candidate
   */
  async handleIceCandidate(candidate, fromPeerId) {
    const peer = this.peers.get(fromPeerId);
    if (peer) {
      await peer.addIceCandidate(candidate);
    }
  }
  
  /**
   * Handle signaling message
   */
  async handleSignal(message, signalCallback) {
    const { type, from, to, offer, answer, candidate } = message;
    
    switch (type) {
      case MessageType.OFFER:
        return await this.handleOffer(offer, from, signalCallback);
        
      case MessageType.ANSWER:
        return await this.handleAnswer(answer, from);
        
      case MessageType.ICE_CANDIDATE:
        return await this.handleIceCandidate(candidate, from);
        
      default:
        console.warn(`[P2P] Unknown message type: ${type}`);
    }
  }
  
  /**
   * Broadcast message to all connected peers
   */
  broadcast(data) {
    const message = {
      type: MessageType.DATA,
      from: this.peerId,
      timestamp: Date.now(),
      payload: data
    };
    
    let successCount = 0;
    for (const [peerId, peer] of this.peers) {
      if (peer.send(message)) {
        successCount++;
      }
    }
    
    return successCount;
  }
  
  /**
   * Send message to specific peer
   */
  sendTo(peerId, data) {
    const peer = this.peers.get(peerId);
    if (peer) {
      const message = {
        type: MessageType.DATA,
        from: this.peerId,
        timestamp: Date.now(),
        payload: data
      };
      return peer.send(message);
    }
    return false;
  }
  
  /**
   * Handle peer disconnect
   */
  _handlePeerDisconnect(peerId) {
    const peer = this.peers.get(peerId);
    if (peer) {
      peer.close();
      this.peers.delete(peerId);
      this.emit('peer-disconnected', peerId);
    }
  }
  
  /**
   * Get connected peers
   */
  getPeers() {
    return Array.from(this.peers.keys());
  }
  
  /**
   * Get peer info
   */
  getPeerInfo(peerId) {
    const peer = this.peers.get(peerId);
    if (!peer) return null;
    
    return {
      peerId,
      state: peer.state,
      connectedAt: peer.createdAt,
      metadata: peer.metadata
    };
  }
  
  /**
   * Start heartbeat
   */
  _startHeartbeat() {
    this._heartbeatTimer = setInterval(() => {
      const heartbeat = {
        type: MessageType.HEARTBEAT,
        from: this.peerId,
        timestamp: Date.now()
      };
      
      this.broadcast(heartbeat);
      this.emit('heartbeat', this.getPeers().length);
    }, this.config.heartbeatInterval);
  }
  
  /**
   * Start cleanup of stale peers
   */
  _startCleanup() {
    this._cleanupTimer = setInterval(() => {
      for (const [peerId, peer] of this.peers) {
        if (peer.state === PeerState.DISCONNECTED || 
            peer.state === PeerState.FAILED) {
          this._handlePeerDisconnect(peerId);
        }
      }
    }, 30000);
  }
  
  /**
   * Stop P2P mesh
   */
  stop() {
    if (this._heartbeatTimer) {
      clearInterval(this._heartbeatTimer);
    }
    if (this._cleanupTimer) {
      clearInterval(this._cleanupTimer);
    }
    
    for (const [, peer] of this.peers) {
      peer.close();
    }
    this.peers.clear();
    
    this.emit('stopped');
  }
}

/**
 * Federated Learning P2P Client
 * Combines federated learning with P2P communication
 */
class FederatedP2PClient extends EventEmitter {
  constructor(config = {}) {
    super();
    
    this.config = {
      ...config,
      peerId: config.peerId || uuidv4()
    };
    
    this.mesh = new P2PMesh({
      peerId: this.config.peerId,
      maxPeers: config.maxPeers || 5,
      iceServers: config.iceServers
    });
    
    this.localModel = null;
    this.roundNumber = 0;
    
    this._setupMeshHandlers();
  }
  
  /**
   * Setup mesh event handlers
   */
  _setupMeshHandlers() {
    this.mesh.on('message', ({ peerId, data }) => {
      if (data.type === MessageType.DATA) {
        this._handleModelUpdate(data.payload, peerId);
      } else if (data.type === MessageType.SYNC) {
        this._handleSync(data.payload, peerId);
      }
    });
    
    this.mesh.on('peer-connected', (peerId) => {
      console.log(`[FederatedP2P] Connected to peer: ${peerId}`);
      this.emit('peer-connected', peerId);
    });
    
    this.mesh.on('peer-disconnected', (peerId) => {
      console.log(`[FederatedP2P] Disconnected from peer: ${peerId}`);
      this.emit('peer-disconnected', peerId);
    });
  }
  
  /**
   * Initialize the P2P client
   */
  async initialize() {
    await this.mesh.initialize();
  }
  
  /**
   * Connect to signaling server and discover peers
   */
  async connectToSignalingServer(serverUrl) {
    // In production, implement WebSocket connection to signaling server
    // For now, return the mesh for direct P2P connections
    return this.mesh;
  }
  
  /**
   * Handle incoming model update
   */
  _handleModelUpdate(payload, fromPeerId) {
    if (payload.updateType === 'gradient') {
      this.emit('gradient-received', {
        from: fromPeerId,
        gradients: payload.gradients,
        round: payload.round
      });
    } else if (payload.updateType === 'weights') {
      this.emit('weights-received', {
        from: fromPeerId,
        weights: payload.weights,
        round: payload.round
      });
    }
  }
  
  /**
   * Handle sync request
   */
  _handleSync(payload, fromPeerId) {
    if (payload.request === 'model') {
      this.sendTo(fromPeerId, {
        updateType: 'weights',
        weights: this.localModel,
        round: this.roundNumber
      });
    }
  }
  
  /**
   * Broadcast local model update
   */
  broadcastModelUpdate(gradients) {
    return this.mesh.broadcast({
      updateType: 'gradient',
      gradients,
      round: this.roundNumber
    });
  }
  
  /**
   * Send model update to specific peer
   */
  sendTo(peerId, data) {
    return this.mesh.sendTo(peerId, data);
  }
  
  /**
   * Request model from peer
   */
  requestModelFrom(peerId) {
    return this.mesh.sendTo(peerId, {
      type: MessageType.SYNC,
      request: 'model'
    });
  }
  
  /**
   * Set local model
   */
  setLocalModel(model) {
    this.localModel = model;
  }
  
  /**
   * Get local model
   */
  getLocalModel() {
    return this.localModel;
  }
  
  /**
   * Get connected peers
   */
  getPeers() {
    return this.mesh.getPeers();
  }
  
  /**
   * Stop the client
   */
  stop() {
    this.mesh.stop();
  }
}

export {
  P2PMesh,
  FederatedP2PClient,
  PeerConnection,
  PeerState,
  MessageType
};

export default {
  P2PMesh,
  FederatedP2PClient,
  PeerConnection,
  PeerState,
  MessageType
};