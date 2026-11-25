/* VIEWPR iconography — one source of truth for category/type icons and colors.
   Icons are Material Symbols (Rounded) ligatures; the font subset is loaded in index.html / table.html. */

'use strict';

/* ── FPR palette ───────────────────────────────────────────────────────────
   Foundation for Puerto Rico's four primary hues and their scales, per the June 2026
   HEX confirmation. These are the brand values, which the logo artwork approximates —
   fpr-mark.png samples as F0533A/FDB813/ABD037/288C9F, a pre-2026 export. The confirmed
   values win so the app matches FPR decks and documents.

   One category maps to one hue, defined here and nowhere else: this file loads before
   viewpr.js, so charts, map markers, legends and badges all read the same values. They
   used to disagree — the map ran on Tailwind defaults, so Gastronomy was green on the
   dashboard and amber on the map.

   Three of the four are the exact base hues. Gastronomy drops one step to Green 600
   because base green and base yellow are nearly indistinguishable under deuteranopia:
   simulating the four base hues gives a minimum pairwise ΔE of 6.5, against 15.7 with
   this substitution. Category is never the only cue in any case — icons, labels and
   percentages carry it too. */

const FPR = {
  red:    { 100:'#FFD0C9', 300:'#FF8270', 500:'#FF4D38', 700:'#B82415', 800:'#8C180D' },
  yellow: { 100:'#FFE9A8', 300:'#FFC83C', 500:'#FFA600', 700:'#B56D00', 800:'#8A5200' },
  green:  { 100:'#E4EFB8', 300:'#C2D85E', 400:'#A6BF33', 600:'#79901E', 800:'#47560F' },
  blue:   { 100:'#BDE0F2', 200:'#8FCAE8', 300:'#5FAFDA', 500:'#338CB3', 700:'#205D7B' },
  gray:   { charcoal:'#2A2E2E', mid:'#666666', neutral:'#B3B3B3', soft:'#E6E6E6', off:'#F2F2F2' },
};

const CATEGORY_META = {
  ATTRACTIONS:      { label: 'Attractions',      color: FPR.blue[500],   soft: FPR.blue[100],   text: FPR.blue[700],   icon: 'attractions' },
  GASTRONOMY:       { label: 'Gastronomy',       color: FPR.green[600],  soft: FPR.green[100],  text: FPR.green[800],  icon: 'restaurant' },
  ACCOMMODATIONS:   { label: 'Accommodations',   color: FPR.yellow[500], soft: FPR.yellow[100], text: FPR.yellow[800], icon: 'hotel' },
  VISITOR_SERVICES: { label: 'Visitor Services', color: FPR.red[500],    soft: FPR.red[100],    text: FPR.red[800],    icon: 'tour' },
};

/* Shades within a hue for the subcategories of one category, alternating dark and light so
   neighboring slices separate while the family stays recognizable. */
const CATEGORY_SCALES = {
  ATTRACTIONS:      [FPR.blue[500],   FPR.blue[700],   FPR.blue[300],   FPR.blue[200],   FPR.blue[100]],
  GASTRONOMY:       [FPR.green[600],  FPR.green[800],  FPR.green[400],  FPR.green[300],  FPR.green[100]],
  ACCOMMODATIONS:   [FPR.yellow[500], FPR.yellow[800], FPR.yellow[300], FPR.yellow[700], FPR.yellow[100]],
  VISITOR_SERVICES: [FPR.red[500],    FPR.red[800],    FPR.red[300],    FPR.red[700],    FPR.red[100]],
};

/** The category a subcategory belongs to, or null if it is not in the taxonomy. */
function categoryOfSubcategory(subcategory) {
  return Object.keys(TYPE_GROUPS).find(c => TYPE_GROUPS[c].includes(subcategory)) || null;
}

/** A subcategory's color: its parent category's hue, stepped so siblings stay distinct. */
function subcategoryColor(subcategory) {
  const cat = categoryOfSubcategory(subcategory);
  if (!cat) return FPR.gray.neutral;           // 'Other' and anything off-taxonomy
  const scale = CATEGORY_SCALES[cat];
  const i = TYPE_GROUPS[cat].indexOf(subcategory);
  return scale[i % scale.length];
}

