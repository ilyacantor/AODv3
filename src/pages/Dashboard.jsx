import React, { useEffect, useState } from 'react';
import Hero from '../components/Hero';
import StatGrid from '../components/StatGrid';
import ActivityList from '../components/ActivityList';
import PageHeader from '../components/PageHeader';
import { getDashboard } from '../lib/dataClient';
import { activityStream } from '../mocks/dashboard';

export default function Dashboard() {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState({ hero: {}, stats: [] });

  useEffect(() => {
    getDashboard()
      .then((payload) => setData(payload))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="text-white/70">Loading dashboard…</p>;

  return (
    <div className="space-y-4">
      <PageHeader title="Dashboard" subtitle="Command center" />
      <Hero hero={data.hero} />
      <StatGrid stats={data.stats} />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <ActivityList items={activityStream} />
        <div className="glass-card p-4 lg:col-span-2">
          <div className="flex items-center justify-between mb-3">
            <p className="text-sm font-semibold text-white">Lifecycle snapshot</p>
            <span className="text-xs text-white/60">Mocked chart</span>
          </div>
          <div className="h-48 bg-gradient-to-r from-white/5 via-white/0 to-white/5 rounded-xl border border-white/5 flex items-center justify-center text-white/50">
            <span>Charts render with mock series in preview mode</span>
          </div>
        </div>
      </div>
    </div>
  );
}
