import React from 'react';
import { Play, Square, Upload, Server, Settings, RefreshCw } from 'lucide-react';

function Controls({
  config,
  setConfig,
  serverStatus,
  transferring,
  onStartServer,
  onStopServer,
  onStartTransfer,
  onRunDemo,
  selectedFile,
  setSelectedFile
}) {
  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  };
  
  const protocols = [
    { id: 'stop_wait', name: 'Stop-and-Wait', desc: 'Simple, one packet at a time' },
    { id: 'go_back_n', name: 'Go-Back-N', desc: 'Cumulative ACKs, single timer' },
    { id: 'selective_repeat', name: 'Selective Repeat', desc: 'Individual ACKs, buffering' }
  ];
  
  return (
    <div className="space-y-4">
      {/* Server Control */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
        <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-3 flex items-center">
          <Server className="h-4 w-4 mr-2" />
          Server Control
        </h3>
        
        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Port</label>
            <input
              type="number"
              value={config.serverPort}
              onChange={(e) => setConfig({ ...config, serverPort: parseInt(e.target.value) })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              disabled={serverStatus?.running}
            />
          </div>
          
          <button
            onClick={serverStatus?.running ? onStopServer : onStartServer}
            className={`w-full flex items-center justify-center px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              serverStatus?.running
                ? 'bg-red-500 hover:bg-red-600 text-white'
                : 'bg-green-500 hover:bg-green-600 text-white'
            }`}
          >
            {serverStatus?.running ? (
              <>
                <Square className="h-4 w-4 mr-2" />
                Stop Server
              </>
            ) : (
              <>
                <Play className="h-4 w-4 mr-2" />
                Start Server
              </>
            )}
          </button>
        </div>
      </div>
      
      {/* Protocol Selection */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
        <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-3 flex items-center">
          <Settings className="h-4 w-4 mr-2" />
          Protocol
        </h3>
        
        <div className="space-y-2">
          {protocols.map((protocol) => (
            <label
              key={protocol.id}
              className={`flex items-start p-3 rounded-md cursor-pointer transition-colors border ${
                config.protocol === protocol.id
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-gray-200 hover:bg-gray-50'
              }`}
            >
              <input
                type="radio"
                name="protocol"
                value={protocol.id}
                checked={config.protocol === protocol.id}
                onChange={(e) => setConfig({ ...config, protocol: e.target.value })}
                className="mt-0.5"
              />
              <div className="ml-3">
                <div className="text-sm font-medium text-gray-900">{protocol.name}</div>
                <div className="text-xs text-gray-500">{protocol.desc}</div>
              </div>
            </label>
          ))}
        </div>
      </div>
      
      {/* Parameters */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
        <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-3">
          Parameters
        </h3>
        
        <div className="space-y-4">
          <div>
            <label className="flex justify-between text-xs font-medium text-gray-500 mb-1">
              <span>Window Size</span>
              <span className="text-blue-600">{config.windowSize}</span>
            </label>
            <input
              type="range"
              min="1"
              max="50"
              value={config.windowSize}
              onChange={(e) => setConfig({ ...config, windowSize: parseInt(e.target.value) })}
              className="w-full"
            />
          </div>
          
          <div>
            <label className="flex justify-between text-xs font-medium text-gray-500 mb-1">
              <span>Timeout (s)</span>
              <span className="text-blue-600">{config.timeout.toFixed(1)}</span>
            </label>
            <input
              type="range"
              min="0.1"
              max="5"
              step="0.1"
              value={config.timeout}
              onChange={(e) => setConfig({ ...config, timeout: parseFloat(e.target.value) })}
              className="w-full"
            />
          </div>
          
          <div>
            <label className="flex justify-between text-xs font-medium text-gray-500 mb-1">
              <span>Packet Loss %</span>
              <span className="text-orange-600">{(config.packetLossRate * 100).toFixed(0)}%</span>
            </label>
            <input
              type="range"
              min="0"
              max="0.5"
              step="0.01"
              value={config.packetLossRate}
              onChange={(e) => setConfig({ ...config, packetLossRate: parseFloat(e.target.value) })}
              className="w-full"
            />
          </div>
          
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-gray-500">Congestion Control</span>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={config.congestionEnabled}
                onChange={(e) => setConfig({ ...config, congestionEnabled: e.target.checked })}
                className="sr-only peer"
              />
              <div className="w-9 h-5 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600"></div>
            </label>
          </div>
        </div>
      </div>
      
      {/* Transfer Control */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
        <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-3 flex items-center">
          <Upload className="h-4 w-4 mr-2" />
          Transfer
        </h3>
        
        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Select File</label>
            <input
              type="file"
              onChange={handleFileChange}
              className="w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
            />
            {selectedFile && (
              <p className="text-xs text-gray-500 mt-1">
                {selectedFile.name} ({formatBytes(selectedFile.size)})
              </p>
            )}
          </div>
          
          <button
            onClick={onStartTransfer}
            disabled={transferring || !serverStatus?.running}
            className={`w-full flex items-center justify-center px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              transferring || !serverStatus?.running
                ? 'bg-gray-300 cursor-not-allowed text-gray-500'
                : 'bg-blue-500 hover:bg-blue-600 text-white'
            }`}
          >
            {transferring ? (
              <>
                <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                Transferring...
              </>
            ) : (
              <>
                <Upload className="h-4 w-4 mr-2" />
                Start Transfer
              </>
            )}
          </button>
          
          <button
            onClick={onRunDemo}
            disabled={transferring}
            className="w-full flex items-center justify-center px-4 py-2 rounded-md text-sm font-medium bg-purple-500 hover:bg-purple-600 text-white transition-colors disabled:bg-gray-300 disabled:cursor-not-allowed"
          >
            <Play className="h-4 w-4 mr-2" />
            Run Demo
          </button>
        </div>
      </div>
    </div>
  );
}

function formatBytes(bytes) {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

export default Controls;
