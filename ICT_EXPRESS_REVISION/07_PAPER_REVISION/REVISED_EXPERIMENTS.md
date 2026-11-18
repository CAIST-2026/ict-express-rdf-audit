# REVISED_EXPERIMENTS

Changes made from executed revision experiments:

1. **Unified latency.** The old mixed-workload latency table was replaced by Table 4 using the same 24 qids for all executable systems. Accepted numbers: full system mean 8,379 ms / median 8,584 ms; real SPARQL mean 290 ms / median 157 ms; translit mean 0.09 ms. Dense e5 was excluded from the latency run because torch/transformers were unavailable; this is stated explicitly.
2. **Wikidata.** The transfer check now uses 184 offline queries derived from saved authentic triples (114 one-hop, 70 cross-lingual). Cross-lingual matched ac1 = 0.700 overall, exactly matching 49/70 train-pool alignment coverage; held-out non-oracle ac1 = 0/21.
3. **Statistics.** Holm-corrected wording remains: all accuracy contrasts p < 1e-3; fair-baseline contrasts p ≤ 3.2e-8. The 0/20 stratum is always reported with exact CI [0, 0.168].
4. **Figures.** The outdated latency figure was removed; table-based reporting is now consistent with the unified workload. Other figures were unchanged because their source experiments were unchanged.
