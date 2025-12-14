const envPreview = (import.meta.env.VITE_PREVIEW_MODE ?? process.env.VITE_PREVIEW_MODE ?? 'true')
  .toString()
  .toLowerCase();

export const PREVIEW_MODE = envPreview !== 'false' && envPreview !== '0';
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || process.env.VITE_API_BASE_URL || '';
