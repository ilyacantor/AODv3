import React from 'react';
import { Routes, Route, NavLink, useLocation } from 'react-router-dom';
import { PREVIEW_MODE } from './lib/config';
import Dashboard from './pages/Dashboard';
import AssetCatalog from './pages/AssetCatalog';
import AssetDetail from './pages/AssetDetail';
import Findings from './pages/Findings';
import RunHistory from './pages/RunHistory';
import Settings from './pages/Settings';
import PreviewBanner from './components/PreviewBanner';

const navItems = [
  { to: '/', label: 'Dashboard' },
  { to: '/assets', label: 'Asset Catalog' },
  { to: '/findings', label: 'Findings' },
  { to: '/runs', label: 'Run Logs' },
  { to: '/settings', label: 'Settings' }
];

function Shell({ children }) {
  const location = useLocation();
  return (
    <div className="min-h-screen bg-gradient-aos">
      <div className="mx-auto max-w-7xl px-6 py-6 space-y-6">
        <header className="flex items-center justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-white/60">AOD</p>
            <h1 className="text-2xl font-semibold text-white">Analytics Observability Deck</h1>
          </div>
          <div className="flex items-center gap-3">
            <span className="tag bg-white/10 text-mint">Live preview</span>
            <div className="h-10 w-10 rounded-full bg-white/10 border border-white/10 flex items-center justify-center text-sm text-white/80">
              UI
            </div>
          </div>
        </header>

        <PreviewBanner active={PREVIEW_MODE} />

        <nav className="glass-card flex flex-wrap gap-2 p-2">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `px-4 py-2 rounded-xl text-sm font-medium transition-colors ${
                  isActive || location.pathname.startsWith(`${item.to}/`)
                    ? 'bg-white/10 text-white shadow-inner'
                    : 'text-white/70 hover:bg-white/5'
                }`
              }
              end={item.to === '/'}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <main>{children}</main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route
        path="/"
        element={
          <Shell>
            <Dashboard />
          </Shell>
        }
      />
      <Route
        path="/assets"
        element={
          <Shell>
            <AssetCatalog />
          </Shell>
        }
      />
      <Route
        path="/assets/:id"
        element={
          <Shell>
            <AssetDetail />
          </Shell>
        }
      />
      <Route
        path="/findings"
        element={
          <Shell>
            <Findings />
          </Shell>
        }
      />
      <Route
        path="/runs"
        element={
          <Shell>
            <RunHistory />
          </Shell>
        }
      />
      <Route
        path="/settings"
        element={
          <Shell>
            <Settings />
          </Shell>
        }
      />
    </Routes>
  );
}
