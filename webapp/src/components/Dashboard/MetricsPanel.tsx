export interface MetricsData {
  totalApiCalls: number
  errorRate: number
  totalCost: number
  tokenUsage: {
    total: number
    byAgent: Record<string, number>
  }
}

interface MetricsPanelProps {
  metrics: MetricsData | null
}

export function MetricsPanel({ metrics }: MetricsPanelProps) {
  const formatNumber = (num: number) => {
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`
    if (num >= 1000) return `${(num / 1000).toFixed(1)}K`
    return num.toString()
  }

  const formatCost = (cost: number) => {
    return `$${cost.toFixed(4)}`
  }

  const getErrorRateColor = (rate: number) => {
    if (rate < 5) return 'text-green-400'
    if (rate < 15) return 'text-yellow-400'
    return 'text-red-400'
  }

  return (
    <div className="bg-gray-800 rounded-lg p-6">
      <h3 className="text-lg font-semibold text-white mb-4">Metrics</h3>

      {metrics ? (
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-gray-700 rounded p-4">
            <div className="text-sm text-gray-400 mb-1">Total API Calls</div>
            <div className="text-2xl font-bold text-white">{formatNumber(metrics.totalApiCalls)}</div>
          </div>

          <div className="bg-gray-700 rounded p-4">
            <div className="text-sm text-gray-400 mb-1">Error Rate</div>
            <div className={`text-2xl font-bold ${getErrorRateColor(metrics.errorRate)}`}>
              {metrics.errorRate.toFixed(1)}%
            </div>
          </div>

          <div className="bg-gray-700 rounded p-4">
            <div className="text-sm text-gray-400 mb-1">Total Cost</div>
            <div className="text-2xl font-bold text-white">{formatCost(metrics.totalCost)}</div>
          </div>

          <div className="bg-gray-700 rounded p-4">
            <div className="text-sm text-gray-400 mb-1">Token Usage</div>
            <div className="text-2xl font-bold text-white">{formatNumber(metrics.tokenUsage.total)}</div>
          </div>
        </div>
      ) : (
        <div className="text-gray-400 text-center py-4">Loading metrics...</div>
      )}
    </div>
  )
}