/**
 * Alpine.js store linking the ensemble's plots with the member table.
 *
 * The plots and the table are rendered separately (the table is replaced on
 * every poll while members run), so they meet here rather than through each
 * other's DOM. Members are held by their member index, the number the table
 * shows in its first column.
 *
 * Two things can select members: a brush on the comparison plot (`selected`)
 * and the checkboxes in the table (`picked`). Ticking rows is the deliberate
 * act, so while any are ticked they win over the brush; `effective()` is the
 * one set every view follows.
 */

export const ensembleSelectionStore = {
  // Member indexes inside every brushed range, or null when nothing is brushed.
  selected: null,
  // Member indexes ticked in the table, in the order they were ticked.
  picked: [],
  // The member index whose table row the pointer is over, or null.
  hovered: null,

  /**
   * The members the page is narrowed to: the ticked ones if any, else the
   * brushed ones, else null for "no selection".
   *
   * @returns {?Array<number>} Member indexes, or null
   */
  effective() {
    if (this.picked.length > 0) {
      return this.picked;
    }
    return this.selected;
  },

  /**
   * Tick or untick a member's row.
   *
   * A new array each time, so watchers on `picked` see the change.
   *
   * @param {number} index - The member index
   */
  togglePicked(index) {
    this.picked = this.picked.includes(index)
      ? this.picked.filter((i) => i !== index)
      : [...this.picked, index];
  },

  /**
   * Whether a member is outside the selection, so its row should be dimmed.
   *
   * @param {number} index - The member index
   * @returns {boolean} True only while a selection is set and leaves this member out
   */
  isDimmed(index) {
    const members = this.effective();
    return members !== null && !members.includes(index);
  },

  /** Untick every row and drop the brush; the plot clears its ranges when it sees this. */
  clear() {
    this.picked = [];
    this.selected = null;
  },

  /**
   * Forget the brush and the hover, which the comparison plot owns. The ticks
   * belong to the table and the compare card (which reads them from the URL),
   * so a plot coming or going must not touch them.
   */
  forgetBrush() {
    this.selected = null;
    this.hovered = null;
  },

  /** Forget everything, for a page that no longer shows the same ensemble. */
  reset() {
    this.picked = [];
    this.selected = null;
    this.hovered = null;
  },
};
