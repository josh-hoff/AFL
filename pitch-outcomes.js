// Result filter: the in-play outcomes that can be picked next to Called Strike / Swinging Strike / Foul / Ball / Ball In Play.
// Each ball in play gets exactly one outcome. Rare ones with no option here (catcher interference) stay under "Ball In Play".
window.PitchOutcomes = (function () {
  const OPTS = [['O_1B', 'Single'], ['O_2B', 'Double'], ['O_3B', 'Triple'], ['O_HR', 'Home Run'], ['O_K', 'Strikeout'], ['O_GO', 'Groundout'], ['O_FO', 'Flyout'], ['O_LO', 'Lineout'], ['O_PO', 'Pop Out'], ['O_DP', 'Double Play'], ['O_FC', "Fielder's Choice"], ['O_E', 'Error']];
  const COLOR = { O_1B: '#2f6fb0', O_2B: '#7b4fb5', O_3B: '#1a8a4a', O_HR: '#f08a1c', O_GO: '#6b7280', O_FO: '#6b7280', O_LO: '#6b7280', O_PO: '#6b7280', O_DP: '#c0392b', O_FC: '#b8860b', O_E: '#8a8f98' };
  // rt = play_result_type, res = play_result, tr = trajectory (all from pitches.csv); only call for balls in play.
  function of(rt, res, tr) {
    rt = rt || ''; res = res || ''; tr = tr || '';
    if (rt === 'single') return 'O_1B';
    if (rt === 'double') return 'O_2B';
    if (rt === 'triple') return 'O_3B';
    if (rt === 'home_run') return 'O_HR';
    if (rt === 'field_error') return 'O_E';
    if (rt === 'grounded_into_double_play' || rt === 'double_play' || rt === 'sac_fly_double_play') return 'O_DP';
    if (rt === 'fielders_choice' || rt === 'fielders_choice_out') return 'O_FC';
    if (/ground/i.test(res)) return 'O_GO';
    if (/fly/i.test(res)) return 'O_FO';
    if (/line/i.test(res)) return 'O_LO';
    if (/pop/i.test(res)) return 'O_PO';
    // force outs, sac flies, sac bunts: use how the ball was hit
    if (/ground|bunt/.test(tr)) return 'O_GO';
    if (/line/.test(tr)) return 'O_LO';
    if (/fly/.test(tr)) return 'O_FO';
    if (/pop/.test(tr)) return 'O_PO';
    return '';
  }
  // Strikeout pitch = the pitch that ends the at-bat on strike three (count before the pitch had 2 strikes).
  function isK(call, strikes) { return strikes === 2 && /^(swinging strike|called strike|foul tip|missed bunt)/i.test(call || ''); }
  return { OPTS, COLOR, of, isK, isKey: k => String(k).indexOf('O_') === 0 };
})();
