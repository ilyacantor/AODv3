export const heroMetrics = {
  title: 'AOD Operational Overview',
  subtitle: 'Unified observability across detection and response',
  updated: 'Just now',
  health: 92,
  trend: '+4.1% vs last week'
};

export const dashboardStats = [
  { label: 'Active Signals', value: '128', change: '+12%', tone: 'positive' },
  { label: 'Assets Protected', value: '64', change: '+6', tone: 'neutral' },
  { label: 'Open Findings', value: '18', change: '-3', tone: 'positive' },
  { label: 'MTTR', value: '42m', change: '-11%', tone: 'positive' }
];

export const activityStream = [
  {
    id: 'evt-1',
    title: 'New dataset ingest: retail_orders_2025_12_14',
    badge: 'ingest',
    time: '2m ago'
  },
  {
    id: 'evt-2',
    title: 'Risk spike contained on warehouse cluster',
    badge: 'risk',
    time: '24m ago'
  },
  {
    id: 'evt-3',
    title: 'Model drift detected: fraud-score-v7',
    badge: 'model',
    time: '1h ago'
  },
  {
    id: 'evt-4',
    title: 'Runbook executed: triage-high-latency',
    badge: 'run',
    time: '2h ago'
  }
];
