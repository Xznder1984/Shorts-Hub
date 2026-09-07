<script lang="ts">
	export let value: string = '';
	export let placeholder: string = 'Search shorts…';
	export let onSearch: (q: string) => void;

	let input: HTMLInputElement;
	let submit = () => {
		const q = (input?.value ?? '').trim();
		if (q) onSearch(q);
	};
</script>

<form on:submit|preventDefault={submit} class="searchbar">
	<span class="icon">🔍</span>
	<input
		bind:this={input}
		type="search"
		bind:value
		{placeholder}
		autocomplete="off"
		autocapitalize="off"
		spellcheck="false"
	/>
	<button type="submit" aria-label="Search" class="go">Search</button>
</form>

<style>
	.searchbar {
		display: flex;
		align-items: center;
		gap: 8px;
		background: var(--bg-elevated);
		border: 1px solid var(--border);
		border-radius: 999px;
		padding: 6px 6px 6px 14px;
		max-width: 600px;
		width: 100%;
	}
	.icon {
		color: var(--text-muted);
		font-size: 14px;
	}
	input {
		flex: 1;
		background: none;
		border: none;
		outline: none;
		color: var(--text);
		font-size: 15px;
		padding: 6px 0;
		min-width: 0;
	}
	.go {
		background: var(--accent);
		color: #fff;
		font-weight: 600;
		font-size: 13px;
		padding: 8px 18px;
		border-radius: 999px;
		white-space: nowrap;
	}
	.go:hover {
		filter: brightness(1.1);
	}
</style>
