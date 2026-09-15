/**
 * Alpine.js component for the topology page.
 * Loads a topology preset and exposes it for display.
 */
export const topologyCanvas = () => ({
  loading: false,
  error: null,
  topology: null,

  /**
   * Load the preset chosen from the dropdown.
   *
   * @param {HTMLSelectElement} selectEl - The preset dropdown element
   */
  async select(selectEl) {
    const url = selectEl.selectedOptions[0]?.dataset.url;
    if (!url) {
      this.topology = null;
      this.error = null;
      return;
    }
    this.loading = true;
    this.error = null;
    try {
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
      }
      this.topology = await response.json();
    } catch (error) {
      this.topology = null;
      this.error = `Could not load topology: ${error.message}`;
    } finally {
      this.loading = false;
    }
  },
});
