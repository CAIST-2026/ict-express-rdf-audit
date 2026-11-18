# Change log: operative manuscript

## Files changed

- `ict_express_submission/paper/main.tex`
- `ict_express_submission/paper/main.pdf`
- `ict_express_submission/tables/table3_latency.tex`
- New revision package copied to `ict_express_submission/ICT_EXPRESS_REVISION/`

## Substantive changes

1. Added compact related-work paragraph after Introduction paragraph 1.
2. Corrected Pan et al. DOI to `10.1109/TKDE.2024.3352100`.
3. Corrected Barnett et al. DOI to `10.1145/3644815.3644945` and pages to 194--199.
4. Added five verified bibliography entries for related-work positioning.
5. Replaced mixed-workload latency table with the accepted unified 24-query workload.
6. Rewrote cost paragraph: full-system mean 8,379 ms, median 8,584 ms; real SPARQL mean 290 ms, median 157 ms.
7. Removed outdated latency figure.
8. Replaced O(1) complexity claim with denominator-effect explanation and approximately stable scanned-triple statement.
9. Updated Wikidata transfer description from 55 to 184 queries and added 0.700 matched coverage result.
10. Updated ICT implications wording from “O(1) access ratio” to “near-constant scanned-triple counts”.
11. Updated code availability to describe the systematic-revision package and release commit `37cab3e` (tag `v2.0`).

## Verification

- `latexmk -pdf -halt-on-error`: passed.
- PDF pages: 6.
- Undefined citations/references: none.
- Visual check: pages 4--6 rendered and inspected; no font-size regression or table overflow observed.
