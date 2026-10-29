/**
 * Alpine.js component for the "Compare selected" card on an ensemble's page.
 *
 * Draws one metric of one switch, terminal, link or PE over time, one line per
 * member, for the members the user has narrowed the page to (ticked rows, or
 * else the brush on the comparison plot; see ensembleSelectionStore). With no
 * selection it shows the first members, so the card is never blank.
 *
 * The series are computed and thinned on the server per ensemble, because the
 * per-run endpoints return every row. Like the comparison plot, the card sits
 * outside the polled member table and refetches after that table's swaps while
 * members are still running, so finished members join the chart.
 *
 * Its choices live in the address bar (`compare`, `entity`, `smetric`,
 * `cumulative`) beside the member table's own (`delta`, `metrics`, `metric`),
 * so a refresh or a shared link shows the same chart.
 */
import _ from 'lodash';
import Plotly from 'plotly';
import { axisConfig, DARK_LAYOUT, purgePlot, setupPlot } from '../plots/plotUtils.js';

// The series endpoint refuses more; more lines than this are unreadable anyway.
const MAX_MEMBERS = 8;

// Entity groups in the order the select lists them.
const DATASET_GROUPS = [
  { key: 'switches', label: 'Switches' },
  { key: 'terminals', label: 'Terminals' },
  { key: 'links', label: 'Links' },
  { key: 'engine', label: 'Engine' },
];

// Legend under the plot: the entries carry each member's swept values and are
// too long to sit beside it.
const LAYOUT = {
  ...DARK_LAYOUT,
  margin: { ...DARK_LAYOUT.margin, l: 70, t: 20 },
  showlegend: true,
  legend: { orientation: 'h', x: 0, y: -0.2, yanchor: 'top' },
  hovermode: 'closest',
  // Hover names in full: the member's values are what tell the lines apart.
  hoverlabel: { namelength: -1 },
};

/**
 * Title an axis with its unit, as the member table's headers do.
 *
 * @param {string} label - The metric name
 * @param {string} unit - Its unit, or an empty string
 * @returns {string} The title
 */
const titled = (label, unit) => (unit ? `${label} (${unit})` : label);

/**
 * Read a comma list of member indexes from the address bar.
 *
 * @param {?string} text - The parameter's value, e.g. "1,4"
 * @returns {Array<number>} The indexes, without blanks or junk
 */
const parseIndexes = (text) =>
  (text ?? '')
    .split(',')
    .filter((part) => part.trim() !== '')
    .map(Number)
    .filter(Number.isInteger);

/**
 * The message to show for a refused request.
 *
 * The series endpoint explains a 400 (an unknown entity, too many members), so
 * that explanation is shown as is, whether it came as JSON or plain text.
 *
 * @param {string} body - The response body
 * @param {number} status - The HTTP status
 * @returns {string} The message
 */
const messageFrom = (body, status) => {
  try {
    const parsed = JSON.parse(body);
    const message = parsed?.error ?? parsed?.detail ?? parsed?.message;
    if (typeof message === 'string' && message) {
      return message;
    }
  } catch {
    const text = body.trim();
    // A plain-text explanation, not a Django error page.
    if (text && !text.startsWith('<')) {
      return text;
    }
  }
  return `Could not load the series (HTTP ${status}).`;
};

/**
 * Name a member's line: its number, then the values that set it apart.
 *
 * @param {Object} member - One member of the series response
 * @returns {string} e.g. "#4 · switch_buffer_gb=8, link_bandwidth_gbps=40"
 */
const legendName = (member) =>
  member.label ? `#${member.index} · ${member.label}` : `#${member.index}`;

