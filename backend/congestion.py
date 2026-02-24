"""
Congestion Control Module

Implements simplified TCP congestion control:
- Slow Start: cwnd doubles each RTT until ssthresh
- Congestion Avoidance: cwnd increases linearly after ssthresh
- On Timeout: ssthresh = cwnd / 2, cwnd = 1
"""

import time
from dataclasses import dataclass, field
from typing import List, Callable, Optional
from enum import Enum


class CongestionState(Enum):
    SLOW_START = "slow_start"
    CONGESTION_AVOIDANCE = "congestion_avoidance"


@dataclass
class CongestionStats:
    """Statistics for congestion control visualization."""
    timestamp: float
    cwnd: float
    ssthresh: float
    state: str
    packets_in_flight: int
    rtt: float


@dataclass
class CongestionController:
    """
    Implements TCP-like congestion control.
    
    Attributes:
        cwnd: Congestion window size (in packets)
        ssthresh: Slow start threshold
        min_cwnd: Minimum congestion window
        max_cwnd: Maximum congestion window
    """
    cwnd: float = 1.0
    ssthresh: float = 64.0
    min_cwnd: float = 1.0
    max_cwnd: float = 1024.0
    enabled: bool = True
    
    # RTT estimation (Jacobson/Karels algorithm)
    srtt: float = 0.0  # Smoothed RTT
    rttvar: float = 0.0  # RTT variance
    rto: float = 1.0  # Retransmission timeout
    
    # Statistics tracking
    stats_history: List[CongestionStats] = field(default_factory=list)
    packets_in_flight: int = 0
    acks_received_in_window: int = 0
    
    # Callbacks
    on_stats_update: Optional[Callable[[CongestionStats], None]] = None
    
    @property
    def state(self) -> CongestionState:
        """Current congestion state."""
        if self.cwnd < self.ssthresh:
            return CongestionState.SLOW_START
        return CongestionState.CONGESTION_AVOIDANCE
    
    @property
    def effective_window(self) -> int:
        """Effective window size (integer packets)."""
        if not self.enabled:
            return int(self.max_cwnd)
        return max(1, int(self.cwnd))
    
    def on_ack_received(self, rtt_sample: Optional[float] = None):
        """
        Called when an ACK is received.
        
        In Slow Start: cwnd += 1 per ACK (doubles per RTT)
        In Congestion Avoidance: cwnd += 1/cwnd per ACK (linear increase)
        """
        if not self.enabled:
            return
        
        # Update RTT estimation
        if rtt_sample is not None:
            self._update_rtt(rtt_sample)
        
        if self.state == CongestionState.SLOW_START:
            # Exponential growth: cwnd increases by 1 for each ACK
            self.cwnd = min(self.cwnd + 1, self.max_cwnd)
        else:
            # Linear growth: cwnd increases by 1/cwnd for each ACK
            # This results in 1 MSS increase per RTT
            self.cwnd = min(self.cwnd + 1.0 / self.cwnd, self.max_cwnd)
        
        self.packets_in_flight = max(0, self.packets_in_flight - 1)
        self.acks_received_in_window += 1
        self._record_stats()
    
    def on_timeout(self):
        """
        Called on timeout event.
        
        ssthresh = cwnd / 2
        cwnd = 1 (back to slow start)
        """
        if not self.enabled:
            return
        
        self.ssthresh = max(self.cwnd / 2, 2)
        self.cwnd = self.min_cwnd
        self.acks_received_in_window = 0
        self._record_stats()
    
    def on_triple_duplicate_ack(self):
        """
        Called on triple duplicate ACK (fast recovery).
        
        ssthresh = cwnd / 2
        cwnd = ssthresh + 3
        """
        if not self.enabled:
            return
        
        self.ssthresh = max(self.cwnd / 2, 2)
        self.cwnd = self.ssthresh + 3
        self._record_stats()
    
    def on_packet_sent(self):
        """Called when a packet is sent."""
        self.packets_in_flight += 1
    
    def can_send(self) -> bool:
        """Check if we can send more packets based on congestion window."""
        if not self.enabled:
            return True
        return self.packets_in_flight < self.effective_window
    
    def _update_rtt(self, rtt_sample: float):
        """Update RTT estimation using Jacobson/Karels algorithm."""
        if self.srtt == 0:
            # First RTT sample
            self.srtt = rtt_sample
            self.rttvar = rtt_sample / 2
        else:
            # SRTT = (1-α) * SRTT + α * R  (α = 1/8)
            # RTTVAR = (1-β) * RTTVAR + β * |SRTT - R|  (β = 1/4)
            alpha = 0.125
            beta = 0.25
            self.rttvar = (1 - beta) * self.rttvar + beta * abs(self.srtt - rtt_sample)
            self.srtt = (1 - alpha) * self.srtt + alpha * rtt_sample
        
        # RTO = SRTT + 4 * RTTVAR (with min 1 second)
        self.rto = max(0.2, min(self.srtt + 4 * self.rttvar, 60.0))
    
    def _record_stats(self):
        """Record current stats for visualization."""
        stats = CongestionStats(
            timestamp=time.time(),
            cwnd=self.cwnd,
            ssthresh=self.ssthresh,
            state=self.state.value,
            packets_in_flight=self.packets_in_flight,
            rtt=self.srtt
        )
        self.stats_history.append(stats)
        
        # Keep only last 1000 entries
        if len(self.stats_history) > 1000:
            self.stats_history = self.stats_history[-1000:]
        
        if self.on_stats_update:
            self.on_stats_update(stats)
    
    def reset(self):
        """Reset congestion control state."""
        self.cwnd = self.min_cwnd
        self.ssthresh = 64.0
        self.srtt = 0.0
        self.rttvar = 0.0
        self.rto = 1.0
        self.packets_in_flight = 0
        self.acks_received_in_window = 0
        self.stats_history.clear()
    
    def get_stats_summary(self) -> dict:
        """Get summary of congestion control stats."""
        return {
            'cwnd': self.cwnd,
            'ssthresh': self.ssthresh,
            'state': self.state.value,
            'srtt': self.srtt,
            'rto': self.rto,
            'packets_in_flight': self.packets_in_flight,
            'enabled': self.enabled
        }
