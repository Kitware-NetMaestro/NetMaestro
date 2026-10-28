/**
 * Alpine.js component for the sweep editor on the new-ensemble form.
 *
 * Holds the axes the user has added, turns each one's inputs into a list of
 * values, and keeps the hidden `sweep_spec` field in step with them. The server
 * re-checks everything against the same registry; this side exists so the member
 * count and preview are visible before anything is created.
 */

/** Key a directed link for a `<select>` value; switch names come from YAML keys. */
const linkKey = (source, target) => JSON.stringify([source, target]);

/**
 * Turn a topology's directed links into picker options. The sweep sets a link and
 * its reverse together, so a bidirectional pair is offered once, as `A ↔ B`.
 */
const linkOptions = (links) => {
  const directed = new Set(links.map((link) => linkKey(link.source, link.target)));
  const seen = new Set();
  const options = [];
  for (const link of links) {
    const reverse = linkKey(link.target, link.source);
    if (seen.has(reverse)) {
      continue;
    }
    seen.add(linkKey(link.source, link.target));
    const arrow = directed.has(reverse) ? '↔' : '→';
    options.push({
      value: linkKey(link.source, link.target),
      label: `${link.source} ${arrow} ${link.target} (${link.bandwidth_label})`,
    });
  }
  return options;
};

