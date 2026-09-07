import { writable, get } from 'svelte/store';
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

const PAGE = 30;

function dedupeAppend(existing: VideoItem[], incoming: VideoItem[]): VideoItem[] {
	const seen = new Set(existing.map((v) => v.id));
	const fresh = incoming.filter((v) => !seen.has(v.id));
	return [...existing, ...fresh];
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
				const res = await api.search(q, PAGE, 0);
				update((s) => ({
					...s,
					items: res.results,
					loading: false,
					offset: PAGE,
					hasMore: res.results.length >= PAGE
				}));
			} catch (e) {
				update((s) => ({ ...s, loading: false, error: e instanceof Error ? e.message : 'Search failed' }));
			}
		},
		async loadFeed() {
			update((s) => ({ ...s, items: [], query: '', loading: true, error: null, offset: 0, hasMore: true }));
			try {
				const res = await api.feed(PAGE, 0);
				update((s) => ({
					...s,
					items: res.results,
					loading: false,
					offset: PAGE,
					hasMore: res.results.length >= PAGE
				}));
			} catch (e) {
				update((s) => ({ ...s, loading: false, error: e instanceof Error ? e.message : 'Feed failed' }));
			}
		},
		async more() {
			const s = get({ subscribe });
			if (s.loading || !s.hasMore) return;
			update((state) => ({ ...state, loading: true }));
			try {
				const res = s.query
					? await api.search(s.query, PAGE, s.offset)
					: await api.feed(PAGE, s.offset);
				update((state) => ({
					...state,
					items: dedupeAppend(state.items, res.results),
					loading: false,
					offset: state.offset + PAGE,
					hasMore: res.results.length >= PAGE
				}));
			} catch (e) {
				update((state) => ({
					...state,
					loading: false,
					error: e instanceof Error ? e.message : 'Load more failed'
				}));
			}
		},
		reset() {
			set({ items: [], query: '', loading: false, error: null, hasMore: true, offset: 0 });
		}
	};
}

export const feed = createFeedStore();