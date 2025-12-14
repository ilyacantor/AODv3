import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import PageHeader from '../components/PageHeader';
import { getAssetById } from '../lib/dataClient';

export default function AssetDetail() {
  const { id } = useParams();
  const [asset, setAsset] = useState(null);

  useEffect(() => {
    getAssetById(id).then(setAsset);
  }, [id]);

  if (!asset) return <p className="text-white/70">Loading asset…</p>;

  return (
    <div className="space-y-4">
      <PageHeader
        title={asset.name || id}
        subtitle="Asset detail"
        actions={
          <Link to="/assets" className="px-3 py-2 rounded-xl bg-white/10 text-sm text-white/80 border border-white/10">
            Back to catalog
          </Link>
        }
      />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="glass-card p-4 space-y-3 lg:col-span-2">
          <div>
            <p className="text-sm text-white/60">Description</p>
            <p className="text-white/90">{asset.description}</p>
          </div>
          <div className="flex flex-wrap gap-3">
            <span className="tag">{asset.lifecycle}</span>
            {asset.tags?.map((tag) => (
              <span key={tag} className="tag">
                {tag}
              </span>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="glass-card p-3">
              <p className="text-xs text-white/60">Datasets</p>
              <p className="text-sm text-white/90">{asset.datasets?.join(', ')}</p>
            </div>
            <div className="glass-card p-3">
              <p className="text-xs text-white/60">Owners</p>
              <p className="text-sm text-white/90">{asset.owners?.join(', ')}</p>
            </div>
          </div>
        </div>
        <div className="glass-card p-4 space-y-3">
          <p className="text-sm font-semibold text-white">Run cadence</p>
          <p className="text-sm text-white/80">Last run at {asset.lastRun}</p>
          <div className="h-28 rounded-xl border border-white/5 bg-gradient-to-br from-white/5 to-white/0 flex items-center justify-center text-white/50">
            Sparkline placeholder (mocked)
          </div>
        </div>
      </div>
    </div>
  );
}
