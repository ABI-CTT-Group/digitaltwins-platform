# digitaltwins-platform

![License](https://img.shields.io/github/license/ABI-CTT-Group/digitaltwins-platform)

![Docker](https://img.shields.io/badge/docker-enabled-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)

![Contributors](https://img.shields.io/github/contributors/ABI-CTT-Group/digitaltwins-platform?color=brightgreen)
![GitHub stars](https://img.shields.io/github/stars/ABI-CTT-Group/digitaltwins-platform?style=social)
![Closed Issues](https://img.shields.io/github/issues-closed/ABI-CTT-Group/digitaltwins-platform)

## Table of contents
* [Introduction](#introduction)
* [Deploying the DigitalTWINS platform](#deploying-the-digitaltwins-platform)
* [Reporting issues](#reporting-issues)
* [Contributing](#contributing)
* [License](#license)
* [Team](#team)
* [Funding](#funding)
* [Acknowledgements](#acknowledgements)


## Introduction
The development of novel medical diagnosis and treatment approaches requires understanding how diseases that operate at the molecular scale influence physiological function at the scale of cells, tissues, organs, and organ systems. The Auckland Bioengineering Institute (ABI) led **Physiome Project aims to establish an integrative “systems medicine” framework based on personalised computational modelling** to link information encoded in the genome to organism-wide physiological function and dysfunction in disease. The **[12 LABOURS project](https://www.auckland.ac.nz/en/abi/our-research/research-groups-themes/12-Labours.html) aims to extend and apply the developments of the Physiome Project to clinical and home-based healthcare applications**.

As part of the 12 LABOURS project, we are **building a DigitalTWINS platform to provide common infrastructure**:
* A **data catalogue** that describes what data is available, what it can be used for, and how to request it.
* A **harmonised data repository** that provides access control to primary and derived data (waveforms, medical images, electronic health records, measurements from remote monitoring devices such as wearables and implantables etc), tools, and workflows that are stored in the SPARC Dataset Structure (SDS). More information about SDS datasets can be found on the [SPARC project's documentation](https://docs.sparc.science/docs/overview-of-sparc-dataset-format). The use of SDS datasets in the 12 LABOURS DigitaTWINS platform is described in the following [presentation](https://docs.google.com/file/d/1zZ3-C17lPIgtRp6bnkSwvKacaTA66GVR/edit?usp=docslist_api&filetype=mspresentation).
* **Describe computational physiology workflows in a standardised language** (including workflows for knowledge discovery, clinical translation, or education, etc), and **run and monitor their progress**.
* **Securely access electronic health records from health systems** (WIP).
* **Securely link data from remote monitoring devices** such as wearables and implantables into computational physiology workflows.
* A **web portal** to enable different researchers, including researchers, clinicians, patients, industry, and the public, to interact with the platform.
* **Guidelines for data management**.
* **Guidelines for clinical translation of computational physiology workflows** and digital twins via commercialisation
* **Unified ethics application templates** that aim to maximise data reusability and linking to enable our vision for creating integrated and personalised digital twins.

These efforts are aimed at **supporting an ecosystem** to:
* **Make research outcomes FAIR** (Findable, Accessible, Interoperable, and Reusable).
* Enable **reproducible science**.
* **Meet data sovereignty requirements**.
* **Support clinical translation via commercialisation** by enabling researchers to conduct clinical trials more efficiently to demonstrate the efficacy of their computational physiology workflows. 
* Provide a **foundation for integrating research developments** across different research groups for assembling more comprehensive computational physiology/digital twin workflows.

**If you find the DigitalTWINS platform useful, please add a GitHub Star to support developments!**

## Deploying the DigitalTWINS platform

See [deploying the DigitalTWINS platform](docs/deploying.md)

## Onboarding projects and workflows

See [onboarding projects and workflows](docs/onboarding.md)

## Reporting issues
To report an issue or suggest a new feature, please use the [issues page](https://github.com/ABI-CTT-Group/digitaltwins-platform/issues). Issue templates are provided to allow users to report bugs, and documentation or feature requests. Please check existing issues before submitting a new one.

## Contributing
Fork this repository and submit a pull request to contribute. Before doing so, please read our [Code of Conduct](https://github.com/ABI-CTT-Group/digitaltwins-platform/blob/master/CODE_OF_CONDUCT.md) and [Contributing Guidelines](https://github.com/ABI-CTT-Group/digitaltwins-api/blob/master/CONTRIBUTING.md). Pull request templates are provided to help developers describe their contribution, mention the issues related to the pull request, and describe their testing environment. 

## License
The DigitalTWINS platform API is fully open source and distributed under the very permissive Apache License 2.0. See [LICENSE](https://github.com/ABI-CTT-Group/digitaltwins-platform/blob/main/LICENSE) for more information.

## Team

## Funding
This software was funded by the [New Zealand Ministry of Business Innovation and Employment’s Catalyst: Strategic fund](https://www.mbie.govt.nz/science-and-technology/science-and-innovation/funding-information-and-opportunities/investment-funds/catalyst-fund/funded-projects/catalyst-strategic-auckland-bioengineering-institute-12-labours-project/). This research is also supported by the use of the Nectar Research Cloud, a collaborative Australian research platform supported by the National Collaborative Research Infrastructure Strategy-funded ARDC.

## Acknowledgements
We gratefully acknowledge the valuable contributions from:
- University of Auckland
  - Auckland Bioengineering Institute (ABI) Clinical Translational Technologies Group (CTT)
  - ABI 12 LABOURS project
  - ABI Breast Biomechanics Research Group (BBRG)
  - Infrastructure and technical support from the Centre for eResearch (including Anita Kean)
- New Zealand eScience Infrastructure (NeSI)
  - Nathalie Giraudon, Claire Rye, Jun Huh, and Nick Jones
- Gen3 team at the Centre for Translational Data Science at the University of Chicago
- Members of the SPARC Data and Resource Center (DRC).

<img src='https://raw.githubusercontent.com/ABI-CTT-Group/digitaltwins-api/main/docs/acknowledgements.jpg' width='500' alt="acknowledgements.jpg">
