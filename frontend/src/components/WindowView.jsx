import React, { useMemo } from 'react';
import { ChevronRight, ChevronLeft } from 'lucide-react';

function WindowView({ windowState, protocol }) {
  const { base, nextSeq, windowSize, totalChunks = 0 } = windowState;
  
  // Generate packet display
  const packets = useMemo(() => {
    const result = [];
    const displayStart = Math.max(0, base - 3);
    const displayEnd = Math.min(totalChunks || base + windowSize + 5, base + windowSize + 5);
    
    for (let i = displayStart; i < displayEnd; i++) {
      let status = 'not_sent';
      
      if (i < base) {
        status = 'acked';
      } else if (i >= base && i < nextSeq) {
        status = 'sent';
      } else if (i >= nextSeq && i < base + windowSize) {
        status = 'available';
      } else {
        status = 'outside';
      }
      
      result.push({ seq: i, status });
    }
    
    return result;
  }, [base, nextSeq, windowSize, totalChunks]);
  
  const getStatusColor = (status) => {
    switch (status) {
      case 'acked':
        return 'bg-green-500 text-white';
      case 'sent':
        return 'bg-blue-500 text-white animate-pulse';
      case 'available':
        return 'bg-yellow-400 text-yellow-900';
      case 'outside':
        return 'bg-gray-200 text-gray-400';
      default:
        return 'bg-gray-100 text-gray-400';
    }
  };
  
  const getStatusLabel = (status) => {
    switch (status) {
      case 'acked': return 'ACKed';
      case 'sent': return 'In-flight';
      case 'available': return 'Window';
      case 'outside': return 'Blocked';
      default: return 'Pending';
    }
  };
  
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
          Sliding Window View
        </h3>
        <div className="flex items-center space-x-2 text-xs text-gray-500">
          <span>Base: {base}</span>
          <span>|</span>
          <span>Next: {nextSeq}</span>
          <span>|</span>
          <span>Window: {windowSize}</span>
          {totalChunks > 0 && (
            <>
              <span>|</span>
              <span>Total: {totalChunks}</span>
            </>
          )}
        </div>
      </div>
      
      {/* Legend */}
      <div className="flex items-center justify-center space-x-4 mb-4 text-xs">
        <div className="flex items-center">
          <div className="w-4 h-4 rounded bg-green-500 mr-1" />
          <span className="text-gray-600">ACKed</span>
        </div>
        <div className="flex items-center">
          <div className="w-4 h-4 rounded bg-blue-500 mr-1" />
          <span className="text-gray-600">In-flight</span>
        </div>
        <div className="flex items-center">
          <div className="w-4 h-4 rounded bg-yellow-400 mr-1" />
          <span className="text-gray-600">Available</span>
        </div>
        <div className="flex items-center">
          <div className="w-4 h-4 rounded bg-gray-200 mr-1" />
          <span className="text-gray-600">Blocked</span>
        </div>
      </div>
      
      {/* Packet Visualization */}
      <div className="flex items-center justify-center overflow-x-auto py-4">
        {packets.length > 0 && packets[0].seq > 0 && (
          <div className="flex items-center mr-2">
            <ChevronLeft className="h-4 w-4 text-gray-400" />
            <span className="text-xs text-gray-400">...</span>
          </div>
        )}
        
        <div className="flex items-center space-x-1">
          {packets.map((packet) => (
            <div
              key={packet.seq}
              className={`relative flex flex-col items-center transition-all duration-300 ${
                packet.seq === base ? 'scale-110' : ''
              }`}
            >
              {/* Packet box */}
              <div
                className={`w-10 h-10 rounded-lg flex items-center justify-center text-sm font-medium ${getStatusColor(packet.status)} transition-all duration-300`}
              >
                {packet.seq}
              </div>
              
              {/* Base pointer */}
              {packet.seq === base && (
                <div className="absolute -bottom-6 flex flex-col items-center">
                  <div className="w-0 h-0 border-l-4 border-r-4 border-b-4 border-transparent border-b-red-500" />
                  <span className="text-xs text-red-500 font-medium">base</span>
                </div>
              )}
              
              {/* Next seq pointer */}
              {packet.seq === nextSeq && nextSeq !== base && (
                <div className="absolute -top-6 flex flex-col items-center">
                  <span className="text-xs text-blue-500 font-medium">next</span>
                  <div className="w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent border-t-blue-500" />
                </div>
              )}
              
              {/* Window boundary markers */}
              {packet.seq === base + windowSize - 1 && (
                <div className="absolute right-0 top-0 bottom-0 w-0.5 bg-orange-500" />
              )}
            </div>
          ))}
        </div>
        
        {totalChunks > 0 && packets.length > 0 && packets[packets.length - 1].seq < totalChunks - 1 && (
          <div className="flex items-center ml-2">
            <span className="text-xs text-gray-400">...</span>
            <ChevronRight className="h-4 w-4 text-gray-400" />
          </div>
        )}
      </div>
      
      {/* Window bracket visualization */}
      <div className="mt-6 relative">
        <div className="flex items-center justify-center">
          <div className="relative" style={{ width: `${Math.min(packets.length, windowSize + 3) * 44}px` }}>
            {/* Window bracket */}
            <div 
              className="absolute border-2 border-orange-500 rounded-lg"
              style={{
                left: `${Math.max(0, (base - Math.max(0, base - 3))) * 44}px`,
                width: `${windowSize * 44 - 4}px`,
                top: '-60px',
                height: '48px',
                borderStyle: 'dashed'
              }}
            />
            <div className="text-center text-xs text-orange-600 font-medium">
              Window [{base} - {base + windowSize - 1}]
            </div>
          </div>
        </div>
      </div>
      
      {/* Protocol-specific info */}
      <div className="mt-6 pt-4 border-t border-gray-200">
        <div className="text-xs text-gray-500">
          {protocol === 'stop_wait' && (
            <p>
              <strong>Stop-and-Wait:</strong> Only one packet at a time. 
              Wait for ACK before sending next packet.
            </p>
          )}
          {protocol === 'go_back_n' && (
            <p>
              <strong>Go-Back-N:</strong> Send up to N packets. 
              If one is lost, retransmit all from that point.
            </p>
          )}
          {protocol === 'selective_repeat' && (
            <p>
              <strong>Selective Repeat:</strong> Send up to N packets. 
              Only retransmit specific lost packets. Receiver buffers out-of-order.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

export default WindowView;
