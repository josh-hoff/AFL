/* pitch-reclass.js
 * Corrects obvious pitch-type mislabels in MLB's feed, per pitcher and season.
 * MLB's original label is never discarded: every row keeps it in _mlb_code / _mlb_desc.
 *
 * How it decides (only "obvious" cases):
 *  1. For each pitch type a pitcher threw (>= MIN_PROFILE pitches labeled that way), build a profile from
 *     the median and spread of velocity, spin rate, horizontal break, induced vertical break and spin direction.
 *  2. For every pitch, measure how far it sits from the profile of its MLB-labeled type and from every other type
 *     (average z-distance over the metrics that exist for that pitch).
 *  3. Relabel only when ALL of these hold: it has >= MIN_FEATURES metrics; it is far from its labeled type
 *     (D_label >= FAR); it sits comfortably inside another type's profile (D_best <= NEAR); the other type is at
 *     least RATIO times closer; and at least 2 metrics individually say "not the labeled type, fits the other".
 *  Pitches that fit nothing, or fit two types about equally (e.g. slider vs curveball overlap), keep MLB's label.
 */
(function (root) {
  var MIN_PROFILE = 6, MIN_FEAT_N = 4, MIN_FEATURES = 3, FAR = 3.0, NEAR = 1.75, RATIO = 2.0;
  var FEATS = [
    { k: 'v',    col: 'start_speed',            floor: 1.5 },
    { k: 'spin', col: 'spin_rate',              floor: 200 },
    { k: 'hb',   col: 'break_horizontal',       floor: 2.5 },
    { k: 'ivb',  col: 'break_vertical_induced', floor: 2.5 },
    { k: 'sd',   col: 'spin_direction',         floor: 25, circ: true }
  ];
  var DESC = { FF: 'Four-Seam Fastball', FT: 'Two-Seam Fastball', SI: 'Sinker', FC: 'Cutter', CH: 'Changeup', FS: 'Splitter',
    FO: 'Forkball', CU: 'Curveball', KC: 'Knuckle Curve', SL: 'Slider', ST: 'Sweeper', SV: 'Slurve', KN: 'Knuckle Ball' };

  function num(x) { if (x === '' || x === undefined || x === null) return null; var n = Number(x); return isNaN(n) ? null : n; }
  function median(a) { var s = a.slice().sort(function (x, y) { return x - y; }), m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; }
  function angDiff(a, b) { var d = Math.abs(a - b) % 360; return d > 180 ? 360 - d : d; }
  function circMean(a) {
    var s = 0, c = 0; a.forEach(function (d) { s += Math.sin(d * Math.PI / 180); c += Math.cos(d * Math.PI / 180); });
    return ((Math.atan2(s, c) * 180 / Math.PI) + 360) % 360;
  }
  function values(r) {
    var o = {}; FEATS.forEach(function (f) { var v = num(r[f.col]); if (f.k === 'spin' && v !== null && v <= 0) v = null; o[f.k] = v; }); return o;
  }

  function buildProfiles(rows, vals) {
    var by = {};
    rows.forEach(function (r, i) { var t = r._mlb_code; if (!t) return; (by[t] = by[t] || []).push(i); });
    var prof = {};
    Object.keys(by).forEach(function (t) {
      if (by[t].length < MIN_PROFILE) return;
      var p = { n: by[t].length, f: {} };
      FEATS.forEach(function (f) {
        var xs = by[t].map(function (i) { return vals[i][f.k]; }).filter(function (v) { return v !== null; });
        if (xs.length < MIN_FEAT_N) return;
        var c = f.circ ? circMean(xs) : median(xs);
        var dev = xs.map(function (v) { return f.circ ? angDiff(v, c) : Math.abs(v - c); });
        p.f[f.k] = { c: c, s: Math.max(1.4826 * median(dev), f.floor), circ: !!f.circ };
      });
      prof[t] = p;
    });
    return prof;
  }

  function zs(v, p) {
    var z = {}, sum = 0, k = 0;
    FEATS.forEach(function (f) {
      var pf = p.f[f.k]; if (v[f.k] === null || !pf) return;
      var d = pf.circ ? angDiff(v[f.k], pf.c) : Math.abs(v[f.k] - pf.c);
      z[f.k] = d / pf.s; sum += z[f.k] * z[f.k]; k++;
    });
    return { z: z, k: k, D: k ? Math.sqrt(sum / k) : Infinity };
  }

  /* rows: every pitch one pitcher threw in one season (raw pitches.csv row objects). */
  function annotate(rows) {
    rows.forEach(function (r) {
      if (r._mlb_code === undefined) { r._mlb_code = r.pitch_type_code; r._mlb_desc = r.pitch_type_desc; }
      r._adj_code = r._mlb_code; r._adj_desc = r._mlb_desc; r._changed = false;
    });
    var vals = rows.map(values), prof = buildProfiles(rows, vals), changed = 0;
    rows.forEach(function (r, i) {
      var lab = prof[r._mlb_code]; if (!lab) return;
      var a = zs(vals[i], lab); if (a.k < MIN_FEATURES || a.D < FAR) return;
      var best = null;
      Object.keys(prof).forEach(function (t) {
        if (t === r._mlb_code) return;
        var b = zs(vals[i], prof[t]); if (b.k < MIN_FEATURES) return;
        if (!best || b.D < best.b.D) best = { t: t, b: b };
      });
      if (!best || best.b.D > NEAR || a.D < RATIO * best.b.D) return;
      var votes = 0;
      Object.keys(best.b.z).forEach(function (k) { if (a.z[k] !== undefined && a.z[k] >= 2.5 && best.b.z[k] <= 2) votes++; });
      if (votes < 2) return;
      r._adj_code = best.t; r._adj_desc = DESC[best.t] || best.t; r._changed = true; changed++;
    });
    return changed;
  }

  /* Point the standard pitch_type_* fields at MLB's tags or the adjusted ones. */
  function setMode(rows, useMlb) {
    rows.forEach(function (r) {
      if (r._mlb_code === undefined) return;
      r.pitch_type_code = useMlb ? r._mlb_code : r._adj_code;
      r.pitch_type_desc = useMlb ? r._mlb_desc : r._adj_desc;
    });
  }

  var api = { annotate: annotate, setMode: setMode, DESC: DESC };
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.PitchReclass = api;
})(typeof window !== 'undefined' ? window : this);
