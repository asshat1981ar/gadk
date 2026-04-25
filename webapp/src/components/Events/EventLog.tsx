import { useState, useRef, useEffect } from 'react';
import { useEventStream, Event } from '../../hooks/useEventStream';

const EVENT_TYPE_COLORS: Record<string, string> = {
  task: 'bg-blue-100 text-blue-800',
  phase: 'bg-purple-100 text-purple-800',
  agent: 'bg-green-100 text-green-800',
  error: 'bg-red-100 text-red-800',
  info: 'bg-gray-100 text-gray-800',
};

function getTypeColor(type: string): string {
  return EVENT_TYPE_COLORS[type.toLowerCase()] || EVENT_TYPE_COLORS.info;
}

function formatTimestamp(ts: string): string {
  const date = new Date(ts);
  return date.toLocaleTimeString('en-US', { hour12: false });
}

interface EventRowProps {
  event: Event;
}

function EventRow({ event }: EventRowProps) {
  const colorClass = getTypeColor(event.type);

  return (
    <div className="flex items-start gap-3 py-2 px-3 border-b border-gray-100 hover:bg-gray-50">
      <span className="text-xs text-gray-400 font-mono mt-0.5">
        {formatTimestamp(event.timestamp)}
      </span>
      <span className={`text-xs font-medium px-2 py-0.5 rounded ${colorClass}`}>
        {event.type}
      </span>
      {event.task_id && (
        <span className="text-xs text-gray-500 font-mono">
          {event.task_id}
        </span>
      )}
      {event.phase && (
        <span className="text-xs text-purple-600">
          [{event.phase}]
        </span>
      )}
      {event.details && (
        <span className="text-sm text-gray-700 truncate flex-1">
          {JSON.stringify(event.details).slice(0, 80)}
        </span>
      )}
    </div>
  );
}

export function EventLog() {
  const { events, connected } = useEventStream();
  const [filterType, setFilterType] = useState<string>('');
  const [filterTaskId, setFilterTaskId] = useState<string>('');
  const [autoScroll, setAutoScroll] = useState(true);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (autoScroll && listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [events, autoScroll]);

  const filteredEvents = events.filter(e => {
    if (filterType && e.type !== filterType) return false;
    if (filterTaskId && !e.task_id?.includes(filterTaskId)) return false;
    return true;
  });

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-4 p-4 border-b border-gray-200">
        <h1 className="text-lg font-semibold">Event Log</h1>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
          <span className="text-sm text-gray-500">
            {connected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
        <span className="text-sm text-gray-400 ml-auto">
          {filteredEvents.length} events
        </span>
      </div>

      {/* Filter controls */}
      <div className="flex items-center gap-3 p-3 border-b border-gray-100 bg-gray-50">
        <select
          className="text-sm border border-gray-300 rounded px-2 py-1"
          value={filterType}
          onChange={e => setFilterType(e.target.value)}
        >
          <option value="">All types</option>
          <option value="task">task</option>
          <option value="phase">phase</option>
          <option value="agent">agent</option>
          <option value="error">error</option>
          <option value="info">info</option>
        </select>
        <input
          type="text"
          placeholder="Filter by task ID..."
          className="text-sm border border-gray-300 rounded px-2 py-1 w-40"
          value={filterTaskId}
          onChange={e => setFilterTaskId(e.target.value)}
        />
        <label className="flex items-center gap-1.5 text-sm text-gray-600 ml-auto cursor-pointer">
          <input
            type="checkbox"
            checked={autoScroll}
            onChange={e => setAutoScroll(e.target.checked)}
            className="rounded"
          />
          Auto-scroll
        </label>
      </div>

      {/* Event list */}
      <div
        ref={listRef}
        className="flex-1 overflow-auto"
        style={{ maxHeight: 'calc(100vh - 200px)' }}
      >
        {filteredEvents.length === 0 ? (
          <div className="flex items-center justify-center h-32 text-gray-400">
            No events
          </div>
        ) : (
          filteredEvents.map(event => (
            <EventRow key={event.id} event={event} />
          ))
        )}
      </div>
    </div>
  );
}