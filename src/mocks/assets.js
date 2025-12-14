export const assets = [
  {
    id: 'asset-001',
    name: 'Fraud Detection Service',
    owner: 'Payments',
    tier: 'Tier 1',
    status: 'Healthy',
    signals: 24,
    risks: 3,
    updated: '5m ago'
  },
  {
    id: 'asset-002',
    name: 'Orders Warehouse',
    owner: 'Data Platform',
    tier: 'Tier 1',
    status: 'Warning',
    signals: 18,
    risks: 5,
    updated: '12m ago'
  },
  {
    id: 'asset-003',
    name: 'Realtime Scoring API',
    owner: 'Fraud',
    tier: 'Tier 2',
    status: 'Healthy',
    signals: 11,
    risks: 1,
    updated: '22m ago'
  }
];

export const assetDetails = {
  'asset-001': {
    id: 'asset-001',
    description: 'Low-latency fraud detection service monitoring transactions in-flight.',
    lifecycle: 'Production',
    datasets: ['transactions', 'users', 'ruleset_v7'],
    owners: ['Alex Stone', 'Priya K.'],
    tags: ['realtime', 'payments', 'fraud'],
    lastRun: '2025-12-14T12:12:00Z'
  },
  'asset-002': {
    id: 'asset-002',
    description: 'Central warehouse powering BI and finance reporting.',
    lifecycle: 'Production',
    datasets: ['orders_fact', 'customers_dim'],
    owners: ['Lena Shaw'],
    tags: ['warehouse', 'finance'],
    lastRun: '2025-12-14T10:30:00Z'
  }
};
