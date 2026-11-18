# REVISED_METHODS

Methods were not expanded into a new architecture. The revision instead tightens the evidence boundary:

- the alignment snapshot is now serialized in `01_MATCHED_SUPERVISION/data/alignment_snapshot.json`;
- the QID/PID mechanism and language-partitioned Wikidata view are specified in `03_WIKIDATA/WIKIDATA_ALIGNMENT_POLICY.md`;
- exact Clopper--Pearson intervals and paired tests are centralized in `04_STATISTICS/results/STATISTICAL_RESULTS.csv`;
- the GSR statement was corrected: GSR decay with |T| is a denominator effect, not proof of O(1) overall complexity.

The paper now reports the observed number of scanned triples as approximately stable across the evaluated 20-fold scaling range instead of claiming overall O(1) complexity.
