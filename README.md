# open-science-catalog-metadata

## About Open Science Catalog

The Open Science Data Catalog([https://opensciencedata.esa.int](https://opensciencedata.esa.int/)) is an ESA Open Science activity aiming to provide enhance the discoverability and use of the various scientific and value-added results (i.e. data, code, documentation) achieved in Earth System Science research activities funded by ESA Earth Observation. The Open Science Data Catalog provides open access for the scientific community to geoscience products (based on EO data from ESA and non-ESA missions and other geospatial information and models) across the whole spectrum of Earth Science domains. 
The Open Science Data Catalog adheres to FAIR principles and promotes reproducibility of scientific studies. The Open Science Data Catalog makes use of various Open-Source geospatial technologies such as pycsw, PySTAC, and OpenLayers and tries to contribute back to these projects in terms of software and standardisation.

Discover Open Science Data Catalog and access products and project's description at[: Open Science Data Catalog](https://opensciencedata.esa.int/).

Open Science Data Catalog documentation contains:

- The User Guide - Starting point for New Users and Contributors
- Release Notes
- Operator's Guide

### Functionalities

- Provide contribution to the ESA EO Open Science framework
- Catalogue of geoscience products, datasets and resources output by scientific research Projects funded by ESA EO
- Discovery and access for geospatial products
- Unified metadata across heterogeneous sources
- Common dictionary
- Discovery & Access to data + documentation (+ code)
- Open to community curation & contribution
- Synoptic view for EO gap analysis

### This repository 

This repository holds metadata all themes, variables, projects and products discoverable by Open Science Catalog Frontend. Each update to metadata is handled via [Pull Request](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/about-pull-requests). This pull request allows for reviewers to see the changes to be applied in advance and to provide reviews as comments. If appropriate, the changes can be merged with the main branch of the repository. 
When a Pull Request is merged, the continuous integration pipeline is run, which triggers the building of a STAC catalog representing the Open Science Data Catalogue on the Static Catalog component.

The design document describes the architecture of Open Science Catalog and its design: [https://docs.google.com/document/d/144d-ACMG\_AzWtP6HohR1A7ltHGNY6NkhWmH9EyJb\_vA/](https://docs.google.com/document/d/144d-ACMG_AzWtP6HohR1A7ltHGNY6NkhWmH9EyJb_vA/)

To add a new product, the metadata corresponding to data set to be uploaded to the catalogue must be provided in a [STAC](https://github.com/radiantearth/stac-spec) .json file format. 
