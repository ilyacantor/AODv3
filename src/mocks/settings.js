export const settings = {
  notifications: [
    { channel: 'Slack', status: 'Enabled', target: '#aod-alerts' },
    { channel: 'Email', status: 'Enabled', target: 'aod-ops@company.com' },
    { channel: 'PagerDuty', status: 'Disabled', target: 'AOD / Tier 1' }
  ],
  featureFlags: [
    { name: 'Auto-mitigate drift', status: 'On' },
    { name: 'Adaptive thresholds', status: 'On' },
    { name: 'LLM triage summaries', status: 'Preview' }
  ],
  apiBase: 'Mocked in preview mode',
  lastDeployed: '2025-12-13 22:10 UTC'
};
