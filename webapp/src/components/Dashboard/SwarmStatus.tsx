export interface SwarmStatusData {
  state: 'RUNNING' | 'PAUSED' | 'STOPPED'
  activeTasks: number
  currentPhase: string
  lastEvent: string
}

interface SwarmStatusProps {
  status: SwarmStatusData | null
  isConnected: boolean
}

export function SwarmStatus({ status, isConnected }: SwarmStatusProps) {
  const getStatusColor = (state: string) => {
    switch (state) {
      case 'RUNNING': return 'bg-green-500'
      case 'PAUSED': return 'bg-yellow-500'
      case 'STOPPED': return 'bg-red-500'
      default: return 'bg-gray-500'
    }
  }

  const formatTimestamp = (ts: string) => {
    if (!ts) return 'Never'
    try {
      return new Date(ts).toLocaleTimeString()
    } catch {
      return ts
    }
  }

  return (
    <div className="bg-gray-800 rounded-lg p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white">Swarm Status</h3>
        <div className="flex items-center gap-2">
          <div className={`w-3 h-3 rounded-full ${isConnected ? 'bg-green-500 animate-pulse' : 'bg-gray-500'}`} />
          <span className="text-sm text-gray-400">{isConnected ? 'Connected' : 'Disconnected'}</span>
        </div>
      </div>

      {status ? (
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <span className={`px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(status.state)} text-white`}>
              {status.state}
            </span>
            <span className="text-gray-400">Phase: {status.currentPhase || 'N/A'}</span>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="bg-gray-700 rounded p-3">
              <div className="text-sm text-gray-400">Active Tasks</div>
              <div className="text-2xl font-bold text-white">{status.activeTasks}</div>
            </div>
            <div className="bg-gray-700 rounded p-3">
              <div className="text-sm text-gray-400">Last Event</div>
              <div className="text-lg font-medium text-white">{formatTimestamp(status.lastEvent)}</div>
            </div>
          </div>
        </div>
      ) : (
        <div className="text-gray-400 text-center py-4">Loading swarm status...</div>
      )}
    </div>
  )
}