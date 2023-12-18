const BaseValidator = require('stac-node-validator/src/baseValidator.js');
const fs = require('fs-extra');
const path = require('path');
const sizeOf = require('image-size');

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

const BEFORE_BUILD = true;

class CustomValidator extends BaseValidator {

  constructor() {
    super();
    this.titles = {};
  }

  async getTitleForFile(file) {
    if (typeof this.titles[file] === 'undefined') {
      const stac = await fs.readJson(file);
      this.registerTitle(file, stac);
    }
    return this.titles[file];
  }

  registerTitle(file, stac) {
    file = path.resolve(file);
    if (stac?.type === "Feature") {
      this.titles[file] = stac?.properties?.title || null;
    }
    else {
      this.titles[file] = stac?.title || null;
    }
  }

	async afterLoading(data, report, config) {
    this.registerTitle(report.id, data);
    return data;
	}

  async afterValidation(data, test, report, config) {
    const isRootCatalog = report.id.endsWith('/catalog.json') && data.id === "osc";
    const isEoMission = !!report.id.match(/\/eo-missions\/[^\/]+\/catalog.json/);
    const isProduct = !!report.id.match(/\/products\/[^\/]+\/collection.json/);
    const isProductUserContent = !!report.id.match(/\/products\/[^\/]+\/.+.json/) && !isProduct;
    const isProject = !!report.id.match(/\/projects\/[^\/]+\/collection.json/);
    const isTheme = !!report.id.match(/\/themes\/[^\/]+\/catalog.json/);
    const isVariable = !!report.id.match(/\/variables\/[^\/]+\/catalog.json/);
    const isSubCatalog = !!report.id.match(/\/(eo-missions|processes|products|projects|themes|variables)\/catalog.json/);

    // Ensure consistent STAC version
    // @todo: Enable STAC 1.1.0 support once released
    test.equal(data.stac_version, "1.0.0", `stac_version must be '1.0.0'`);

    // Ensure all catalogs and collections have a title
    test.truthy(!data.isCatalogLike() || (typeof data.title === 'string' && data.title.length > 0), "must have a title");

    const run = new ValidationRun(this, data, test, report);

    if (isProductUserContent) {
      run.validateUserContent();
    }
    else if (isSubCatalog) {
      const childEntity = path.basename(path.dirname(report.id));
      let childStacType = 'Catalog';
      if (['products', 'projects'].includes(childEntity)) {
        childStacType = 'Collection';
      }
      else if (childEntity === 'processes') {
        childStacType = 'Process';
      }
      await run.validateSubCatalogs(childStacType);
    }
    else if (isRootCatalog) {
      await run.validateRoot();
    }
    else if (isEoMission) {
      await run.validateEoMission();
    }
    else if (isProduct) {
      await run.validateProduct();
    }
    else if (isProject) {
      await run.validateProject();
    }
    else if (isTheme) {
      await run.validateTheme();
    }
    else if (isVariable) {
      await run.validateVariable();
    }
    else {
      test.fail("File should not exist");
    }
  }
}

class ValidationRun {

  constructor(parent, data, test, report) {
    this.parent = parent;
    this.data = data;
    this.t = test;
    this.report = report;
    this.folder = path.dirname(report.id);
  }

  async validateRoot() {
    this.t.equal(this.data.type, "Catalog", `type must be 'Catalog'`);
    this.t.equal(this.data.id, "osc", `id must be 'osc'`);
    this.t.equal(this.data.title, "Open Science Catalog", `title must be 'Open Science Catalog'`);
  
    // check parent and root
    await this.requireRootLink("./catalog.json");
    this.t.truthy(!this.data.getLinkWithRel('parent'), "must NOT have a parent");
  
    // check child links
    await this.requireChildLinksForOtherJsonFiles("Catalog", ROOT_CHILDREN);
  }
  
  async validateSubCatalogs(childStacType) {
    this.t.equal(this.data.type, "Catalog", `type must be 'Catalog'`);
    this.ensureIdIsFolderName();
  
    // check that catalog.json is parent and root
    await this.requireParentLink("../catalog.json");
    await this.requireRootLink("../catalog.json");
  
    // check child links
    if (childStacType === 'Process') {
      await this.requireChildLinksForOtherJsonFiles(null, [], 'cwl', 'process', 'application/cwl');
    }
    else {
      await this.requireChildLinksForOtherJsonFiles(childStacType);
    }
  }
  
  validateUserContent() {
    // @todo: Which rules apply?
  }
  
  async validateEoMission() {
    this.t.equal(this.data.type, "Catalog", `type must be 'Catalog'`);
    this.ensureIdIsFolderName();
  
    this.requireViaLink();
    await this.requireParentLink("../catalog.json");
    await this.requireRootLink("../../catalog.json");
    BEFORE_BUILD && this.disallowRelatedLinks();
  }
  
