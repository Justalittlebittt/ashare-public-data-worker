# A-share public data worker

Standalone collection of **candidate-only** daily CSI300 and STAR50 closes from public Eastmoney endpoints. This repository contains no private AI Core EVID research code or secrets.

Workflow runs offline unit tests, then fetches closes and uploads raw CSV plus SHA-256 manifest as a short-lived artifact. Candidate data are NOT source-admitted, PIT-verified, or trading-authorized.