export const ensembleCompare = () => ({
  entitiesUrl: '',
  seriesUrl: '',
  membersUrl: '',
  // From the entities endpoint: what can be plotted, and each dataset's metrics.
  entities: [],
  datasetMetrics: {},
  entity: '',
  metric: '',
  cumulative: true,
  // Every member's index, from members.json, for the "no selection" default.
  memberIndexes: [],
  membersLoaded: false,
  running: 0,
  // The last series response drawn, and its text so an identical poll is skipped.
  series: null,
  lastBody: '',
  error: '',
  loadError: false,
  plotEl: null,
  isPlotInitialized: false,
  pagePath: '',
  onSwap: null,
  onHistory: null,
  refetchSeries: null,
  refetchMembers: null,
  // Increases with each series request, so a slow reply to an old one is dropped.
  requestSeq: 0,

  /** The entities for the select, grouped by dataset, empty groups left out. */
  get entityGroups() {
    return DATASET_GROUPS.map((group) => ({
      ...group,
      entities: this.entities.filter((entity) => entity.dataset === group.key),
    })).filter((group) => group.entities.length > 0);
  },

  get entityInfo() {
    return this.entities.find((entity) => entity.id === this.entity) ?? null;
  },

  /** The metrics of the chosen entity's dataset. */
  get metricOptions() {
    return this.datasetMetrics[this.entityInfo?.dataset] ?? [];
  },

  get metricInfo() {
    return this.metricOptions.find((metric) => metric.key === this.metric) ?? null;
  },

  /** Whether the metric counts per interval, so a running total makes sense. */
  get isDelta() {
    return this.metricInfo?.kind === 'delta';
  },

  /** The `cumulative` parameter: only a delta metric has one. */
  get cumulativeParam() {
    if (!this.isDelta) {
      return '';
    }
    return this.cumulative ? '1' : '0';
  },

  /** How many members the selection holds, or null when nothing is selected. */
  get selectedCount() {
    const chosen = this.$store.ensembleSelectionStore.effective();
    return chosen === null ? null : chosen.length;
  },

  /** Whether the selection holds more members than the chart draws. */
  get overCap() {
    return (this.selectedCount ?? 0) > MAX_MEMBERS;
  },

  /**
   * The members to draw: the selection's first eight by index, or the
   * ensemble's first eight when nothing is selected.
   *
   * @returns {Array<number>} Member indexes, ascending
   */
  get chartMembers() {
    const chosen = this.$store.ensembleSelectionStore.effective();
    const pool = chosen === null ? this.memberIndexes : [...chosen].sort((a, b) => a - b);
    return pool.slice(0, MAX_MEMBERS);
  },

  /** Members in the response with no samples: still running, failed, or another preset. */
  get withoutResults() {
    return (this.series?.members ?? []).filter((member) => member.points.length === 0);
  },

  get isEmpty() {
    return this.series !== null && this.withoutResults.length === this.series.members.length;
  },

  get showPlot() {
    return this.series !== null && !this.isEmpty && !this.error;
  },

  init() {
    const { entitiesUrl, seriesUrl, membersUrl } = this.$el.dataset;
    this.entitiesUrl = entitiesUrl;
    this.seriesUrl = seriesUrl;
    this.membersUrl = membersUrl;
    this.pagePath = window.location.pathname;
    this.readUrl();

    this.refetchSeries = _.debounce(() => this.loadSeries(), 200);
    // A poll can swap several elements at once, each firing afterSwap.
    this.refetchMembers = _.debounce(() => this.loadMembers(), 250);
    this.onSwap = (event) => {
      if (event.detail?.target?.id === 'ensemble-members' && this.running > 0) {
        this.refetchMembers();
      }
    };
    // The member toolbar and the effect card rewrite the address bar with only
    // their own parameters; put this card's back after them.
    this.onHistory = () => {
      if (window.location.pathname === this.pagePath) {
        this.writeUrl();
      }
    };
    document.body.addEventListener('htmx:afterSwap', this.onSwap);
    document.body.addEventListener('htmx:replacedInHistory', this.onHistory);

    this.$watch('entity', () => {
      this.ensureMetric();
      this.changed();
    });
    this.$watch('metric', () => this.changed());
    this.$watch('cumulative', () => this.changed());
    this.$watch('$store.ensembleSelectionStore.picked', () => this.changed());
    this.$watch('$store.ensembleSelectionStore.selected', () => this.changed());

    this.loadEntities();
    this.loadMembers();
  },

  /** Called by Alpine when the card leaves the page. */
  destroy() {
    document.body.removeEventListener('htmx:afterSwap', this.onSwap);
    document.body.removeEventListener('htmx:replacedInHistory', this.onHistory);
    this.refetchSeries?.cancel();
    this.refetchMembers?.cancel();
    purgePlot(this, 'plotEl');
  },

  /**
   * Take the card's state from the address bar; `compare` ticks those rows.
   *
   * The ticks are set even when `compare` is absent: this card owns them, and a
   * page reached from another ensemble would otherwise inherit its ticks.
   */
  readUrl() {
    const params = new URLSearchParams(window.location.search);
    this.$store.ensembleSelectionStore.picked = parseIndexes(params.get('compare'));
    this.entity = params.get('entity') ?? '';
    this.metric = params.get('smetric') ?? '';
    this.cumulative = params.get('cumulative') !== '0';
  },

  /** Write the card's state to the address bar, leaving every other parameter as it is. */
  writeUrl() {
    const url = new URL(window.location.href);
    const set = (key, value) => {
      if (value) {
        url.searchParams.set(key, value);
      } else {
        url.searchParams.delete(key);
      }
    };
    set('compare', this.$store.ensembleSelectionStore.picked.join(','));
    set('entity', this.entity);
    set('smetric', this.metric);
    set('cumulative', this.cumulativeParam);
    if (url.href !== window.location.href) {
      // Keep htmx's history entry for this page.
      history.replaceState(history.state, '', url);
    }
  },

  /** Something the chart depends on changed. */
  changed() {
    this.writeUrl();
    this.refetchSeries();
  },

  /** Keep the metric if the entity's dataset has it, else take its first gauge. */
  ensureMetric() {
    if (this.metricInfo || this.entities.length === 0) {
      return;
    }
    const options = this.metricOptions;
    this.metric = (options.find((metric) => metric.kind === 'gauge') ?? options[0])?.key ?? '';
  },

  /** Fetch what can be plotted, and settle on an entity and metric. */
  async loadEntities() {
    try {
      const response = await fetch(this.entitiesUrl);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const body = await response.json();
      this.entities = body.entities ?? [];
      this.datasetMetrics = body.metrics ?? {};
    } catch {
      this.loadError = true;
      return;
    }
    if (!this.entityInfo) {
      const first =
        this.entities.find((entity) => entity.dataset === 'switches') ?? this.entities[0];
      this.entity = first?.id ?? '';
    }
    this.ensureMetric();
    this.changed();
  },

  /** Fetch the member list, for the default members and to know whether any still run. */
  async loadMembers() {
    let members;
    try {
      const response = await fetch(this.membersUrl);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      members = (await response.json()).members ?? [];
    } catch {
      this.loadError = true;
      return;
    }
    this.memberIndexes = members.map((member) => member.index).filter(Number.isInteger);
    this.running = members.filter(
      (member) => member.status === 'pending' || member.status === 'running',
    ).length;
    this.membersLoaded = true;
    // Members that just finished now have series to show.
    this.refetchSeries();
  },

  /**
   * Request one set of series.
   *
   * @param {Array<number>} members - Member indexes, at most eight
   * @returns {Promise<{ok: boolean, status: number, body: string}>} The reply
   */
  async fetchSeries(members) {
    const params = new URLSearchParams({
      entity: this.entity,
      metric: this.metric,
      members: members.join(','),
    });
    if (this.cumulativeParam) {
      params.set('cumulative', this.cumulativeParam);
    }
    const response = await fetch(`${this.seriesUrl}?${params}`);
    return { ok: response.ok, status: response.status, body: await response.text() };
  },

  /** Fetch the chosen members' series and redraw when they changed. */
  async loadSeries() {
    if (!(this.membersLoaded && this.entityInfo && this.metricInfo)) {
      return;
    }
    const members = this.chartMembers;
    const seq = ++this.requestSeq;
    if (members.length === 0) {
      // A brush that catches no member; the card says so.
      this.showNothing('');
      return;
    }
    let reply;
    try {
      reply = await this.fetchSeries(members);
    } catch {
      reply = null;
    }
    if (seq !== this.requestSeq) {
      return;
    }
    this.loadError = reply === null;
    if (reply === null) {
      return;
    }
    if (!reply.ok) {
      this.showNothing(messageFrom(reply.body, reply.status));
      return;
    }
    this.error = '';
    // While members run the same members' series are refetched every poll;
    // most replies are what is already drawn.
    if (reply.body === this.lastBody) {
      return;
    }
    this.lastBody = reply.body;
    this.series = JSON.parse(reply.body);
    this.render();
  },

  /**
   * Clear the chart, with an error to show in its place or none.
   *
   * @param {string} error - The message, or an empty string
   */
  showNothing(error) {
    this.error = error;
    this.series = null;
    this.lastBody = '';
    purgePlot(this, 'plotEl');
  },

  /** Draw one line per member that has samples. */
  render() {
    if (!this.showPlot) {
      purgePlot(this, 'plotEl');
      return;
    }
    const traces = this.series.members
      .filter((member) => member.points.length > 0)
      .toSorted((a, b) => a.index - b.index)
      .map((member) => ({
        type: 'scatter',
        mode: 'lines',
        name: legendName(member),
        x: member.points.map((point) => point[0]),
        y: member.points.map((point) => point[1]),
        hovertemplate: '%{y}<extra>%{fullData.name}</extra>',
      }));
    const metric = this.series.metric ?? this.metricInfo ?? {};
    const layout = {
      ...LAYOUT,
      xaxis: axisConfig(this.series.x_label ?? 'Virtual time (s)'),
      yaxis: axisConfig(titled(metric.label ?? this.metric, metric.unit ?? '')),
    };
    // The plot div is shown by x-show once there is something to draw, and
    // Plotly sizes itself from it, so draw after Alpine has shown it.
    this.$nextTick(() => {
      if (this.isPlotInitialized) {
        Plotly.react(this.plotEl, traces, layout);
      } else {
        setupPlot({
          component: this,
          elementId: 'ensembleComparePlot',
          elementProp: 'plotEl',
          data: traces,
          layout,
        });
      }
    });
  },
});
