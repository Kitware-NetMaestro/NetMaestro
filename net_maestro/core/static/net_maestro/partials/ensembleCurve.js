/**
 * Alpine.js component for the "Sweep curve" card on an ensemble's page.
 *
 * The conventional parameter-study plot: one metric against one swept
 * parameter, one line per value of another. Swept parameters not on the plot
 * are averaged away, and the card says which.
 *
 * Fed by the same members.json as the comparison plot, and refetched the same
 * way after the polled member table swaps while members run. The members the
 * page is narrowed to (ensembleSelectionStore) keep their markers bright and
 * the rest are faded rather than removed, so the curve keeps its shape.
 */
import _ from 'lodash';
import Plotly from 'plotly';
import { axisConfig, DARK_LAYOUT, purgePlot, setupPlot } from '../plots/plotUtils.js';

const LAYOUT = {
  ...DARK_LAYOUT,
  margin: { ...DARK_LAYOUT.margin, l: 70, t: 20 },
  legend: { orientation: 'h', x: 0, y: -0.2, yanchor: 'top' },
  hovermode: 'closest',
};

// Markers of members outside the selection.
const FADED = 0.25;

/**
 * Title an axis with its unit, as the member table's headers do.
 *
 * @param {string} label - The axis or metric name
 * @param {string} unit - Its unit, or an empty string
 * @returns {string} The title
 */
const titled = (label, unit) => (unit ? `${label} (${unit})` : label);

