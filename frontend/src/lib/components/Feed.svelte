<script lang="ts">
	import { onMount } from 'svelte';
	import type { VideoItem } from '$lib/api/types';
	import VideoPlayer from './VideoPlayer.svelte';

	export let items: VideoItem[] = [];
	export let onPageEnd: () => void;

	let container: HTMLDivElement;
	let activeIndex = 0;
	let prevLength = 0;

	onMount(() => {
		prevLength = items.length;
	});

	// When a fresh search loads (shorter list), jump back to the top.
	// Appends (infinite scroll) leave the scroll position untouched.
	$: if (container && items.length !== prevLength) {
		if (items.length < prevLength) {
			container.scrollTop = 0;
		}
		prevLength = items.length;
	}

	function onScroll() {
		if (!container) return;
		const { scrollTop, scrollHeight, clientHeight } = container;
		// Reached within 400px of the end → load more
		if (scrollHeight - scrollTop - clientHeight < 400) {
			onPageEnd();
		}
		// Determine which video is centered (for autoplay / active state)
		const els = container.querySelectorAll('.snap-item');
		let best = 0;
		let bestDist = Infinity;
		const center = scrollTop + clientHeight / 2;
		els.forEach((el, i) => {
			const rect = el.getBoundingClientRect();
			const itemCenter = rect.top + rect.height / 2;
			const dist = Math.abs(itemCenter - center - container.getBoundingClientRect().top);
			if (dist < bestDist) {
				bestDist = dist;
				best = i;
			}
		});
		if (best !== activeIndex) activeIndex = best;
	}
</script>

<div class="viewport" bind:this={container} on:scroll={onScroll}>
	{#each items as item, i (item.id)}
		<div class="snap-item">
			<VideoPlayer video={item} active={i === activeIndex} />
		</div>
	{/each}
</div>

<style>
	.viewport {
		height: 100%;
		width: 100%;
		overflow-y: auto;
		scroll-snap-type: y mandatory;
		scroll-behavior: smooth;
	}
	.snap-item {
		height: 100%;
		width: 100%;
		scroll-snap-align: start;
		scroll-snap-stop: always;
		position: relative;
		background: #000;
	}
</style>