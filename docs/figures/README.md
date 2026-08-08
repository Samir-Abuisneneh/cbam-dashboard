# Dashboard figures

Captured 8 August 2026 from the results freeze (`results-freeze-2026-08-08`),
after the CBAM benchmark correction. Regenerate with:

```bash
.venv/bin/streamlit run dashboard.py --server.headless true --server.port 8511 &
.venv/bin/python capture_figures.py --port 8511
```

`capture_figures.py` sets the scenario in code rather than by clicking, so the
figures and the numbers reported in `docs/findings_2026-08-08.md` cannot drift
apart. Change the scenario there, not in the UI.

**Scenario captured:** Halifax to Hamburg, hydrogen, CBAM regulatory default
pathway, 2030, medium carbon price, gas carrier, base speed, Suez routing.

| File | Tab | Where it goes |
|---|---|---|
| `dashboard_1_compliance_cost.png` | Compliance cost | Methodology, to show the model is interactive rather than a fixed table |
| `dashboard_2_maritime.png` | Maritime layer only | Appendix. The maritime layer is Gayu's and is reported in her own chapter |
| `dashboard_3_sensitivity.png` | Sensitivity | Findings, alongside the sensitivity ranking CSVs |
| `dashboard_4_pathway_corridor.png` | Which pathway / corridor | **Dissertation and defence video.** The strongest visual, and the one that carries the corridor finding |

The 5 to 10 minute defence video should lead on tab 4. It shows the pathway
ranking and the corridor comparison on one screen, which is the study's headline
in a single frame.

Note the corridor chart in tab 4 is on the `frozen` UK price path, the baseline.
Hydrogen's corridor ordering depends on which path is chosen, so if a figure is
used to support a hydrogen corridor claim, the caption has to name the path. See
`docs/findings_2026-08-08.md` section 2.
