import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';
import type { Task } from '../lib/api';

export function useTasks(filters?: { status?: string; phase?: string }) {
  const { data, refetch } = useQuery({
    queryKey: ['tasks', filters],
    queryFn: () => api.tasks.list(filters),
    refetchInterval: 5000,
  });
  return { tasks: (data || []) as Task[], refetch };
}