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
  terminal: '#00b5ff',
  terminalOverflow: '#a6adba',
};

const FIT_PADDING = 30;
const MAX_FIT_ZOOM = 1.5;

// Terminal badges drawn inside each node.
const STRIP_HEIGHT = 16;
const TERMINAL_ICON_LIMIT = 6;
const ICON_WIDTH = 9;
const ICON_HEIGHT = 8;
const ICON_GAP = 3;
const OVERFLOW_TEXT_WIDTH = 22;
const MAX_ICONS_WIDTH = TERMINAL_ICON_LIMIT * ICON_WIDTH + (TERMINAL_ICON_LIMIT - 1) * ICON_GAP;
const STRIP_WIDTH = MAX_ICONS_WIDTH + ICON_GAP + OVERFLOW_TEXT_WIDTH;
const NODE_WIDTH = STRIP_WIDTH + 16;
const NODE_HEIGHT = 64;

/**
 * Draw a node's terminals as a strip of small icons.
 *
 * Switches with more terminals than fit are drawn up to the limit followed by
 * a "+N" count, so it stays readable.
 *
 * @param {number} count - Number of terminals attached to the switch
 * @returns {string} SVG data URI, or 'none' when the switch has no terminals
 */
const terminalStrip = (count) => {
  if (!count) {
    return 'none';
  }
  const shown = Math.min(count, TERMINAL_ICON_LIMIT);
  const overflow = count - shown;
  const iconsWidth = shown * ICON_WIDTH + (shown - 1) * ICON_GAP;
  const totalWidth = iconsWidth + (overflow ? ICON_GAP + OVERFLOW_TEXT_WIDTH : 0);
  const left = (STRIP_WIDTH - totalWidth) / 2;
  const top = (STRIP_HEIGHT - ICON_HEIGHT) / 2;

  const icons = Array.from({ length: shown }, (_, index) => {
    const x = left + index * (ICON_WIDTH + ICON_GAP);
    return `<rect x="${x}" y="${top}" width="${ICON_WIDTH}" height="${ICON_HEIGHT}" rx="2" fill="${THEME.terminal}"/>`;
  }).join('');

  const overflowLabel = overflow
    ? `<text x="${left + iconsWidth + ICON_GAP}" y="${STRIP_HEIGHT - 4}" font-family="sans-serif" font-size="10" fill="${THEME.terminalOverflow}">+${overflow}</text>`
    : '';

  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${STRIP_WIDTH}" height="${STRIP_HEIGHT}" viewBox="0 0 ${STRIP_WIDTH} ${STRIP_HEIGHT}">${icons}${overflowLabel}</svg>`;
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
};

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
      'text-margin-y': -8,
      'background-image': 'data(terminalIcons)',
      'background-fit': 'none',
      'background-width': `${STRIP_WIDTH}px`,
      'background-height': `${STRIP_HEIGHT}px`,
      'background-position-x': '50%',
      'background-position-y': '78%',
      'background-clip': 'none',
      'background-image-containment': 'over',
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
      terminalIcons: terminalStrip(item.terminals),
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

/**
 * Convert an API topology payload into the editor form model.
 *
 * The payload carries links as a flat directed list; the YAML nests them under
 * the switch they leave from, so regroup them that way for editing.
 *
 * @param {Object} topology - Value from the topology detail endpoint
 * @returns {Object} Form model holding every field the YAML file defines
 */
const toForm = (topology) => ({
  name: topology.name,
  label: topology.label,
  switches: topology.switches.map((item) => ({
    name: item.name,
    terminals: item.terminals,
    terminalBandwidth: item.terminal_bandwidth,
    switchBuffer: item.switch_buffer,
    connections: topology.links
      .filter((link) => link.source === item.name)
      .map((link) => ({ target: link.target, bandwidth: link.bandwidth })),
  })),
});

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
    editor: null,

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
     * Open the edit dialog with a copy of the selected topology.
     */
    openEditor() {
      if (!this.topology) {
        return;
      }
      this.editor = toForm(this.topology);
      this.$refs.editorDialog.showModal();
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
        if (autoFit) {
          this.fitToView();
        } else {
          cy?.resize();
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
      if (!cy) {
        return;
      }
      cy.resize();
      cy.fit(undefined, FIT_PADDING);
      if (cy.zoom() > MAX_FIT_ZOOM) {
        cy.zoom(MAX_FIT_ZOOM);
        cy.center();
      }
    },
  };
};
