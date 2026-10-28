/**
 * Alpine.js store linking the ensemble comparison plot with the member table.
 *
 * The plot and the table are rendered separately (the table is replaced on
 * every poll while members run), so they meet here rather than through each
 * other's DOM. Members are held by their member index, the number the table
 * shows in its first column.
 */

export const ensembleSelectionStore = {
  // Member indexes inside every brushed range, or null when nothing is brushed.
  selected: null,
  // The member index whose table row the pointer is over, or null.
  hovered: null,

  /**
   * Whether a member is outside the brush, so its row should be dimmed.
   *
   * @param {number} index - The member index
   * @returns {boolean} True only while a brush is set and leaves this member out
   */
  isDimmed(index) {
    return this.selected !== null && !this.selected.includes(index);
  },

  /** Drop the brush; the plot clears its ranges when it sees this. */
  clear() {
    this.selected = null;
  },

  /** Forget everything, for a page that no longer shows the same ensemble. */
  reset() {
    this.selected = null;
    this.hovered = null;
  },
};
