"""
Go-Back-N Protocol Implementation

Sliding window protocol with cumulative acknowledgments:
- Send up to N packets before waiting for ACK
- Single timer for oldest unACKed packet
- On timeout: retransmit ALL packets from base onwards
- Receiver only accepts in-order packets
"""

import socket
import time
import random
import threading
from typing import List, Optional, Callable, Tuple, Dict
from dataclasses import dataclass, field
from collections import OrderedDict

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from packet import (
    Packet, create_data_packet, create_ack_packet,
    MAX_DATA_SIZE, MAX_PACKET_SIZE
)


@dataclass
class GBNStats:
    """Statistics for Go-Back-N protocol."""
    packets_sent: int = 0
    acks_received: int = 0
    retransmissions: int = 0
    timeouts: int = 0
    bytes_sent: int = 0
    window_advances: int = 0
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
    def efficiency(self) -> float:
        """Protocol efficiency (packets sent vs unique packets)."""
        if self.packets_sent > 0:
            unique_packets = self.packets_sent - self.retransmissions
            return unique_packets / self.packets_sent
        return 0.0


@dataclass
class SendWindow:
    """Send window for Go-Back-N."""
    base: int = 0  # First unACKed sequence number
    next_seq: int = 0  # Next sequence to send
    window_size: int = 10
    
    @property
    def slots_available(self) -> int:
        """Number of slots available in window."""
        return self.window_size - (self.next_seq - self.base)
    
    @property
    def is_full(self) -> bool:
        """Check if window is full."""
        return self.next_seq >= self.base + self.window_size
    
    def can_send(self) -> bool:
        """Check if we can send more packets."""
        return self.next_seq < self.base + self.window_size
    
    def advance_base(self, new_ack: int):
        """Advance base on cumulative ACK."""
        if new_ack > self.base:
            self.base = new_ack


class GBNSender:
    """
    Go-Back-N protocol sender.
    
    Uses sliding window with cumulative ACKs.
    On timeout, retransmits all packets from base.
    """
    
    def __init__(self,
                 sock: socket.socket,
                 dest_addr: Tuple[str, int],
                 window_size: int = 10,
                 timeout: float = 1.0,
                 packet_loss_rate: float = 0.0):
        self.sock = sock
        self.dest_addr = dest_addr
        self.window = SendWindow(window_size=window_size)
        self.timeout = timeout
        self.packet_loss_rate = packet_loss_rate
        
        self.stats = GBNStats()
        self.sent_packets: Dict[int, Tuple[Packet, float]] = {}  # seq -> (packet, send_time)
        self.data_chunks: List[bytes] = []
        self.total_chunks = 0
        
        # Threading
        self.lock = threading.Lock()
        self.running = False
        self.timer_start: Optional[float] = None
        
        # Callbacks
        self.on_packet_sent: Optional[Callable[[Packet, SendWindow], None]] = None
        self.on_ack_received: Optional[Callable[[int, SendWindow], None]] = None
        self.on_timeout: Optional[Callable[[int], None]] = None
        self.on_window_slide: Optional[Callable[[SendWindow], None]] = None
    
    def send_data(self, data: bytes) -> bool:
        """Send data using Go-Back-N."""
        self.data_chunks = [
            data[i:i + MAX_DATA_SIZE]
            for i in range(0, len(data), MAX_DATA_SIZE)
        ]
        self.total_chunks = len(self.data_chunks)
        
        self.stats = GBNStats()
        self.stats.start_time = time.time()
        self.window.base = 0
        self.window.next_seq = 0
        self.sent_packets.clear()
        
        self.running = True
        
        # Start receiver thread
        receiver = threading.Thread(target=self._receive_acks, daemon=True)
        receiver.start()
        
        # Main send loop
        while self.running and self.window.base < self.total_chunks:
            # Send packets within window
            with self.lock:
                while (self.window.can_send() and 
                       self.window.next_seq < self.total_chunks):
                    self._send_packet(self.window.next_seq)
                    self.window.next_seq += 1
            
            # Check timeout
            if self._check_timeout():
                self._handle_timeout()
            
            time.sleep(0.001)
        
        self.running = False
        receiver.join(timeout=1.0)
        
        self.stats.end_time = time.time()
        return self.window.base >= self.total_chunks
    
    def _send_packet(self, seq_no: int):
        """Send a single packet."""
        if seq_no >= self.total_chunks:
            return
        
        chunk = self.data_chunks[seq_no]
        packet = create_data_packet(seq_no, chunk, self.window.window_size)
        send_time = time.time()
        
        # Start timer if this is first unACKed
        if self.timer_start is None:
            self.timer_start = send_time
        
        # Store for potential retransmission
        self.sent_packets[seq_no] = (packet, send_time)
        
        # Simulate packet loss
        if random.random() >= self.packet_loss_rate:
            self.sock.sendto(packet.to_bytes(), self.dest_addr)
        
        self.stats.packets_sent += 1
        self.stats.bytes_sent += len(chunk)
        
        if self.on_packet_sent:
            self.on_packet_sent(packet, self.window)
    
    def _receive_acks(self):
        """Receive ACKs in separate thread."""
        self.sock.settimeout(0.1)
        
        while self.running:
            try:
                data, _ = self.sock.recvfrom(MAX_PACKET_SIZE)
                ack = Packet.from_bytes(data)
                
                if ack and ack.is_ack:
                    self._handle_ack(ack)
            except socket.timeout:
                continue
            except Exception:
                continue
    
    def _handle_ack(self, ack: Packet):
        """Handle received cumulative ACK."""
        ack_no = ack.ack_no
        
        with self.lock:
            if ack_no > self.window.base:
                # Calculate RTT for acknowledged packets
                for seq in range(self.window.base, ack_no):
                    if seq in self.sent_packets:
                        _, send_time = self.sent_packets[seq]
                        rtt = time.time() - send_time
                        self.stats.rtt_samples.append(rtt)
                        del self.sent_packets[seq]
                
                self.window.advance_base(ack_no)
                self.stats.acks_received += 1
                self.stats.window_advances += 1
                
                # Reset timer if there are still unACKed packets
                if self.window.base < self.window.next_seq:
                    self.timer_start = time.time()
                else:
                    self.timer_start = None
                
                if self.on_ack_received:
                    self.on_ack_received(ack_no, self.window)
                if self.on_window_slide:
                    self.on_window_slide(self.window)
    
    def _check_timeout(self) -> bool:
        """Check if timer has expired."""
        if self.timer_start is None:
            return False
        return time.time() - self.timer_start > self.timeout
    
    def _handle_timeout(self):
        """Handle timeout - retransmit all from base."""
        with self.lock:
            self.stats.timeouts += 1
            
            if self.on_timeout:
                self.on_timeout(self.window.base)
            
            # Retransmit all packets from base
            for seq in range(self.window.base, self.window.next_seq):
                if seq in self.sent_packets:
                    packet, _ = self.sent_packets[seq]
                    
                    # Update send time
                    self.sent_packets[seq] = (packet, time.time())
                    
                    # Simulate packet loss
                    if random.random() >= self.packet_loss_rate:
                        self.sock.sendto(packet.to_bytes(), self.dest_addr)
                    
                    self.stats.retransmissions += 1
            
            # Reset timer
            self.timer_start = time.time()


