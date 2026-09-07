export type Source = 'youtube' | 'tiktok' | 'instagram';

export interface VideoItem {
	id: string;
	source: Source;
	video_url?: string | null;
	thumbnail_url?: string | null;
	caption: string;
	hashtags: string[];
	author_name: string;
	author_handle: string;
	author_profile_url?: string | null;
	channel_url?: string | null;
	original_post_url?: string | null;
	published_at?: string | null;
	duration_seconds?: number | null;
	embed_url?: string | null;
	can_embed: boolean;
}

export interface SearchResponse {
	query: string;
	count: number;
	results: VideoItem[];
}

export interface FeedResponse {
	count: number;
	results: VideoItem[];
}

export interface StatusResponse {
	available_sources: string[];
	disabled_sources: string[];
	version: string;
}
