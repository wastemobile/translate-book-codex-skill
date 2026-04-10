# Third-Party Licenses

This repository depends on third-party software and source data for some parts of the translation workflow.

This file is a project-level record of third-party license information that should remain easy to find when reviewing, packaging, or redistributing this project.

## OpenCC-Related Components

This project uses OpenCC-related tooling for `zh-TW` regional wording normalization during the audit stage.

Current Python dependency used by this repository:

- `opencc-python-reimplemented`

Referenced upstream project:

- OpenCC
- Repository: https://github.com/BYVoid/OpenCC
- License: Apache License 2.0
- License URL: https://www.apache.org/licenses/LICENSE-2.0

## Redistribution Note

If you redistribute packaged environments, release artifacts, or other builds that include OpenCC-related components, keep the applicable third-party license text and any required notices with that distribution.

This file is informational and does not replace the original license terms of any third-party dependency.

## NAER Term Data

This repository also supports importing terminology datasets published by the National Academy for Educational Research (NAER) through 樂詞網.

Referenced source:

- National Academy for Educational Research (NAER) Term Search / 樂詞網
- Site: https://terms.naer.edu.tw/
- Open data statement: https://terms.naer.edu.tw/mysite/about/2/

Summary of relevant usage conditions from the published open data statement:

- the site states that covered materials are provided for public use on a no-fee, non-exclusive basis
- the statement says users may reproduce, adapt, edit, publicly transmit, and build derivative works from covered materials
- use should include source attribution
- some materials may be excluded or separately restricted if specially identified or owned by third parties
- use should not falsely imply endorsement by the publishing agency

If you redistribute imported NAER-derived datasets, generated glossary databases, or packaged artifacts containing such data, include source attribution and review whether any dataset-specific or third-party restrictions apply.

This summary is informational only. The original published statement on the source site remains authoritative.