class GBNReceiver:
    """
    Go-Back-N protocol receiver.
    
    Only accepts in-order packets.
    Discards out-of-order packets.
    Sends cumulative ACKs.
    """
    
    def __init__(self,
                 sock: socket.socket,
                 packet_loss_rate: float = 0.0):
        self.sock = sock
        self.packet_loss_rate = packet_loss_rate
        
        self.expected_seq = 0
        self.received_data: List[bytes] = []
        
        # Callbacks
        self.on_packet_received: Optional[Callable[[Packet, bool], None]] = None
        self.on_ack_sent: Optional[Callable[[int], None]] = None
    
    def receive_packet(self, packet: Packet, sender_addr: Tuple[str, int]) -> Optional[bytes]:
        """
        Process received packet.
        
        Returns data if in-order, None otherwise.
        """
        is_in_order = packet.seq_no == self.expected_seq
        
        if self.on_packet_received:
            self.on_packet_received(packet, is_in_order)
        
        if is_in_order:
            # Accept packet
            self.received_data.append(packet.data)
            self.expected_seq += 1
        
        # Always send cumulative ACK
        # Simulate ACK loss
        if random.random() >= self.packet_loss_rate:
            ack = create_ack_packet(0, self.expected_seq, window=10)
            self.sock.sendto(ack.to_bytes(), sender_addr)
            
            if self.on_ack_sent:
                self.on_ack_sent(self.expected_seq)
        
        return packet.data if is_in_order else None
    
    def get_all_data(self) -> bytes:
        """Get all received data."""
        return b''.join(self.received_data)
    
    def reset(self):
        """Reset receiver state."""
        self.expected_seq = 0
        self.received_data.clear()


def demonstrate_go_back_n():
    """Demonstration of Go-Back-N protocol."""
    print("=== Go-Back-N Protocol Demonstration ===")
    print()
    print("How it works:")
    print("1. Sender has window of N packets")
    print("2. Can send N packets before requiring ACK")
    print("3. Uses CUMULATIVE ACKs (ACK n means all packets < n received)")
    print("4. On timeout: retransmit ALL unACKed packets")
    print("5. Receiver DISCARDS out-of-order packets")
    print()
    print("Window visualization (N=4):")
    print()
    print("  Already ACKed | In-flight (unACKed) | Available | Not yet sent")
    print("  ─────────────────────────────────────────────────────────────")
    print("  [0][1][2]      | [3][4][5][6]        |           | [7][8][9]...")
    print("        ↑                    ↑")
    print("      base              next_seq")
    print()
    print("Timeline with loss:")
    print()
    print("  Sender                              Receiver")
    print("    |----[Pkt 0]--------------------->| ✓")
    print("    |----[Pkt 1]----------X          | (lost)")
    print("    |----[Pkt 2]--------------------->| ✗ (out of order, discard)")
    print("    |----[Pkt 3]--------------------->| ✗ (out of order, discard)")
    print("    |<---------[ACK 1]----------------|")
    print("    |                                 |")
    print("    |  TIMEOUT - Go back to seq 1     |")
    print("    |                                 |")
    print("    |----[Pkt 1]--------------------->| ✓")
    print("    |----[Pkt 2]--------------------->| ✓")
    print("    |----[Pkt 3]--------------------->| ✓")
    print()
    print("Pros:")
    print("  + Better utilization than Stop-and-Wait")
    print("  + Simple receiver (no buffering needed)")
    print("  + Single timer simplifies sender")
    print()
    print("Cons:")
    print("  - Retransmits packets that were received correctly")
    print("  - Wastes bandwidth on retransmission")
    print("  - Performance degrades with high loss rates")


if __name__ == '__main__':
    demonstrate_go_back_n()
