import React, { useEffect, useState } from 'react';
import PageHeader from '../components/PageHeader';
import { getSettings } from '../lib/dataClient';

export default function Settings() {
  const [config, setConfig] = useState(null);

  useEffect(() => {
    getSettings().then(setConfig);
  }, []);

  if (!config) return <p className="text-white/70">Loading settings…</p>;

  return (
    <div className="space-y-4">
      <PageHeader title="Settings" subtitle="Preview safe" />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="glass-card p-4 space-y-3">
          <p className="text-sm font-semibold text-white">Notifications</p>
          <div className="space-y-2">
            {config.notifications.map((item) => (
              <div key={item.channel} className="flex items-center justify-between border-b border-white/5 pb-2 last:border-none last:pb-0">
                <div>
                  <p className="text-sm text-white/90">{item.channel}</p>
                  <p className="text-xs text-white/60">{item.target}</p>
                </div>
                <span className="tag">{item.status}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="glass-card p-4 space-y-3">
          <p className="text-sm font-semibold text-white">Feature flags</p>
          <div className="space-y-2">
            {config.featureFlags.map((flag) => (
              <div key={flag.name} className="flex items-center justify-between">
                <p className="text-sm text-white/90">{flag.name}</p>
                <span className="tag">{flag.status}</span>
              </div>
            ))}
          </div>
          <div className="text-xs text-white/60 pt-2 border-t border-white/5">
            API base: <span className="text-mint">{config.apiBase}</span>
          </div>
          <div className="text-xs text-white/60">Last deployed: {config.lastDeployed}</div>
        </div>
      </div>
    </div>
  );
}
