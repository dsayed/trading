import { NavLink, Outlet } from 'react-router-dom';

const NAV_ITEMS = [
  { to: '/scan', label: 'Scan', icon: '⟐' },
  { to: '/watchlists', label: 'Watchlists', icon: '☰' },
  { to: '/positions', label: 'Positions', icon: '◈' },
  { to: '/plays', label: 'Plays', icon: '♟' },
  { to: '/history', label: 'History', icon: '↻' },
  { to: '/settings', label: 'Settings', icon: '⚙' },
] as const;

export default function Layout() {
  return (
    <div className="flex h-screen bg-zinc-950 text-zinc-100">
      {/* Sidebar */}
      <nav className="flex w-56 flex-col border-r border-zinc-800 bg-zinc-950">
        <div className="flex h-14 items-center gap-2 border-b border-zinc-800 px-5">
          <span className="text-lg font-semibold tracking-tight text-emerald-400">
            Trading
          </span>
        </div>
        <div className="flex flex-1 flex-col gap-1 p-3">
          {NAV_ITEMS.map(({ to, label, icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-zinc-800 text-emerald-400'
                    : 'text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200'
                }`
              }
            >
              <span className="text-base">{icon}</span>
              {label}
            </NavLink>
          ))}
        </div>
      </nav>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto p-8">
        <Outlet />
      </main>
    </div>
  );
}
