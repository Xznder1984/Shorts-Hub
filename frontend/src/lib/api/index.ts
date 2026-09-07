import type { SearchResponse, FeedResponse, StatusResponse } from './types';

/** Base URL for the backend API. Overridable via VITE_API_URL for local dev. */
const BASE = (
	(import.meta.env.VITE_API_URL as string | undefined) ??
	''
).replace(/\/$/, '');

async function request<T>(path: string): Promise<T> {
	const res = await fetch(`${BASE}${path}`);
	if (!res.ok) {
		const body = await res.text();
		throw new Error(`Request failed (${res.status}): ${body}`);
	}
	return res.json() as Promise<T>;
}

export const api = {
	search(query: string, limit = 30, offset = 0): Promise<SearchResponse> {
		return request(`/api/search?q=${encodeURIComponent(query)}&limit=${limit}&offset=${offset}`);
	},
	feed(limit = 30, offset = 0): Promise<FeedResponse> {
		return request(`/api/feed?limit=${limit}&offset=${offset}`);
	},
	status(): Promise<StatusResponse> {
		return request('/api/status');
	}
};
