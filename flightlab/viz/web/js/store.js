// Telemetry received from the server: one array per log channel, all the same
// length, oldest first. Only the recent past is kept (the plots show 20 s).

const KEEP_ROWS = 6000;          // 60 s at the 100 Hz log rate
const TRIM_AT = 2 * KEEP_ROWS;

export class Store {
  constructor() {
    this.clear();
  }

  clear() {
    this.columns = new Map();    // channel name -> array of numbers (null = no value)
    this.n = 0;
    this.version = 0;            // bumped on every change, so views know to redraw
  }

  /** Append columnar rows {channel: [values]} from a frame. */
  ingest(rows, reset) {
    if (reset) this.clear();
    const names = Object.keys(rows);
    if (names.length === 0) {
      if (reset) this.version++;
      return;
    }
    const added = rows[names[0]].length;
    for (const name of names) {
      let col = this.columns.get(name);
      if (!col) {                // a channel that appeared mid-run: backfill
        col = new Array(this.n).fill(null);
        this.columns.set(name, col);
      }
      for (const v of rows[name]) col.push(v);
    }
    this.n += added;
    for (const col of this.columns.values()) {
      while (col.length < this.n) col.push(null);
    }
    if (this.n > TRIM_AT) {
      const drop = this.n - KEEP_ROWS;
      for (const col of this.columns.values()) col.splice(0, drop);
      this.n = KEEP_ROWS;
    }
    this.version++;
  }

  col(name) {
    return this.columns.get(name);
  }

  last(name, fallback = NaN) {
    const col = this.columns.get(name);
    if (!col || this.n === 0) return fallback;
    const v = col[this.n - 1];
    return v === null ? fallback : v;
  }

  /** Index of the first row with time >= t. */
  indexAt(t) {
    const times = this.columns.get("t");
    if (!times) return 0;
    let lo = 0, hi = this.n;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (times[mid] < t) lo = mid + 1; else hi = mid;
    }
    return lo;
  }

  /** Names of the student's self.log() signals. */
  studentSignals() {
    const out = [];
    for (const name of this.columns.keys()) {
      if (name.startsWith("log.")) out.push(name.slice(4));
    }
    return out.sort();
  }
}
