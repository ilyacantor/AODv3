import React from 'react';

const toneStyles = {
  positive: 'text-mint bg-mint/10 border-mint/30',
  negative: 'text-rose-200 bg-rose-500/10 border-rose-400/30',
  neutral: 'text-white/90 bg-white/5 border-white/10'
};

export default function StatGrid({ stats }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {stats.map((stat) => (
        <div key={stat.label} className={`glass-card p-4 border ${toneStyles[stat.tone] || toneStyles.neutral}`}>
          <p className="text-sm text-white/70">{stat.label}</p>
          <div className="flex items-baseline gap-2">
            <p className="text-2xl font-semibold text-white">{stat.value}</p>
            <span className="text-xs px-2 py-1 rounded-full bg-white/5 text-mint font-medium">{stat.change}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
