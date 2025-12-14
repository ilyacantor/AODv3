import React from 'react';

export default function Hero({ hero }) {
  return (
    <div className="glass-card p-6 flex flex-wrap items-center justify-between gap-4">
      <div>
        <p className="text-sm text-white/60">{hero.subtitle}</p>
        <h2 className="text-2xl font-semibold text-white">{hero.title}</h2>
        <p className="text-xs text-white/60 mt-2">Updated {hero.updated}</p>
      </div>
      <div className="flex items-center gap-6">
        <div className="text-right">
          <p className="text-white/70 text-sm">Platform health</p>
          <p className="text-3xl font-semibold text-mint">{hero.health}%</p>
        </div>
        <span className="tag">{hero.trend}</span>
      </div>
    </div>
  );
}
