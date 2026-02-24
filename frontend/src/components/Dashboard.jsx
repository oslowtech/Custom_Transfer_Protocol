import React from 'react';
import { Activity, Server, Send, AlertTriangle, CheckCircle, Clock, Zap } from 'lucide-react';

function Dashboard({ serverStatus, clientStatus, config }) {
  const serverStats = serverStatus?.stats || {};
  const clientStats = clientStatus?.stats || {};
  const congestion = clientStatus?.congestion || {};
  
  const StatCard = ({ title, value, icon: Icon, color, subtitle }) => (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-500">{title}</p>
          <p className={`text-2xl font-bold ${color || 'text-gray-900'}`}>
            {value}
          </p>
          {subtitle && (
            <p className="text-xs text-gray-400 mt-1">{subtitle}</p>
          )}
        </div>
        {Icon && (
          <div className={`p-3 rounded-full ${color?.replace('text-', 'bg-').replace('600', '100').replace('500', '100') || 'bg-gray-100'}`}>
            <Icon className={`h-6 w-6 ${color || 'text-gray-600'}`} />
          </div>
        )}
      </div>
    </div>
  );
  
  return (
    <div className="space-y-4">
      {/* Status Bar */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2">
              <Server className={`h-5 w-5 ${serverStatus?.running ? 'text-green-500' : 'text-gray-400'}`} />
              <span className="text-sm font-medium">
                Server: {serverStatus?.running ? 'Running' : 'Stopped'}
              </span>
            </div>
            <div className="flex items-center space-x-2">
              <Activity className={`h-5 w-5 ${clientStatus?.state === 'transferring' ? 'text-blue-500 animate-pulse' : 'text-gray-400'}`} />
              <span className="text-sm font-medium">
                Client: {clientStatus?.state || 'idle'}
              </span>
            </div>
          </div>
          <div className="flex items-center space-x-2 text-sm text-gray-500">
            <span className="px-2 py-1 bg-gray-100 rounded">
              {config.protocol.replace('_', ' ').toUpperCase()}
            </span>
            <span className="px-2 py-1 bg-gray-100 rounded">
              Window: {config.windowSize}
            </span>
            <span className="px-2 py-1 bg-gray-100 rounded">
              Loss: {(config.packetLossRate * 100).toFixed(0)}%
            </span>
          </div>
        </div>
      </div>
      
      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          title="Packets Sent"
          value={clientStats.packets_sent || 0}
          icon={Send}
          color="text-blue-600"
        />
        <StatCard
          title="ACKs Received"
          value={clientStats.acks_received || 0}
          icon={CheckCircle}
          color="text-green-600"
        />
        <StatCard
          title="Retransmissions"
          value={clientStats.retransmissions || 0}
          icon={AlertTriangle}
          color="text-orange-500"
        />
        <StatCard
          title="Throughput"
          value={`${(clientStats.throughput_mbps || 0).toFixed(2)} Mbps`}
          icon={Zap}
          color="text-purple-600"
        />
      </div>
      
      {/* Additional Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          title="Avg RTT"
          value={`${((clientStats.avg_rtt || 0) * 1000).toFixed(1)} ms`}
          icon={Clock}
          color="text-cyan-600"
        />
        <StatCard
          title="CWND"
          value={congestion.cwnd?.toFixed(1) || '-'}
          subtitle={congestion.state || '-'}
          color="text-indigo-600"
        />
        <StatCard
          title="Server Received"
          value={serverStats.packets_received || 0}
          color="text-teal-600"
        />
        <StatCard
          title="Bytes Sent"
          value={formatBytes(clientStats.bytes_sent || 0)}
          color="text-gray-600"
        />
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

export default Dashboard;
