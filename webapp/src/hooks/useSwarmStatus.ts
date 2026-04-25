import { useState, useEffect, useCallback } from 'react';
import { api, SwarmStatus, TaskEvent } from '../lib/api';

interface UseSwarmStatusResult {
  status: SwarmStatus['status'];
  tasks: number;
  phase: string;
  errors: number;
  lastUpdate: string | null;
  events: TaskEvent[];
  refresh: () => void;
}

export function useSwarmStatus(): UseSwarmStatusResult {
  const [status, setStatus] = useState<'running' | 'paused' | 'stopped'>('stopped');
  const [tasks, setTasks] = useState(0);
  const [phase, setPhase] = useState('');
  const [errors, setErrors] = useState(0);
  const [lastUpdate, setLastUpdate] = useState<string | null>(null);
  const [events, setEvents] = useState<TaskEvent[]>([]);

  const fetchStatus = useCallback(async () => {
    try {
      const data = await api.swarm.status();
      setStatus(data.status);
      setTasks(data.tasks);
      setPhase(data.phase);
      setErrors(data.errors);
      setLastUpdate(data.lastUpdate);
    } catch (err) {
      console.error('Failed to fetch swarm status:', err);
    }
  }, []);

  useEffect(() => {
    // Fetch initial status
    fetchStatus();

    // Connect to SSE stream for real-time updates
    let eventSource: EventSource | null = null;

    const connectSSE = () => {
      eventSource = new EventSource(api.events.streamUrl);

      eventSource.onopen = () => {
        console.log('SSE connected');
      };

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as TaskEvent;
          setEvents((prev) => [...prev.slice(-999), data]);
          setLastUpdate(new Date().toISOString());
        } catch {
          // Ignore malformed events
        }
      };

      eventSource.onerror = () => {
        console.error('SSE connection error, reconnecting...');
        eventSource?.close();
        // Reconnect after 5 seconds
        setTimeout(connectSSE, 5000);
      };
    };

    connectSSE();

    // Cleanup on unmount
    return () => {
      eventSource?.close();
    };
  }, [fetchStatus]);

  return {
    status,
    tasks,
    phase,
    errors,
    lastUpdate,
    events,
    refresh: fetchStatus,
  };
}