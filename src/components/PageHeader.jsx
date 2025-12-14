import React from 'react';

export default function PageHeader({ title, subtitle, actions }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
      <div>
        <p className="text-xs uppercase tracking-[0.3em] text-white/60">{subtitle}</p>
        <h2 className="text-xl font-semibold text-white">{title}</h2>
      </div>
      {actions && <div className="flex gap-2">{actions}</div>}
    </div>
  );
}
