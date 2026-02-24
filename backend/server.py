"""
UDP Server for Reliable Data Transfer Protocol

Responsibilities:
- Listen on port
- Receive packets
- Validate checksum
- Send ACK
- Store received data
- Handle out-of-order packets
"""

import socket
import threading
import time
import random
import os
from typing import Dict, Optional, Callable, List, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

from packet import (
    Packet, create_ack_packet, create_syn_ack_packet, create_fin_ack_packet,
    FLAG_SYN, FLAG_ACK, FLAG_FIN, FLAG_DATA, MAX_PACKET_SIZE
)


@dataclass
class TransferStats:
    """Statistics for a transfer session."""
    packets_received: int = 0
    acks_sent: int = 0
    checksum_errors: int = 0
    out_of_order: int = 0
    duplicate_packets: int = 0
    packets_dropped: int = 0
    bytes_received: int = 0
    start_time: float = 0.0
    end_time: float = 0.0
    
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
            return (self.bytes_received * 8) / (self.duration * 1_000_000)
        return 0.0
    
    def to_dict(self) -> dict:
        return {
            'packets_received': self.packets_received,
            'acks_sent': self.acks_sent,
            'checksum_errors': self.checksum_errors,
            'out_of_order': self.out_of_order,
            'duplicate_packets': self.duplicate_packets,
            'packets_dropped': self.packets_dropped,
            'bytes_received': self.bytes_received,
            'duration': self.duration,
            'throughput_mbps': self.throughput_mbps
        }


@dataclass
class ReceiverBuffer:
    """Buffer for storing received packets."""
    expected_seq: int = 0
    received_data: Dict[int, bytes] = field(default_factory=dict)
    max_buffer_size: int = 1024  # Max packets to buffer
    
    def add_packet(self, seq_no: int, data: bytes) -> Tuple[bool, int]:
        """
        Add packet to buffer.
        Returns: (is_in_order, expected_seq_for_ack)
        """
        if seq_no < self.expected_seq:
            # Duplicate packet
            return False, self.expected_seq
        
        if seq_no == self.expected_seq:
            # In-order packet
            self.received_data[seq_no] = data
            # Advance expected_seq to next missing packet
            while self.expected_seq in self.received_data:
                self.expected_seq += 1
            return True, self.expected_seq
        else:
            # Out-of-order packet - buffer it (for Selective Repeat)
            if len(self.received_data) < self.max_buffer_size:
                self.received_data[seq_no] = data
            return False, self.expected_seq
    
    def get_ordered_data(self) -> bytes:
        """Get all received data in order."""
        result = b''
        for i in sorted(self.received_data.keys()):
            result += self.received_data[i]
        return result
    
    def clear(self):
        """Clear the buffer."""
        self.expected_seq = 0
        self.received_data.clear()


