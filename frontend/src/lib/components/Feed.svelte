<script lang="ts">
	import { onMount } from 'svelte';
	import type { VideoItem } from '$lib/api/types';
	import VideoPlayer from './VideoPlayer.svelte';

	export let items: VideoItem[] = [];
	export let onPageEnd: () => void;

	let container: HTMLDivElement;
	let activeIndex = 0;
	let touchStartY = 0;

	function scrollToActive() {
		if (!container) return;
		const item = container.querySelector(`[data-index="${activeIndex}"]`);
		item?.scrollIntoView({ behavior: 'smooth', block: 'center' });
	}

	onMount(() => {
		scrollToActive();
	});

	function onScroll() {
		if (!container) return;
		const { scrollTop, scrollHeight, clientHeight } = container;
		if (scrollHeight - scrollTop - clientHeight < 400) {
			onPageEnd();
		}
		// Determine active video from scroll position
		const itemsEl = container.querySelectorAll('.snap-item');
		let best = 0;
		let bestDist = Infinity;
		const center = scrollTop + clientHeight / 2;
		itemsEl.forEach((el, i) => {
			const rect = el.getBoundingClientRect();
			const itemCenter = rect.top + rect.height / 2 - container.getBoundingClientRect().top;
			const dist = Math.abs(itemCenter - clientHeight / 2);
			if (dist < bestDist) {
				bestDist = dist;
				best = i;
			}
		});
		activeIndex = best;
	}

	$: if (container) {
		scrollToActive();
	}
</script>

<div class="viewport" bind:this={container} on:scroll={onScroll}>
	{#each items as item, i (item.id)}
		<div class="snap-item" data-index={i}>
			<VideoPlayer video={item} active={i === activeIndex} />
		</div>
	{/each}
</div>

<style>
	.viewport {
		height: 100dvh;
		width: 100%;
		overflow-y: auto;
		scroll-snap-type: y mandatory;
		scroll-behavior: smooth;
	}
	.snap-item {
		height: 100dvh;
		width: 100%;
		scroll-snap-align: center;
		scroll-snap-stop: always;
		position: relative;
		background: #000;
	}
</style>