  async validateProduct() {
    this.t.equal(this.data.type, "Collection", `type must be 'Collection'`);
    this.hasExtensions(["osc"]);
    this.ensureIdIsFolderName();
  
    if (!VIA_LINK_PRODUCT_EXCEPTIONS.includes(this.data.id)) {
      this.requireViaLink();
    }
    await this.requireParentLink("../catalog.json");
    await this.requireRootLink("../../catalog.json");
    BEFORE_BUILD && this.disallowRelatedLinks();
  
    await this.checkOscExtension("product");

    if (Array.isArray(this.data.keywords)) {
      // Check that keywords do not contain a colon to be able to distinguish them
      // from the keywords generated based on the OSC extension fields in the builder
      BEFORE_BUILD && this.data.keywords.forEach(
        keyword => this.t.truthy(!keyword.includes(':'), `Keyword '${keyword}' MUST NOT contain ':'`)
      );
    }
  }
  
  async validateProject() {
    this.t.equal(this.data.type, "Collection", `type must be 'Collection'`);
    this.hasExtensions(["osc", "contacts"]);
    this.ensureIdIsFolderName();
  
    if (!VIA_LINK_PROJECT_EXCEPTIONS.includes(this.data.id)) {
      this.requireViaLink();
    }
    await this.requireParentLink("../catalog.json");
    await this.requireRootLink("../../catalog.json");
    BEFORE_BUILD && this.disallowRelatedLinks();
  
    if (!TECHNICAL_OFFICER_EXCEPTIONS.includes(this.data.id)) {
      this.requireTechnicalOfficer();
    }
  
    await this.checkOscExtension("project");
  }
  
  async validateTheme() {
    this.t.equal(this.data.type, "Catalog", `type must be 'Catalog'`);
    this.ensureIdIsFolderName();
  
    await this.requireParentLink("../catalog.json");
    await this.requireRootLink("../../catalog.json");
    BEFORE_BUILD && this.disallowRelatedLinks();
  
    this.checkPreviewImage();
  }

  async validateVariable() {
    this.t.equal(this.data.type, "Catalog", `type must be 'Catalog'`);
    this.hasExtensions(["themes"]);
    this.ensureIdIsFolderName();
  
    this.requireViaLink();
    await this.requireParentLink("../catalog.json");
    await this.requireRootLink("../../catalog.json");
    BEFORE_BUILD && this.disallowRelatedLinks();
  
    const theme = this.data.themes.find(theme => theme.scheme === THEMES_SCHEME);

    this.t.truthy(theme, `must have theme with scheme '${THEMES_SCHEME}'`);

    const conceptArray = theme.concepts.map(concept => concept.id);
    await this.checkOscCrossRefArray(conceptArray, "themes");
  }
  
  hasExtensions(extensions) {
    if (Array.isArray(this.data.stac_extensions)) {
      for(let ext of extensions) {
        this.t.truthy(this.data.stac_extensions.includes(EXTENSION_SCHEMES[ext]), "must implement extension: " + ext);
      }
    }
    else {
      this.t.fail("must implement extensions: " + extensions.join(", "));
    }
  }

  checkPreviewImage() {
    // Check that the theme has a preview image with valid properties and that the file exists
    const link = this.data.getLinkWithRel("preview");
    this.t.truthy(link, "must have 'preview' link");
    this.t.equal(link.type, "image/webp");
    this.t.equal(link["proj:epsg"], null);

    const previewPath = path.resolve(this.folder, link.href);

    try {
      const dimensions = sizeOf(previewPath);
      this.t.deepEqual(link["proj:shape"], [dimensions.height, dimensions.width]);
    } catch(error) {
      this.t.fail(`Preview image doesn't exist or is corrupt: ${previewPath}`);
    }
  }
  
  ensureIdIsFolderName() {
    const match = this.report.id.match(/\/([^\/]+)\/[^\/]+.json/);
    this.t.equal(this.data.id, match[1], "parent folder name must match id");
  }
  
