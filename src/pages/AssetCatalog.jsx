import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import PageHeader from '../components/PageHeader';
import TableCard from '../components/TableCard';
import { getAssets, simulateLatency } from '../lib/dataClient';

export default function AssetCatalog() {
  const [assets, setAssets] = useState([]);

  useEffect(() => {
    simulateLatency(() => getAssets()).then(setAssets);
  }, []);

  const columns = [
    {
      key: 'name',
      label: 'Asset',
      render: (value, row) => (
        <Link to={`/assets/${row.id}`} className="text-teal hover:text-mint font-semibold">
          {value}
        </Link>
      )
    },
    { key: 'owner', label: 'Owner' },
    { key: 'tier', label: 'Tier' },
    {
      key: 'status',
      label: 'Status',
      render: (value) => (
        <span className={`px-2 py-1 rounded-full text-xs ${value === 'Warning' ? 'bg-amber-500/10 text-amber-100' : 'bg-emerald-500/10 text-emerald-100'}`}>
          {value}
        </span>
      )
    },
    { key: 'signals', label: 'Signals' },
    { key: 'risks', label: 'Risks' },
    { key: 'updated', label: 'Updated' }
  ];

  return (
    <div className="space-y-4">
      <PageHeader title="Asset Catalog" subtitle="Inventory" />
      <TableCard title="Assets" columns={columns} rows={assets} helper="Mock fixtures" />
    </div>
  );
}
