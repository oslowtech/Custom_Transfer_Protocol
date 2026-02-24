"""
UDP Client for Reliable Data Transfer Protocol

Responsibilities:
- Break file into chunks
- Add sequence numbers
- Maintain send window
- Handle timeout and retransmission
- Manage congestion window
"""

import socket
import threading
import time
import random
import os
from typing import Dict, Optional, Callable, List, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum

from packet import (
    Packet, create_syn_packet, create_data_packet, create_fin_packet,
    create_ack_packet, FLAG_SYN, FLAG_ACK, FLAG_FIN, MAX_DATA_SIZE, MAX_PACKET_SIZE
)
from congestion import CongestionController, CongestionStats


class TransferState(Enum):
    IDLE = "idle"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    TRANSFERRING = "transferring"
    CLOSING = "closing"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class PacketInfo:
    """Information about a sent packet."""
    packet: Packet
    send_time: float
    retransmissions: int = 0
    acked: bool = False


@dataclass
class ClientStats:
    """Statistics for transfer session."""
    packets_sent: int = 0
    acks_received: int = 0
    retransmissions: int = 0
    timeouts: int = 0
    packets_dropped: int = 0
    bytes_sent: int = 0
    start_time: float = 0.0
    end_time: float = 0.0
    rtt_samples: List[float] = field(default_factory=list)
    
    @property
    def duration(self) -> float:
        if self.end_time > 0:
            return self.end_time - self.start_time
        elif self.start_time > 0:
            return time.time() - self.start_time
        return 0.0
    
    @property
    def throughput_mbps(self) -> float:
        if self.duration > 0:
            return (self.bytes_sent * 8) / (self.duration * 1_000_000)
        return 0.0
    
    @property
    def avg_rtt(self) -> float:
        if self.rtt_samples:
            return sum(self.rtt_samples) / len(self.rtt_samples)
        return 0.0
    
    def to_dict(self) -> dict:
        return {
            'packets_sent': self.packets_sent,
            'acks_received': self.acks_received,
            'retransmissions': self.retransmissions,
            'timeouts': self.timeouts,
            'packets_dropped': self.packets_dropped,
            'bytes_sent': self.bytes_sent,
            'duration': self.duration,
            'throughput_mbps': self.throughput_mbps,
            'avg_rtt': self.avg_rtt
        }


