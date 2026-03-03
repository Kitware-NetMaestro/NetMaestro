document.addEventListener('alpine:init', () => {
    Alpine.store('state', {
        activeAnalysisTab: 'network',
        selectedRunId: null,
    });
});
