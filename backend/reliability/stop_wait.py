"""
Stop-and-Wait Protocol Implementation

The simplest reliable transfer protocol:
- Send 1 packet
- Wait for ACK
- If timeout → retransmit
"""

import socket
import time
import random
from typing import List, Optional, Callable, Tuple
from dataclasses import dataclass, field

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from packet import (
    Packet, create_data_packet, create_ack_packet,
    MAX_DATA_SIZE, MAX_PACKET_SIZE
)


@dataclass
class StopWaitStats:
    """Statistics for Stop-and-Wait protocol."""
    packets_sent: int = 0
    acks_received: int = 0
    retransmissions: int = 0
    timeouts: int = 0
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
    
    @property
    def utilization(self) -> float:
        """Protocol utilization (affected by RTT)."""
        if self.avg_rtt > 0 and self.duration > 0:
            # Time spent transmitting vs total time
            transmission_time = self.packets_sent * 0.001  # Assume 1ms per packet
            return transmission_time / self.duration
        return 0.0


class StopWaitSender:
    """
    Stop-and-Wait protocol sender.
    
    Simple but inefficient - only one packet in flight at a time.
    Good for learning and low bandwidth-delay product networks.
    """
    
    def __init__(self,
                 sock: socket.socket,
                 dest_addr: Tuple[str, int],
                 timeout: float = 1.0,
                 max_retries: int = 10,
                 packet_loss_rate: float = 0.0):
        self.sock = sock
        self.dest_addr = dest_addr
        self.timeout = timeout
        self.max_retries = max_retries
        self.packet_loss_rate = packet_loss_rate
        
        self.stats = StopWaitStats()
        self.current_seq = 0
        
        # Callbacks
        self.on_packet_sent: Optional[Callable[[Packet], None]] = None
        self.on_ack_received: Optional[Callable[[Packet], None]] = None
        self.on_timeout: Optional[Callable[[int], None]] = None
        self.on_retransmit: Optional[Callable[[Packet], None]] = None
    
    def send_data(self, data: bytes) -> bool:
        """
        Send data using Stop-and-Wait protocol.
        
        Returns True if all data was successfully sent.
        """
        # Chunk data
        chunks = [
            data[i:i + MAX_DATA_SIZE]
            for i in range(0, len(data), MAX_DATA_SIZE)
        ]
        
        self.stats = StopWaitStats()
        self.stats.start_time = time.time()
        
        for chunk in chunks:
            if not self._send_chunk(chunk):
                return False
        
        self.stats.end_time = time.time()
        return True
    
    def _send_chunk(self, chunk: bytes) -> bool:
        """Send a single chunk with Stop-and-Wait."""
        packet = create_data_packet(self.current_seq, chunk, window=1)
        retries = 0
        
        while retries < self.max_retries:
            send_time = time.time()
            
            # Simulate packet loss
            if random.random() >= self.packet_loss_rate:
                self._send_packet(packet)
                self.stats.packets_sent += 1
                self.stats.bytes_sent += len(chunk)
                
                if self.on_packet_sent:
                    self.on_packet_sent(packet)
            
            # Wait for ACK
            try:
                self.sock.settimeout(self.timeout)
                data, _ = self.sock.recvfrom(MAX_PACKET_SIZE)
                ack = Packet.from_bytes(data)
                
                if ack and ack.is_ack and ack.ack_no > self.current_seq:
                    # ACK received
                    rtt = time.time() - send_time
                    self.stats.rtt_samples.append(rtt)
                    self.stats.acks_received += 1
                    self.current_seq += 1
                    
                    if self.on_ack_received:
                        self.on_ack_received(ack)
                    
                    return True
                    
            except socket.timeout:
                retries += 1
                self.stats.timeouts += 1
                self.stats.retransmissions += 1
                
                if self.on_timeout:
                    self.on_timeout(self.current_seq)
                if self.on_retransmit:
                    self.on_retransmit(packet)
        
        return False
    
    def _send_packet(self, packet: Packet):
        """Send packet to destination."""
        self.sock.sendto(packet.to_bytes(), self.dest_addr)


class StopWaitReceiver:
    """
    Stop-and-Wait protocol receiver.
    """
    
    def __init__(self,
                 sock: socket.socket,
                 packet_loss_rate: float = 0.0):
        self.sock = sock
        self.packet_loss_rate = packet_loss_rate
        
        self.expected_seq = 0
        self.received_data: List[bytes] = []
        
        # Callbacks
        self.on_packet_received: Optional[Callable[[Packet], None]] = None
        self.on_ack_sent: Optional[Callable[[Packet], None]] = None
    
    def receive_packet(self, packet: Packet, sender_addr: Tuple[str, int]) -> Optional[bytes]:
        """
        Process received packet.
        
        Returns the data if packet is in order, None otherwise.
        """
        # Simulate ACK loss
        if random.random() < self.packet_loss_rate:
            return None
        
        if self.on_packet_received:
            self.on_packet_received(packet)
        
        if packet.seq_no == self.expected_seq:
            # In-order packet
            self.received_data.append(packet.data)
            self.expected_seq += 1
            
            # Send ACK
            ack = create_ack_packet(0, self.expected_seq, window=1)
            self.sock.sendto(ack.to_bytes(), sender_addr)
            
            if self.on_ack_sent:
                self.on_ack_sent(ack)
            
            return packet.data
        else:
            # Out of order or duplicate - resend last ACK
            ack = create_ack_packet(0, self.expected_seq, window=1)
            self.sock.sendto(ack.to_bytes(), sender_addr)
            
            if self.on_ack_sent:
                self.on_ack_sent(ack)
            
            return None
    
    def get_all_data(self) -> bytes:
        """Get all received data."""
        return b''.join(self.received_data)
    
    def reset(self):
        """Reset receiver state."""
        self.expected_seq = 0
        self.received_data.clear()


def demonstrate_stop_wait():
    """Demonstration of Stop-and-Wait protocol."""
    print("=== Stop-and-Wait Protocol Demonstration ===")
    print()
    print("How it works:")
    print("1. Sender sends ONE packet")
    print("2. Sender waits for ACK")
    print("3. If ACK received: send next packet")
    print("4. If timeout: retransmit same packet")
    print()
    print("Timeline visualization:")
    print()
    print("  Sender                    Receiver")
    print("    |                          |")
    print("    |----[Packet 0]----------->|")
    print("    |                          |")
    print("    |<---------[ACK 1]---------|")
    print("    |                          |")
    print("    |----[Packet 1]----------->|")
    print("    |                          |")
    print("    |<---------[ACK 2]---------|")
    print("    |                          |")
    print()
    print("Pros:")
    print("  + Simple to implement")
    print("  + Low buffer requirements")
    print()
    print("Cons:")
    print("  - Poor utilization (one packet at a time)")
    print("  - High latency for long-distance transfers")
    print("  - Throughput limited by RTT")
    print()
    print("Utilization = L/R / (RTT + L/R)")
    print("  Where L = packet size, R = transmission rate")


if __name__ == '__main__':
    demonstrate_stop_wait()
