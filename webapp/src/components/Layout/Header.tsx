import { useSwarmStatus } from '../../hooks/useSwarmStatus';

interface HeaderProps {
  title?: string;
}

export function Header({ title = 'Cognitive Foundry Swarm' }: HeaderProps) {
  const { status, tasks, lastUpdate } = useSwarmStatus();

  const statusColors = {
    running: 'bg-green-500',
    paused: 'bg-yellow-500',
    stopped: 'bg-red-500',
  };

  const statusColor = statusColors[status as keyof typeof statusColors] || 'bg-gray-500';

  return (
    <header className="bg-gray-800 border-b border-gray-700 px-6 py-4 flex items-center justify-between">
      <div>
        <h2 className="text-xl font-bold text-white">{title}</h2>
        <p className="text-sm text-gray-400">
          Active Tasks: <span className="text-blue-400 font-semibold">{tasks}</span>
        </p>
      </div>
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-3">
          <div className={`w-3 h-3 rounded-full ${statusColor} animate-pulse`} />
          <span className="text-sm font-medium text-gray-300 capitalize">{status}</span>
        </div>
        <div className="text-xs text-gray-500">
          Last update: {lastUpdate ? new Date(lastUpdate).toLocaleTimeString() : 'N/A'}
        </div>
      </div>
    </header>
  );
}