import { useState } from 'react';
import { Task } from '../../lib/api';
import TaskDetail from './TaskDetail';

interface TaskTableProps {
  tasks: Task[];
}

type SortKey = 'id' | 'phase' | 'status' | 'created' | 'updated';
type SortDir = 'asc' | 'desc';

const PHASES = ['PLAN', 'ARCHITECT', 'IMPLEMENT', 'REVIEW', 'GOVERN', 'OPERATE'];
const STATUSES = ['PENDING', 'PLANNED', 'IN_PROGRESS', 'COMPLETED', 'DELIVERED', 'BLOCKED', 'FAILED'];

const PAGE_SIZE = 20;

export default function TaskTable({ tasks }: TaskTableProps) {
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [statusFilter, setStatusFilter] = useState('');
  const [phaseFilter, setPhaseFilter] = useState('');
  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('id');
  const [sortDir, setSortDir] = useState<SortDir>('asc');
  const [page, setPage] = useState(0);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  };

  const filtered = tasks.filter(t => {
    if (statusFilter && t.status !== statusFilter) return false;
    if (phaseFilter && t.phase !== phaseFilter) return false;
    if (search) {
      const s = search.toLowerCase();
      return (
        t.id.toLowerCase().includes(s) ||
        (t.title || '').toLowerCase().includes(s) ||
        (t.description || '').toLowerCase().includes(s)
      );
    }
    return true;
  });

  const sorted = [...filtered].sort((a, b) => {
    let av = '', bv = '';
    if (sortKey === 'id') { av = a.id; bv = b.id; }
    else if (sortKey === 'phase') { av = a.phase || ''; bv = b.phase || ''; }
    else if (sortKey === 'status') { av = a.status || ''; bv = b.status || ''; }
    else if (sortKey === 'created') { av = a.created_at || ''; bv = b.created_at || ''; }
    else if (sortKey === 'updated') { av = a.updated_at || ''; bv = b.updated_at || ''; }
    const cmp = av.localeCompare(bv);
    return sortDir === 'asc' ? cmp : -cmp;
  });

  const totalPages = Math.ceil(sorted.length / PAGE_SIZE);
  const pageTasks = sorted.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  const SortIcon = ({ col }: { col: SortKey }) => (
    <span className="ml-1 text-xs text-gray-400">
      {sortKey === col ? (sortDir === 'asc' ? '▲' : '▼') : '⇅'}
    </span>
  );

  return (
    <div>
      {/* Filter bar */}
      <div className="flex gap-4 mb-4 items-center flex-wrap">
        <input
          type="text"
          placeholder="Search tasks..."
          value={search}
          onChange={e => { setSearch(e.target.value); setPage(0); }}
          className="border rounded px-3 py-1.5 w-64"
        />
        <select
          value={statusFilter}
          onChange={e => { setStatusFilter(e.target.value); setPage(0); }}
          className="border rounded px-3 py-1.5"
        >
          <option value="">All Statuses</option>
          {STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <select
          value={phaseFilter}
          onChange={e => { setPhaseFilter(e.target.value); setPage(0); }}
          className="border rounded px-3 py-1.5"
        >
          <option value="">All Phases</option>
          {PHASES.map(p => <option key={p} value={p}>{p}</option>)}
        </select>
        <span className="text-sm text-gray-500">{filtered.length} tasks</span>
      </div>

      {/* Table */}
      <div className="overflow-x-auto border rounded-lg">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              {[
                { key: 'id' as SortKey, label: 'ID' },
                { key: 'phase' as SortKey, label: 'Phase' },
                { key: 'status' as SortKey, label: 'Status' },
                { key: 'created' as SortKey, label: 'Created' },
                { key: 'updated' as SortKey, label: 'Updated' },
              ].map(col => (
                <th
                  key={col.key}
                  className="px-4 py-3 text-left font-medium text-gray-600 cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSort(col.key)}
                >
                  {col.label}<SortIcon col={col.key} />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pageTasks.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-gray-400">
                  No tasks found
                </td>
              </tr>
            ) : pageTasks.map(task => (
              <tr
                key={task.id}
                className="border-b hover:bg-blue-50 cursor-pointer transition"
                onClick={() => setSelectedTask(task)}
              >
                <td className="px-4 py-3 font-mono text-xs max-w-[200px] truncate">{task.id}</td>
                <td className="px-4 py-3">
                  {task.phase ? (
                    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                      task.phase === 'PLAN' ? 'bg-blue-100 text-blue-700' :
                      task.phase === 'ARCHITECT' ? 'bg-purple-100 text-purple-700' :
                      task.phase === 'IMPLEMENT' ? 'bg-green-100 text-green-700' :
                      task.phase === 'REVIEW' ? 'bg-yellow-100 text-yellow-700' :
                      task.phase === 'GOVERN' ? 'bg-orange-100 text-orange-700' :
                      task.phase === 'OPERATE' ? 'bg-gray-100 text-gray-700' :
                      'bg-gray-100 text-gray-600'
                    }`}>{task.phase}</span>
                  ) : <span className="text-gray-400">—</span>}
                </td>
                <td className="px-4 py-3">
                  <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                    task.status === 'COMPLETED' || task.status === 'DELIVERED' ? 'bg-green-100 text-green-700' :
                    task.status === 'IN_PROGRESS' ? 'bg-blue-100 text-blue-700' :
                    task.status === 'BLOCKED' || task.status === 'FAILED' ? 'bg-red-100 text-red-700' :
                    task.status === 'PLANNED' || task.status === 'PENDING' ? 'bg-gray-100 text-gray-600' :
                    'bg-gray-100 text-gray-600'
                  }`}>{task.status || '—'}</span>
                </td>
                <td className="px-4 py-3 text-gray-500">{task.created_at || '—'}</td>
                <td className="px-4 py-3 text-gray-500">{task.updated_at || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-between items-center mt-4">
          <button
            onClick={() => setPage(p => Math.max(0, p - 1))}
            disabled={page === 0}
            className="px-3 py-1 border rounded disabled:opacity-40"
          >
            Prev
          </button>
          <span className="text-sm text-gray-500">
            Page {page + 1} of {totalPages}
          </span>
          <button
            onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
            className="px-3 py-1 border rounded disabled:opacity-40"
          >
            Next
          </button>
        </div>
      )}

      {/* Detail modal */}
      {selectedTask && (
        <TaskDetail task={selectedTask} onClose={() => setSelectedTask(null)} />
      )}
    </div>
  );
}