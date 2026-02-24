"""
Selective Repeat Protocol Implementation

Advanced sliding window protocol:
- Individual timers for each packet
- Only retransmit lost packets
- Receiver buffers out-of-order packets
- Individual ACKs for each packet
"""

import socket
import time
import random
import threading
from typing import List, Optional, Callable, Tuple, Dict, Set
from dataclasses import dataclass, field
from enum import Enum

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from packet import (
    Packet, create_data_packet, create_ack_packet,
    MAX_DATA_SIZE, MAX_PACKET_SIZE
)


class PacketState(Enum):
    NOT_SENT = "not_sent"
    SENT = "sent"
    ACKED = "acked"


@dataclass
class SRStats:
    """Statistics for Selective Repeat protocol."""
    packets_sent: int = 0
    unique_acks: int = 0
    duplicate_acks: int = 0
    retransmissions: int = 0
    timeouts: int = 0
    bytes_sent: int = 0
    out_of_order_received: int = 0
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
        """Protocol efficiency."""
        if self.packets_sent > 0:
            unique = self.packets_sent - self.retransmissions
            return unique / self.packets_sent
        return 0.0


@dataclass
class PacketEntry:
    """Entry for tracking sent packets."""
    packet: Packet
    state: PacketState = PacketState.NOT_SENT
    send_time: float = 0.0
    retransmissions: int = 0


@dataclass
class SRWindow:
    """Send window for Selective Repeat."""
    base: int = 0
    next_seq: int = 0
    window_size: int = 10
    acked: Set[int] = field(default_factory=set)
    
    @property
    def slots_available(self) -> int:
        return self.window_size - (self.next_seq - self.base)
    
    def can_send(self) -> bool:
        return self.next_seq < self.base + self.window_size
    
    def mark_acked(self, seq_no: int):
        """Mark a sequence number as ACKed."""
        self.acked.add(seq_no)
        # Advance base if possible
        while self.base in self.acked:
            self.base += 1
    
    def is_acked(self, seq_no: int) -> bool:
        return seq_no in self.acked
    
    def in_window(self, seq_no: int) -> bool:
        return self.base <= seq_no < self.base + self.window_size


