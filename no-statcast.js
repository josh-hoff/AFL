// Games with no Statcast tracking. Their box score, stats and play-by-play stay everywhere; only the Statcast views
// (pills, charts, pitch tables) skip them.
// 1) Any game played at these ballparks, in any season. Kino Veterans Memorial Stadium (Tucson) has no MLB tracking
//    (first seen 10/10/2026: Mesa at Peoria 867705 and Scottsdale at Salt River 867706).
window.NO_STATCAST_VENUES = ['Kino Veterans Memorial Stadium'];
// 2) Individual games listed by hand, if one ever needs it.
window.NO_STATCAST_GAMES = new Set(['867705', '867706']);
const _noVenue = v => window.NO_STATCAST_VENUES.some(n => String(v || '').includes(n));
// Full set from pitches.csv: the lists above plus any game where not one pitch has a velocity.
window.untrackedGames = function (rows) {
  const s = new Set(window.NO_STATCAST_GAMES), seen = new Map();
  rows.forEach(r => {
    if (!seen.has(r.game_pk)) seen.set(r.game_pk, false);
    if ((r.start_speed !== '' && r.start_speed != null) && !_noVenue(r.venue)) seen.set(r.game_pk, true);
    if (_noVenue(r.venue)) s.add(r.game_pk);
  });
  seen.forEach((tracked, k) => { if (!tracked) s.add(k); });
  return s;
};
// For the box-score pills: pass the venue, or set window.BOX_VENUE before building the box score.
window.hasStatcast = (pk, venue) => !(window.NO_STATCAST_GAMES.has(String(pk)) || _noVenue(venue != null ? venue : window.BOX_VENUE));
