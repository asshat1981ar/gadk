import { useQuery } from '@tanstack/react-query';
import { Task, TaskEvent } from '../../lib/api';

interface TaskDetailProps {
  task: Task;
  onClose: () => void;
}

const PHASES = ['PLAN', 'ARCHITECT', 'IMPLEMENT', 'REVIEW', 'GOVERN', 'OPERATE'];

const PHASE_COLORS: Record<string, string> = {
  PLAN: 'bg-blue-500',
  ARCHITECT: 'bg-purple-500',
  IMPLEMENT: 'bg-green-500',
  REVIEW: 'bg-yellow-500',
  GOVERN: 'bg-orange-500',
  OPERATE: 'bg-gray-500',
};

export default function TaskDetail({ task, onClose }: TaskDetailProps) {
  const { data: events } = useQuery({
    queryKey: ['task-events', task.id],
    queryFn: async () => {
      try {
        const res = await fetch('/api/events');
        if (!res.ok) return [];
        const allEvents: TaskEvent[] = await res.json();
        return allEvents.filter(e => e.task_id === task.id);
      } catch {
        return [];
      }
    },
  });

  // Build phase history from events
  const phaseHistory = buildPhaseHistory(task, events || []);

  const currentPhaseIndex = PHASES.indexOf(task.phase || '');

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex justify-between items-start p-6 border-b">
          <div>
            <h2 className="text-xl font-bold font-mono">{task.id}</h2>
            <p className="text-gray-500 mt-1">{task.title || task.description?.slice(0, 60) || 'No title'}</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
          >
            ×
          </button>
        </div>

        {/* Status badge */}
        <div className="px-6 pt-4">
          <div className="flex items-center gap-3">
            <span className={`inline-block px-3 py-1 rounded-full text-sm font-medium ${
              (task.status === 'COMPLETED' || task.status === 'DELIVERED') ? 'bg-green-100 text-green-700' :
              task.status === 'IN_PROGRESS' ? 'bg-blue-100 text-blue-700' :
              task.status === 'BLOCKED' || task.status === 'FAILED' ? 'bg-red-100 text-red-700' :
              'bg-gray-100 text-gray-600'
            }`}>{task.status || 'UNKNOWN'}</span>
            {task.agent && (
              <span className="text-sm text-gray-500">Agent: {task.agent}</span>
            )}
          </div>
        </div>

        {/* Phase progress indicator */}
        <div className="px-6 py-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Phase Progress</h3>
          <div className="flex items-center gap-1">
            {PHASES.map((phase, i) => {
              const isCompleted = currentPhaseIndex > i;
              const isCurrent = currentPhaseIndex === i;
              const colorClass = PHASE_COLORS[phase] || 'bg-gray-400';
              return (
                <div key={phase} className="flex-1 flex flex-col items-center">
                  <div className={`w-full h-2 rounded-full ${isCompleted || isCurrent ? colorClass : 'bg-gray-200'}`}
                    title={phase} />
                  <span className={`text-xs mt-1 ${isCurrent ? 'font-bold text-gray-800' : 'text-gray-400'}`}>
                    {phase}
                  </span>
                </div>
              );
            })}
          </div>
          {task.phase && (
            <p className="text-center text-sm text-gray-500 mt-2">
              Current: <span className="font-medium">{task.phase}</span>
            </p>
          )}
        </div>

        {/* Task metadata */}
        <div className="px-6 pb-4">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Task Metadata</h3>
          <div className="bg-gray-50 rounded-lg p-4 space-y-2 text-sm">
            {task.description && (
              <div>
                <span className="text-gray-500 font-medium">Description: </span>
                <span className="text-gray-800">{task.description}</span>
              </div>
            )}
            {task.priority && (
              <div>
                <span className="text-gray-500 font-medium">Priority: </span>
                <span className="text-gray-800">{task.priority}</span>
              </div>
            )}
            {task.source && (
              <div>
                <span className="text-gray-500 font-medium">Source: </span>
                <span className="text-gray-800">{task.source}</span>
              </div>
            )}
            {task.artifact && (
              <div>
                <span className="text-gray-500 font-medium">Artifact: </span>
                <span className="text-gray-800 font-mono text-xs">{task.artifact}</span>
              </div>
            )}
            {task.branch && (
              <div>
                <span className="text-gray-500 font-medium">Branch: </span>
                <span className="text-gray-800 font-mono text-xs">{task.branch}</span>
              </div>
            )}
            {task.pr_url && (
              <div>
                <span className="text-gray-500 font-medium">PR: </span>
                <a href={task.pr_url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline text-xs">
                  {task.pr_url}
                </a>
              </div>
            )}
            {task.issue_url && (
              <div>
                <span className="text-gray-500 font-medium">Issue: </span>
                <a href={task.issue_url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline text-xs">
                  {task.issue_url}
                </a>
              </div>
            )}
          </div>
        </div>

        {/* Phase history timeline */}
        <div className="px-6 pb-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Phase History</h3>
          {phaseHistory.length === 0 ? (
            <p className="text-sm text-gray-400 italic">No phase transitions recorded</p>
          ) : (
            <div className="space-y-3">
              {phaseHistory.map((entry, i) => (
                <div key={i} className="flex gap-3">
                  <div className="flex flex-col items-center">
                    <div className={`w-3 h-3 rounded-full ${PHASE_COLORS[entry.to] || 'bg-gray-400'} mt-1`} />
                    {i < phaseHistory.length - 1 && (
                      <div className="w-0.5 flex-1 bg-gray-200 my-1" />
                    )}
                  </div>
                  <div className="pb-3">
                    <div className="flex items-baseline gap-2">
                      <span className={`text-sm font-medium ${PHASE_COLORS[entry.to]?.replace('bg-', 'text-') || 'text-gray-700'}`}>
                        {entry.to}
                      </span>
                      {entry.from && (
                        <span className="text-xs text-gray-400">from {entry.from}</span>
                      )}
                    </div>
                    <div className="text-xs text-gray-400">{entry.timestamp}</div>
                    {entry.agent && (
                      <div className="text-xs text-gray-500">Agent: {entry.agent}</div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

interface PhaseEntry {
  timestamp: string;
  from?: string;
  to: string;
  agent?: string;
}

function buildPhaseHistory(task: Task, events: TaskEvent[]): PhaseEntry[] {
  const history: PhaseEntry[] = [];
  const taskEvents = events.filter(e => e.task_id === task.id);

  // Find phase transitions from events
  const phaseChanges = taskEvents.filter(e =>
    e.diff && ('phase' in e.diff || ('status' in e.diff && e.action === 'SET'))
  );

  for (const evt of phaseChanges) {
    if (evt.diff) {
      // Look for phase changes
      if ('phase' in evt.diff) {
        history.push({
          timestamp: evt.timestamp,
          from: evt.diff.phase?.old as string | undefined,
          to: evt.diff.phase?.new as string || task.phase || 'UNKNOWN',
          agent: evt.agent || undefined,
        });
      }
      // Also record status changes as they can indicate phase progression
      if ('status' in evt.diff) {
        // Only add if it's a meaningful transition
        const newStatus = evt.diff.status?.new as string;
        if (newStatus && !history.some(h => h.to === newStatus)) {
          history.push({
            timestamp: evt.timestamp,
            to: newStatus,
            agent: evt.agent || undefined,
          });
        }
      }
    }
  }

  // If no events found, add current phase as the starting point
  if (history.length === 0 && task.phase) {
    history.push({
      timestamp: task.created_at || new Date().toISOString(),
      to: task.phase,
    });
  }

  return history;
}