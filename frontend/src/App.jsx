import React, { useState, useEffect, useCallback } from 'react';
import Dashboard from './components/Dashboard';
import Controls from './components/Controls';
import Graphs from './components/Graphs';
import WindowView from './components/WindowView';
import EventLog from './components/EventLog';
import { useWebSocket } from './hooks/useWebSocket';
import { useApi } from './hooks/useApi';

function App() {
  // Connection state
  const [serverStatus, setServerStatus] = useState({ running: false });
  const [clientStatus, setClientStatus] = useState({ state: 'idle' });
  
  // Configuration
  const [config, setConfig] = useState({
    protocol: 'selective_repeat',
    windowSize: 10,
    timeout: 1.0,
    packetLossRate: 0.1,
    congestionEnabled: true,
    serverHost: 'localhost',
    serverPort: 5000
  });
  
  // Transfer state
  const [transferring, setTransferring] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  
  // Real-time data
  const [throughputHistory, setThroughputHistory] = useState([]);
  const [congestionHistory, setCongestionHistory] = useState([]);
  const [events, setEvents] = useState([]);
  const [windowState, setWindowState] = useState({ base: 0, nextSeq: 0, windowSize: 10, packets: [] });
  
  // API hooks
  const api = useApi();
  
  // WebSocket connection for real-time updates
  const onMessage = useCallback((data) => {
    if (data.type === 'stats_update') {
      setServerStatus(data.server || { running: false });
      setClientStatus(data.client || { state: 'idle' });
      
      // Update throughput history
      if (data.client?.stats?.throughput_mbps !== undefined) {
        setThroughputHistory(prev => {
          const newData = [...prev, {
            time: Date.now(),
            throughput: data.client.stats.throughput_mbps,
            packets: data.client.stats.packets_sent || 0,
            retransmissions: data.client.stats.retransmissions || 0
          }].slice(-100);
          return newData;
        });
      }
      
      // Update congestion history
      if (data.client?.congestion) {
        setCongestionHistory(prev => {
          const newData = [...prev, {
            time: Date.now(),
            cwnd: data.client.congestion.cwnd,
            ssthresh: data.client.congestion.ssthresh,
            rtt: data.client.congestion.srtt * 1000 // Convert to ms
          }].slice(-100);
          return newData;
        });
      }
      
      // Update window state
      if (data.client?.base !== undefined) {
        setWindowState({
          base: data.client.base,
          nextSeq: data.client.next_seq,
          windowSize: data.client.window_size || config.windowSize,
          totalChunks: data.client.total_chunks
        });
      }
    }
  }, [config.windowSize]);
  
  const { connected, connect, disconnect } = useWebSocket(onMessage);
  
  // Connect WebSocket on mount
  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);
  
  // Fetch initial status
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const server = await api.get('/api/server/status');
        const client = await api.get('/api/client/status');
        setServerStatus(server);
        setClientStatus(client);
      } catch (error) {
        console.error('Failed to fetch status:', error);
      }
    };
    
    fetchStatus();
    const interval = setInterval(fetchStatus, 2000);
    return () => clearInterval(interval);
  }, []);
  
  // Fetch events periodically
  useEffect(() => {
    const fetchEvents = async () => {
      try {
        const serverEvents = await api.get('/api/server/events?limit=50');
        const clientEvents = await api.get('/api/client/events?limit=50');
        
        const allEvents = [
          ...(serverEvents.events || []).map(e => ({ ...e, source: 'server' })),
          ...(clientEvents.events || []).map(e => ({ ...e, source: 'client' }))
        ].sort((a, b) => b.timestamp - a.timestamp).slice(0, 100);
        
        setEvents(allEvents);
      } catch (error) {
        // Ignore errors for events
      }
    };
    
    const interval = setInterval(fetchEvents, 500);
    return () => clearInterval(interval);
  }, []);
  
  // Handlers
  const handleStartServer = async () => {
    try {
      await api.post('/api/server/start', {
        host: '0.0.0.0',
        port: config.serverPort,
        packet_loss_rate: config.packetLossRate,
        protocol_mode: config.protocol,
        window_size: config.windowSize
      });
      setServerStatus(prev => ({ ...prev, running: true }));
    } catch (error) {
      console.error('Failed to start server:', error);
      alert('Failed to start server: ' + error.message);
    }
  };
  
  const handleStopServer = async () => {
    try {
      await api.post('/api/server/stop');
      setServerStatus(prev => ({ ...prev, running: false }));
    } catch (error) {
      console.error('Failed to stop server:', error);
    }
  };
  
  const handleStartTransfer = async () => {
    if (!serverStatus.running) {
      alert('Please start the server first');
      return;
    }
    
    setTransferring(true);
    setThroughputHistory([]);
    setCongestionHistory([]);
    
    try {
      // Configure client
      await api.post('/api/client/configure', {
        server_host: config.serverHost,
        server_port: config.serverPort,
        protocol_mode: config.protocol,
        window_size: config.windowSize,
        timeout: config.timeout,
        packet_loss_rate: config.packetLossRate,
        congestion_enabled: config.congestionEnabled
      });
      
      // Start transfer
      if (selectedFile) {
        const formData = new FormData();
        formData.append('file', selectedFile);
        
        const response = await fetch('/api/client/transfer/file', {
          method: 'POST',
          body: formData
        });
        
        if (!response.ok) {
          throw new Error('Transfer failed');
        }
      } else {
        // Demo transfer with random data
        await api.post('/api/client/transfer/data', {
          filename: 'demo_data',
          protocol_mode: config.protocol,
          window_size: config.windowSize,
          packet_loss_rate: config.packetLossRate,
          congestion_enabled: config.congestionEnabled
        });
      }
    } catch (error) {
      console.error('Transfer error:', error);
      alert('Transfer failed: ' + error.message);
    } finally {
      setTransferring(false);
    }
  };
  
  const handleRunDemo = async () => {
    if (!serverStatus.running) {
      await handleStartServer();
      await new Promise(resolve => setTimeout(resolve, 500));
    }
    
    setTransferring(true);
    setThroughputHistory([]);
    setCongestionHistory([]);
    
    try {
      const result = await api.post('/api/demo/run', null, {
        protocol: config.protocol,
        window_size: config.windowSize,
        packet_loss: config.packetLossRate,
        data_size: 50000
      });
      
      console.log('Demo result:', result);
    } catch (error) {
      console.error('Demo error:', error);
    } finally {
      setTransferring(false);
    }
  };
  
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">
                Reliable Data Transfer Protocol
              </h1>
              <p className="text-sm text-gray-500 mt-1">
                TCP-like protocol over UDP • Visual Simulator
              </p>
            </div>
            <div className="flex items-center space-x-4">
              <div className={`flex items-center space-x-2 px-3 py-1 rounded-full ${
                connected ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
              }`}>
                <div className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
                <span className="text-sm font-medium">
                  {connected ? 'Connected' : 'Disconnected'}
                </span>
              </div>
            </div>
          </div>
        </div>
      </header>
      
      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-6 sm:px-6 lg:px-8">
        <div className="grid grid-cols-12 gap-6">
          {/* Left Column - Controls */}
          <div className="col-span-12 lg:col-span-3">
            <Controls
              config={config}
              setConfig={setConfig}
              serverStatus={serverStatus}
              transferring={transferring}
              onStartServer={handleStartServer}
              onStopServer={handleStopServer}
              onStartTransfer={handleStartTransfer}
              onRunDemo={handleRunDemo}
              selectedFile={selectedFile}
              setSelectedFile={setSelectedFile}
            />
          </div>
          
          {/* Center Column - Dashboard & Graphs */}
          <div className="col-span-12 lg:col-span-6 space-y-6">
            <Dashboard
              serverStatus={serverStatus}
              clientStatus={clientStatus}
              config={config}
            />
            
            <WindowView
              windowState={windowState}
              protocol={config.protocol}
            />
            
            <Graphs
              throughputHistory={throughputHistory}
              congestionHistory={congestionHistory}
              serverStats={serverStatus.stats}
              clientStats={clientStatus.stats}
            />
          </div>
          
          {/* Right Column - Event Log */}
          <div className="col-span-12 lg:col-span-3">
            <EventLog events={events} />
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
