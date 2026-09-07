import { writable } from 'svelte/store';
import type { VideoItem } from '../api/types';
import { api } from '../api';

export interface FeedState {
	items: VideoItem[];
	query: string;
	loading: boolean;
	error: string | null;
	hasMore: boolean;
	offset: number;
}

function createFeedStore() {
	const { subscribe, set, update } = writable<FeedState>({
		items: [],
		query: '',
		loading: false,
		error: null,
		hasMore: true,
		offset: 0
	});

	return {
		subscribe,
		async search(q: string) {
			update((s) => ({ ...s, items: [], query: q, loading: true, error: null, offset: 0, hasMore: true }));
			try {
				const res = await api.search(q, 30, 0);
				update((s) => ({ ...s, items: res.results, loading: false, offset: 30, hasMore: res.results.length >= 30 }));
			} catch (e) {
				update((s) => ({ ...s, loading: false, error: e instanceof Error ? e.message : 'Search failed' }));
			}
		},
		async loadFeed() {
			update((s) => ({ ...s, items: [], query: '', loading: true, error: null, offset: 0, hasMore: true }));
			try {
				const res = await api.feed(30, 0);
				update((s) => ({ ...s, items: res.results, loading: false, offset: 30, hasMore: res.results.length >= 30 }));
			} catch (e) {
				update((s) => ({ ...s, loading: false, error: e instanceof Error ? e.message : 'Feed failed' }));
			}
		},
		async more() {
			let current: FeedState | undefined;
			update((s) => ((current = s), s));
			if (!current || current.loading || !current.hasMore) return;
			update((s) => ({ ...s, loading: true }));
			try {
				const q = current.query;
				const res = q ? await api.search(q, 30, current.offset) : await api.feed(30, current.offset);
				update((s) => ({
					...s,
					items: [...s.items, ...res.results],
					loading: false,
					offset: s.offset + 30,
					hasMore: res.results.length >= 30
				}));
			} catch (e) {
				update((s) => ({ ...s, loading: false, error: e instanceof Error ? e.message : 'Load more failed' }));
			}
		},
		reset() {
			set({ items: [], query: '', loading: false, error: null, hasMore: true, offset: 0 });
		}
	};
}

export const feed = createFeedStore();
