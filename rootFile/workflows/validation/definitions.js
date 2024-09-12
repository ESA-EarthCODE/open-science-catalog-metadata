const EXTENSION_SCHEMES = {
  themes: 'https://stac-extensions.github.io/themes/v1.0.0/schema.json',
  contacts: 'https://stac-extensions.github.io/contacts/v0.1.1/schema.json',
  osc: 'https://stac-extensions.github.io/osc/v1.0.0-rc.3/schema.json'
};

// List of project IDs that do not have a technical officer
const TECHNICAL_OFFICER_EXCEPTIONS = [
  'livas',
  'polar-low-detection-from-s-1-data',
  'pre-melt',
];

// List of project IDs that do not have a via link
const VIA_LINK_PROJECT_EXCEPTIONS = [
  'ocean-health-oa',
];

// List of product IDs that do not have a via link
const VIA_LINK_PRODUCT_EXCEPTIONS = [
  'dem-antarctica-2013-lpf-mitap',
  'dem-antarctica-2017-lpf-mitap',
  'glacier-elevation-cryosat-mountain-glaciers',
  'glacier-mass-balance-lpf-mitap',
  'model-ionosphere-4dionosphere',
  's2l2a-uncertainty-sr-lpf-l2arut',
  'surface-elevation-change-lpf-mitap',
];

const ROOT_CHILDREN = [
  './eo-missions/catalog.json',
  './processes/catalog.json',
  './products/catalog.json',
  './projects/catalog.json',
  './themes/catalog.json',
  './variables/catalog.json'
];

const THEMES_SCHEME = 'https://github.com/stac-extensions/osc#theme';

module.exports = {
  EXTENSION_SCHEMES,
  TECHNICAL_OFFICER_EXCEPTIONS,
  VIA_LINK_PROJECT_EXCEPTIONS,
  VIA_LINK_PRODUCT_EXCEPTIONS,
  ROOT_CHILDREN,
  THEMES_SCHEME
};
