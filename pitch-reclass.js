/* pitch-reclass.js
 * Corrects obvious pitch-type mislabels in MLB's feed, per pitcher and season.
 * MLB's original label is never discarded: every row keeps it in _mlb_code / _mlb_desc.
 *
 * Spin rate comes first. Because spin differs from pitcher to pitcher, it is judged against that pitcher's own
 * fastball (median spin of his four-seamers / sinkers / two-seamers): ratio = pitch spin / fastball spin.
 * Across the whole league, breaking balls almost never spin below ~70% of the pitcher's fastball, and changeups /
 * splitters rarely spin above ~92% of it. A pitch whose spin sits on the wrong side of that line is a candidate,
 * and only becomes a re-label if its other measurements (velocity, horizontal break, induced vertical break,
 * spin direction) also fit the other type's profile for that pitcher.
 *
 * Changeup and splitter are treated as ONE family (MLB tags the same pitch either way depending on the day).
 * The family is shown as Changeup if the pitcher only has changeups tagged, Splitter if only splitters, and
 * "Split/Change" (code CS) if he has both.
 *
 * Every other pair of types (e.g. slider vs. curveball) keeps the stricter multi-metric rule, and now also needs
 * spin rate itself to disagree with the MLB tag when spin is available. Pitches that fit nothing, or fit two types
 * about equally, keep MLB's label.
 */
