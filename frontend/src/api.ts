import axios from 'axios';

// Served by the API itself (browser) -> same origin. Inside the Tauri webview -> talk to localhost:8000.
export const BASE = typeof location !== 'undefined' && location.port === '8000' ? '' : 'http://localhost:8000';
export const http = axios.create({ baseURL: BASE + '/api', timeout: 600000 });

export const get = <T = any>(url: string, params?: any) => http.get<T>(url, { params }).then(r => r.data);
export const post = <T = any>(url: string, body?: any) => http.post<T>(url, body ?? {}).then(r => r.data);
export const put = <T = any>(url: string, body?: any) => http.put<T>(url, body ?? {}).then(r => r.data);
export const patch = <T = any>(url: string, body?: any) => http.patch<T>(url, body ?? {}).then(r => r.data);
export const del = <T = any>(url: string) => http.delete<T>(url).then(r => r.data);

export const errText = (e: any): string =>
  e?.response?.data?.detail || (e?.code === 'ERR_NETWORK' ? 'Can’t reach the SmartWard backend.' : e?.message || 'Something went wrong.');

export function ago(ts?: number | null) {
  if (!ts) return '';
  const s = Date.now() / 1000 - ts;
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  if (s < 86400 * 14) return `${Math.floor(s / 86400)}d ago`;
  return new Date(ts * 1000).toLocaleDateString();
}