class UDPServer:
    """
    UDP Server implementing reliable data transfer receiver.
    """
    
    def __init__(self, 
                 host: str = '0.0.0.0',
                 port: int = 5000,
                 packet_loss_rate: float = 0.0,
                 output_dir: str = './received_files'):
        self.host = host
        self.port = port
        self.packet_loss_rate = packet_loss_rate
        self.output_dir = output_dir
        
        self.socket: Optional[socket.socket] = None
        self.running = False
        self.receiver_thread: Optional[threading.Thread] = None
        
        # Session management
        self.buffer = ReceiverBuffer()
        self.stats = TransferStats()
        self.current_client: Optional[Tuple[str, int]] = None
        self.transfer_complete = False
        
        # Protocol mode: 'stop_wait', 'go_back_n', 'selective_repeat'
        self.protocol_mode = 'selective_repeat'
        self.window_size = 10
        
        # Callbacks for UI updates
        self.on_packet_received: Optional[Callable[[Packet, TransferStats], None]] = None
        self.on_transfer_complete: Optional[Callable[[str, TransferStats], None]] = None
        self.on_stats_update: Optional[Callable[[TransferStats], None]] = None
        
        # Event log for UI
        self.event_log: List[dict] = []
        self.max_log_size = 500
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
    
    def start(self):
        """Start the UDP server."""
        if self.running:
            return
        
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))
        self.socket.settimeout(1.0)  # For graceful shutdown
        
        self.running = True
        self.receiver_thread = threading.Thread(target=self._receive_loop, daemon=True)
        self.receiver_thread.start()
        
        self._log_event('server_start', f'Server started on {self.host}:{self.port}')
    
    def stop(self):
        """Stop the UDP server."""
        self.running = False
        if self.receiver_thread:
            self.receiver_thread.join(timeout=2.0)
        if self.socket:
            self.socket.close()
            self.socket = None
        self._log_event('server_stop', 'Server stopped')
    
    def reset(self):
        """Reset server state for new transfer."""
        self.buffer.clear()
        self.stats = TransferStats()
        self.current_client = None
        self.transfer_complete = False
        self.event_log.clear()
    
    def set_protocol_mode(self, mode: str, window_size: int = 10):
        """Set protocol mode and window size."""
        self.protocol_mode = mode
        self.window_size = window_size
    
    def _receive_loop(self):
        """Main receive loop."""
        while self.running:
            try:
                data, addr = self.socket.recvfrom(MAX_PACKET_SIZE)
                self._handle_packet(data, addr)
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    self._log_event('error', f'Receive error: {e}')
    
    def _handle_packet(self, data: bytes, addr: Tuple[str, int]):
        """Handle received packet."""
        # Simulate packet loss
        if random.random() < self.packet_loss_rate:
            self.stats.packets_dropped += 1
            self._log_event('packet_drop', f'Dropped packet from {addr}')
            return
        
        # Parse packet
        packet = Packet.from_bytes(data)
        if packet is None:
            self._log_event('error', f'Invalid packet from {addr}')
            return
        
        # Verify checksum
        if not packet.verify_checksum():
            self.stats.checksum_errors += 1
            self._log_event('checksum_error', f'Checksum error for seq={packet.seq_no}')
            return
        
        self.stats.packets_received += 1
        
        # Handle by packet type
        if packet.is_syn and not packet.is_ack:
            self._handle_syn(packet, addr)
        elif packet.is_data:
            self._handle_data(packet, addr)
        elif packet.is_fin:
            self._handle_fin(packet, addr)
        
        # Notify callbacks
        if self.on_packet_received:
            self.on_packet_received(packet, self.stats)
        if self.on_stats_update:
            self.on_stats_update(self.stats)
    
    def _handle_syn(self, packet: Packet, addr: Tuple[str, int]):
        """Handle SYN packet - connection establishment."""
        self._log_event('syn_received', f'SYN from {addr}, seq={packet.seq_no}')
        
        # Reset state for new connection
        self.buffer.clear()
        self.stats = TransferStats()
        self.stats.start_time = time.time()
        self.current_client = addr
        self.transfer_complete = False
        
        # Send SYN-ACK
        syn_ack = create_syn_ack_packet(
            seq_no=0,
            ack_no=packet.seq_no + 1,
            window=self.window_size
        )
        self._send_packet(syn_ack, addr)
        self._log_event('syn_ack_sent', f'SYN-ACK to {addr}')
    
    def _handle_data(self, packet: Packet, addr: Tuple[str, int]):
        """Handle DATA packet."""
        self._log_event('data_received', 
                       f'DATA seq={packet.seq_no}, len={len(packet.data)}')
        
        # Add to buffer based on protocol mode
        if self.protocol_mode == 'stop_wait':
            is_in_order, next_expected = self._handle_stop_wait(packet)
        elif self.protocol_mode == 'go_back_n':
            is_in_order, next_expected = self._handle_go_back_n(packet)
        else:  # selective_repeat
            is_in_order, next_expected = self._handle_selective_repeat(packet)
        
        if is_in_order:
            self.stats.bytes_received += len(packet.data)
        else:
            if packet.seq_no < self.buffer.expected_seq:
                self.stats.duplicate_packets += 1
            else:
                self.stats.out_of_order += 1
    
    def _handle_stop_wait(self, packet: Packet) -> Tuple[bool, int]:
        """Handle packet in Stop-and-Wait mode."""
        if packet.seq_no == self.buffer.expected_seq:
            self.buffer.received_data[packet.seq_no] = packet.data
            self.buffer.expected_seq += 1
            ack = create_ack_packet(0, self.buffer.expected_seq, 1)
            self._send_packet(ack, self.current_client)
            self.stats.acks_sent += 1
            self._log_event('ack_sent', f'ACK {self.buffer.expected_seq}')
            return True, self.buffer.expected_seq
        else:
            # Send ACK for last received in-order packet
            ack = create_ack_packet(0, self.buffer.expected_seq, 1)
            self._send_packet(ack, self.current_client)
            self.stats.acks_sent += 1
            return False, self.buffer.expected_seq
    
    def _handle_go_back_n(self, packet: Packet) -> Tuple[bool, int]:
        """Handle packet in Go-Back-N mode."""
        # GBN only accepts in-order packets
        if packet.seq_no == self.buffer.expected_seq:
            self.buffer.received_data[packet.seq_no] = packet.data
            self.buffer.expected_seq += 1
            # Send cumulative ACK
            ack = create_ack_packet(0, self.buffer.expected_seq, self.window_size)
            self._send_packet(ack, self.current_client)
            self.stats.acks_sent += 1
            self._log_event('ack_sent', f'Cumulative ACK {self.buffer.expected_seq}')
            return True, self.buffer.expected_seq
        else:
            # Discard out-of-order, send ACK for last in-order
            ack = create_ack_packet(0, self.buffer.expected_seq, self.window_size)
            self._send_packet(ack, self.current_client)
            self.stats.acks_sent += 1
            return False, self.buffer.expected_seq
    
    def _handle_selective_repeat(self, packet: Packet) -> Tuple[bool, int]:
        """Handle packet in Selective Repeat mode."""
        is_in_order, expected = self.buffer.add_packet(packet.seq_no, packet.data)
        
        # Send individual ACK for this packet
        ack = create_ack_packet(0, packet.seq_no + 1, self.window_size)
        self._send_packet(ack, self.current_client)
        self.stats.acks_sent += 1
        self._log_event('ack_sent', f'Selective ACK for seq={packet.seq_no}')
        
        return is_in_order, expected
    
    def _handle_fin(self, packet: Packet, addr: Tuple[str, int]):
        """Handle FIN packet - connection termination."""
        self._log_event('fin_received', f'FIN from {addr}')
        
        self.stats.end_time = time.time()
        self.transfer_complete = True
        
        # Send FIN-ACK
        fin_ack = create_fin_ack_packet(0, packet.seq_no + 1)
        self._send_packet(fin_ack, addr)
        self._log_event('fin_ack_sent', f'FIN-ACK to {addr}')
        
        # Save received file
        filename = f'received_{int(time.time())}.bin'
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, 'wb') as f:
            f.write(self.buffer.get_ordered_data())
        
        self._log_event('transfer_complete', 
                       f'File saved: {filename}, {self.stats.bytes_received} bytes')
        
        if self.on_transfer_complete:
            self.on_transfer_complete(filepath, self.stats)
    
    def _send_packet(self, packet: Packet, addr: Tuple[str, int]):
        """Send packet to address."""
        if self.socket and addr:
            self.socket.sendto(packet.to_bytes(), addr)
    
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
    
    def get_status(self) -> dict:
        """Get current server status."""
        return {
            'running': self.running,
            'host': self.host,
            'port': self.port,
            'protocol_mode': self.protocol_mode,
            'window_size': self.window_size,
            'packet_loss_rate': self.packet_loss_rate,
            'current_client': self.current_client,
            'transfer_complete': self.transfer_complete,
            'stats': self.stats.to_dict(),
            'buffer_size': len(self.buffer.received_data),
            'expected_seq': self.buffer.expected_seq
        }


if __name__ == '__main__':
    # Test server
    server = UDPServer(port=5000, packet_loss_rate=0.1)
    server.start()
    print(f"Server running on port {server.port}")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()
        print("Server stopped")