const TYPE_ICONS = {
  // Attractions
  'Tourist Attractions':           'attractions',
  'Beaches':                       'beach_access',
  'Parks':                         'park',
  'Nature Reserves':               'forest',
  'Museums':                       'museum',
  'Historic Sites':                'account_balance',
  'Cultural Attractions':          'theater_comedy',
  'Landmarks':                     'church',
  'Scenic Areas':                  'landscape',
  'Places of Worship':             'church',
  // Gastronomy
  'Restaurants':                   'restaurant',
  'Cafes':                         'local_cafe',
  'Bakeries':                      'bakery_dining',
  'Bars':                          'local_bar',
  'Nightlife':                     'nightlife',
  'Food Markets':                  'storefront',
  'Food Experiences':              'wine_bar',
  // Accommodations
  'Hotels':                        'hotel',
  'Resorts':                       'pool',
  'Inns':                          'bed',
  'Guest Houses':                  'house',
  'Vacation Properties':           'holiday_village',
  'Lodging':                       'night_shelter',
  // Visitor services
  'Tour Operators':                'tour',
  'Visitor Centers':               'info',
  'Marinas':                       'sailing',
  'Adventure Operators':           'hiking',
  'Transportation':                'directions_car',
  'Cultural Experience Providers': 'palette',
};

const STATUS_META = {
  OPERATIONAL:        { label: 'Open',               color: '#10B981', icon: 'check_circle' },
  CLOSED_TEMPORARILY: { label: 'Temp. Closed',       color: '#F59E0B', icon: 'schedule' },
  CLOSED_PERMANENTLY: { label: 'Permanently Closed', color: '#EF4444', icon: 'cancel' },
};

function catMeta(cat) {
  return CATEGORY_META[cat] || { label: cat || '—', color: FPR.gray.mid, soft: FPR.gray.off, text: FPR.gray.charcoal, icon: 'place' };
}

/* Names in the page language. The English text of CATEGORY_META, STATUS_META and TYPE_ICONS is also what the code looks things up by, so it is translated only where it is shown.
   A category is T('Attractions'...) (i18n_src/es/icons.json); a type is a data value of places.json (i18n_src/es/labels_places.json). Anything else that shows p.type or a category label calls these. */
function categoryLabel(category) { const m = CATEGORY_META[category]; return m ? T(m.label) : (category || '—'); }
function typeLabel(subcategory) { return subcategory ? T(subcategory) : ''; }
function statusLabel(status) { const m = STATUS_META[status]; return m ? T(m.label) : (status || '—'); }

function typeIconName(subcategory, category) {
  return TYPE_ICONS[subcategory] || catMeta(category).icon;
}