export const ensembleCurve = () => ({
  url: '',
  payload: null,
  lastBody: '',
  loadError: false,
  metric: '',
  xAxis: '',
  // An axis key, or '' for one line over everything.
  seriesAxis: '',
  // Points drawn by the last render, for the empty state.
  pointCount: 0,
  plotEl: null,
  isPlotInitialized: false,
  onSwap: null,
  refetch: null,
  renderQueued: false,

  get axes() {
    return this.payload?.axes ?? [];
  },

  get metrics() {
    return this.payload?.metrics ?? [];
  },

  get members() {
    return this.payload?.members ?? [];
  },

  get running() {
    return this.members.filter((m) => m.status === 'pending' || m.status === 'running').length;
  },

  /** The axes a line can be drawn per value of: every one but the x axis. */
  get seriesOptions() {
    return this.axes.filter((axis) => axis.key !== this.xAxis);
  },

  /** Labels of the swept axes neither on x nor split into lines, so averaged. */
  get averagedOver() {
    return this.axes
      .filter((axis) => axis.key !== this.xAxis && axis.key !== this.seriesAxis)
      .map((axis) => axis.label);
  },

  init() {
    this.url = this.$el.dataset.url;
    // A poll can swap several elements at once, each firing afterSwap.
    this.refetch = _.debounce(() => this.load(), 250);
    this.onSwap = (event) => {
      if (event.detail?.target?.id === 'ensemble-members' && this.running > 0) {
        this.refetch();
      }
    };
    document.body.addEventListener('htmx:afterSwap', this.onSwap);

    this.$watch('metric', () => this.scheduleRender());
    this.$watch('xAxis', (key) => {
      // An axis cannot be both x and the line split.
      if (this.seriesAxis === key) {
        this.seriesAxis = this.seriesOptions[0]?.key ?? '';
      }
      this.scheduleRender();
    });
    this.$watch('seriesAxis', () => this.scheduleRender());
    this.$watch('$store.ensembleSelectionStore.picked', () => this.scheduleRender());
    this.$watch('$store.ensembleSelectionStore.selected', () => this.scheduleRender());
    this.load();
  },

  /** Called by Alpine when the card leaves the page. */
  destroy() {
    document.body.removeEventListener('htmx:afterSwap', this.onSwap);
    this.refetch?.cancel();
    purgePlot(this, 'plotEl');
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
    if (body === this.lastBody) {
      return;
    }
    this.lastBody = body;
    this.payload = JSON.parse(body);
    this.settleChoices();
    this.render();
  },

  /**
   * Default the selects on the first load, and keep them valid after later
   * ones (engine metrics only appear once some member has them).
   */
  settleChoices() {
    const axisKeys = this.axes.map((axis) => axis.key);
    if (!this.metrics.some((metric) => metric.key === this.metric)) {
      this.metric = this.payload.headline?.[0] ?? this.metrics[0]?.key ?? '';
    }
    if (!axisKeys.includes(this.xAxis)) {
      this.xAxis = axisKeys[0] ?? '';
      // Second axis as lines; a one-axis sweep has none to split by.
      this.seriesAxis = axisKeys[1] ?? '';
    }
    if (this.seriesAxis && !axisKeys.includes(this.seriesAxis)) {
      this.seriesAxis = '';
    }
  },

  /** Coalesce bursts of changes (a brush being dragged) into one redraw per frame. */
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
   * Group members into points: one per (series value, x value), the mean of
   * every member there. Several members share a point only when some swept
   * axis is on neither x nor the series.
   *
   * @param {Object} xAxis - The axis on x
   * @param {?Object} seriesAxis - The axis split into lines, or null
   * @param {Function} yOf - The member's y value, or null
   * @returns {Map<number, Map<number, {sum: number, members: Array<number>}>>}
   *   Points by series position, then x position
   */
  groupPoints(xAxis, seriesAxis, yOf) {
    const lines = new Map();
    for (const member of this.members) {
      const y = yOf(member);
      const xPos = xAxis.values.indexOf(member.params[xAxis.key]);
      const sPos = seriesAxis ? seriesAxis.values.indexOf(member.params[seriesAxis.key]) : 0;
      if (y === null || xPos < 0 || sPos < 0) {
        continue;
      }
      if (!lines.has(sPos)) {
        lines.set(sPos, new Map());
      }
      const line = lines.get(sPos);
      const point = line.get(xPos) ?? { sum: 0, members: [] };
      point.sum += y;
      point.members.push(member.index);
      line.set(xPos, point);
    }
    return lines;
  },

  /** Draw one line per series value from the members that have the metric. */
  render() {
    const xAxis = this.axes.find((axis) => axis.key === this.xAxis);
    const metric = this.metrics.find((m) => m.key === this.metric);
    if (!(xAxis && metric)) {
      this.pointCount = 0;
      purgePlot(this, 'plotEl');
      return;
    }
    const seriesAxis = this.axes.find((axis) => axis.key === this.seriesAxis) ?? null;
    // Fractions are stored 0-1 and shown as percentages, as in the member table.
    const yOf = (member) => {
      const value = member.metrics[metric.key];
      if (!Number.isFinite(value)) {
        return null;
      }
      return metric.is_fraction ? value * 100 : value;
    };
    const lines = this.groupPoints(xAxis, seriesAxis, yOf);
    const chosen = this.$store.ensembleSelectionStore.effective();
    const isChoice = xAxis.kind === 'choice';

    const traces = [...lines.entries()]
      .toSorted(([a], [b]) => a - b)
      .map(([sPos, line]) => {
        const points = [...line.entries()].toSorted(([a], [b]) => a - b);
        const name = seriesAxis ? `${seriesAxis.label} = ${seriesAxis.labels[sPos]}` : metric.label;
        return {
          type: 'scatter',
          mode: 'lines+markers',
          name,
          x: points.map(([xPos]) => (isChoice ? xAxis.labels[xPos] : xAxis.values[xPos])),
          y: points.map(([, point]) => point.sum / point.members.length),
          customdata: points.map(([, point]) => point.members.map((i) => `#${i}`).join(', ')),
          hovertemplate: `%{y}<br>%{customdata}<extra>${_.escape(name)}</extra>`,
          marker: {
            size: 8,
            // Per point, so the line itself stays whole and keeps its shape.
            opacity: points.map(([, point]) =>
              chosen === null || point.members.some((i) => chosen.includes(i)) ? 1 : FADED,
            ),
          },
        };
      });
    this.pointCount = traces.reduce((n, trace) => n + trace.x.length, 0);
    if (this.pointCount === 0) {
      purgePlot(this, 'plotEl');
      return;
    }

    const link = xAxis.link ? ` ${xAxis.link.source}→${xAxis.link.target}` : '';
    const layout = {
      ...LAYOUT,
      showlegend: seriesAxis !== null,
      xaxis: axisConfig(
        `${titled(xAxis.label, xAxis.unit)}${link}`,
        // Choice values have no scale; keep them in sweep order, even when they
        // look like numbers.
        isChoice
          ? { type: 'category', categoryorder: 'array', categoryarray: [...xAxis.labels] }
          : { type: 'linear' },
      ),
      yaxis: axisConfig(titled(metric.label, metric.is_fraction ? '%' : metric.unit)),
    };
    // The plot div is shown by x-show once there is something to draw, and
    // Plotly sizes itself from it, so draw after Alpine has shown it.
    this.$nextTick(() => {
      if (this.isPlotInitialized) {
        Plotly.react(this.plotEl, traces, layout);
      } else {
        setupPlot({
          component: this,
          elementId: 'ensembleCurvePlot',
          elementProp: 'plotEl',
          data: traces,
          layout,
        });
      }
    });
  },
});
