import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  AreaChart,
  Area
} from 'recharts';

function Graphs({ throughputHistory, congestionHistory, serverStats, clientStats }) {
  // Format data for throughput chart
  const throughputData = throughputHistory.map((d, i) => ({
    name: i,
    throughput: d.throughput,
    packets: d.packets,
    retransmissions: d.retransmissions
  }));
  
  // Format data for congestion chart
  const congestionData = congestionHistory.map((d, i) => ({
    name: i,
    cwnd: d.cwnd,
    ssthresh: d.ssthresh,
    rtt: d.rtt
  }));
  
  return (
    <div className="space-y-4">
      {/* Throughput Chart */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
        <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-4">
          Throughput & Packets
        </h3>
        <div className="h-48">
          {throughputData.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={throughputData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis 
                  dataKey="name" 
                  tick={{ fontSize: 10 }}
                  tickLine={false}
                />
                <YAxis 
                  yAxisId="left"
                  tick={{ fontSize: 10 }}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis 
                  yAxisId="right" 
                  orientation="right"
                  tick={{ fontSize: 10 }}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip 
                  contentStyle={{
                    backgroundColor: '#fff',
                    border: '1px solid #e5e7eb',
                    borderRadius: '6px',
                    fontSize: '12px'
                  }}
                />
                <Legend 
                  wrapperStyle={{ fontSize: '11px' }}
                />
                <Area
                  yAxisId="left"
                  type="monotone"
                  dataKey="throughput"
                  name="Throughput (Mbps)"
                  stroke="#3b82f6"
                  fill="#93c5fd"
                  fillOpacity={0.6}
                />
                <Line
                  yAxisId="right"
                  type="stepAfter"
                  dataKey="packets"
                  name="Packets"
                  stroke="#10b981"
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  yAxisId="right"
                  type="stepAfter"
                  dataKey="retransmissions"
                  name="Retransmissions"
                  stroke="#ef4444"
                  strokeWidth={2}
                  dot={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-full flex items-center justify-center text-gray-400 text-sm">
              No data yet. Start a transfer to see graphs.
            </div>
          )}
        </div>
      </div>
      
      {/* Congestion Control Chart */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
        <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-4">
          Congestion Control (CWND / SSThresh)
        </h3>
        <div className="h-48">
          {congestionData.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={congestionData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis 
                  dataKey="name" 
                  tick={{ fontSize: 10 }}
                  tickLine={false}
                />
                <YAxis 
                  yAxisId="left"
                  tick={{ fontSize: 10 }}
                  tickLine={false}
                  axisLine={false}
                  label={{ value: 'Window', angle: -90, position: 'insideLeft', fontSize: 10 }}
                />
                <YAxis 
                  yAxisId="right" 
                  orientation="right"
                  tick={{ fontSize: 10 }}
                  tickLine={false}
                  axisLine={false}
                  label={{ value: 'RTT (ms)', angle: 90, position: 'insideRight', fontSize: 10 }}
                />
                <Tooltip 
                  contentStyle={{
                    backgroundColor: '#fff',
                    border: '1px solid #e5e7eb',
                    borderRadius: '6px',
                    fontSize: '12px'
                  }}
                  formatter={(value, name) => [
                    typeof value === 'number' ? value.toFixed(2) : value,
                    name
                  ]}
                />
                <Legend 
                  wrapperStyle={{ fontSize: '11px' }}
                />
                <Line
                  yAxisId="left"
                  type="stepAfter"
                  dataKey="cwnd"
                  name="CWND"
                  stroke="#8b5cf6"
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  yAxisId="left"
                  type="stepAfter"
                  dataKey="ssthresh"
                  name="SSThresh"
                  stroke="#f59e0b"
                  strokeWidth={2}
                  strokeDasharray="5 5"
                  dot={false}
                />
                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="rtt"
                  name="RTT (ms)"
                  stroke="#06b6d4"
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-full flex items-center justify-center text-gray-400 text-sm">
              No congestion data yet.
            </div>
          )}
        </div>
      </div>
      
      {/* Packet Loss Stats */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
        <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-3">
          Transfer Summary
        </h3>
        <div className="grid grid-cols-4 gap-4 text-center">
          <div>
            <div className="text-2xl font-bold text-blue-600">
              {clientStats?.packets_sent || 0}
            </div>
            <div className="text-xs text-gray-500">Packets Sent</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-green-600">
              {serverStats?.packets_received || 0}
            </div>
            <div className="text-xs text-gray-500">Received</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-orange-600">
              {clientStats?.retransmissions || 0}
            </div>
            <div className="text-xs text-gray-500">Retransmissions</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-red-600">
              {clientStats?.packets_dropped || 0}
            </div>
            <div className="text-xs text-gray-500">Dropped</div>
          </div>
        </div>
        
        {/* Efficiency bar */}
        <div className="mt-4">
          <div className="flex justify-between text-xs text-gray-500 mb-1">
            <span>Transfer Efficiency</span>
            <span>
              {clientStats?.packets_sent
                ? (((clientStats.packets_sent - clientStats.retransmissions) / clientStats.packets_sent) * 100).toFixed(1)
                : 100}%
            </span>
          </div>
          <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-green-500 to-emerald-400 transition-all duration-500"
              style={{
                width: `${clientStats?.packets_sent
                  ? ((clientStats.packets_sent - clientStats.retransmissions) / clientStats.packets_sent) * 100
                  : 100}%`
              }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

export default Graphs;
