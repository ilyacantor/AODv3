import React, { useEffect, useState } from 'react';
import PageHeader from '../components/PageHeader';
import TableCard from '../components/TableCard';
import { getRuns, simulateLatency } from '../lib/dataClient';

export default function RunHistory() {
  const [runs, setRuns] = useState([]);

  useEffect(() => {
    simulateLatency(() => getRuns()).then(setRuns);
  }, []);

  const columns = [
    { key: 'name', label: 'Run' },
    { key: 'status', label: 'Status', render: (val) => <span className="tag">{val}</span> },
    { key: 'duration', label: 'Duration' },
    { key: 'triggeredBy', label: 'Triggered By' },
    { key: 'timestamp', label: 'Timestamp' }
  ];

  return (
    <div className="space-y-4">
      <PageHeader title="Run Logs & History" subtitle="Executions" />
      <TableCard title="Recent runs" columns={columns} rows={runs} helper="Mock fixtures" />
    </div>
  );
}
