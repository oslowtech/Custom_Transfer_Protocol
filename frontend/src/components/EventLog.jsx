import React, { useRef, useEffect } from 'react';
import { 
  Send, 
  Check, 
  AlertTriangle, 
  RefreshCw, 
  Clock, 
  Wifi, 
  WifiOff,
  ArrowRight,
  ArrowLeft
} from 'lucide-react';

function EventLog({ events }) {
  const containerRef = useRef(null);
  
  // Auto-scroll to bottom on new events
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [events]);
  
  const getEventIcon = (type) => {
    switch (type) {
      case 'packet_sent':
      case 'data_sent':
        return <Send className="h-3 w-3 text-blue-500" />;
      case 'ack_received':
      case 'ack_sent':
        return <Check className="h-3 w-3 text-green-500" />;
      case 'timeout':
        return <Clock className="h-3 w-3 text-orange-500" />;
      case 'retransmit':
        return <RefreshCw className="h-3 w-3 text-yellow-500" />;
      case 'packet_drop':
      case 'checksum_error':
        return <AlertTriangle className="h-3 w-3 text-red-500" />;
      case 'syn_sent':
      case 'syn_received':
        return <ArrowRight className="h-3 w-3 text-purple-500" />;
      case 'syn_ack_sent':
      case 'syn_ack_received':
        return <ArrowLeft className="h-3 w-3 text-purple-500" />;
      case 'server_start':
        return <Wifi className="h-3 w-3 text-green-500" />;
      case 'server_stop':
        return <WifiOff className="h-3 w-3 text-red-500" />;
      case 'transfer_complete':
        return <Check className="h-3 w-3 text-green-600" />;
      default:
        return <div className="h-3 w-3 bg-gray-300 rounded-full" />;
    }
  };
  
  const getEventColor = (type) => {
    if (type.includes('error') || type.includes('drop')) return 'text-red-600';
    if (type.includes('ack') || type.includes('complete')) return 'text-green-600';
    if (type.includes('timeout') || type.includes('retransmit')) return 'text-orange-600';
    if (type.includes('syn')) return 'text-purple-600';
    return 'text-gray-700';
  };
  
  const formatTimestamp = (timestamp) => {
    const date = new Date(timestamp * 1000);
    return date.toLocaleTimeString('en-US', { 
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    }) + '.' + date.getMilliseconds().toString().padStart(3, '0');
  };
  
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 h-full flex flex-col">
      <div className="px-4 py-3 border-b border-gray-200">
        <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
          Event Log
        </h3>
      </div>
      
      <div 
        ref={containerRef}
        className="flex-1 overflow-y-auto p-2 max-h-[600px]"
      >
        {events.length === 0 ? (
          <div className="flex items-center justify-center h-full text-gray-400 text-sm">
            No events yet
          </div>
        ) : (
          <div className="space-y-1">
            {events.map((event, index) => (
              <div
                key={`${event.timestamp}-${index}`}
                className="flex items-start space-x-2 p-2 hover:bg-gray-50 rounded text-xs transition-colors"
              >
                <div className="flex-shrink-0 mt-0.5">
                  {getEventIcon(event.type)}
                </div>
                <div className="flex-1 min-w-0">
                  <div className={`font-medium truncate ${getEventColor(event.type)}`}>
                    {event.message}
                  </div>
                  <div className="flex items-center space-x-2 mt-0.5">
                    <span className="text-gray-400">
                      {formatTimestamp(event.timestamp)}
                    </span>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                      event.source === 'server' 
                        ? 'bg-blue-100 text-blue-700' 
                        : 'bg-green-100 text-green-700'
                    }`}>
                      {event.source || 'client'}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
      
      {/* Quick stats */}
      <div className="px-4 py-2 border-t border-gray-200 bg-gray-50">
        <div className="flex justify-between text-xs text-gray-500">
          <span>
            {events.filter(e => e.type.includes('sent')).length} sent
          </span>
          <span>
            {events.filter(e => e.type.includes('ack')).length} ACKs
          </span>
          <span>
            {events.filter(e => e.type.includes('timeout') || e.type.includes('retransmit')).length} retries
          </span>
          <span>
            {events.filter(e => e.type.includes('drop') || e.type.includes('error')).length} errors
          </span>
        </div>
      </div>
    </div>
  );
}

export default EventLog;
