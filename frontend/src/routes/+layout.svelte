<script lang="ts">
	import { onMount } from 'svelte';
	import '../app.css';

	onMount(() => {
		if (import.meta.env.PROD && 'serviceWorker' in navigator) {
			navigator.serviceWorker.register('/service-worker.js', { scope: '/' }).catch(() => {});
		}
	});
</script>

<slot />
