/**
 * Alpine.js component for the topology page.
 * Loads a topology preset and draws it on a Cytoscape canvas.
 */
import cytoscape from 'cytoscape';

/**
 * Canvas colors
 */
const THEME = {
  switchFill: '#1d232a',
  switchBorder: '#00b5ff',
  label: '#ffffff',
  link: '#6b7683',
  linkLabel: '#a6adba',
};

const NODE_WIDTH = 96;
const NODE_HEIGHT = 56;
const FIT_PADDING = 30;

/**
 * Build the Cytoscape stylesheet for the topology graph.
 *
 * @returns {Array} Cytoscape style entries
 */
const graphStyle = () => [
  {
    selector: 'node',
    style: {
      shape: 'round-rectangle',
      width: NODE_WIDTH,
      height: NODE_HEIGHT,
      'background-color': THEME.switchFill,
      'border-color': THEME.switchBorder,
      'border-width': 2,
      label: 'data(name)',
      color: THEME.label,
      'font-size': 14,
      'text-valign': 'center',
      'text-halign': 'center',
    },
  },
  {
    selector: 'edge',
    style: {
      'curve-style': 'bezier',
      'target-arrow-shape': 'triangle',
      'line-color': THEME.link,
      'target-arrow-color': THEME.link,
      width: 2,
      label: 'data(bandwidthLabel)',
      color: THEME.linkLabel,
      'font-size': 10,
      'text-rotation': 'autorotate',
      'text-background-color': THEME.switchFill,
      'text-background-opacity': 0.85,
      'text-background-padding': 2,
    },
  },
];

/**
 * Convert an API topology payload into Cytoscape elements.
 *
 * @param {Object} topology - Value from the topology detail endpoint
 * @returns {Array} Cytoscape element definitions
 */
const toElements = (topology) => [
  ...topology.switches.map((item) => ({
    data: {
      id: item.name,
      name: item.name,
      terminals: item.terminals,
      terminalBandwidth: item.terminal_bandwidth,
      switchBuffer: item.switch_buffer,
    },
  })),
  ...topology.links.map((link) => ({
    data: {
      id: `${link.source}->${link.target}`,
      source: link.source,
      target: link.target,
      bandwidth: link.bandwidth,
      bandwidthLabel: link.bandwidth_label,
    },
  })),
];

export const topologyCanvas = () => {
  // Outside of the Alpine data object on purpose: With Alpine, its properties
  // are deeply reactive. Wrapping a Cytoscape instance that way seems to break things.
  let cy = null;
  let resizeObserver = null;
  // The container keeps growing after the graph is built. Refit on every
  // resize until the user starts interacting.
  let autoFit = true;

  return {
    loading: false,
    error: null,
    topology: null,

    destroy() {
      this.teardown();
    },

    teardown() {
      resizeObserver?.disconnect();
      resizeObserver = null;
      cy?.destroy();
      cy = null;
    },

    /**
     * Load the preset chosen in the dropdown and draw it.
     *
     * @param {HTMLSelectElement} selectEl - The preset dropdown element
     */
    async select(selectEl) {
      const url = selectEl.selectedOptions[0]?.dataset.url;
      this.error = null;
      if (!url) {
        this.teardown();
        this.topology = null;
        return;
      }
      this.loading = true;
      try {
        const response = await fetch(url);
        if (!response.ok) {
          throw new Error(`Request failed with status ${response.status}`);
        }
        this.topology = await response.json();
      } catch (error) {
        this.teardown();
        this.topology = null;
        this.error = `Could not load topology: ${error.message}`;
        return;
      } finally {
        this.loading = false;
      }
      this.$nextTick(() => this.draw());
    },

    /**
     * Render the loaded topology onto the canvas.
     */
    draw() {
      const container = this.$refs.canvas;
      if (!(container && this.topology)) {
        return;
      }
      this.teardown();
      autoFit = true;
      cy = cytoscape({
        container,
        elements: toElements(this.topology),
        style: graphStyle(),
      });

      const layout = cy.layout({
        name: 'cose',
        animate: false,
        nodeDimensionsIncludeLabels: true,
        fit: false,
      });
      layout.one('layoutstop', () => this.fitToView());
      layout.run();

      resizeObserver = new ResizeObserver(() => {
        cy?.resize();
        if (autoFit) {
          cy?.fit(undefined, FIT_PADDING);
        }
      });
      resizeObserver.observe(container);

      const releaseViewport = () => {
        autoFit = false;
      };
      container.addEventListener('pointerdown', releaseViewport, { once: true });
      container.addEventListener('wheel', releaseViewport, { once: true, passive: true });
    },

    /**
     * Re-fit the graph into the visible canvas area.
     */
    fitToView() {
      cy?.resize();
      cy?.fit(undefined, FIT_PADDING);
    },
  };
};
