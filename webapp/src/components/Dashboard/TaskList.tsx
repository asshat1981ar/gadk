export interface Task {
  id: string
  status: string
  source: string
  created?: string
  phase?: string
}

interface TaskListProps {
  tasks: Task[]
  onTaskClick?: (taskId: string) => void
}

export function TaskList({ tasks, onTaskClick }: TaskListProps) {
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'COMPLETED': return 'text-green-400'
      case 'PENDING': return 'text-blue-400'
      case 'PLANNED': return 'text-yellow-400'
      case 'STALLED': return 'text-red-400'
      case 'FAILED': return 'text-red-400'
      default: return 'text-gray-400'
    }
  }

  const formatAge = (created?: string) => {
    if (!created) return '—'
    try {
      const diff = Date.now() - new Date(created).getTime()
      const minutes = Math.floor(diff / 60000)
      if (minutes < 60) return `${minutes}m ago`
      const hours = Math.floor(minutes / 60)
      if (hours < 24) return `${hours}h ago`
      return `${Math.floor(hours / 24)}d ago`
    } catch {
      return '—'
    }
  }

  const displayTasks = tasks.slice(0, 10)

  return (
    <div className="bg-gray-800 rounded-lg p-6">
      <h3 className="text-lg font-semibold text-white mb-4">Active Tasks</h3>

      {displayTasks.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-400 border-b border-gray-700">
                <th className="text-left py-2 px-3">ID</th>
                <th className="text-left py-2 px-3">Phase</th>
                <th className="text-left py-2 px-3">Status</th>
                <th className="text-left py-2 px-3">Created</th>
              </tr>
            </thead>
            <tbody>
              {displayTasks.map((task) => (
                <tr
                  key={task.id}
                  className="border-b border-gray-700 hover:bg-gray-700 cursor-pointer"
                  onClick={() => onTaskClick?.(task.id)}
                >
                  <td className="py-2 px-3 text-cyan-400 font-mono text-xs truncate max-w-[120px]">
                    {task.id.substring(0, 40)}
                  </td>
                  <td className="py-2 px-3 text-gray-300">
                    {task.phase || '—'}
                  </td>
                  <td className={`py-2 px-3 font-medium ${getStatusColor(task.status)}`}>
                    {task.status}
                  </td>
                  <td className="py-2 px-3 text-gray-400">
                    {formatAge(task.created)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="text-gray-400 text-center py-4">No active tasks</div>
      )}

      {tasks.length > 10 && (
        <div className="mt-3 text-sm text-gray-400 text-center">
          + {tasks.length - 10} more tasks
        </div>
      )}
    </div>
  )
}