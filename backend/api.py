"""
FastAPI Backend API for Reliable Data Transfer Protocol

Provides REST API and WebSocket endpoints for:
- Starting/stopping server
- File transfers
- Real-time statistics
- Configuration management
"""

import os
import sys
import asyncio
import threading
import time
import base64
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server import UDPServer
from client import UDPClient, TransferState
from packet import Packet
from report import generate_transfer_report

# FastAPI app
app = FastAPI(
    title="Reliable Data Transfer Protocol API",
    description="Custom TCP-like protocol over UDP with web interface",
    version="1.0.0"
)

# CORS middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
udp_server: Optional[UDPServer] = None
udp_client: Optional[UDPClient] = None
transfer_history: List[dict] = []

# WebSocket connections for real-time updates
connected_clients: List[WebSocket] = []

# Upload/download directories
UPLOAD_DIR = Path("./uploads")
RECEIVED_DIR = Path("./received_files")
UPLOAD_DIR.mkdir(exist_ok=True)
RECEIVED_DIR.mkdir(exist_ok=True)


# ============ Pydantic Models ============

class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 5000
    packet_loss_rate: float = Field(0.0, ge=0.0, le=1.0)
    protocol_mode: str = "selective_repeat"
    window_size: int = Field(10, ge=1, le=100)


class ClientConfig(BaseModel):
    server_host: str = "localhost"
    server_port: int = 5000
    protocol_mode: str = "selective_repeat"
    window_size: int = Field(10, ge=1, le=100)
    timeout: float = Field(1.0, ge=0.1, le=10.0)
    packet_loss_rate: float = Field(0.0, ge=0.0, le=1.0)
    congestion_enabled: bool = True


class TransferRequest(BaseModel):
    filename: str
    data_base64: Optional[str] = None
    protocol_mode: str = "selective_repeat"
    window_size: int = 10
    packet_loss_rate: float = 0.0
    congestion_enabled: bool = True


class TransferResponse(BaseModel):
    success: bool
    message: str
    transfer_id: str
    stats: Optional[dict] = None


# ============ WebSocket Manager ============

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()


# ============ Background Task for Stats Broadcasting ============

async def broadcast_stats():
    """Broadcast stats to all connected WebSocket clients."""
    while True:
        try:
            stats = {
                "type": "stats_update",
                "timestamp": time.time(),
                "server": get_server_status(),
                "client": get_client_status()
            }
            await manager.broadcast(stats)
        except Exception:
            pass
        await asyncio.sleep(0.1)  # 10 Hz update rate


def get_server_status() -> dict:
    """Get current server status."""
    global udp_server
    if udp_server:
        return udp_server.get_status()
    return {"running": False}


def get_client_status() -> dict:
    """Get current client status."""
    global udp_client
    if udp_client:
        return udp_client.get_status()
    return {"state": "idle"}


# ============ Server Endpoints ============

@app.post("/api/server/start", tags=["Server"])
async def start_server(config: ServerConfig):
    """Start the UDP server."""
    global udp_server
    
    if udp_server and udp_server.running:
        raise HTTPException(status_code=400, detail="Server already running")
    
    try:
        udp_server = UDPServer(
            host=config.host,
            port=config.port,
            packet_loss_rate=config.packet_loss_rate,
            output_dir=str(RECEIVED_DIR)
        )
        udp_server.set_protocol_mode(config.protocol_mode, config.window_size)
        udp_server.start()
        
        return {"success": True, "message": f"Server started on {config.host}:{config.port}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/server/stop", tags=["Server"])
async def stop_server():
    """Stop the UDP server."""
    global udp_server
    
    if not udp_server or not udp_server.running:
        raise HTTPException(status_code=400, detail="Server not running")
    
    udp_server.stop()
    return {"success": True, "message": "Server stopped"}


@app.get("/api/server/status", tags=["Server"])
async def server_status():
    """Get server status."""
    return get_server_status()


@app.post("/api/server/reset", tags=["Server"])
async def reset_server():
    """Reset server state."""
    global udp_server
    
    if udp_server:
        udp_server.reset()
        return {"success": True, "message": "Server reset"}
    return {"success": False, "message": "Server not initialized"}


@app.get("/api/server/events", tags=["Server"])
async def get_server_events(limit: int = 100):
    """Get server event log."""
    global udp_server
    
    if udp_server:
        return {"events": udp_server.event_log[-limit:]}
    return {"events": []}


# ============ Client Endpoints ============

@app.post("/api/client/configure", tags=["Client"])
async def configure_client(config: ClientConfig):
    """Configure the UDP client."""
    global udp_client
    
    udp_client = UDPClient(
        server_host=config.server_host,
        server_port=config.server_port,
        timeout=config.timeout,
        packet_loss_rate=config.packet_loss_rate
    )
    udp_client.configure(
        protocol_mode=config.protocol_mode,
        window_size=config.window_size,
        timeout=config.timeout,
        packet_loss_rate=config.packet_loss_rate,
        congestion_enabled=config.congestion_enabled
    )
    
    return {"success": True, "message": "Client configured"}


