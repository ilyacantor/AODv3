import React from 'react';

const badgeClasses = {
  ingest: 'bg-emerald-500/10 text-emerald-200 border-emerald-500/20',
  risk: 'bg-amber-500/10 text-amber-200 border-amber-500/20',
  model: 'bg-sky-500/10 text-sky-200 border-sky-500/20',
  run: 'bg-indigo-500/10 text-indigo-200 border-indigo-500/20'
};

export default function ActivityList({ items }) {
  return (
    <div className="glass-card p-4">
      <div className="flex items-center justify-between mb-3">
        <p className="text-sm font-semibold text-white">Live signals</p>
        <span className="text-xs text-white/60">Live refresh mocked</span>
      </div>
      <div className="space-y-3">
        {items.map((item) => (
          <div key={item.id} className="flex items-center justify-between border-b border-white/5 pb-3 last:border-none last:pb-0">
            <div className="flex items-center gap-3">
              <span className={`text-xs px-2 py-1 rounded-full border ${badgeClasses[item.badge] || 'bg-white/5 text-white/80 border-white/10'}`}>
                {item.badge}
              </span>
              <p className="text-sm text-white/90">{item.title}</p>
            </div>
            <span className="text-xs text-white/60">{item.time}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
