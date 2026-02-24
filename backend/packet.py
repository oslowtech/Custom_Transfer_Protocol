"""
Custom Packet Structure for Reliable Data Transfer Protocol

Packet Format:
| Seq No (4B) | ACK No (4B) | Flags (1B) | Window (2B) | Checksum (2B) | Data (up to 1024B) |

Flags:
- SYN (0x01): Connection establishment
- ACK (0x02): Acknowledgment
- FIN (0x04): Connection termination
- DATA (0x08): Data packet
"""

import struct
import zlib
from dataclasses import dataclass
from typing import Optional

# Flag constants
FLAG_SYN = 0x01
FLAG_ACK = 0x02
FLAG_FIN = 0x04
FLAG_DATA = 0x08

# Header format: seq_no(I), ack_no(I), flags(B), window(H), checksum(H)
HEADER_FORMAT = '!IIBHH'
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)  # 13 bytes
MAX_DATA_SIZE = 1024
MAX_PACKET_SIZE = HEADER_SIZE + MAX_DATA_SIZE


@dataclass
class Packet:
    """Represents a custom protocol packet."""
    seq_no: int
    ack_no: int
    flags: int
    window: int
    data: bytes = b''
    checksum: int = 0
    
    def __post_init__(self):
        if len(self.data) > MAX_DATA_SIZE:
            raise ValueError(f"Data size {len(self.data)} exceeds max {MAX_DATA_SIZE}")
    
    @property
    def is_syn(self) -> bool:
        return bool(self.flags & FLAG_SYN)
    
    @property
    def is_ack(self) -> bool:
        return bool(self.flags & FLAG_ACK)
    
    @property
    def is_fin(self) -> bool:
        return bool(self.flags & FLAG_FIN)
    
    @property
    def is_data(self) -> bool:
        return bool(self.flags & FLAG_DATA)
    
    def calculate_checksum(self) -> int:
        """Calculate CRC32 checksum of packet contents (excluding checksum field)."""
        header_without_checksum = struct.pack('!IIBH', 
            self.seq_no, self.ack_no, self.flags, self.window)
        return zlib.crc32(header_without_checksum + self.data) & 0xFFFF
    
    def to_bytes(self) -> bytes:
        """Serialize packet to bytes."""
        self.checksum = self.calculate_checksum()
        header = struct.pack(HEADER_FORMAT,
            self.seq_no, self.ack_no, self.flags, self.window, self.checksum)
        return header + self.data
    
    @classmethod
    def from_bytes(cls, data: bytes) -> Optional['Packet']:
        """Deserialize bytes to packet. Returns None if invalid."""
        if len(data) < HEADER_SIZE:
            return None
        
        try:
            seq_no, ack_no, flags, window, checksum = struct.unpack(
                HEADER_FORMAT, data[:HEADER_SIZE])
            payload = data[HEADER_SIZE:]
            
            packet = cls(
                seq_no=seq_no,
                ack_no=ack_no,
                flags=flags,
                window=window,
                data=payload,
                checksum=checksum
            )
            return packet
        except struct.error:
            return None
    
    def verify_checksum(self) -> bool:
        """Verify packet checksum."""
        return self.checksum == self.calculate_checksum()
    
    def __repr__(self) -> str:
        flags_str = []
        if self.is_syn: flags_str.append('SYN')
        if self.is_ack: flags_str.append('ACK')
        if self.is_fin: flags_str.append('FIN')
        if self.is_data: flags_str.append('DATA')
        return (f"Packet(seq={self.seq_no}, ack={self.ack_no}, "
                f"flags=[{','.join(flags_str)}], window={self.window}, "
                f"data_len={len(self.data)})")


def create_syn_packet(seq_no: int, window: int = 1) -> Packet:
    """Create a SYN packet for connection establishment."""
    return Packet(seq_no=seq_no, ack_no=0, flags=FLAG_SYN, window=window)


def create_syn_ack_packet(seq_no: int, ack_no: int, window: int = 1) -> Packet:
    """Create a SYN-ACK packet."""
    return Packet(seq_no=seq_no, ack_no=ack_no, flags=FLAG_SYN | FLAG_ACK, window=window)


def create_ack_packet(seq_no: int, ack_no: int, window: int = 1) -> Packet:
    """Create an ACK packet."""
    return Packet(seq_no=seq_no, ack_no=ack_no, flags=FLAG_ACK, window=window)


def create_data_packet(seq_no: int, data: bytes, window: int = 1) -> Packet:
    """Create a DATA packet."""
    return Packet(seq_no=seq_no, ack_no=0, flags=FLAG_DATA, window=window, data=data)


def create_fin_packet(seq_no: int) -> Packet:
    """Create a FIN packet for connection termination."""
    return Packet(seq_no=seq_no, ack_no=0, flags=FLAG_FIN, window=0)


def create_fin_ack_packet(seq_no: int, ack_no: int) -> Packet:
    """Create a FIN-ACK packet."""
    return Packet(seq_no=seq_no, ack_no=ack_no, flags=FLAG_FIN | FLAG_ACK, window=0)
