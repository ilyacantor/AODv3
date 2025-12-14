import React from 'react';
import { PREVIEW_MODE, API_BASE_URL } from '../lib/config';

export default function PreviewBanner({ active }) {
  if (!active) return null;
  return (
    <div className="glass-card border border-mint/40 shadow-glass px-4 py-3 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="h-10 w-10 rounded-xl bg-mint/20 border border-mint/30 flex items-center justify-center text-mint font-semibold">
          Ⓟ
        </div>
        <div>
          <p className="text-sm font-semibold text-white">Preview Mode (mock data)</p>
          <p className="text-xs text-white/70">
            PREVIEW_MODE is enabled. All data is served from local fixtures and no backend or database is required.
          </p>
        </div>
      </div>
      <div className="text-xs text-white/60">
        API base when disabled: <span className="text-mint">{API_BASE_URL || 'not configured'}</span>
      </div>
    </div>
  );
}
