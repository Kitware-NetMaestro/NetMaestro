/**
 * Shared utilities for Plotly plot components.
 * Centralizes common patterns for layout, initialization, and synchronization.
 *
 * NOTE: The synchronization code (setupXYSyncWatchers, setupParallelSyncWatchers, handleRelayout)
 * currently only supports simulation plots. When multiple event or model plots are added, the
 * synchronization system will need to be extended to support syncing within each plot type
 * (model plots with model plots, event plots with event plots, etc.).
 */
import Plotly from 'plotly';

/**
 * Dark theme layout configuration for Plotly plots.
 */
export const DARK_LAYOUT = {
  // biome-ignore-start lint/style/useNamingConvention: Plotly layout API requires snake_case keys
  paper_bgcolor: '#1d232a',
  plot_bgcolor: '#1d232a',
  // biome-ignore-end lint/style/useNamingConvention: Plotly layout API requires snake_case keys
  font: {
    color: 'white',
  },
  margin: {
    l: 50,
    r: 50,
    b: 50,
    t: 50,
    pad: 4,
  },
};

/**
 * Creates an axis configuration with title and styling.
 * @param {string} title - Axis title text
 * @param {Object} options - Additional axis options
 * @returns {Object} Plotly axis configuration
 */
export function axisConfig(title, options = {}) {
  return {
    title: {
      text: title,
    },
    color: 'white',
    ...options,
  };
}

/**
 * Initializes a plot with standard configuration.
 * @param {Object} options - Configuration options
 * @param {Object} options.component - Component instance
 * @param {string} options.elementId - DOM element ID for the plot
 * @param {string} options.elementProp - Property name storing the element reference
 * @param {Array} options.data - Plotly data array
 * @param {Object} options.layout - Plotly layout configuration
 * @param {Array} options.eventHandlers - Array of {event, handler} objects
 */
export function initPlot({ component, elementId, elementProp, data, layout, eventHandlers = [] }) {
  if (component.isPlotInitialized) {
    return;
  }
  const el = document.getElementById(elementId);
  if (!el) {
    return;
  }
  component[elementProp] = el;

  const config = { responsive: true };
  Plotly.newPlot(el, data, layout, config);
  component.isPlotInitialized = true;

  for (const { event, handler } of eventHandlers) {
    el.on(event, handler);
  }
}

/**
 * Purges a plot and resets initialization state.
 * @param {Object} component - Component instance
 * @param {string} elementProp - Property name storing the element reference
 */
export function purgePlot(component, elementProp) {
  const el = component[elementProp];
  if (el) {
    Plotly.purge(el);
    component.isPlotInitialized = false;
  }
}

/**
 * Sets up axis state persistence using uiStateStore.
 * @param {Object} component - Component instance
 * @param {string} plotName - Name of the plot for state key
 * @param {Array} axisConfigs - Array of {prop, default} objects
 */
export function setupAxisState(component, plotName, axisConfigs) {
  const savedState = component.$store.uiStateStore.getUIState(plotName);
  for (const { prop, default: defaultValue } of axisConfigs) {
    component[prop] = savedState[prop] ?? defaultValue;
    component.$watch(prop, (newValue) => {
      if (newValue) {
        component.$store.uiStateStore.saveUIState(plotName, { [prop]: newValue });
      }
    });
  }
}

/**
 * Sets up a watcher for dataStore.loadTick to trigger data loading.
 * @param {Object} component - Component instance
 * @param {Function} loadFn - Function to call when loadTick changes
 */
export function setupLoadWatcher(component, loadFn) {
  // Load data if a run is already selected
  if (component.$store.dataStore.selectedRunId) {
    loadFn();
  }
  // Watch for new data loads
  component.$watch('$store.dataStore.loadTick', () => {
    loadFn();
  });
}

/**
 * Handles plotly_relayout events for X/Y axis synchronization.
 * @param {Object} component - Component instance
 * @param {Object} eventData - Plotly relayout event data
 * @param {Function} getXAxis - Function returning current X axis key
 * @param {Function} getYAxis - Function returning current Y axis key
 */
export function handleRelayout(component, eventData, getXAxis, getYAxis) {
  if (component.isSyncing) {
    return;
  }
  const sync = component.$store.plotSyncStore;

  // Detect double-click reset
  if (eventData['xaxis.autorange'] || eventData['yaxis.autorange']) {
    sync.resetAll(component.plotId);
    return;
  }

  const updates = _collectRangeUpdates(eventData, getXAxis, getYAxis);
  if (updates.length > 0) {
    sync.updateRanges(updates, component.plotId);
  }
}

/**
 * Collects range updates from relayout event data.
 * @param {Object} eventData - Relayout event data
 * @param {Function} getXAxis - Function returning current X axis key
 * @param {Function} getYAxis - Function returning current Y axis key
 * @returns {Array} Array of {parameter, range} objects
 */
function _collectRangeUpdates(eventData, getXAxis, getYAxis) {
  const updates = [];
  if (eventData['xaxis.range[0]'] != null) {
    updates.push({
      parameter: getXAxis(),
      range: { min: eventData['xaxis.range[0]'], max: eventData['xaxis.range[1]'] },
    });
  }
  if (eventData['yaxis.range[0]'] != null) {
    updates.push({
      parameter: getYAxis(),
      range: { min: eventData['yaxis.range[0]'], max: eventData['yaxis.range[1]'] },
    });
  }
  return updates;
}