  // check that all files are linked to as child links and that all child links exist
  async requireChildLinksForOtherJsonFiles(type, files = [], fileExt = 'json', linkRel = 'child', linkType = 'application/json') {
    if(files.length === 0) {
      const dir = await fs.opendir(this.folder);
      for await (const file of dir) {
        if (file.isDirectory()) {
          if (type) {
            const filename = type.toLowerCase();
            const filepath = path.normalize(`${this.folder}/${file.name}/${filename}.${fileExt}`);
            files.push(filepath);
          }
          else {
            const subfolder = `${this.folder}/${file.name}`;
            const subdir = await fs.opendir(subfolder);
            for await (const file of subdir) {
              if (file.name.endsWith(`.${fileExt}`)) {
                const filepath = path.normalize(`${subfolder}/${file.name}`);
                files.push(filepath);
              }
            }
          }
        }
      }
    }
    else {
      files = files.map(file => path.resolve(this.folder, file));
    }

    const links = this.data.getLinksWithRels([linkRel]);
    for(const link of links) {
      this.t.equal(link.type, linkType, `Link with relation ${linkRel} to ${link.href} must be of type ${linkType}`);
      if (link.href.endsWith('.json')) {
        await this.checkLinkTitle(link, this.folder);
      }
    }
  
    const linkHrefs = links.map(link => path.resolve(this.folder, link.href));
  
    let missingChilds = files.filter(x => !linkHrefs.includes(x));
    for(const file of missingChilds) {
      this.t.fail(`must have link with relation ${linkRel} to ${file}`);
    }
  
    let missingFiles = linkHrefs.filter(x => !files.includes(x));
    for(const file of missingFiles) {
      this.t.fail(`must have file for link ${file} with relation ${linkRel}`);
    }
  }

  async checkLinkTitle(link) {
    const href = path.resolve(this.folder, link.href);
    const title = await this.parent.getTitleForFile(href);
    if (typeof title === "string") {
      this.t.equal(link.title, title, `Title of link to ${link.href} is not the title of the linked file ${href}`);
    }
  }

  async checkOscExtension(type) {
    this.t.equal(this.data["osc:type"], type, `'osc:type' must be '${type}'`);

    if (type === "product") {
      await this.checkOscCrossRef(this.data["osc:project"], "projects");
      await this.checkOscCrossRefArray(this.data["osc:variables"], "variables");
    }
    await this.checkOscCrossRefArray(this.data["osc:missions"], "eo-missions");
    await this.checkOscCrossRefArray(this.data["osc:themes"], "themes");
  }

  async checkOscCrossRefArray(values, type) {
    if (typeof values !== 'undefined') {
      await Promise.all(values.map(value => this.checkOscCrossRef(value, type)));
    }
  }

  async checkOscCrossRef(value, type) {
    const slug = this.slugify(value);
    const filename = ['products', 'projects'].includes(type) ? 'collection' : 'catalog';
    const filepath = path.resolve(this.folder, `../../${type}/${slug}/${filename}.json`);

    this.t.truthy(await fs.pathExists(filepath), `The referenced ${type} '${value}' must exist at ${filepath}`);
  }

  slugify(value) {
    // This is a simple version and might not work for all cases
    // as the Python slugify method used in the builder is much more advanced
    // @todo: use the same slugify method as the builder
    return value
      .replace(/[^a-z0-9]+/gi, '-') // Replace all sequences of non-alphanumeric characters with a dash
      .replace(/^-+|-+$/g, '') // Trim leading/trailing dashes
      .toLowerCase();
  }
  
  requireTechnicalOfficer() {
    // Check for technical officer information
    this.t.truthy(Array.isArray(this.data.contacts), "must have contacts");
    const contact = this.data.contacts.find(c => c.role === "technical_officer");
    if (contact) {
      this.t.truthy(typeof contact.name === "string" && contact.name.length > 1, "must have name for technical officer");
      this.t.truthy(Array.isArray(contact.emails) && contact.emails.length > 0, "must have email array for technical officer");
      const email = contact.emails[0].value;
      this.t.truthy(typeof email === 'string' && email.length > 1, "must have email value for technical officer");
    }
    else {
      this.t.fail("must have technical officer as contact");
    }
  }
  
  disallowRelatedLinks() {
    const link = this.data.getLinkWithRel('related');
    this.t.truthy(!link, `must NOT have a 'related' link`);
  }
  
  async requireParentLink(path) {
    await this.checkStacLink('parent', path);
  }
  
  async requireRootLink(path) {
    await this.checkStacLink('root', path);
  }
  
  async checkStacLink(type, expectedPath) {
    const link = this.data.getLinkWithRel(type);
    this.t.truthy(link, `must have ${type} link`);
    // @todo: make more robust and make it work with absolute links
    this.t.equal(link.href, expectedPath, `${type} link must point to ${expectedPath}`);
    this.t.equal(link.type, "application/json", `${type} link type must be of type application/json`);

    if (typeof link.title !== 'undefined') {
      await this.checkLinkTitle(link);
    }
  }
  
  requireViaLink() {
    const link = this.data.getLinkWithRel("via");
    this.t.truthy(link, "must have 'via' link");
    // @todo: enable if we can ensure that all links have a HTML media type
    // this.test.equal(link.type, "text/html", "via link type must be of type text/html");
  }

}

module.exports = CustomValidator;
