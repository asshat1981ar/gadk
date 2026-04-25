import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useQuery, useMutation } from '@tanstack/react-query';
import { SwarmStatus, TaskList, MetricsPanel, Controls } from './components/Dashboard';
import type { SwarmStatusData, MetricsData } from './components/Dashboard';
import { useState, useEffect } from 'react';
import { Sidebar } from './components/Layout/Sidebar';
import { Header } from './components/Layout/Header';

const queryClient = new QueryClient();

function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col">
        <Header />
        <main className="flex-1 p-8 bg-gray-50">{children}</main>
      </div>
    </div>
  );
}

async function fetchSwarmStatus(): Promise<SwarmStatusData> {
  return {
    state: 'RUNNING',
    activeTasks: 0,
    currentPhase: 'PLAN',
    lastEvent: new Date().toISOString()
  }
}

async function fetchMetrics(): Promise<MetricsData> {
  return {
    totalApiCalls: 0,
    errorRate: 0,
    totalCost: 0,
    tokenUsage: { total: 0, byAgent: {} }
  }
}

async function stopSwarm(): Promise<void> {
  console.log('Stop swarm requested')
}

async function injectPrompt(prompt: string): Promise<void> {
  console.log('Inject prompt:', prompt)
}

function Dashboard() {
  const [isConnected, setIsConnected] = useState(false)

  const { data: swarmStatus, refetch: refetchStatus } = useQuery({
    queryKey: ['swarmStatus'],
    queryFn: fetchSwarmStatus,
    refetchInterval: 5000
  })

  const { data: metrics, refetch: refetchMetrics } = useQuery({
    queryKey: ['metrics'],
    queryFn: fetchMetrics,
    refetchInterval: 10000
  })

  const stopMutation = useMutation({
    mutationFn: stopSwarm,
    onSuccess: () => {
      refetchStatus()
    }
  })

  const injectMutation = useMutation({
    mutationFn: injectPrompt,
    onSuccess: () => {
      refetchStatus()
    }
  })

  const handleRefresh = () => {
    refetchStatus()
    refetchMetrics()
  }

  useEffect(() => {
    setIsConnected(true)
  }, [])

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <SwarmStatus status={swarmStatus ?? null} isConnected={isConnected} />
        <MetricsPanel metrics={metrics ?? null} />
      </div>

      <TaskList tasks={[]} />

      <Controls
        onStop={() => stopMutation.mutate()}
        onRefresh={handleRefresh}
        onInjectPrompt={(prompt) => injectMutation.mutate(prompt)}
        isLoading={stopMutation.isPending || injectMutation.isPending}
      />
    </div>
  )
}

function TasksPage() {
  return (
    <div>
      <h2 className="text-2xl font-bold mb-4">Tasks</h2>
      <p>Task queue and management</p>
    </div>
  );
}

function Events() {
  return (
    <div>
      <h2 className="text-2xl font-bold mb-4">Events</h2>
      <p>Event log and history</p>
    </div>
  )
}

function Metrics() {
  return (
    <div>
      <h2 className="text-2xl font-bold mb-4">Metrics</h2>
      <p>Performance and health metrics</p>
    </div>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/tasks" element={<TasksPage />} />
            <Route path="/events" element={<Events />} />
            <Route path="/metrics" element={<Metrics />} />
            <Route path="/" element={<Dashboard />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </QueryClientProvider>
  )
}