/**
 * Sets up X/Y axis synchronization watchers.
 * @param {Object} component - Component instance
 * @param {string} elementProp - Property name storing the element reference
 * @param {Function} getXAxis - Function returning current X axis key
 * @param {Function} getYAxis - Function returning current Y axis key
 */
export function setupXYSyncWatchers(component, elementProp, getXAxis, getYAxis) {
  const sync = component.$store.plotSyncStore;

  // Watch for range changes from other plots
  component.$watch('$store.plotSyncStore.parameterRanges', (ranges) => {
    if (sync.lastUpdatedBy === component.plotId) {
      return;
    }
    const xRange = ranges[getXAxis()];
    const yRange = ranges[getYAxis()];
    if (!(xRange || yRange)) {
      return;
    }
    _applySyncedRange(component, elementProp, xRange, yRange);
  });

  // Watch for reset from other plots
  component.$watch('$store.plotSyncStore.resetTick', async () => {
    if (sync.lastUpdatedBy === component.plotId || !component.isPlotInitialized) {
      return;
    }
    component.isSyncing = true;
    try {
      await Plotly.relayout(component[elementProp], {
        'xaxis.autorange': true,
        'yaxis.autorange': true,
      });
    } finally {
      component.isSyncing = false;
    }
  });
}

/**
 * Applies synced X/Y axis ranges from another plot.
 * @param {Object} component - Component instance
 * @param {string} elementProp - Property name storing the element reference
 * @param {Object} xRange - X axis range {min, max}
 * @param {Object} yRange - Y axis range {min, max}
 */
async function _applySyncedRange(component, elementProp, xRange, yRange) {
  const el = component[elementProp];
  if (!(el && component.isPlotInitialized)) {
    return;
  }
  const update = {};
  if (xRange) {
    update['xaxis.range'] = [xRange.min, xRange.max];
  }
  if (yRange) {
    update['yaxis.range'] = [yRange.min, yRange.max];
  }
  if (Object.keys(update).length === 0) {
    return;
  }
  component.isSyncing = true;
  try {
    await Plotly.relayout(el, update);
  } finally {
    component.isSyncing = false;
  }
}

/**
 * Sets up parallel coordinates dimension synchronization watchers.
 * @param {Object} component - Component instance
 * @param {string} elementProp - Property name storing the element reference
 * @param {Array} dimensions - Array of dimension objects with key property
 */
export function setupParallelSyncWatchers(component, elementProp, dimensions) {
  const sync = component.$store.plotSyncStore;

  component.$watch('$store.plotSyncStore.parameterRanges', (ranges) => {
    if (sync.lastUpdatedBy === component.plotId || !component.isPlotInitialized) {
      return;
    }
    for (let i = 0; i < dimensions.length; i++) {
      const dimKey = dimensions[i].key;
      const range = ranges[dimKey];
      if (range) {
        _applySyncedDimension(component, elementProp, i, [range.min, range.max]);
      }
    }
  });

  component.$watch('$store.plotSyncStore.resetTick', () => {
    if (sync.lastUpdatedBy === component.plotId || !component.isPlotInitialized) {
      return;
    }
    _resetAllDimensions(component, elementProp);
  });
}

/**
 * Applies synced dimension constraint range from another plot.
 * @param {Object} component - Component instance
 * @param {string} elementProp - Property name storing the element reference
 * @param {number} index - Dimension index
 * @param {Array} constraintRange - [min, max] constraint range
 */
async function _applySyncedDimension(component, elementProp, index, constraintRange) {
  const el = component[elementProp];
  if (!el) {
    return;
  }
  component.isSyncing = true;
  const dimensions = el.data[0]?.dimensions;
  if (dimensions?.[index]) {
    dimensions[index].constraintrange = constraintRange;
    try {
      await Plotly.restyle(el, { dimensions: [dimensions] });
    } finally {
      component.isSyncing = false;
    }
  } else {
    component.isSyncing = false;
  }
}

/**
 * Resets all dimension constraints.
 * @param {Object} component - Component instance
 * @param {string} elementProp - Property name storing the element reference
 */
async function _resetAllDimensions(component, elementProp) {
  const el = component[elementProp];
  if (!el) {
    return;
  }
  component.isSyncing = true;
  const dimensions = el.data[0]?.dimensions;
  if (dimensions) {
    for (const dim of dimensions) {
      dim.constraintrange = undefined;
      dim.range = undefined;
    }
    try {
      await Plotly.restyle(el, { dimensions: [dimensions] });
    } finally {
      component.isSyncing = false;
    }
  } else {
    component.isSyncing = false;
  }
}

/**
 * Creates a value list from columns, excluding specified columns.
 * @param {Array} columns - Column names
 * @param {Array} excludedColumns - Columns to exclude
 * @returns {Array} Array of {key, label} objects
 */
export function createValueList(columns, excludedColumns = []) {
  const filteredColumns = columns.filter((column) => column && !excludedColumns.includes(column));
  return filteredColumns.map((value) => ({
    key: value,
    label: value.replaceAll('_', ' '),
  }));
}

/**
 * Gets label for a key from a value list, with fallback.
 * @param {Array} valueList - Array of {key, label} objects
 * @param {string} key - Key to look up
 * @param {string} fallback - Fallback label if key not found
 * @returns {string} Label or fallback
 */
export function getLabel(valueList, key, fallback) {
  return valueList.find((item) => item.key === key)?.label ?? fallback;
}
