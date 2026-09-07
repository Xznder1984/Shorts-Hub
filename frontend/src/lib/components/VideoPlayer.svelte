<script lang="ts">
	import type { VideoItem } from '$lib/api/types';

	export let video: VideoItem;
	export let active: boolean = false;
</script>

<article class="card" class:active>
	{#if video.can_embed && video.embed_url}
		<div class="media">
			<iframe
				src={active ? `${video.embed_url}?autoplay=1&mute=1&playsinline=1&rel=0` : ''}
				title="video player"
				allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
				allowfullscreen
				loading="lazy"
			></iframe>
		</div>
	{:else if video.video_url}
		<div class="media">
			<video
				src={active ? video.video_url : undefined}
				poster={video.thumbnail_url ?? undefined}
				controls
				playsinline
				autoplay={active}
				muted={active}
				controlslist="nodownload"
				preload={active ? 'metadata' : 'none'}
			></video>
		</div>
	{:else}
		<div class="media fallback">
			{#if video.thumbnail_url}
				<img src={video.thumbnail_url} alt={video.caption} loading="lazy" />
			{/if}
			<div class="fallback-overlay">
				<span>Direct play unavailable</span>
				{#if video.original_post_url}
					<a href={video.original_post_url} target="_blank" rel="noopener" class="open-btn">Open original ↗</a>
				{/if}
			</div>
		</div>
	{/if}

	<div class="meta">
		<div class="header-row">
			<span class="badge badge-{video.source}">{video.source}</span>
			{#if video.author_handle}
				<a
					class="author"
					href={video.author_profile_url ?? video.original_post_url}
					target="_blank"
					rel="noopener"
				>
					@{video.author_handle}
				</a>
			{/if}
		</div>

		{#if video.caption}
			<p class="caption">{video.caption}</p>
		{/if}

		{#if video.hashtags?.length}
			<div class="tags">
				{#each video.hashtags as tag (tag)}
					<a class="tag" href="/?q=%23{tag}">{`#${tag}`}</a>
				{/each}
			</div>
		{/if}

		<div class="actions">
			{#if video.original_post_url}
				<a href={video.original_post_url} target="_blank" rel="noopener" class="action-link">
					Open original ↗
				</a>
			{/if}
		</div>
	</div>
</article>

<style>
	.card {
		position: relative;
		height: 100%;
		width: 100%;
		overflow: hidden;
		background: var(--bg);
	}
	.media {
		position: absolute;
		inset: 0;
		display: flex;
		align-items: center;
		justify-content: center;
	}
	.media :global(iframe),
	.media :global(video),
	.media :global(img) {
		width: 100%;
		height: 100%;
		object-fit: contain;
		border: none;
		background: #000;
	}
	.fallback img {
		object-fit: cover;
		filter: brightness(0.5);
	}
	.fallback-overlay {
		position: absolute;
		inset: 0;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 12px;
		color: #fff;
		font-size: 14px;
		text-align: center;
		padding: 16px;
	}
	.open-btn {
		background: var(--accent);
		color: #fff;
		padding: 10px 18px;
		border-radius: 999px;
		font-weight: 600;
	}
	.meta {
		position: absolute;
		left: 0;
		right: 0;
		bottom: 0;
		padding: 48px 16px 20px;
		background: linear-gradient(to top, rgba(0, 0, 0, 0.85), transparent);
		pointer-events: none;
	}
	/* Re-enable pointer events for interactive child elements */
	.meta :global(a),
	.meta .tags,
	.meta .actions {
		pointer-events: auto;
	}
	.header-row {
		display: flex;
		align-items: center;
		gap: 10px;
		margin-bottom: 8px;
	}
	.badge {
		text-transform: uppercase;
		font-size: 11px;
		font-weight: 700;
		letter-spacing: 0.5px;
		padding: 3px 8px;
		border-radius: 6px;
	}
	.badge-youtube {
		background: #ff0000;
		color: #fff;
	}
	.badge-tiktok {
		background: var(--accent);
		color: #fff;
	}
	.badge-instagram {
		background: linear-gradient(45deg, #f09433, #e6683c, #dc2743, #cc2366, #bc1888);
		color: #fff;
	}
	.author {
		font-weight: 600;
		font-size: 14px;
		color: #fff;
	}
	.caption {
		font-size: 14px;
		line-height: 1.4;
		color: #fff;
		margin-bottom: 8px;
		display: -webkit-box;
		-webkit-line-clamp: 4;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}
	.tags {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
		margin-bottom: 10px;
		padding-bottom: 12px;
	}
	.tag {
		background: rgba(255, 255, 255, 0.15);
		color: var(--accent-2);
		padding: 4px 10px;
		border-radius: 999px;
		font-size: 12px;
		font-weight: 600;
	}
	.actions {
		display: flex;
		gap: 10px;
	}
	.action-link {
		background: rgba(255, 255, 255, 0.15);
		color: #fff;
		padding: 8px 14px;
		border-radius: 999px;
		font-size: 13px;
		font-weight: 600;
	}
</style>
