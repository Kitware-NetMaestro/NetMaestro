document.addEventListener('alpine:init', () => {
    Alpine.store('state', {
        activeAnalysisTab: 'events',
        selectedRunId: null,
    });
});