@app.post("/api/client/transfer/file", tags=["Client"])
async def transfer_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """Upload and transfer a file."""
    global udp_client, transfer_history
    
    if not udp_client:
        raise HTTPException(status_code=400, detail="Client not configured")
    
    # Save uploaded file
    file_path = UPLOAD_DIR / file.filename
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)
    
    # Start transfer in background
    transfer_id = f"transfer_{int(time.time())}"
    
    def run_transfer():
        success = udp_client.send_file(str(file_path))
        transfer_history.append({
            "id": transfer_id,
            "filename": file.filename,
            "size": len(content),
            "success": success,
            "stats": udp_client.stats.to_dict(),
            "timestamp": datetime.now().isoformat()
        })
    
    background_tasks.add_task(run_transfer)
    
    return TransferResponse(
        success=True,
        message=f"Transfer started for {file.filename}",
        transfer_id=transfer_id
    )


@app.post("/api/client/transfer/data", tags=["Client"])
async def transfer_data(request: TransferRequest):
    """Transfer raw data."""
    global udp_client
    
    if not udp_client:
        # Auto-configure client
        udp_client = UDPClient()
    
    udp_client.configure(
        protocol_mode=request.protocol_mode,
        window_size=request.window_size,
        timeout=1.0,
        packet_loss_rate=request.packet_loss_rate,
        congestion_enabled=request.congestion_enabled
    )
    
    # Decode data
    if request.data_base64:
        data = base64.b64decode(request.data_base64)
    else:
        # Generate test data
        data = b"Test data " * 1000
    
    success = udp_client.send_data(data)
    
    return TransferResponse(
        success=success,
        message="Transfer complete" if success else "Transfer failed",
        transfer_id=f"transfer_{int(time.time())}",
        stats=udp_client.stats.to_dict()
    )


@app.get("/api/client/status", tags=["Client"])
async def client_status():
    """Get client status."""
    return get_client_status()


@app.get("/api/client/events", tags=["Client"])
async def get_client_events(limit: int = 100):
    """Get client event log."""
    global udp_client
    
    if udp_client:
        return {"events": udp_client.event_log[-limit:]}
    return {"events": []}


@app.post("/api/client/close", tags=["Client"])
async def close_client():
    """Close the client connection."""
    global udp_client
    
    if udp_client:
        udp_client.close()
        return {"success": True, "message": "Client closed"}
    return {"success": False, "message": "Client not initialized"}


# ============ Transfer History ============

@app.get("/api/transfers", tags=["Transfers"])
async def get_transfers():
    """Get transfer history."""
    return {"transfers": transfer_history}


@app.get("/api/transfers/{transfer_id}", tags=["Transfers"])
async def get_transfer(transfer_id: str):
    """Get specific transfer details."""
    for transfer in transfer_history:
        if transfer["id"] == transfer_id:
            return transfer
    raise HTTPException(status_code=404, detail="Transfer not found")


@app.get("/api/report/download", tags=["Reports"])
async def download_report(
    filename: str = "transfer",
    file_size: int = 0
):
    """Generate and download a detailed PDF transfer analysis report."""
    global udp_server, udp_client
    
    # Get current stats
    client_stats = {}
    server_stats = {}
    congestion_stats = {}
    config = {
        'protocol_mode': 'selective_repeat',
        'window_size': 10,
        'packet_loss_rate': 0.1,
        'congestion_enabled': True
    }
    
    if udp_client:
        client_stats = udp_client.stats.to_dict() if hasattr(udp_client, 'stats') else {}
        congestion_stats = udp_client.congestion.get_stats_summary() if hasattr(udp_client, 'congestion') else {}
        config = {
            'protocol_mode': udp_client.protocol_mode,
            'window_size': udp_client.window_size,
            'packet_loss_rate': udp_client.packet_loss_rate,
            'congestion_enabled': udp_client.congestion.enabled if hasattr(udp_client, 'congestion') else True
        }
        if file_size == 0:
            file_size = client_stats.get('bytes_sent', 0)
    
    if udp_server:
        server_stats = udp_server.stats.to_dict() if hasattr(udp_server, 'stats') else {}
    
    # Generate PDF report
    transfer_id = f"transfer_{int(time.time())}"
    
    try:
        pdf_bytes = generate_transfer_report(
            transfer_id=transfer_id,
            filename=filename,
            file_size=file_size,
            protocol_mode=config['protocol_mode'],
            window_size=config['window_size'],
            packet_loss_rate=config['packet_loss_rate'],
            congestion_enabled=config['congestion_enabled'],
            client_stats=client_stats,
            server_stats=server_stats,
            congestion_stats=congestion_stats
        )
        
        # Return PDF as downloadable file
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=transfer_report_{transfer_id}.pdf"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")


