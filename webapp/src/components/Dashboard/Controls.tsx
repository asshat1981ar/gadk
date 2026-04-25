import { useState } from 'react'

interface ControlsProps {
  onStop?: () => void
  onRefresh?: () => void
  onInjectPrompt?: (prompt: string) => void
  isLoading?: boolean
}

export function Controls({ onStop, onRefresh, onInjectPrompt, isLoading }: ControlsProps) {
  const [prompt, setPrompt] = useState('')
  const [showPromptForm, setShowPromptForm] = useState(false)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (prompt.trim() && onInjectPrompt) {
      onInjectPrompt(prompt.trim())
      setPrompt('')
      setShowPromptForm(false)
    }
  }

  return (
    <div className="bg-gray-800 rounded-lg p-6">
      <h3 className="text-lg font-semibold text-white mb-4">Controls</h3>

      <div className="flex flex-wrap gap-3 mb-4">
        <button
          onClick={onStop}
          disabled={isLoading}
          className="px-4 py-2 bg-red-600 hover:bg-red-700 disabled:bg-red-800 disabled:cursor-not-allowed text-white rounded font-medium transition-colors"
        >
          Stop Swarm
        </button>

        <button
          onClick={onRefresh}
          disabled={isLoading}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 disabled:cursor-not-allowed text-white rounded font-medium transition-colors"
        >
          {isLoading ? 'Refreshing...' : 'Refresh'}
        </button>

        <button
          onClick={() => setShowPromptForm(!showPromptForm)}
          className="px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded font-medium transition-colors"
        >
          Inject Prompt
        </button>
      </div>

      {showPromptForm && (
        <form onSubmit={handleSubmit} className="space-y-3">
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Enter a prompt to inject into the swarm..."
            className="w-full p-3 bg-gray-700 text-white rounded border border-gray-600 focus:border-blue-500 focus:outline-none resize-none"
            rows={4}
          />
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={!prompt.trim()}
              className="px-4 py-2 bg-green-600 hover:bg-green-700 disabled:bg-green-800 disabled:cursor-not-allowed text-white rounded font-medium transition-colors"
            >
              Submit
            </button>
            <button
              type="button"
              onClick={() => {
                setShowPromptForm(false)
                setPrompt('')
              }}
              className="px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded font-medium transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      )}
    </div>
  )
}