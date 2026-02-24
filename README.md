# 🧠 Reliable Data Transfer Protocol (TCP-like) over UDP

A complete implementation of a custom Reliable Data Transfer Protocol that recreates core ideas of TCP on top of UDP, featuring a visual web dashboard for real-time monitoring and simulation.

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Usage](#usage)
- [Protocol Details](#protocol-details)
- [API Reference](#api-reference)
- [Project Structure](#project-structure)

## 🎯 Overview

This project implements a reliable data transfer protocol from scratch, demonstrating:

- **Stop-and-Wait**: Simple protocol sending one packet at a time
- **Go-Back-N**: Sliding window with cumulative ACKs
- **Selective Repeat**: Advanced sliding window with individual ACKs and buffering
- **TCP-like Congestion Control**: Slow start, congestion avoidance, and timeout handling

## ✨ Features

### Backend Protocol Engine
- Custom packet structure with header (seq, ack, flags, window, checksum)
- UDP socket communication with reliability layer
- Three configurable reliability algorithms
- Packet loss simulation for testing
- TCP-like congestion control (slow start, congestion avoidance)

### Web Dashboard (React)
- Real-time statistics display
- Live window movement animation
- Throughput and RTT graphs
- Congestion window visualization
- Event log with packet tracking
- File upload and transfer

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (React)                          │
│  ┌──────────┐  ┌──────────┐  ┌─────────┐  ┌─────────────┐  │
│  │Dashboard │  │ Controls │  │ Graphs  │  │ WindowView  │  │
│  └────┬─────┘  └────┬─────┘  └────┬────┘  └──────┬──────┘  │
│       │             │             │              │          │
│       └─────────────┴──────┬──────┴──────────────┘          │
│                            │                                 │
│                     WebSocket / REST API                     │
└────────────────────────────┼────────────────────────────────┘
                             │
┌────────────────────────────┼────────────────────────────────┐
│                    Backend (FastAPI)                         │
│                            │                                 │
│  ┌─────────────────────────┴─────────────────────────────┐  │
│  │                      API Layer                         │  │
│  └─────────────────────────┬─────────────────────────────┘  │
│                            │                                 │
│  ┌───────────┐  ┌──────────┴───────────┐  ┌─────────────┐  │
│  │ UDPServer │  │    Reliability       │  │  UDPClient  │  │
│  │           │  │  ┌───────────────┐   │  │             │  │
│  │  • Listen │  │  │ Stop-and-Wait│   │  │ • Chunking  │  │
│  │  • Verify │  │  │ Go-Back-N    │   │  │ • Windowing │  │
│  │  • ACK    │  │  │ Selective Rep│   │  │ • Timeout   │  │
│  └───────────┘  │  └───────────────┘   │  └─────────────┘  │
│                 │                      │                    │
│                 │  ┌───────────────┐   │                    │
│                 │  │  Congestion   │   │                    │
│                 │  │   Control     │   │                    │
│                 │  └───────────────┘   │                    │
│                 └──────────────────────┘                    │
└─────────────────────────────────────────────────────────────┘
                             │
                        UDP Sockets
```

## 📦 Installation

### Prerequisites
- Python 3.8+
- Node.js 18+
- npm or yarn

### Backend Setup

```bash
cd backend

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install
```

## 🚀 Usage

### Starting the Backend

```bash
cd backend
python -m uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000`

### Starting the Frontend

```bash
cd frontend
npm run dev
```

The dashboard will be available at `http://localhost:3000`

### Running a Demo Transfer

1. Open the dashboard at `http://localhost:3000`
2. Click "Start Server" to start the UDP server
3. Select protocol type (Stop-and-Wait, Go-Back-N, or Selective Repeat)
4. Adjust window size, timeout, and packet loss rate
5. Click "Run Demo" to start a demo transfer
6. Watch the real-time visualization!

## 📜 Protocol Details

### Packet Structure

```
| Seq No (4B) | ACK No (4B) | Flags (1B) | Window (2B) | Checksum (2B) | Data (≤1024B) |
```

**Flags:**
- `SYN (0x01)`: Connection establishment
- `ACK (0x02)`: Acknowledgment
- `FIN (0x04)`: Connection termination
- `DATA (0x08)`: Data packet

### Reliability Algorithms

#### Stop-and-Wait
```
Sender                    Receiver
   |                         |
   |----[Packet 0]---------->|
   |                         |
   |<---------[ACK 1]--------|
   |                         |
   |----[Packet 1]---------->|
   |                         |
   |<---------[ACK 2]--------|
```

- Send one packet
- Wait for ACK
- If timeout → retransmit

#### Go-Back-N
```
Window: [0][1][2][3] | [4][5]...
            ↑
          base

- Send up to N packets
- Cumulative ACKs
- On loss: retransmit ALL from base
```

#### Selective Repeat
```
Sender:   [0:✓][1:?][2:✓][3:?] | [4][5]
Receiver: [0:✓][1:-][2:✓][3:✓] | waiting

- Individual ACKs
- Receiver buffers out-of-order
- Only retransmit lost packets
```

### Congestion Control

```python
# Slow Start (cwnd < ssthresh)
cwnd = cwnd * 2  # Double every RTT

# Congestion Avoidance (cwnd >= ssthresh)
cwnd = cwnd + 1  # Linear increase per RTT

# On Timeout
ssthresh = cwnd / 2
cwnd = 1  # Back to slow start
```

## 📚 API Reference

### Server Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/server/start` | Start UDP server |
| POST | `/api/server/stop` | Stop UDP server |
| GET | `/api/server/status` | Get server status |
| POST | `/api/server/reset` | Reset server state |
| GET | `/api/server/events` | Get event log |

### Client Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/client/configure` | Configure client |
| POST | `/api/client/transfer/file` | Upload and transfer file |
| POST | `/api/client/transfer/data` | Transfer raw data |
| GET | `/api/client/status` | Get client status |
| GET | `/api/client/events` | Get event log |

### WebSocket

Connect to `/ws` for real-time stats updates.

## 📁 Project Structure

```
rudp-project/
│
├── backend/
│   ├── __init__.py
│   ├── packet.py          # Packet structure definition
│   ├── server.py          # UDP server implementation
│   ├── client.py          # UDP client implementation
│   ├── congestion.py      # Congestion control
│   ├── api.py             # FastAPI REST/WebSocket API
│   ├── requirements.txt   # Python dependencies
│   │
│   └── reliability/
│       ├── __init__.py
│       ├── stop_wait.py       # Stop-and-Wait protocol
│       ├── go_back_n.py       # Go-Back-N protocol
│       └── selective_repeat.py # Selective Repeat protocol
│
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   │
│   └── src/
│       ├── main.jsx
│       ├── App.jsx            # Main application
│       ├── index.css          # Global styles
│       │
│       ├── components/
│       │   ├── Dashboard.jsx   # Stats display
│       │   ├── Controls.jsx    # Protocol settings
│       │   ├── Graphs.jsx      # Throughput/congestion charts
│       │   ├── WindowView.jsx  # Sliding window animation
│       │   └── EventLog.jsx    # Real-time event log
│       │
│       └── hooks/
│           ├── useWebSocket.js # WebSocket hook
│           └── useApi.js       # API client hook
│
└── README.md
```

## 🔧 Configuration Options

### Protocol Parameters

| Parameter | Range | Default | Description |
|-----------|-------|---------|-------------|
| Window Size | 1-100 | 10 | Sliding window size |
| Timeout | 0.1s-10s | 1s | Retransmission timeout |
| Packet Loss | 0%-50% | 10% | Simulated packet loss rate |
| Congestion Control | on/off | on | Enable TCP-like congestion control |

## 📊 Dashboard Features

- **Real-Time Stats**: Packets sent, ACKs received, retransmissions, throughput
- **Window Animation**: Visual representation of sliding window movement
- **Graphs**: 
  - Throughput over time
  - CWND and SSThresh evolution
  - RTT measurements
- **Event Log**: Detailed packet-by-packet history

## 🎓 Educational Value

This project demonstrates:

1. **Network Protocols**: How reliable transfer works over unreliable networks
2. **Sliding Window**: Efficient use of network bandwidth
3. **Error Recovery**: Handling packet loss with different strategies
4. **Congestion Control**: Preventing network congestion
5. **Full-Stack Development**: React frontend + Python backend
6. **Real-Time Communication**: WebSocket for live updates

## 📝 License

MIT License - feel free to use for educational purposes!

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.
