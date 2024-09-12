# Instructions

To run validation you need the following folders:

- `/.github/workflows/validation`
- `/schemas`

The following commands can run the validation.

Switch to this folder (if not done yet):

```bash
cd .github/workflows/validation
```

Install dependencies:

```bash
npm ci
```

Set the hosted location of the schemas.
The URL has usually the form `https://raw.githubusercontent.com/{github org}/{github repo}/{github branch}`.
For example:

- Windows PowerShell: `$env:GITHUB_SCHEMA_URI="https://raw.githubusercontent.com/EOEPCA/open-science-catalog-metadata-testing/ui-schemas"`
- Linux/MacOS: `export GITHUB_SCHEMA_URI="https://raw.githubusercontent.com/EOEPCA/open-science-catalog-metadata-testing/ui-schemas"`

Run the validator:

```bash
npm test
```
