<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { feed } from '$lib/stores/feed';
	import SearchBar from '$lib/components/SearchBar.svelte';
	import Feed from '$lib/components/Feed.svelte';
	import { api } from '$lib/api';

	let lastQuery: string | null = null;
	$: q = $page.url.searchParams.get('q') ?? '';

	// Runs when the ?q= param changes (initial load AND hashtag-link clicks,
	// which SvelteKit handles as client-side navigation without re-mounting).
	$: if (q !== lastQuery) {
		lastQuery = q;
		if (q) {
			feed.search(q);
		} else {
			feed.loadFeed();
		}
	}

	function handleSearch(query: string) {
		const existing = $page.url.searchParams.get('q') ?? '';
		if (existing === query) {
			// Same query re-submitted (e.g. re-pressing Enter) — reload explicitly.
			feed.search(query);
			return;
		}
		goto(`/?q=${encodeURIComponent(query)}`, { replaceState: true });
	}

	function handlePageEnd() {
		feed.more();
	}

	let available: string[] = [];
	onMount(async () => {
		try {
			const s = await api.status();
			available = s.available_sources;
		} catch {
			available = [];
		}
	});
</script>

<svelte:head>
	<title>Shorts Hub</title>
</svelte:head>

<div class="app">
	<header class="topbar">
		<div class="brand">
			<span class="logo">▶</span>
			<h1>Shorts&nbsp;Hub</h1>
		</div>
		<div class="search-wrap">
			<SearchBar value={$feed.query} onSearch={handleSearch} />
		</div>
		<div class="sources">
			{#each ['youtube', 'tiktok', 'instagram'] as s (s)}
				<span class="source-dot {available.includes(s) ? 'on' : 'off'}" title={s}>{s.slice(0, 2).toUpperCase()}</span>
			{/each}
		</div>
	</header>

	<main class="stage">
		{#if $feed.loading && $feed.items.length === 0}
			<div class="empty">Loading…</div>
		{:else if $feed.error && $feed.items.length === 0}
			<div class="empty error">
				<p>{$feed.error}</p>
				<button on:click={() => ($feed.query ? feed.search($feed.query) : feed.loadFeed())}>Retry</button>
			</div>
		{:else if $feed.items.length === 0 && !$feed.loading}
			<div class="empty">
				<p>No results yet. Try a search above, or load the feed.</p>
				<button on:click={() => feed.loadFeed()}>Explore feed</button>
			</div>
		{:else}
			<Feed items={$feed.items} onPageEnd={handlePageEnd} />
		{/if}
	</main>
</div>

<style>
	.app {
		display: flex;
		flex-direction: column;
		height: 100dvh;
		width: 100%;
	}
	.topbar {
		display: flex;
		align-items: center;
		gap: 16px;
		padding: calc(10px + env(safe-area-inset-top)) 16px 10px;
		background: rgba(15, 15, 15, 0.95);
		backdrop-filter: blur(8px);
		border-bottom: 1px solid var(--border);
		z-index: 10;
	}
	.brand {
		display: flex;
		align-items: center;
		gap: 8px;
		flex-shrink: 0;
	}
	.logo {
		color: var(--accent);
		font-size: 20px;
	}
	.brand h1 {
		font-size: 18px;
		font-weight: 800;
		letter-spacing: -0.5px;
	}
	.search-wrap {
		flex: 1;
		display: flex;
		justify-content: center;
	}
	.sources {
		display: flex;
		gap: 6px;
		flex-shrink: 0;
	}
	.source-dot {
		width: 22px;
		height: 22px;
		border-radius: 6px;
		font-size: 9px;
		font-weight: 700;
		display: flex;
		align-items: center;
		justify-content: center;
	}
	.source-dot.on {
		background: var(--accent);
		color: #fff;
	}
	.source-dot.off {
		background: var(--bg-card);
		color: var(--text-muted);
	}
	.stage {
		flex: 1;
		position: relative;
		overflow: hidden;
	}
	.empty {
		height: 100%;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 14px;
		color: var(--text-muted);
		padding: 20px;
		text-align: center;
	}
	.empty.error {
		color: #ff6b6b;
	}
	.empty button {
		background: var(--accent);
		color: #fff;
		padding: 10px 20px;
		border-radius: 999px;
		font-weight: 600;
	}

	@media (max-width: 640px) {
		.brand h1 {
			display: none;
		}
		.sources {
			display: none;
		}
	}
</style>
