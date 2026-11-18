# FINAL_REVISION_REPORT

## Manuscript changes

- Added compact related-work positioning after the Introduction opening.
- Corrected Pan et al. DOI to `10.1109/TKDE.2024.3352100`.
- Corrected Barnett et al. DOI and pages to `10.1145/3644815.3644945`, 194--199.
- Added verified references for GraphRAG, entity alignment, multilingual retrieval, and evidence-grounded evaluation.
- Replaced the confounded latency table with the unified-workload table.
- Removed the outdated latency figure.
- Updated the real-world RDF paragraph to the expanded Wikidata benchmark and its strict scope limits.
- Replaced all unsupported O(1) complexity wording.
- Updated the ICT implications paragraph to near-constant scanned-triple counts.
- Added the systematic-revision artefacts to the code/data availability statement.

## Format verification

- LaTeX compilation: passed with `-halt-on-error`.
- PDF pages: 6.
- Abstract: approximately 230 words.
- Undefined citations/references: none.
- Visual inspection: pages 4--6 rendered and checked; tables fit within columns; no font-size regression.

## Release status

- Release tag `v2.0` points to commit `37cab3e` containing the revision experiments and artefacts.
- Final paper commit `4c30ec6` points the availability statement to that release.
- Remote `origin/main` is synchronised at the final review commit (`v2.1` or later).

## Remaining author-side actions

- Optional language polish by a native English co-author.
- If a later submission round is allowed, add a denser real cross-graph RDF benchmark and a full multilingual dense latency run.
