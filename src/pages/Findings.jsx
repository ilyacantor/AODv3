import React, { useEffect, useState } from 'react';
import PageHeader from '../components/PageHeader';
import TableCard from '../components/TableCard';
import { getFindings, simulateLatency } from '../lib/dataClient';

export default function Findings() {
  const [rows, setRows] = useState([]);

  useEffect(() => {
    simulateLatency(() => getFindings()).then(setRows);
  }, []);

  const columns = [
    { key: 'title', label: 'Finding' },
    { key: 'severity', label: 'Severity', render: (val) => <span className="tag bg-white/5">{val}</span> },
    { key: 'status', label: 'Status' },
    { key: 'owner', label: 'Owner' },
    { key: 'updated', label: 'Updated' }
  ];

  return (
    <div className="space-y-4">
      <PageHeader title="Findings & Risks" subtitle="Live signals" />
      <TableCard title="Risks" columns={columns} rows={rows} helper="Mock fixtures" />
    </div>
  );
}
