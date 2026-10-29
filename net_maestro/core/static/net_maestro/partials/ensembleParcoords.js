/**
 * Alpine.js component for the "Compare members" card on an ensemble's page.
 *
 * One line per member across the swept parameters and the chosen metrics, so
 * which settings lead to which results reads off the plot directly. Brushing an
 * axis writes the members inside every brushed range to ensembleSelectionStore,
 * which dims the other rows of the member table; hovering a table row lights its
 * line here.
 *
 * The card sits outside the member table's region, which replaces itself on
 * every poll while members run, so the plot (and the user's brush) survive the
 * polls. It refetches its own numbers after each of those swaps instead.
 */
import _ from 'lodash';
import Plotly from 'plotly';
import { DARK_LAYOUT, purgePlot, setupPlot } from '../plots/plotUtils.js';

// The "colour by" choice that colours lines by member number, not a metric.
const MEMBER_COLOUR = '__member';

// Room above the axes for their titles and on the right for the colourbar.
const LAYOUT = { ...DARK_LAYOUT, margin: { ...DARK_LAYOUT.margin, t: 80, l: 70, r: 90 } };

// While a table row is hovered, its line is drawn bright and the rest faded.
// Parcoords has a single trace and no per-line styling other than its colour
// array, so the highlight swaps the colourscale for this two-stop one.
const HOVER_SCALE = [
  [0, 'rgba(140, 140, 140, 0.25)'],
  [1, '#fde725'],
];

/**
 * Whether a value falls inside an axis's brush.
 *
 * @param {number} value - The member's value on the axis
 * @param {Array} constraint - One [low, high] range, or a list of them when
 *   the axis was brushed in several places
 * @returns {boolean} True when the value is inside any of the ranges
 */
const inConstraint = (value, constraint) => {
  const ranges = Array.isArray(constraint[0]) ? constraint : [constraint];
  return ranges.some(([low, high]) => value >= low && value <= high);
};

/**
 * Title an axis with its unit, as the member table's headers do.
 *
 * @param {string} label - The axis or metric name
 * @param {string} unit - Its unit, or an empty string
 * @returns {string} The title
 */
const titled = (label, unit) => (unit ? `${label} (${unit})` : label);