@app.post("/api/report/generate", tags=["Reports"])
async def generate_report_from_data(
    filename: str = "transfer",
    file_size: int = 0,
    protocol_mode: str = "selective_repeat",
    window_size: int = 10,
    packet_loss_rate: float = 0.1,
    congestion_enabled: bool = True
):
    """Generate a report using provided or current transfer data."""
    global udp_server, udp_client
    
    # Get current stats
    client_stats = udp_client.stats.to_dict() if udp_client and hasattr(udp_client, 'stats') else {}
    server_stats = udp_server.stats.to_dict() if udp_server and hasattr(udp_server, 'stats') else {}
    congestion_stats = udp_client.congestion.get_stats_summary() if udp_client and hasattr(udp_client, 'congestion') else {}
    
    if file_size == 0:
        file_size = client_stats.get('bytes_sent', 0)
    
    transfer_id = f"transfer_{int(time.time())}"
    
    try:
        pdf_bytes = generate_transfer_report(
            transfer_id=transfer_id,
            filename=filename,
            file_size=file_size,
            protocol_mode=protocol_mode,
            window_size=window_size,
            packet_loss_rate=packet_loss_rate,
            congestion_enabled=congestion_enabled,
            client_stats=client_stats,
            server_stats=server_stats,
            congestion_stats=congestion_stats
        )
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=transfer_report_{transfer_id}.pdf"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")


# ============ Files ============

@app.get("/api/files/received", tags=["Files"])
async def list_received_files():
    """List received files."""
    files = []
    for f in RECEIVED_DIR.iterdir():
        if f.is_file():
            files.append({
                "name": f.name,
                "size": f.stat().st_size,
                "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat()
            })
    return {"files": files}


@app.get("/api/files/download/{filename}", tags=["Files"])
async def download_file(filename: str):
    """Download a received file."""
    file_path = RECEIVED_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(file_path), filename=filename)


# ============ WebSocket ============

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await manager.connect(websocket)
    
    try:
        while True:
            # Send stats every 100ms
            stats = {
                "type": "stats_update",
                "timestamp": time.time(),
                "server": get_server_status(),
                "client": get_client_status()
            }
            await websocket.send_json(stats)
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


# ============ Demo/Test Endpoints ============

@app.post("/api/demo/run", tags=["Demo"])
async def run_demo(
    protocol: str = "selective_repeat",
    window_size: int = 10,
    packet_loss: float = 0.1,
    data_size: int = 10000
):
    """Run a demo transfer to see the protocol in action."""
    global udp_server, udp_client
    
    # Start server if not running
    if not udp_server or not udp_server.running:
        udp_server = UDPServer(port=5000, packet_loss_rate=packet_loss)
        udp_server.set_protocol_mode(protocol, window_size)
        udp_server.start()
        await asyncio.sleep(0.5)  # Wait for server to start
    
    # Configure and run client
    udp_client = UDPClient(packet_loss_rate=packet_loss)
    udp_client.configure(
        protocol_mode=protocol,
        window_size=window_size,
        timeout=1.0,
        packet_loss_rate=packet_loss,
        congestion_enabled=True
    )
    
    # Generate test data
    test_data = os.urandom(data_size)
    
    # Run transfer
    success = udp_client.send_data(test_data)
    
    return {
        "success": success,
        "protocol": protocol,
        "window_size": window_size,
        "packet_loss": packet_loss,
        "data_size": data_size,
        "client_stats": udp_client.stats.to_dict(),
        "server_stats": udp_server.stats.to_dict()
    }


@app.get("/api/protocols", tags=["Info"])
async def get_protocol_info():
    """Get information about available protocols."""
    return {
        "protocols": [
            {
                "id": "stop_wait",
                "name": "Stop-and-Wait",
                "description": "Simple protocol - send one packet, wait for ACK",
                "pros": ["Simple implementation", "Low buffer requirements"],
                "cons": ["Poor utilization", "High latency"]
            },
            {
                "id": "go_back_n",
                "name": "Go-Back-N",
                "description": "Sliding window with cumulative ACKs",
                "pros": ["Better utilization", "Simple receiver"],
                "cons": ["Retransmits all on loss", "Wastes bandwidth"]
            },
            {
                "id": "selective_repeat",
                "name": "Selective Repeat",
                "description": "Sliding window with individual ACKs and buffering",
                "pros": ["Best efficiency", "Only retransmits lost"],
                "cons": ["Complex implementation", "Higher buffer requirements"]
            }
        ]
    }


# ============ Health Check ============

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "server_running": udp_server.running if udp_server else False,
        "client_state": udp_client.state.value if udp_client else "idle"
    }


# ============ Run Server ============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