class SRSender:
    """
    Selective Repeat protocol sender.
    
    Individual timers for each packet.
    Only retransmits specific lost packets.
    """
    
    def __init__(self,
                 sock: socket.socket,
                 dest_addr: Tuple[str, int],
                 window_size: int = 10,
                 timeout: float = 1.0,
                 packet_loss_rate: float = 0.0):
        self.sock = sock
        self.dest_addr = dest_addr
        self.window = SRWindow(window_size=window_size)
        self.timeout = timeout
        self.packet_loss_rate = packet_loss_rate
        
        self.stats = SRStats()
        self.packets: Dict[int, PacketEntry] = {}  # seq -> PacketEntry
        self.data_chunks: List[bytes] = []
        self.total_chunks = 0
        
        # Threading
        self.lock = threading.Lock()
        self.running = False
        
        # Callbacks
        self.on_packet_sent: Optional[Callable[[Packet, SRWindow], None]] = None
        self.on_ack_received: Optional[Callable[[int, SRWindow, bool], None]] = None
        self.on_timeout: Optional[Callable[[int], None]] = None
        self.on_retransmit: Optional[Callable[[Packet], None]] = None
        self.on_window_update: Optional[Callable[[SRWindow], None]] = None
    
    def send_data(self, data: bytes) -> bool:
        """Send data using Selective Repeat."""
        self.data_chunks = [
            data[i:i + MAX_DATA_SIZE]
            for i in range(0, len(data), MAX_DATA_SIZE)
        ]
        self.total_chunks = len(self.data_chunks)
        
        # Initialize
        self.stats = SRStats()
        self.stats.start_time = time.time()
        self.window = SRWindow(window_size=self.window.window_size)
        self.packets.clear()
        
        # Prepare all packets
        for i, chunk in enumerate(self.data_chunks):
            packet = create_data_packet(i, chunk, self.window.window_size)
            self.packets[i] = PacketEntry(packet=packet)
        
        self.running = True
        
        # Start receiver thread
        receiver = threading.Thread(target=self._receive_acks, daemon=True)
        receiver.start()
        
        # Start timer thread
        timer = threading.Thread(target=self._timer_thread, daemon=True)
        timer.start()
        
        # Main send loop
        while self.running and self.window.base < self.total_chunks:
            with self.lock:
                # Send packets within window
                while (self.window.can_send() and 
                       self.window.next_seq < self.total_chunks):
                    
                    seq = self.window.next_seq
                    if not self.window.is_acked(seq):
                        self._send_packet(seq)
                    self.window.next_seq += 1
            
            time.sleep(0.001)
        
        self.running = False
        receiver.join(timeout=1.0)
        timer.join(timeout=1.0)
        
        self.stats.end_time = time.time()
        return self.window.base >= self.total_chunks
    
    def _send_packet(self, seq_no: int, is_retransmit: bool = False):
        """Send or retransmit a packet."""
        if seq_no not in self.packets:
            return
        
        entry = self.packets[seq_no]
        entry.send_time = time.time()
        entry.state = PacketState.SENT
        
        if is_retransmit:
            entry.retransmissions += 1
            self.stats.retransmissions += 1
            
            if self.on_retransmit:
                self.on_retransmit(entry.packet)
        else:
            self.stats.packets_sent += 1
            self.stats.bytes_sent += len(entry.packet.data)
        
        # Simulate packet loss
        if random.random() >= self.packet_loss_rate:
            self.sock.sendto(entry.packet.to_bytes(), self.dest_addr)
        
        if self.on_packet_sent:
            self.on_packet_sent(entry.packet, self.window)
    
    def _receive_acks(self):
        """Receive ACKs thread."""
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
        """Handle individual ACK."""
        # In SR, ack_no is the seq_no + 1 of the packet being ACKed
        seq_acked = ack.ack_no - 1
        
        with self.lock:
            is_new = seq_acked not in self.window.acked
            
            if is_new and seq_acked in self.packets:
                # Calculate RTT
                entry = self.packets[seq_acked]
                if entry.send_time > 0:
                    rtt = time.time() - entry.send_time
                    self.stats.rtt_samples.append(rtt)
                
                entry.state = PacketState.ACKED
                self.window.mark_acked(seq_acked)
                self.stats.unique_acks += 1
            else:
                self.stats.duplicate_acks += 1
            
            if self.on_ack_received:
                self.on_ack_received(seq_acked, self.window, is_new)
            if self.on_window_update:
                self.on_window_update(self.window)
    
    def _timer_thread(self):
        """Timer thread to check for timeouts."""
        while self.running:
            time.sleep(0.05)  # Check every 50ms
            
            current_time = time.time()
            
            with self.lock:
                for seq_no in range(self.window.base, min(self.window.next_seq, self.total_chunks)):
                    if seq_no in self.packets and seq_no not in self.window.acked:
                        entry = self.packets[seq_no]
                        
                        if entry.state == PacketState.SENT:
                            if current_time - entry.send_time > self.timeout:
                                self.stats.timeouts += 1
                                
                                if self.on_timeout:
                                    self.on_timeout(seq_no)
                                
                                # Retransmit only this packet
                                self._send_packet(seq_no, is_retransmit=True)


