"""
PDF Report Generator for Reliable Data Transfer Protocol

Generates detailed analysis reports of file transfers including:
- Transfer statistics
- Protocol performance metrics
- Packet loss analysis
- Congestion control behavior
- Efficiency calculations
- Visual charts
"""

import io
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, HRFlowable
)
from reportlab.graphics.shapes import Drawing, Rect, String, Line
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.widgets.markers import makeMarker


def generate_transfer_report(
    transfer_id: str,
    filename: str,
    file_size: int,
    protocol_mode: str,
    window_size: int,
    packet_loss_rate: float,
    congestion_enabled: bool,
    client_stats: Dict[str, Any],
    server_stats: Dict[str, Any],
    congestion_stats: Optional[Dict[str, Any]] = None,
    throughput_history: Optional[List[Dict]] = None,
    congestion_history: Optional[List[Dict]] = None,
    event_log: Optional[List[Dict]] = None
) -> bytes:
    """
    Generate a comprehensive PDF report for a file transfer.
    
    Returns the PDF as bytes.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        textColor=colors.HexColor('#1e40af')
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        spaceBefore=20,
        spaceAfter=10,
        textColor=colors.HexColor('#1e3a8a')
    )
    subheading_style = ParagraphStyle(
        'CustomSubheading',
        parent=styles['Heading3'],
        fontSize=12,
        spaceBefore=15,
        spaceAfter=8,
        textColor=colors.HexColor('#3b82f6')
    )
    normal_style = styles['Normal']
    
    # Build document content
    story = []
    
    # Title
    story.append(Paragraph("Reliable Data Transfer Protocol", title_style))
    story.append(Paragraph("Transfer Analysis Report", heading_style))
    story.append(Spacer(1, 10))
    
    # Report metadata
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#e5e7eb')))
    story.append(Spacer(1, 10))
    
    meta_data = [
        ["Report Generated:", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
        ["Transfer ID:", transfer_id],
        ["Filename:", filename],
        ["File Size:", format_bytes(file_size)]
    ]
    meta_table = Table(meta_data, colWidths=[2*inch, 4*inch])
    meta_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#6b7280')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 20))
    
    # ========== SECTION 1: Configuration Summary ==========
    story.append(Paragraph("1. Configuration Summary", heading_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#e5e7eb')))
    
    protocol_names = {
        'stop_wait': 'Stop-and-Wait',
        'go_back_n': 'Go-Back-N',
        'selective_repeat': 'Selective Repeat'
    }
    
    config_text = f"""
    The transfer was configured with the following parameters:
    <br/><br/>
    <b>Protocol:</b> {protocol_names.get(protocol_mode, protocol_mode)}<br/>
    <b>Window Size:</b> {window_size} packets<br/>
    <b>Simulated Packet Loss Rate:</b> {packet_loss_rate * 100:.1f}%<br/>
    <b>Congestion Control:</b> {'Enabled' if congestion_enabled else 'Disabled'}
    """
    story.append(Paragraph(config_text, normal_style))
    story.append(Spacer(1, 10))
    
    # Protocol description
    story.append(Paragraph("Protocol Description", subheading_style))
    
    protocol_descriptions = {
        'stop_wait': """
        <b>Stop-and-Wait</b> is the simplest reliable data transfer protocol. 
        It sends one packet at a time and waits for an acknowledgment (ACK) before sending the next packet.
        <br/><br/>
        <i>Characteristics:</i>
        <br/>• Simple implementation
        <br/>• Low buffer requirements
        <br/>• Poor utilization on high-latency networks
        <br/>• Throughput limited by RTT
        """,
        'go_back_n': """
        <b>Go-Back-N</b> uses a sliding window to send multiple packets before requiring acknowledgment.
        It uses cumulative ACKs, where ACK n confirms all packets up to n-1 have been received.
        <br/><br/>
        <i>Characteristics:</i>
        <br/>• Better utilization than Stop-and-Wait
        <br/>• Simple receiver (no buffering needed)
        <br/>• On packet loss, retransmits ALL packets from the lost one
        <br/>• Single timer for oldest unACKed packet
        """,
        'selective_repeat': """
        <b>Selective Repeat</b> is the most efficient sliding window protocol.
        It sends individual ACKs for each packet and only retransmits specifically lost packets.
        <br/><br/>
        <i>Characteristics:</i>
        <br/>• Most efficient use of bandwidth
        <br/>• Receiver buffers out-of-order packets
        <br/>• Individual timers for each packet
        <br/>• Best performance under high packet loss
        """
    }
    story.append(Paragraph(protocol_descriptions.get(protocol_mode, ""), normal_style))
    story.append(Spacer(1, 20))
    
    # ========== SECTION 2: Transfer Statistics ==========
    story.append(Paragraph("2. Transfer Statistics", heading_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#e5e7eb')))
    
    # Client-side stats table
    story.append(Paragraph("Sender Statistics", subheading_style))
    
    packets_sent = client_stats.get('packets_sent', 0)
    acks_received = client_stats.get('acks_received', 0)
    retransmissions = client_stats.get('retransmissions', 0)
    timeouts = client_stats.get('timeouts', 0)
    bytes_sent = client_stats.get('bytes_sent', 0)
    duration = client_stats.get('duration', 0)
    throughput = client_stats.get('throughput_mbps', 0)
    avg_rtt = client_stats.get('avg_rtt', 0)
    
    client_data = [
        ["Metric", "Value", "Description"],
        ["Packets Sent", str(packets_sent), "Total number of packets transmitted"],
        ["ACKs Received", str(acks_received), "Total acknowledgments received"],
        ["Retransmissions", str(retransmissions), "Packets retransmitted due to loss/timeout"],
        ["Timeouts", str(timeouts), "Number of timeout events"],
        ["Bytes Sent", format_bytes(bytes_sent), "Total data transmitted"],
        ["Duration", f"{duration:.3f} s", "Total transfer time"],
        ["Throughput", f"{throughput:.3f} Mbps", "Effective data rate"],
        ["Average RTT", f"{avg_rtt * 1000:.2f} ms", "Mean round-trip time"]
    ]
    
    client_table = Table(client_data, colWidths=[1.5*inch, 1.5*inch, 3.5*inch])
    client_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(client_table)
    story.append(Spacer(1, 15))
    
    # Server-side stats
    story.append(Paragraph("Receiver Statistics", subheading_style))
    
    server_packets = server_stats.get('packets_received', 0)
    server_acks = server_stats.get('acks_sent', 0)
    checksum_errors = server_stats.get('checksum_errors', 0)
    out_of_order = server_stats.get('out_of_order', 0)
    duplicates = server_stats.get('duplicate_packets', 0)
    server_bytes = server_stats.get('bytes_received', 0)
    
    server_data = [
        ["Metric", "Value", "Description"],
        ["Packets Received", str(server_packets), "Total packets received (including duplicates)"],
        ["ACKs Sent", str(server_acks), "Total acknowledgments sent"],
        ["Checksum Errors", str(checksum_errors), "Packets with invalid checksum"],
        ["Out-of-Order", str(out_of_order), "Packets received out of sequence"],
        ["Duplicate Packets", str(duplicates), "Duplicate packets received"],
        ["Bytes Received", format_bytes(server_bytes), "Total data received"]
    ]
    
    server_table = Table(server_data, colWidths=[1.5*inch, 1.5*inch, 3.5*inch])
    server_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#059669')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0fdf4')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(server_table)
    story.append(Spacer(1, 20))
    
    # ========== SECTION 3: Performance Analysis ==========
    story.append(Paragraph("3. Performance Analysis", heading_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#e5e7eb')))
    
    # Calculate efficiency metrics
    unique_packets = packets_sent - retransmissions
    efficiency = (unique_packets / packets_sent * 100) if packets_sent > 0 else 100
    actual_loss = (retransmissions / packets_sent * 100) if packets_sent > 0 else 0
    goodput = (bytes_sent / duration / 1_000_000 * 8) if duration > 0 else 0
    
    # Theoretical max throughput (no loss)
    theoretical_max = goodput / (1 - packet_loss_rate) if packet_loss_rate < 1 else goodput
    utilization = (throughput / theoretical_max * 100) if theoretical_max > 0 else 100
    
    story.append(Paragraph("Efficiency Metrics", subheading_style))
    
    efficiency_data = [
        ["Metric", "Value", "Analysis"],
        ["Protocol Efficiency", f"{efficiency:.2f}%", 
         "Good" if efficiency > 90 else "Moderate" if efficiency > 70 else "Poor"],
        ["Actual Packet Loss", f"{actual_loss:.2f}%", 
         f"{'Matches' if abs(actual_loss - packet_loss_rate*100) < 5 else 'Differs from'} configured loss rate"],
        ["Goodput", f"{goodput:.3f} Mbps", "Effective throughput excluding retransmissions"],
        ["Network Utilization", f"{min(utilization, 100):.1f}%", 
         "High" if utilization > 80 else "Medium" if utilization > 50 else "Low"],
        ["Retransmission Ratio", f"{retransmissions}:{packets_sent}", 
         f"1 retransmit per {packets_sent//max(retransmissions,1)} packets"]
    ]
    
    efficiency_table = Table(efficiency_data, colWidths=[1.5*inch, 1.5*inch, 3.5*inch])
    efficiency_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#7c3aed')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f3ff')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(efficiency_table)
    story.append(Spacer(1, 20))
    
    # ========== SECTION 4: Congestion Control Analysis ==========
    if congestion_enabled and congestion_stats:
        story.append(Paragraph("4. Congestion Control Analysis", heading_style))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#e5e7eb')))
        
        cwnd = congestion_stats.get('cwnd', 1)
        ssthresh = congestion_stats.get('ssthresh', 64)
        state = congestion_stats.get('state', 'unknown')
        srtt = congestion_stats.get('srtt', 0)
        rto = congestion_stats.get('rto', 1)
        
        congestion_text = f"""
        The TCP-like congestion control mechanism was active during this transfer.
        <br/><br/>
        <b>Final Congestion Window (cwnd):</b> {cwnd:.2f} packets<br/>
        <b>Slow Start Threshold (ssthresh):</b> {ssthresh:.2f} packets<br/>
        <b>Final State:</b> {state.replace('_', ' ').title()}<br/>
        <b>Smoothed RTT:</b> {srtt * 1000:.2f} ms<br/>
        <b>Retransmission Timeout (RTO):</b> {rto * 1000:.2f} ms
        """
        story.append(Paragraph(congestion_text, normal_style))
        story.append(Spacer(1, 10))
        
        # Congestion behavior explanation
        story.append(Paragraph("Congestion Control Behavior", subheading_style))
        
        cc_description = """
        <b>Slow Start Phase:</b> The congestion window doubles every RTT until it reaches ssthresh.
        This allows rapid bandwidth discovery while being cautious.
        <br/><br/>
        <b>Congestion Avoidance Phase:</b> After reaching ssthresh, cwnd increases linearly 
        (by 1/cwnd per ACK). This prevents aggressive growth that could cause congestion.
        <br/><br/>
        <b>On Timeout:</b> ssthresh is set to cwnd/2 and cwnd resets to 1, returning to slow start.
        This is an aggressive response to presumed network congestion.
        """
        story.append(Paragraph(cc_description, normal_style))
        story.append(Spacer(1, 20))
    
    # ========== SECTION 5: Protocol Comparison ==========
    story.append(PageBreak())
    story.append(Paragraph("5. Protocol Comparison", heading_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#e5e7eb')))
    
    comparison_text = """
    The following table compares the three reliability protocols implemented in this system:
    """
    story.append(Paragraph(comparison_text, normal_style))
    story.append(Spacer(1, 10))
    
    comparison_data = [
        ["Feature", "Stop-and-Wait", "Go-Back-N", "Selective Repeat"],
        ["Window Size", "1", "N", "N"],
        ["ACK Type", "Individual", "Cumulative", "Individual"],
        ["Receiver Buffer", "None", "None", "Required"],
        ["Retransmission", "Single packet", "All from error", "Only lost packets"],
        ["Timers", "Single", "Single", "Per-packet"],
        ["Complexity", "Low", "Medium", "High"],
        ["Efficiency", "Low", "Medium", "High"],
        ["Best For", "Simple networks", "Moderate loss", "High loss networks"]
    ]
    
    comparison_table = Table(comparison_data, colWidths=[1.5*inch, 1.4*inch, 1.4*inch, 1.6*inch])
    comparison_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#374151')),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#4b5563')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#9ca3af')),
        ('ROWBACKGROUNDS', (1, 1), (-1, -1), [colors.white, colors.HexColor('#f3f4f6')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(comparison_table)
    story.append(Spacer(1, 20))
    
    # ========== SECTION 6: Recommendations ==========
    story.append(Paragraph("6. Recommendations", heading_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#e5e7eb')))
    
    # Generate recommendations based on analysis
    recommendations = []
    
    if efficiency < 70:
        recommendations.append(
            "• <b>Low Efficiency:</b> Consider using Selective Repeat protocol for better handling of packet loss."
        )
    
    if actual_loss > packet_loss_rate * 100 + 5:
        recommendations.append(
            "• <b>Higher Than Expected Loss:</b> Network conditions may be worse than simulated. Consider increasing timeout values."
        )
    
    if protocol_mode == 'stop_wait' and duration > 5:
        recommendations.append(
            "• <b>Slow Transfer:</b> Stop-and-Wait has poor utilization. Consider Go-Back-N or Selective Repeat for faster transfers."
        )
    
    if window_size < 5 and protocol_mode != 'stop_wait':
        recommendations.append(
            "• <b>Small Window:</b> Consider increasing window size for better throughput, especially on high-latency networks."
        )
    
    if timeouts > retransmissions * 0.8 and avg_rtt > 0:
        recommendations.append(
            "• <b>Many Timeouts:</b> Consider increasing the timeout value to reduce unnecessary retransmissions."
        )
    
    if not congestion_enabled:
        recommendations.append(
            "• <b>No Congestion Control:</b> Enable congestion control for more realistic behavior and to prevent network congestion."
        )
    
    if not recommendations:
        recommendations.append(
            "• <b>Good Performance:</b> The transfer was efficient with current settings. No major improvements needed."
        )
    
    for rec in recommendations:
        story.append(Paragraph(rec, normal_style))
        story.append(Spacer(1, 5))
    
    story.append(Spacer(1, 20))
    
    # ========== SECTION 7: Summary ==========
    story.append(Paragraph("7. Summary", heading_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#e5e7eb')))
    
    summary_text = f"""
    This report analyzed a file transfer using the <b>{protocol_names.get(protocol_mode, protocol_mode)}</b> 
    protocol.
    <br/><br/>
    <b>Key Findings:</b>
    <br/>• Successfully transferred {format_bytes(bytes_sent)} of data
    <br/>• Achieved throughput of {throughput:.3f} Mbps
    <br/>• Protocol efficiency: {efficiency:.2f}%
    <br/>• {retransmissions} packets required retransmission out of {packets_sent} sent
    <br/>• Average round-trip time: {avg_rtt * 1000:.2f} ms
    <br/><br/>
    The transfer {'completed successfully' if server_bytes >= bytes_sent * 0.95 else 'may have had issues'} 
    with {protocol_names.get(protocol_mode, protocol_mode)} providing 
    {'optimal' if efficiency > 90 else 'acceptable' if efficiency > 70 else 'suboptimal'} performance 
    under {packet_loss_rate * 100:.1f}% simulated packet loss.
    """
    story.append(Paragraph(summary_text, normal_style))
    story.append(Spacer(1, 30))
    
    # Footer
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#e5e7eb')))
    footer_style = ParagraphStyle(
        'Footer',
        parent=normal_style,
        fontSize=8,
        textColor=colors.HexColor('#9ca3af'),
        alignment=1  # Center
    )
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        f"Generated by Reliable Data Transfer Protocol Simulator | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        footer_style
    ))
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def format_bytes(bytes_val: int) -> str:
    """Format bytes to human-readable string."""
    if bytes_val == 0:
        return "0 B"
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    i = 0
    while bytes_val >= 1024 and i < len(units) - 1:
        bytes_val /= 1024
        i += 1
    return f"{bytes_val:.2f} {units[i]}"


if __name__ == '__main__':
    # Test report generation
    pdf_bytes = generate_transfer_report(
        transfer_id="test_001",
        filename="test_file.bin",
        file_size=102400,
        protocol_mode="selective_repeat",
        window_size=10,
        packet_loss_rate=0.1,
        congestion_enabled=True,
        client_stats={
            'packets_sent': 100,
            'acks_received': 98,
            'retransmissions': 12,
            'timeouts': 5,
            'bytes_sent': 102400,
            'duration': 2.5,
            'throughput_mbps': 0.327,
            'avg_rtt': 0.05
        },
        server_stats={
            'packets_received': 98,
            'acks_sent': 98,
            'checksum_errors': 0,
            'out_of_order': 5,
            'duplicate_packets': 3,
            'bytes_received': 100352
        },
        congestion_stats={
            'cwnd': 15.5,
            'ssthresh': 32,
            'state': 'congestion_avoidance',
            'srtt': 0.05,
            'rto': 0.25
        }
    )
    
    with open('test_report.pdf', 'wb') as f:
        f.write(pdf_bytes)
    print("Test report generated: test_report.pdf")