(function (root) {
  var MIN_PROFILE = 6, MIN_FEAT_N = 4, MIN_FEATURES = 3, FAR = 3.0, NEAR = 1.75, RATIO = 2.0;
  var MIN_ANCHOR = 10;          // fastballs (with spin) needed to know a pitcher's normal spin
  var LOW_R = 0.70, HIGH_R = 0.92; // spin vs. own fastball: breaking balls below LOW_R, changeups/splitters above HIGH_R are suspect
  var FIT_Z = 2.0;              // a metric "fits" a profile when it is within this many spreads
  var FAM = 'FAM';              // internal class for changeup + splitter
  var FAMILY = { CH: 1, FS: 1 };
  var FASTBALLS = { FF: 1, SI: 1, FT: 1 };
  var BREAKERS = { SL: 1, FC: 1, CU: 1, KC: 1, ST: 1, SV: 1 };
  var FEATS = [
    { k: 'v',    col: 'start_speed',            floor: 1.5 },
    { k: 'spin', col: 'spin_rate',              floor: 200 },
    { k: 'hb',   col: 'break_horizontal',       floor: 2.5 },
    { k: 'ivb',  col: 'break_vertical_induced', floor: 2.5 },
    { k: 'sd',   col: 'spin_direction',         floor: 25, circ: true }
  ];
  var DESC = { FF: 'Four-Seam Fastball', FT: 'Two-Seam Fastball', SI: 'Sinker', FC: 'Cutter', CH: 'Changeup', FS: 'Splitter',
    CS: 'Split/Change', FO: 'Forkball', CU: 'Curveball', KC: 'Knuckle Curve', SL: 'Slider', ST: 'Sweeper', SV: 'Slurve', KN: 'Knuckle Ball' };

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
  function cls(code) { return FAMILY[code] ? FAM : code; }

  /* Profile (median + robust spread per metric) from the pitches at the given row indexes. */
  function makeProfile(idx, vals) {
    var p = { n: idx.length, f: {} };
    FEATS.forEach(function (f) {
      var xs = idx.map(function (i) { return vals[i][f.k]; }).filter(function (v) { return v !== null; });
      if (xs.length < MIN_FEAT_N) return;
      var c = f.circ ? circMean(xs) : median(xs);
      var dev = xs.map(function (v) { return f.circ ? angDiff(v, c) : Math.abs(v - c); });
      p.f[f.k] = { c: c, s: Math.max(1.4826 * median(dev), f.floor), circ: !!f.circ };
    });
    return p;
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

  /* How many of the non-spin metrics sit on a profile (within FIT_Z) and how many exist. */
  function otherFit(a) {
    var fit = 0, have = 0;
    Object.keys(a.z).forEach(function (k) { if (k === 'spin') return; have++; if (a.z[k] <= FIT_Z) fit++; });
    return { fit: fit, have: have };
  }

  /* rows: every pitch one pitcher threw in one season (raw pitches.csv row objects). */
  function annotate(rows) {
    rows.forEach(function (r) {
      if (r._mlb_code === undefined) { r._mlb_code = r.pitch_type_code; r._mlb_desc = r.pitch_type_desc; }
      r._adj_code = r._mlb_code; r._adj_desc = r._mlb_desc; r._changed = false; r._why = '';
    });
    var vals = rows.map(values);

    // The pitcher's own fastball spin is the yardstick for every other pitch's spin.
    var fbSpins = [];
    rows.forEach(function (r, i) { if (FASTBALLS[r._mlb_code] && vals[i].spin !== null) fbSpins.push(vals[i].spin); });
    var anchor = fbSpins.length >= MIN_ANCHOR ? median(fbSpins) : null;
    var ratio = vals.map(function (v) { return anchor && v.spin !== null ? v.spin / anchor : null; });

    // Group by MLB tag (changeup + splitter together). Breaking-ball profiles ignore pitches whose spin is
    // implausibly low for a breaking ball, and the changeup/splitter profile ignores pitches whose spin is
    // implausibly high, so a run of mis-tagged pitches cannot become the pitcher's "normal" for that type.
    var groups = {};
    rows.forEach(function (r, i) {
      var c = cls(r._mlb_code); if (!c) return;
      var rr = ratio[i];
      if (rr !== null) {
        if (c === FAM && rr >= HIGH_R) return;
        if (BREAKERS[c] && rr < LOW_R) return;
      }
      (groups[c] = groups[c] || []).push(i);
    });
    var prof = {};
    Object.keys(groups).forEach(function (c) { if (groups[c].length >= MIN_PROFILE) prof[c] = makeProfile(groups[c], vals); });
    // changeup/splitter tags that survive the plausibility filter (used to see if a breaking ball really is one)

    var FB_MIN_R = 0.85; // a pitch matched to a fastball type should spin at least this much vs. his fastball
    // Does a target type make sense against his fastball spin? (the second baseline)
    function plausibleVsFastball(t, rr) {
      if (rr === null) return true;
      if (t === FAM) return rr < HIGH_R;
      if (BREAKERS[t]) return rr >= LOW_R;
      if (FASTBALLS[t]) return rr >= FB_MIN_R;
      return true;
    }
    rows.forEach(function (r, i) {
      var c = cls(r._mlb_code), v = vals[i], rr = ratio[i], target = null;
      if (!c) return;
      var own = prof[c], a = own ? zs(v, own) : null;

      if (v.spin !== null) {
        // 1) Own type first: is this pitch's spin far from the median of the type MLB tagged (for this pitcher)?
        var ownOff = !!(a && a.z.spin !== undefined && a.z.spin >= 2.5 && a.D >= FAR);
        // 2) Fastball second: does his fastball spin say this type's spin is impossible? (e.g. a "splitter" spinning above his fastball)
        var fbOff = rr !== null && ((c === FAM && rr >= HIGH_R) || (BREAKERS[c] && rr < LOW_R));
        if (ownOff || fbOff) {
          var best = null;
          Object.keys(prof).forEach(function (t) {
            if (t === c) return;
            if (!(BREAKERS[t] || FASTBALLS[t] || t === FAM)) return;
            if (!plausibleVsFastball(t, rr)) return;
            var b = zs(v, prof[t]); if (b.k < MIN_FEATURES || !(b.z.spin <= FIT_Z)) return;
            if (!best || b.D < best.b.D) best = { t: t, b: b };
          });
          if (best) {
            var of = otherFit(best.b), lim = (best.t === FAM) ? NEAR + 0.5 : NEAR;
            var closer = a ? a.D >= RATIO * best.b.D : (fbOff && c === FAM); // with no profile of its own, only the fastball baseline can speak
            if (of.have >= 2 && of.fit >= 2 && best.b.D <= lim && closer) target = best.t;
          }
        }
      } else if (c !== FAM && own) {
        // No spin number: stricter multi-metric rule, never touching changeup/splitter.
        if (a.k >= MIN_FEATURES && a.D >= FAR) {
          var nb = null;
          Object.keys(prof).forEach(function (t) {
            if (t === c || t === FAM) return;
            var b = zs(v, prof[t]); if (b.k < MIN_FEATURES) return;
            if (!nb || b.D < nb.b.D) nb = { t: t, b: b };
          });
          if (nb && nb.b.D <= NEAR && a.D >= RATIO * nb.b.D) {
            var votes = 0;
            Object.keys(nb.b.z).forEach(function (k) { if (a.z[k] !== undefined && a.z[k] >= 2.5 && nb.b.z[k] <= 2) votes++; });
            if (votes >= 3) target = nb.t;
          }
        }
      }
      if (target && target !== c) { r._adj_code = target; r._why = 'measure'; }
    });

    // Changeup/splitter family naming: only changeups tagged -> Changeup, only splitters -> Splitter, both -> Split/Change.
    var hasCH = false, hasFS = false;
    rows.forEach(function (r) {
      if (r._adj_code === FAM || FAMILY[r._adj_code]) {
        var o = r._mlb_code; if (o === 'CH') hasCH = true; else if (o === 'FS') hasFS = true;
      }
    });
    var famCode = hasCH && hasFS ? 'CS' : (hasFS ? 'FS' : 'CH');
    var changed = 0;
    rows.forEach(function (r) {
      if (r._adj_code === FAM) r._adj_code = famCode;
      else if (FAMILY[r._adj_code] && r._adj_code !== famCode && hasCH && hasFS) { r._adj_code = famCode; if (!r._why) r._why = 'family'; }
      if (r._adj_code !== r._mlb_code) { r._adj_desc = DESC[r._adj_code] || r._adj_code; r._changed = true; changed++; if (!r._why) r._why = 'family'; }
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