export const ensembleParcoords = () => ({
  url: '',
  payload: null,
  lastBody: '',
  loadError: false,
  // Metric keys shown as axes after the swept parameters, in the order added.
  chosen: [],
  colourBy: '',
  // Members drawn, in line order; the brush is read back against these.
  plotted: [],
  plotEl: null,
  isPlotInitialized: false,
  isSyncing: false,
  // Dimension keys in plot order, so a brush can be carried across a redraw.
  dimKeys: [],
  onSwap: null,
  refetch: null,
  renderQueued: false,

  get members() {
    return this.payload?.members ?? [];
  },

  get metrics() {
    return this.payload?.metrics ?? [];
  },

  get running() {
    return this.members.filter((m) => m.status === 'pending' || m.status === 'running').length;
  },

  get tooFew() {
    return this.plotted.length < 2;
  },

  /** The "colour by" options: each metric on the plot, then member number. */
  get colourOptions() {
    const options = this.chosen
      .map((key) => this.metricFor(key))
      .filter(Boolean)
      .map((metric) => ({ key: metric.key, label: metric.label }));
    return [...options, { key: MEMBER_COLOUR, label: 'Member #' }];
  },

  init() {
    this.url = this.$el.dataset.url;
    // Only the brush: ticked rows may already have been restored from the URL.
    this.$store.ensembleSelectionStore.forgetBrush();
    // A poll can swap several elements at once, each firing afterSwap.
    this.refetch = _.debounce(() => this.load(), 250);
    this.onSwap = (event) => {
      if (event.detail?.target?.id === 'ensemble-members') {
        this.refetch();
      }
    };
    document.body.addEventListener('htmx:afterSwap', this.onSwap);

    this.$watch('colourBy', () => this.scheduleRender());
    this.$watch('$store.ensembleSelectionStore.hovered', () => this.scheduleRender());
    // The table's "clear" link empties the selection; the brush has to follow.
    this.$watch('$store.ensembleSelectionStore.selected', (selected) => {
      if (selected === null) {
        this.clearConstraints();
      }
    });
    this.load();
  },

  /** Called by Alpine when the card leaves the page. */
  destroy() {
    document.body.removeEventListener('htmx:afterSwap', this.onSwap);
    this.refetch?.cancel();
    purgePlot(this, 'plotEl');
    this.$store.ensembleSelectionStore.forgetBrush();
  },

  /** Fetch the members' numbers, and redraw only when they changed. */
  async load() {
    let body;
    try {
      const response = await fetch(this.url);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      body = await response.text();
    } catch {
      this.loadError = true;
      return;
    }
    this.loadError = false;
    // Polls repeat every two seconds; most return what is already drawn.
    if (body === this.lastBody) {
      return;
    }
    this.lastBody = body;
    const first = this.payload === null;
    this.payload = JSON.parse(body);
    const offered = new Set(this.metrics.map((metric) => metric.key));
    if (first) {
      this.chosen = this.payload.headline.filter((key) => offered.has(key));
      this.colourBy = this.chosen[0] ?? MEMBER_COLOUR;
    } else {
      this.chosen = this.chosen.filter((key) => offered.has(key));
    }
    this.render();
  },

  metricFor(key) {
    return this.metrics.find((metric) => metric.key === key);
  },

  isChosen(key) {
    return this.chosen.includes(key);
  },

  /**
   * Add a metric as an axis, or take it off.
   *
   * @param {string} key - The metric key
   */
  toggleMetric(key) {
    this.chosen = this.isChosen(key) ? this.chosen.filter((k) => k !== key) : [...this.chosen, key];
    this.render();
  },

  /**
   * Describe each axis: its key, title, how to read a member's value on it,
   * and any fixed ticks. Every swept parameter comes first, then the chosen
   * metrics.
   *
   * Choice axes (a topology, a sync protocol) have no scale, so a member sits
   * at the position of its value in the sweep, with the values' names as ticks.
   * Fractions are shown as percentages, so their values are scaled by 100.
   *
   * @returns {Array<Object>} One column per dimension
   */
  columns() {
    const axes = this.payload.axes.map((axis) => {
      const link = axis.link ? ` ${axis.link.source}→${axis.link.target}` : '';
      const column = { key: `axis:${axis.key}`, label: `${titled(axis.label, axis.unit)}${link}` };
      if (axis.kind === 'choice') {
        const ticks = axis.values.map((_value, i) => i);
        return {
          ...column,
          valueOf: (member) => {
            const position = axis.values.indexOf(member.params[axis.key]);
            return position < 0 ? null : position;
          },
          extra: {
            tickvals: ticks,
            ticktext: [...axis.labels],
            range: [0, Math.max(ticks.length - 1, 1)],
          },
        };
      }
      return {
        ...column,
        valueOf: (member) => member.params[axis.key],
        // Copies, so Plotly never holds Alpine's reactive arrays.
        extra: { tickvals: [...axis.values], ticktext: [...axis.labels] },
      };
    });
    const metrics = this.chosen
      .map((key) => this.metricFor(key))
      .filter(Boolean)
      .map((metric) => ({
        key: `metric:${metric.key}`,
        label: titled(metric.label, metric.is_fraction ? '%' : metric.unit),
        valueOf: (member) => {
          const value = member.metrics[metric.key];
          if (value === null || value === undefined) {
            return null;
          }
          return metric.is_fraction ? value * 100 : value;
        },
        extra: {},
      }));
    return [...axes, ...metrics];
  },

  /**
   * The line colours: the "colour by" values on Viridis, or, while a table row
   * is hovered and its member is drawn, that line bright and the rest faded.
   *
   * @param {Array<Object>} columns - The plot's columns
   * @returns {Object} The trace's `line`
   */
  lineFor(columns) {
    const hovered = this.$store.ensembleSelectionStore.hovered;
    if (hovered !== null && this.plotted.some((member) => member.index === hovered)) {
      return {
        color: this.plotted.map((member) => (member.index === hovered ? 1 : 0)),
        colorscale: HOVER_SCALE,
        cmin: 0,
        cmax: 1,
        showscale: false,
      };
    }
    let column = columns.find((c) => c.key === `metric:${this.colourBy}`);
    if (!column && this.colourBy !== MEMBER_COLOUR) {
      // The colouring metric was taken off the plot; fall back to the first left.
      this.colourBy = this.chosen[0] ?? MEMBER_COLOUR;
      column = columns.find((c) => c.key === `metric:${this.colourBy}`);
    }
    const colour = column ?? { label: 'Member #', valueOf: (member) => member.index };
    return {
      color: this.plotted.map((member) => colour.valueOf(member)),
      colorscale: 'Viridis',
      showscale: true,
      colorbar: { title: { text: colour.label, side: 'right' } },
    };
  },

  /** Coalesce bursts of redraws (a pointer sweeping down the table) into one per frame. */
  scheduleRender() {
    if (this.renderQueued) {
      return;
    }
    this.renderQueued = true;
    requestAnimationFrame(() => {
      this.renderQueued = false;
      this.render();
    });
  },

  /**
   * Draw the members that have a value on every axis.
   *
   * Parcoords needs every dimension for every line, so a member still running
   * (or one that failed) is left out until it has results, and the card says
   * how many are drawn. The user's brush is carried over by dimension key, so a
   * poll that adds a member keeps it.
   */
  render() {
    if (!this.payload) {
      return;
    }
    const columns = this.columns();
    const previous = this.currentConstraints();
    this.plotted = this.members.filter((member) =>
      columns.every((column) => Number.isFinite(column.valueOf(member))),
    );
    if (this.tooFew) {
      purgePlot(this, 'plotEl');
      this.dimKeys = [];
      this.publishSelection(columns);
      return;
    }
    const trace = {
      type: 'parcoords',
      line: this.lineFor(columns),
      dimensions: columns.map((column) => ({
        label: column.label,
        values: this.plotted.map((member) => column.valueOf(member)),
        ...column.extra,
        ...(previous[column.key] ? { constraintrange: previous[column.key] } : {}),
      })),
    };
    this.dimKeys = columns.map((column) => column.key);
    // The plot div is shown by x-show once there is something to draw, and
    // Plotly sizes itself from it, so draw after Alpine has shown it.
    this.$nextTick(() => this.draw(trace, columns));
  },

  async draw(trace, columns) {
    if (this.isPlotInitialized) {
      this.isSyncing = true;
      try {
        await Plotly.react(this.plotEl, [trace], LAYOUT);
      } finally {
        this.isSyncing = false;
      }
    } else {
      setupPlot({
        component: this,
        elementId: 'ensembleParcoords',
        elementProp: 'plotEl',
        data: [trace],
        layout: LAYOUT,
        eventHandlers: [{ event: 'plotly_restyle', handler: () => this.onRestyle() }],
      });
    }
    this.publishSelection(columns);
  },

  /** A brush changed on the plot. */
  onRestyle() {
    if (!this.isSyncing) {
      this.publishSelection(this.columns());
    }
  },

  /**
   * The brushed range of each dimension that has one, by dimension key.
   *
   * @returns {Object} Constraint ranges keyed like `dimKeys`
   */
  currentConstraints() {
    const dimensions = this.isPlotInitialized ? (this.plotEl?.data?.[0]?.dimensions ?? []) : [];
    const ranges = {};
    dimensions.forEach((dimension, i) => {
      const range = dimension.constraintrange;
      if (this.dimKeys[i] && Array.isArray(range) && range.length > 0) {
        ranges[this.dimKeys[i]] = range;
      }
    });
    return ranges;
  },

  /**
   * Write the members inside every brushed range to the store, or null when
   * nothing is brushed.
   *
   * @param {Array<Object>} columns - The plot's columns
   */
  publishSelection(columns) {
    const store = this.$store.ensembleSelectionStore;
    const constraints = Object.entries(this.currentConstraints());
    if (constraints.length === 0) {
      if (store.selected !== null) {
        store.selected = null;
      }
      return;
    }
    const byKey = Object.fromEntries(columns.map((column) => [column.key, column]));
    const selected = this.plotted
      .filter((member) =>
        constraints.every(([key, range]) => {
          const column = byKey[key];
          return !column || inConstraint(column.valueOf(member), range);
        }),
      )
      .map((member) => member.index);
    if (!_.isEqual(selected, store.selected)) {
      store.selected = selected;
    }
  },

  /** Remove every brush, after the selection was cleared from the table. */
  async clearConstraints() {
    const dimensions = this.isPlotInitialized ? this.plotEl?.data?.[0]?.dimensions : null;
    if (!dimensions?.some((dimension) => dimension.constraintrange)) {
      return;
    }
    const update = {};
    dimensions.forEach((_dimension, i) => {
      update[`dimensions[${i}].constraintrange`] = null;
    });
    this.isSyncing = true;
    try {
      await Plotly.restyle(this.plotEl, update, [0]);
    } finally {
      this.isSyncing = false;
    }
  },
});
