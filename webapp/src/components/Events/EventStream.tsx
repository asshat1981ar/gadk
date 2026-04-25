import { useEventStream, Event } from '../../hooks/useEventStream';

const TYPE_BADGES: Record<string, { bg: string; label: string }> = {
  task: { bg: 'bg-blue-500', label: 'TASK' },
  phase: { bg: 'bg-purple-500', label: 'PHASE' },
  agent: { bg: 'bg-green-500', label: 'AGENT' },
  error: { bg: 'bg-red-500', label: 'ERR' },
  info: { bg: 'bg-gray-500', label: 'INFO' },
};

function getBadge(type: string) {
  return TYPE_BADGES[type.toLowerCase()] || TYPE_BADGES.info;
}

interface EventBadgeProps {
  event: Event;
}

function EventBadge({ event }: EventBadgeProps) {
  const badge = getBadge(event.type);
  const time = new Date(event.timestamp).toLocaleTimeString('en-US', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });

  return (
    <div className="flex items-center gap-2 py-1 px-2 hover:bg-gray-100 rounded text-sm">
      <span className="text-xs text-gray-400">{time}</span>
      <span className={`${badge.bg} text-white text-xs font-bold px-1.5 py-0.5 rounded`}>
        {badge.label}
      </span>
      {event.task_id && (
        <span className="text-xs text-gray-500 font-mono">
          {event.task_id.slice(0, 12)}
        </span>
      )}
      {event.phase && (
        <span className="text-xs text-purple-600">
          {event.phase}
        </span>
      )}
    </div>
  );
}

export function EventStream() {
  const { events, connected } = useEventStream();
  const recentEvents = events.slice(-10);

  return (
    <div className="flex flex-col">
      {/* Header */}
      <div className="flex items-center gap-2 mb-2">
        <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
        <span className="text-sm font-medium">Live Events</span>
        <span className="text-xs text-gray-400 ml-auto">
          {events.length} total
        </span>
      </div>

      {/* Ticker */}
      <div className="flex flex-col gap-1 p-3 bg-gray-50 rounded-lg border border-gray-200">
        {recentEvents.length === 0 ? (
          <span className="text-sm text-gray-400">Waiting for events...</span>
        ) : (
          recentEvents.map(event => (
            <EventBadge key={event.id} event={event} />
          ))
        )}
      </div>
    </div>
  );
}