class SRReceiver:
    """
    Selective Repeat protocol receiver.
    
    Buffers out-of-order packets.
    Sends individual ACK for each packet.
    Delivers in-order to application.
    """
    
    def __init__(self,
                 sock: socket.socket,
                 window_size: int = 10,
                 packet_loss_rate: float = 0.0):
        self.sock = sock
        self.window_size = window_size
        self.packet_loss_rate = packet_loss_rate
        
        self.base = 0  # Next expected seq for delivery
        self.buffer: Dict[int, bytes] = {}  # Out-of-order buffer
        self.received_data: List[bytes] = []  # Ordered data
        
        # Callbacks
        self.on_packet_received: Optional[Callable[[Packet, bool], None]] = None
        self.on_ack_sent: Optional[Callable[[int], None]] = None
        self.on_data_delivered: Optional[Callable[[int, bytes], None]] = None
    
    def receive_packet(self, packet: Packet, sender_addr: Tuple[str, int]) -> Optional[bytes]:
        """
        Process received packet.
        
        Buffers out-of-order packets.
        Returns data being delivered (if any).
        """
        seq_no = packet.seq_no
        
        # Check if in receive window
        if not (self.base <= seq_no < self.base + self.window_size):
            # Outside window - might be old, ACK anyway
            if seq_no < self.base:
                self._send_ack(seq_no, sender_addr)
            return None
        
        is_in_order = seq_no == self.base
        
        if self.on_packet_received:
            self.on_packet_received(packet, is_in_order)
        
        # Buffer the packet
        if seq_no not in self.buffer:
            self.buffer[seq_no] = packet.data
        
        # Send individual ACK
        if random.random() >= self.packet_loss_rate:
            self._send_ack(seq_no, sender_addr)
        
        # Deliver in-order data
        delivered = b''
        while self.base in self.buffer:
            data = self.buffer.pop(self.base)
            self.received_data.append(data)
            delivered += data
            
            if self.on_data_delivered:
                self.on_data_delivered(self.base, data)
            
            self.base += 1
        
        return delivered if delivered else None
    
    def _send_ack(self, seq_no: int, sender_addr: Tuple[str, int]):
        """Send ACK for specific sequence number."""
        ack = create_ack_packet(0, seq_no + 1, self.window_size)
        self.sock.sendto(ack.to_bytes(), sender_addr)
        
        if self.on_ack_sent:
            self.on_ack_sent(seq_no)
    
    def get_all_data(self) -> bytes:
        """Get all delivered data."""
        return b''.join(self.received_data)
    
    def reset(self):
        """Reset receiver state."""
        self.base = 0
        self.buffer.clear()
        self.received_data.clear()


def demonstrate_selective_repeat():
    """Demonstration of Selective Repeat protocol."""
    print("=== Selective Repeat Protocol Demonstration ===")
    print()
    print("How it works:")
    print("1. Independent timer for EACH unACKed packet")
    print("2. Only retransmit specific lost packets")  
    print("3. Receiver BUFFERS out-of-order packets")
    print("4. Individual ACKs for each packet")
    print()
    print("Window visualization (N=4):")
    print()
    print("  Sender Window:")
    print("  [0:ACKed][1:Sent][2:ACKed][3:Sent] | [4][5] available")
    print("      ↑                                 ")
    print("    base (advances when 1 is ACKed)")
    print()
    print("  Receiver Window:")
    print("  [0:Recv][1:---][2:Recv][3:Recv] | waiting")
    print("      ↑                             ")
    print("    base (advances when 1 arrives)")
    print()
    print("Timeline with loss:")
    print()
    print("  Sender                              Receiver")
    print("    |----[Pkt 0]--------------------->| ✓ Buffer[0]")
    print("    |----[Pkt 1]----------X          | (lost)")
    print("    |----[Pkt 2]--------------------->| ✓ Buffer[2]")
    print("    |----[Pkt 3]--------------------->| ✓ Buffer[3]")
    print("    |<---------[ACK 0]----------------|")
    print("    |<---------[ACK 2]----------------|")
    print("    |<---------[ACK 3]----------------|")
    print("    |                                 |")
    print("    |  Timeout for Pkt 1 only         |")
    print("    |                                 |")
    print("    |----[Pkt 1]--------------------->| ✓ Buffer[1]")
    print("    |                                 | → Deliver 0,1,2,3")
    print("    |<---------[ACK 1]----------------|")
    print()
    print("Pros:")
    print("  + Only retransmits lost packets")
    print("  + Most efficient use of bandwidth")
    print("  + Best performance with high loss rates")
    print()
    print("Cons:")
    print("  - Complex implementation")
    print("  - Requires buffering at receiver")
    print("  - Multiple timers needed")
    print()
    print("Window Size Requirement:")
    print("  For SR to work correctly: window_size <= seq_no_space / 2")
    print("  This prevents old packets from being confused with new ones.")


if __name__ == '__main__':
    demonstrate_selective_repeat()
