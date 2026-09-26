/**
 * Per-simulation-type plot settings, keyed by Run.simulation_type.
 * Add an entry when a new simulation type is added, affecting the generation of plots
 */

// Event trace, CODES model stats and ROSS engine stats: produced by PHOLD and ingested ESnet runs.
const ROSS_PROFILE = {
  heatmap: {
    dataset: 'event',
    sourceKey: 'source_lp',
    destKey: 'dest_lp',
    xTitle: 'Receiving LP ID',
    yTitle: 'Sending LP ID',
    metrics: [
      { key: 'num_messages', label: 'Num Messages', aggregate: 'count' },
      {
        key: 'bytes_sent',
        label: 'Bytes Sent (not available)',
        disabled: true,
        tooltip: 'Message size data not available in current event trace format',
      },
    ],
  },
  networkTime: {
    dataset: 'model',
    groupBy: 'lp_id',
    excludedColumns: ['lp_id', 'component_id', 'real_time', 'virtual_time'],
    timeAxes: [
      { key: 'virtual_time', label: 'Virtual Time' },
      { key: 'real_time', label: 'Real Time' },
    ],
    defaults: { x: 'virtual_time', y: 'send_count' },
  },
  simulation: {
    dataset: 'ross',
    groupBy: 'PE_ID',
    excludedColumns: ['PE_ID', 'real_time', 'virtual_time'],
    timeAxes: [
      { key: 'virtual_time', label: 'Virtual Time' },
      { key: 'real_time', label: 'Real Time' },
    ],
    scatterDefaults: { x: 'events_processed', y: 'events_rolled_back' },
    timeDefaults: { x: 'virtual_time', y: 'events_processed' },
    parallelDimensions: [
      { key: 'PE_ID', label: 'PE ID' },
      { key: 'events_processed', label: 'Events Processed' },
      { key: 'events_rolled_back', label: 'Events Rolled Back' },
      { key: 'total_rollbacks', label: 'Total Rollbacks' },
      { key: 'secondary_rollbacks', label: 'Secondary Rollbacks' },
    ],
  },
};

const PLOT_PROFILES = {
  phold: ROSS_PROFILE,
  esnet: ROSS_PROFILE,
};

/** Return the plot profile for a simulation type, defaulting to the ROSS profile. */
export function plotProfileFor(simulationType) {
  return PLOT_PROFILES[simulationType] ?? ROSS_PROFILE;
}