class UDPClient:
    """
    UDP Client implementing reliable data transfer sender.
    """
    
    def __init__(self,
                 server_host: str = 'localhost',
                 server_port: int = 5000,
                 timeout: float = 1.0,
                 packet_loss_rate: float = 0.0):
        self.server_host = server_host
        self.server_port = server_port
        self.base_timeout = timeout
        self.packet_loss_rate = packet_loss_rate
        
        self.socket: Optional[socket.socket] = None
        self.state = TransferState.IDLE
        
        # Protocol settings
        self.protocol_mode = 'selective_repeat'  # 'stop_wait', 'go_back_n', 'selective_repeat'
        self.window_size = 10
        
        # Window management
        self.base = 0  # Base of send window
        self.next_seq = 0  # Next sequence number to use
        self.sent_packets: Dict[int, PacketInfo] = {}  # seq_no -> PacketInfo
        self.acked_packets: Set[int] = set()  # For selective repeat
        
        # Data to send
        self.data_chunks: List[bytes] = []
        self.total_chunks = 0
        
        # Congestion control
        self.congestion = CongestionController(enabled=True)
        
        # Threading
        self.send_lock = threading.Lock()
        self.receiver_thread: Optional[threading.Thread] = None
        self.timer_thread: Optional[threading.Thread] = None
        self.running = False
        
        # Statistics
        self.stats = ClientStats()
        
        # Callbacks for UI updates
        self.on_packet_sent: Optional[Callable[[Packet, ClientStats], None]] = None
        self.on_ack_received: Optional[Callable[[Packet, ClientStats], None]] = None
        self.on_window_update: Optional[Callable[[int, int, int], None]] = None  # base, next, window
        self.on_stats_update: Optional[Callable[[ClientStats], None]] = None
        self.on_state_change: Optional[Callable[[TransferState], None]] = None
        self.on_congestion_update: Optional[Callable[[CongestionStats], None]] = None
        
        # Event log
        self.event_log: List[dict] = []
        self.max_log_size = 500
    
    def connect(self) -> bool:
        """Establish connection with server."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.settimeout(self.base_timeout)
            
            self._set_state(TransferState.CONNECTING)
            
            # Send SYN
            syn = create_syn_packet(0, self.window_size)
            self._send_raw_packet(syn)
            self._log_event('syn_sent', 'SYN sent')
            
            # Wait for SYN-ACK
            try:
                data, _ = self.socket.recvfrom(MAX_PACKET_SIZE)
                packet = Packet.from_bytes(data)
                
                if packet and packet.is_syn and packet.is_ack:
                    self._log_event('syn_ack_received', 'SYN-ACK received')
                    
                    # Send ACK to complete handshake
                    ack = create_ack_packet(0, packet.seq_no + 1, self.window_size)
                    self._send_raw_packet(ack)
                    
                    self._set_state(TransferState.CONNECTED)
                    return True
            except socket.timeout:
                self._log_event('timeout', 'Connection timeout')
                self._set_state(TransferState.ERROR)
                return False
                
        except Exception as e:
            self._log_event('error', f'Connection error: {e}')
            self._set_state(TransferState.ERROR)
            return False
        
        return False
    
    def send_file(self, filepath: str) -> bool:
        """Send a file to the server."""
        if self.state != TransferState.CONNECTED:
            if not self.connect():
                return False
        
        # Read and chunk file
        try:
            with open(filepath, 'rb') as f:
                file_data = f.read()
        except Exception as e:
            self._log_event('error', f'Failed to read file: {e}')
            return False
        
        self.data_chunks = [
            file_data[i:i + MAX_DATA_SIZE]
            for i in range(0, len(file_data), MAX_DATA_SIZE)
        ]
        self.total_chunks = len(self.data_chunks)
        
        self._log_event('transfer_start', 
                       f'Starting transfer: {len(file_data)} bytes, {self.total_chunks} chunks')
        
        # Reset state
        self.base = 0
        self.next_seq = 0
        self.sent_packets.clear()
        self.acked_packets.clear()
        self.stats = ClientStats()
        self.stats.start_time = time.time()
        self.congestion.reset()
        
        self._set_state(TransferState.TRANSFERRING)
        
        # Start receiver and timer threads
        self.running = True
        self.receiver_thread = threading.Thread(target=self._receive_loop, daemon=True)
        self.timer_thread = threading.Thread(target=self._timer_loop, daemon=True)
        self.receiver_thread.start()
        self.timer_thread.start()
        
        # Send based on protocol mode
        if self.protocol_mode == 'stop_wait':
            return self._send_stop_wait()
        elif self.protocol_mode == 'go_back_n':
            return self._send_sliding_window()
        else:  # selective_repeat
            return self._send_sliding_window()
    
    def send_data(self, data: bytes) -> bool:
        """Send raw data to the server."""
        if self.state != TransferState.CONNECTED:
            if not self.connect():
                return False
        
        self.data_chunks = [
            data[i:i + MAX_DATA_SIZE]
            for i in range(0, len(data), MAX_DATA_SIZE)
        ]
        self.total_chunks = len(self.data_chunks)
        
        # Reset state
        self.base = 0
        self.next_seq = 0
        self.sent_packets.clear()
        self.acked_packets.clear()
        self.stats = ClientStats()
        self.stats.start_time = time.time()
        self.congestion.reset()
        
        self._set_state(TransferState.TRANSFERRING)
        
        # Start receiver and timer threads
        self.running = True
        self.receiver_thread = threading.Thread(target=self._receive_loop, daemon=True)
        self.timer_thread = threading.Thread(target=self._timer_loop, daemon=True)
        self.receiver_thread.start()
        self.timer_thread.start()
        
        # Send based on protocol mode
        if self.protocol_mode == 'stop_wait':
            return self._send_stop_wait()
        else:
            return self._send_sliding_window()
    
    def _send_stop_wait(self) -> bool:
        """Send using Stop-and-Wait protocol."""
        for i, chunk in enumerate(self.data_chunks):
            packet = create_data_packet(i, chunk, 1)
            
            retries = 0
            max_retries = 10
            
            while retries < max_retries:
                # Simulate packet loss
                if random.random() >= self.packet_loss_rate:
                    self._send_raw_packet(packet)
                    self.stats.packets_sent += 1
                    self.stats.bytes_sent += len(chunk)
                    self._log_event('packet_sent', f'DATA seq={i}')
                else:
                    self.stats.packets_dropped += 1
                    self._log_event('packet_drop', f'Dropped outgoing seq={i}')
                
                # Wait for ACK
                try:
                    self.socket.settimeout(self.congestion.rto if self.congestion.enabled else self.base_timeout)
                    data, _ = self.socket.recvfrom(MAX_PACKET_SIZE)
                    ack_packet = Packet.from_bytes(data)
                    
                    if ack_packet and ack_packet.is_ack and ack_packet.ack_no > i:
                        self.stats.acks_received += 1
                        self._log_event('ack_received', f'ACK {ack_packet.ack_no}')
                        self.congestion.on_ack_received()
                        break
                except socket.timeout:
                    retries += 1
                    self.stats.retransmissions += 1
                    self.stats.timeouts += 1
                    self.congestion.on_timeout()
                    self._log_event('timeout', f'Timeout for seq={i}, retry {retries}')
            
            if retries >= max_retries:
                self._log_event('error', f'Max retries exceeded for seq={i}')
                self._set_state(TransferState.ERROR)
                return False
            
            if self.on_stats_update:
                self.on_stats_update(self.stats)
        
        self._finish_transfer()
        return True
    
    def _send_sliding_window(self) -> bool:
        """Send using sliding window protocol (GBN or SR)."""
        while self.base < self.total_chunks:
            # Send packets within window
            with self.send_lock:
                effective_window = min(
                    self.window_size,
                    self.congestion.effective_window if self.congestion.enabled else self.window_size
                )
                
                while (self.next_seq < self.total_chunks and 
                       self.next_seq < self.base + effective_window):
                    
                    if self.protocol_mode == 'selective_repeat' and self.next_seq in self.acked_packets:
                        self.next_seq += 1
                        continue
                    
                    chunk = self.data_chunks[self.next_seq]
                    packet = create_data_packet(self.next_seq, chunk, self.window_size)
                    
                    # Simulate packet loss
                    if random.random() >= self.packet_loss_rate:
                        self._send_raw_packet(packet)
                        self.congestion.on_packet_sent()
                    else:
                        self.stats.packets_dropped += 1
                        self._log_event('packet_drop', f'Dropped outgoing seq={self.next_seq}')
                    
                    self.sent_packets[self.next_seq] = PacketInfo(
                        packet=packet,
                        send_time=time.time()
                    )
                    self.stats.packets_sent += 1
                    self.stats.bytes_sent += len(chunk)
                    self._log_event('packet_sent', f'DATA seq={self.next_seq}')
                    
                    if self.on_packet_sent:
                        self.on_packet_sent(packet, self.stats)
                    
                    self.next_seq += 1
                
                if self.on_window_update:
                    self.on_window_update(self.base, self.next_seq, effective_window)
            
            # Small sleep to prevent busy waiting
            time.sleep(0.001)
        
        # Wait for remaining ACKs
        timeout_count = 0
        while self.base < self.total_chunks and timeout_count < 50:
            time.sleep(0.1)
            timeout_count += 1
        
        self.running = False
        
        if self.base >= self.total_chunks:
            self._finish_transfer()
            return True
        else:
            self._log_event('error', 'Transfer incomplete')
            self._set_state(TransferState.ERROR)
            return False
    
    def _receive_loop(self):
        """Receive ACKs from server."""
        while self.running:
            try:
                self.socket.settimeout(0.1)
                data, _ = self.socket.recvfrom(MAX_PACKET_SIZE)
                packet = Packet.from_bytes(data)
                
                if packet and packet.is_ack:
                    self._handle_ack(packet)
                    
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    self._log_event('error', f'Receive error: {e}')
    
    def _handle_ack(self, packet: Packet):
        """Handle received ACK."""
        ack_no = packet.ack_no
        self.stats.acks_received += 1
        
        with self.send_lock:
            if self.protocol_mode == 'go_back_n':
                # Cumulative ACK - advance base
                if ack_no > self.base:
                    # Calculate RTT for acknowledged packets
                    for seq in range(self.base, ack_no):
                        if seq in self.sent_packets:
                            rtt = time.time() - self.sent_packets[seq].send_time
                            self.stats.rtt_samples.append(rtt)
                            self.congestion.on_ack_received(rtt)
                            del self.sent_packets[seq]
                    
                    self.base = ack_no
                    self._log_event('ack_received', f'Cumulative ACK {ack_no}, base={self.base}')
                    
            else:  # selective_repeat
                # Individual ACK
                seq_acked = ack_no - 1
                if seq_acked not in self.acked_packets:
                    self.acked_packets.add(seq_acked)
                    
                    if seq_acked in self.sent_packets:
                        rtt = time.time() - self.sent_packets[seq_acked].send_time
                        self.stats.rtt_samples.append(rtt)
                        self.congestion.on_ack_received(rtt)
                        del self.sent_packets[seq_acked]
                    
                    self._log_event('ack_received', f'Selective ACK for seq={seq_acked}')
                    
                    # Advance base if possible
                    while self.base in self.acked_packets:
                        self.base += 1
        
        if self.on_ack_received:
            self.on_ack_received(packet, self.stats)
        if self.on_stats_update:
            self.on_stats_update(self.stats)
        if self.on_congestion_update and self.congestion.stats_history:
            self.on_congestion_update(self.congestion.stats_history[-1])
    
    def _timer_loop(self):
        """Timer thread for timeout detection."""
        while self.running:
            time.sleep(0.05)  # Check every 50ms
            
            current_time = time.time()
            timeout = self.congestion.rto if self.congestion.enabled else self.base_timeout
            
            with self.send_lock:
                if self.protocol_mode == 'go_back_n':
                    # Check only oldest unacked packet
                    if self.base in self.sent_packets:
                        info = self.sent_packets[self.base]
                        if current_time - info.send_time > timeout:
                            self._handle_timeout_gbn()
                else:
                    # Check all unacked packets (selective repeat)
                    for seq_no, info in list(self.sent_packets.items()):
                        if not info.acked and current_time - info.send_time > timeout:
                            self._retransmit_packet(seq_no)
    
    def _handle_timeout_gbn(self):
        """Handle timeout in Go-Back-N mode."""
        self._log_event('timeout', f'Timeout at base={self.base}')
        self.stats.timeouts += 1
        self.congestion.on_timeout()
        
        # Retransmit all packets from base
        for seq_no in range(self.base, self.next_seq):
            if seq_no in self.sent_packets:
                self._retransmit_packet(seq_no)
    
    def _retransmit_packet(self, seq_no: int):
        """Retransmit a specific packet."""
        if seq_no not in self.sent_packets:
            return
        
        info = self.sent_packets[seq_no]
        info.retransmissions += 1
        info.send_time = time.time()
        
        self.stats.retransmissions += 1
        self._log_event('retransmit', f'Retransmit seq={seq_no}')
        
        # Simulate packet loss even on retransmit
        if random.random() >= self.packet_loss_rate:
            self._send_raw_packet(info.packet)
        else:
            self.stats.packets_dropped += 1
            
        if self.on_stats_update:
            self.on_stats_update(self.stats)
    
    def _finish_transfer(self):
        """Complete the transfer with FIN."""
        self._set_state(TransferState.CLOSING)
        
        # Send FIN
        fin = create_fin_packet(self.next_seq)
        self._send_raw_packet(fin)
        self._log_event('fin_sent', 'FIN sent')
        
        # Wait for FIN-ACK
        try:
            self.socket.settimeout(2.0)
            data, _ = self.socket.recvfrom(MAX_PACKET_SIZE)
            packet = Packet.from_bytes(data)
            
            if packet and packet.is_fin and packet.is_ack:
                self._log_event('fin_ack_received', 'FIN-ACK received')
        except socket.timeout:
            self._log_event('warning', 'FIN-ACK timeout')
        
        self.stats.end_time = time.time()
        self._set_state(TransferState.COMPLETED)
        self._log_event('transfer_complete', 
                       f'Transfer complete: {self.stats.bytes_sent} bytes, '
                       f'{self.stats.duration:.2f}s, '
                       f'{self.stats.throughput_mbps:.2f} Mbps')
    
    def _send_raw_packet(self, packet: Packet):
        """Send raw packet to server."""
        if self.socket:
            self.socket.sendto(packet.to_bytes(), (self.server_host, self.server_port))
    
    def _set_state(self, state: TransferState):
        """Set client state."""
        self.state = state
        if self.on_state_change:
            self.on_state_change(state)
    
    def _log_event(self, event_type: str, message: str):
        """Log event for UI."""
        event = {
            'timestamp': time.time(),
            'type': event_type,
            'message': message
        }
        self.event_log.append(event)
        if len(self.event_log) > self.max_log_size:
            self.event_log = self.event_log[-self.max_log_size:]
    
    def close(self):
        """Close the client."""
        self.running = False
        if self.receiver_thread:
            self.receiver_thread.join(timeout=1.0)
        if self.timer_thread:
            self.timer_thread.join(timeout=1.0)
        if self.socket:
            self.socket.close()
            self.socket = None
        self._set_state(TransferState.IDLE)
    
    def configure(self, protocol_mode: str, window_size: int, 
                  timeout: float, packet_loss_rate: float,
                  congestion_enabled: bool):
        """Configure client parameters."""
        self.protocol_mode = protocol_mode
        self.window_size = window_size
        self.base_timeout = timeout
        self.packet_loss_rate = packet_loss_rate
        self.congestion.enabled = congestion_enabled
    
    def get_status(self) -> dict:
        """Get current client status."""
        return {
            'state': self.state.value,
            'protocol_mode': self.protocol_mode,
            'window_size': self.window_size,
            'base': self.base,
            'next_seq': self.next_seq,
            'total_chunks': self.total_chunks,
            'packet_loss_rate': self.packet_loss_rate,
            'stats': self.stats.to_dict(),
            'congestion': self.congestion.get_stats_summary()
        }


if __name__ == '__main__':
    # Test client
    import sys
    
    client = UDPClient(server_host='localhost', server_port=5000)
    client.configure(
        protocol_mode='selective_repeat',
        window_size=10,
        timeout=1.0,
        packet_loss_rate=0.1,
        congestion_enabled=True
    )
    
    # Create test file
    test_data = b'Hello, World! ' * 1000
    test_file = 'test_file.bin'
    with open(test_file, 'wb') as f:
        f.write(test_data)
    
    if client.send_file(test_file):
        print("Transfer successful!")
        print(f"Stats: {client.stats.to_dict()}")
    else:
        print("Transfer failed!")
    
    client.close()
    os.remove(test_file)