export const ensembleSweep = () => ({
  registry: [],
  maxMembers: 0,
  axes: [],
  links: [],
  linksLoading: false,
  linksError: '',
  pendingKey: '',

  init() {
    this.registry = JSON.parse(document.getElementById('sweep-axes').textContent);
    this.maxMembers = Number(this.$el.dataset.maxMembers);
    this.restore(document.getElementById('sweep-initial').textContent);
    const topology = this.$root.querySelector('[name="topology_name"]');
    if (topology) {
      this.loadLinks(topology.value);
      topology.addEventListener('change', () => this.loadLinks(topology.value));
    }
  },

  /** Rebuild the editor from a posted spec, so a rejected form keeps its sweep. */
  restore(initialJson) {
    let spec = [];
    try {
      spec = JSON.parse(JSON.parse(initialJson) || '[]');
    } catch {
      return;
    }
    if (!Array.isArray(spec)) {
      return;
    }
    for (const entry of spec) {
      const axis = this.restoreAxis(entry);
      if (axis) {
        this.axes.push(axis);
      }
    }
  },

  restoreAxis(entry) {
    const meta = this.meta(entry.key);
    if (!(meta && Array.isArray(entry.values))) {
      return null;
    }
    const axis = this.blankAxis(meta);
    if (meta.kind === 'choice') {
      axis.selected = meta.choices
        .map((choice, index) => (entry.values.includes(choice.value) ? index : -1))
        .filter((index) => index >= 0);
    } else {
      axis.raw = entry.values.join(', ');
    }
    if (entry.link) {
      axis.link = linkKey(entry.link.source, entry.link.target);
    }
    return axis;
  },

  meta(key) {
    return this.registry.find((axis) => axis.key === key) ?? null;
  },

  blankAxis(meta) {
    return { key: meta.key, raw: '', selected: [], link: '' };
  },

  /** Registry axes not yet in the sweep; each parameter can be swept once. */
  get available() {
    const used = new Set(this.axes.map((axis) => axis.key));
    return this.registry.filter((axis) => !used.has(axis.key));
  },

  addAxis() {
    const meta = this.meta(this.pendingKey);
    if (meta) {
      this.axes.push(this.blankAxis(meta));
    }
    this.pendingKey = '';
  },

  removeAxis(index) {
    this.axes.splice(index, 1);
  },

  toggleChoice(axis, index) {
    const at = axis.selected.indexOf(index);
    if (at >= 0) {
      axis.selected.splice(at, 1);
    } else {
      axis.selected.push(index);
    }
    axis.selected.sort((a, b) => a - b);
  },

  /**
   * Split a comma-separated list into numbers and the tokens that are not.
   * Applies the registry's whole-number and minimum rules too, so a bad value
   * is flagged where it was typed rather than after the round trip.
   */
  parseNumbers(axis) {
    const meta = this.meta(axis.key);
    const values = [];
    const invalid = [];
    for (const token of axis.raw.split(',')) {
      const text = token.trim();
      if (!text) {
        continue;
      }
      const value = Number(text);
      if (Number.isFinite(value) && this.inRange(meta, value)) {
        values.push(value);
      } else {
        invalid.push(text);
      }
    }
    return { values, invalid };
  },

  inRange(meta, value) {
    if (meta?.integer && !Number.isInteger(value)) {
      return false;
    }
    if (meta?.minimum == null) {
      return true;
    }
    return meta.minimum_exclusive ? value > meta.minimum : value >= meta.minimum;
  },

  values(axis) {
    const meta = this.meta(axis.key);
    if (meta?.kind === 'choice') {
      return axis.selected.map((index) => meta.choices[index].value);
    }
    return this.parseNumbers(axis).values;
  },

  /** How a value reads in the preview: a choice's label, a number with its unit. */
  display(axis, value) {
    const meta = this.meta(axis.key);
    if (meta?.kind === 'choice') {
      return meta.choices.find((choice) => choice.value === value)?.label ?? String(value);
    }
    return meta?.unit ? `${value} ${meta.unit}` : String(value);
  },

  axisProblem(axis) {
    const meta = this.meta(axis.key);
    if (meta?.needs_link && !axis.link) {
      return 'Choose a link.';
    }
    if (meta?.kind !== 'choice' && this.parseNumbers(axis).invalid.length) {
      return `Not a valid value: ${this.parseNumbers(axis).invalid.join(', ')}`;
    }
    if (this.values(axis).length === 0) {
      return 'Give at least one value.';
    }
    return '';
  },

  get memberCount() {
    if (this.axes.length === 0) {
      return 0;
    }
    return this.axes.reduce((count, axis) => count * this.values(axis).length, 1);
  },

  get hasProblems() {
    return this.axes.some((axis) => this.axisProblem(axis));
  },

  get canSubmit() {
    return this.memberCount > 0 && this.memberCount <= this.maxMembers && !this.hasProblems;
  },

  /** Every member's values, in the same order the server expands the grid. */
  get previewRows() {
    if (!this.canSubmit) {
      return [];
    }
    let rows = [[]];
    for (const axis of this.axes) {
      const next = [];
      for (const row of rows) {
        for (const value of this.values(axis)) {
          next.push([...row, this.display(axis, value)]);
        }
      }
      rows = next;
    }
    return rows;
  },

  axisHeading(axis) {
    const meta = this.meta(axis.key);
    if (!(meta?.needs_link && axis.link)) {
      return meta?.label ?? axis.key;
    }
    const [source, target] = JSON.parse(axis.link);
    return `${meta.label}, ${source} → ${target}`;
  },

  get specJson() {
    const spec = this.axes.map((axis) => {
      const entry = { key: axis.key, values: this.values(axis) };
      if (this.meta(axis.key)?.needs_link && axis.link) {
        const [source, target] = JSON.parse(axis.link);
        entry.link = { source, target };
      }
      return entry;
    });
    return JSON.stringify(spec);
  },

  /** Load the base topology's links for link axes. */
  async loadLinks(name) {
    this.links = [];
    this.linksError = '';
    if (!name) {
      return;
    }
    this.linksLoading = true;
    try {
      const response = await fetch(`/api/v1/topologies/${encodeURIComponent(name)}`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const topology = await response.json();
      this.links = linkOptions(topology.links);
    } catch (error) {
      console.warn('Failed to load topology links', error);
      this.linksError = 'Could not load the links of this topology.';
    } finally {
      this.linksLoading = false;
    }
    this.reconcileLinks();
  },

  /** Keep each chosen link that the new topology also has; clear the rest. */
  reconcileLinks() {
    const known = new Set(this.links.map((link) => link.value));
    for (const axis of this.axes) {
      if (!axis.link || known.has(axis.link)) {
        continue;
      }
      const [source, target] = JSON.parse(axis.link);
      axis.link = known.has(linkKey(target, source)) ? linkKey(target, source) : '';
    }
  },
});
