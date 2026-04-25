import { useState, useEffect } from 'react';

export interface Event {
  id: string;
  timestamp: string;
  type: string;
  task_id?: string;
  phase?: string;
  details?: Record<string, unknown>;
}

export function useEventStream() {
  const [events, setEvents] = useState<Event[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const es = new EventSource('/api/events/stream');
    es.onopen = () => setConnected(true);
    es.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data);
        setEvents(prev => [...prev.slice(-999), event]);
      } catch {
        // Ignore malformed events
      }
    };
    es.onerror = () => setConnected(false);
    return () => es.close();
  }, []);

  return { events, connected };
}