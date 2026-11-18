# Open Science Catalogue Metadata

## About Open Science Catalogue

The Open Science Catalogue ([https://opensciencedata.esa.int](https://opensciencedata.esa.int/)) Open Science activity by the European Space Agency (ESA) aiming to enhance the discoverability and use of the various scientific and value-added results (i.e., data, code, documentation) achieved in Earth System Science research activities funded by ESA Earth Observation. The Open Science Catalogue (OSC) provides open access for the scientific community to geoscience products (based on EO data from ESA and non-ESA missions and other geospatial information and models) across the whole spectrum of Earth Science domains.
The OSC adheres to FAIR principles and promotes reproducibility of scientific studies. It makes use of various Open-Source geospatial technologies such as STAC Browser and OpenLayers and tries to contribute back to these projects in terms of software and standardisation.

Discover the [Open Science Catalogue and access products and project's description online](https://opensciencedata.esa.int/).

### Functionalities

- Provide contribution to the ESA EO Open Science framework
- Catalogue of geoscience products, datasets, and resources output by scientific research Projects funded by ESA EO
- Discovery and access for geospatial products
- Unified metadata across heterogeneous sources
- Common dictionary
- Discovery & Access to data + documentation (+ code)
- Open to community curation & contribution
- Synoptic view for EO gap analysis

### This repository

This repository holds metadata for all themes, variables, projects, products, workflows, and experiments discoverable via the Open Science Catalogue frontend. Each update to the metadata is handled via a [Pull Request](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/about-pull-requests). This pull request allows for reviewers to see the changes to be applied in advance and to provide reviews as comments. If appropriate, the changes can be merged with the main branch of the repository.
When a Pull Request is merged, the continuous integration pipeline is run, which triggers the building of a STAC catalog representing the Open Science Catalogue on the Static Catalog component.

To add a new product, the metadata corresponding to dataset to be uploaded to the catalogue must be provided in a [STAC](https://github.com/radiantearth/stac-spec) `.json` file format.