function _escIcon(s) {
  return s == null ? '' : String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

/** Raw icon glyph. size in px; color any CSS color. */
function icon(name, { size = 18, color, cls = '', title = '' } = {}) {
  const style = `font-size:${size}px;${color ? `color:${color};` : ''}`;
  return `<span class="ms-icon ${cls}" style="${style}" aria-hidden="true"${title ? ` title="${_escIcon(title)}"` : ''}>${name}</span>`;
}

/** Colored round icon for a type, tinted by its category (used in tables, lists, popups). */
function typeIcon(subcategory, category, size = 26) {
  const m = catMeta(category);
  return `<span class="type-icon" style="width:${size}px;height:${size}px;background:${m.soft};color:${m.text}" title="${_escIcon(subcategory ? typeLabel(subcategory) : categoryLabel(category))}">${icon(typeIconName(subcategory, category), { size: Math.round(size * 0.62) })}</span>`;
}

/** Pill with icon + label for a category. */
function categoryBadge(category) {
  const m = catMeta(category);
  return `<span class="badge badge-icon" style="background:${m.soft};color:${m.text}">${icon(m.icon, { size: 14 })}${_escIcon(categoryLabel(category))}</span>`;
}

/** Pill with icon + label for a type (subcategory), tinted by category. */
function typeChip(subcategory, category) {
  if (!subcategory) return '';
  const m = catMeta(category);
  return `<span class="badge badge-icon" style="background:${m.soft};color:${m.text}">${icon(typeIconName(subcategory, category), { size: 14 })}${_escIcon(typeLabel(subcategory))}</span>`;
}

/** Icon + label cell content for tables (icon tinted by category, text plain). */
function typeCell(subcategory, category) {
  return `<span class="type-cell">${typeIcon(subcategory, category, 22)}<span>${_escIcon(subcategory ? typeLabel(subcategory) : categoryLabel(category))}</span></span>`;
}

function statusBadge(status) {
  const m = STATUS_META[status];
  if (!m) return '<span class="td-muted">—</span>';
  return `<span class="status-inline" style="color:${m.color}">${icon(m.icon, { size: 15 })}${_escIcon(statusLabel(status))}</span>`;
}

/** Leaflet DivIcon: colored pin with the type glyph. Requires Leaflet. */
function assetMarkerIcon(pt) {
  const cat = pt.primary_category || pt.category, sub = pt.subcategory || pt.type;
  const m = catMeta(cat);
  const closed = pt.business_status && pt.business_status !== 'OPERATIONAL';
  return L.divIcon({
    className: 'asset-marker-wrap',
    html: `<div class="asset-marker${closed ? ' is-closed' : ''}${pt.sfha ? ' is-sfha' : ''}" style="background:${m.color}">${icon(typeIconName(sub, cat), { size: 14, color: '#fff' })}</div>`,
    iconSize: [26, 26],
    iconAnchor: [13, 13],
    tooltipAnchor: [0, -14],
  });
}

/** Legend HTML: four categories, each expandable to its types. */
function iconLegendHTML(typeCounts = null) {
  const groups = {};
  Object.entries(TYPE_ICONS).forEach(([t]) => {
    const cat = Object.keys(CATEGORY_META).find(c => TYPE_GROUPS[c].includes(t));
    (groups[cat] = groups[cat] || []).push(t);
  });
  return Object.entries(CATEGORY_META).map(([cat, m]) => `
    <details class="legend-group">
      <summary class="legend-item">
        <span class="legend-pin" style="background:${m.color}">${icon(m.icon, { size: 12, color: '#fff' })}</span>${_escIcon(categoryLabel(cat))}
      </summary>
      <div class="legend-types">
        ${(groups[cat] || []).map(t => `
          <div class="legend-type">${icon(typeIconName(t, cat), { size: 14, color: m.text })}<span>${_escIcon(typeLabel(t))}</span>${typeCounts && typeCounts[t] != null ? `<em>${fmt(typeCounts[t])}</em>` : ''}</div>
        `).join('')}
      </div>
    </details>
  `).join('');
}

const TYPE_GROUPS = {
  ATTRACTIONS: ['Tourist Attractions', 'Beaches', 'Parks', 'Nature Reserves', 'Museums', 'Historic Sites', 'Cultural Attractions', 'Landmarks', 'Scenic Areas', 'Places of Worship'],
  GASTRONOMY: ['Restaurants', 'Cafes', 'Bakeries', 'Bars', 'Nightlife', 'Food Markets', 'Food Experiences'],
  ACCOMMODATIONS: ['Hotels', 'Resorts', 'Inns', 'Guest Houses', 'Vacation Properties', 'Lodging'],
  VISITOR_SERVICES: ['Tour Operators', 'Visitor Centers', 'Marinas', 'Adventure Operators', 'Transportation', 'Cultural Experience Providers'],
};

/** All icon names used, sorted — must match the &icon_names= subset in the font <link>. */
const ICON_NAMES_USED = [...new Set([
  ...Object.values(TYPE_ICONS),
  ...Object.values(CATEGORY_META).map(m => m.icon),
  ...Object.values(STATUS_META).map(m => m.icon),
  'place', 'open_in_new', 'download', 'table_view', 'flood', 'water', 'shield', 'commute', 'directions_bus', 'directions_boat', 'train', 'subway', 'flight', 'local_taxi', 'ev_station', 'airlines', 'transfer_within_a_station', 'layers', 'close', 'search', 'tune', 'warning', 'groups', 'location_city', 'waves', 'public', 'bar_chart', 'menu', 'chevron_right', 'arrow_back', 'help', 'verified',
])].sort();
