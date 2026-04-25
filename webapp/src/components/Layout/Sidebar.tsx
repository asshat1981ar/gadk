import { NavLink } from 'react-router-dom';

interface NavItem {
  path: string;
  label: string;
  icon?: string;
}

const navItems: NavItem[] = [
  { path: '/', label: 'Dashboard', icon: '📊' },
  { path: '/tasks', label: 'Tasks', icon: '📋' },
  { path: '/events', label: 'Events', icon: '📅' },
  { path: '/metrics', label: 'Metrics', icon: '📈' },
];

export function Sidebar() {
  return (
    <aside className="w-64 bg-gray-900 text-white p-4 flex flex-col h-full">
      <h1 className="text-xl font-bold mb-8 px-4">GADK Swarm</h1>
      <nav className="space-y-1 flex-1">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                isActive
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-300 hover:bg-gray-800 hover:text-white'
              }`
            }
            end={item.path === '/'}
          >
            {item.icon && <span className="text-lg">{item.icon}</span>}
            <span className="font-medium">{item.label}</span>
          </NavLink>
        ))}
      </nav>
      <div className="mt-auto pt-4 border-t border-gray-700">
        <div className="px-4 text-xs text-gray-500">
          Cognitive Foundry Swarm v0.1.0
        </div>
      </div>
    </aside>
  );
}