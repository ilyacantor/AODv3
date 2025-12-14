import { PREVIEW_MODE, API_BASE_URL } from './config';
import { dashboardStats, heroMetrics } from '../mocks/dashboard';
import { assets, assetDetails } from '../mocks/assets';
import { findings } from '../mocks/findings';
import { runHistory } from '../mocks/runs';
import { settings } from '../mocks/settings';

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function fetchJson(path) {
  const url = `${API_BASE_URL}${path}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Request failed: ${res.status}`);
  return res.json();
}

export async function getDashboard() {
  if (PREVIEW_MODE || !API_BASE_URL) return { stats: dashboardStats, hero: heroMetrics };
  try {
    return await fetchJson('/dashboard');
  } catch (error) {
    console.warn('Falling back to mock dashboard data', error);
    return { stats: dashboardStats, hero: heroMetrics };
  }
}

export async function getAssets() {
  if (PREVIEW_MODE || !API_BASE_URL) return assets;
  try {
    return await fetchJson('/assets');
  } catch (error) {
    console.warn('Falling back to mock assets', error);
    return assets;
  }
}

export async function getAssetById(id) {
  if (PREVIEW_MODE || !API_BASE_URL) return assetDetails[id] ?? assets.find((item) => item.id === id);
  try {
    return await fetchJson(`/assets/${id}`);
  } catch (error) {
    console.warn('Falling back to mock asset', error);
    return assetDetails[id] ?? assets.find((item) => item.id === id);
  }
}

export async function getFindings() {
  if (PREVIEW_MODE || !API_BASE_URL) return findings;
  try {
    return await fetchJson('/findings');
  } catch (error) {
    console.warn('Falling back to mock findings', error);
    return findings;
  }
}

export async function getRuns() {
  if (PREVIEW_MODE || !API_BASE_URL) return runHistory;
  try {
    return await fetchJson('/runs');
  } catch (error) {
    console.warn('Falling back to mock runs', error);
    return runHistory;
  }
}

export async function getSettings() {
  if (PREVIEW_MODE || !API_BASE_URL) return settings;
  try {
    return await fetchJson('/settings');
  } catch (error) {
    console.warn('Falling back to mock settings', error);
    return settings;
  }
}

export async function simulateLatency(fn, delay = 220) {
  await sleep(delay);
  return fn();
}
