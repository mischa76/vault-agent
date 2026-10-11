# The browser walk (WP67 §4)

`walk.mjs` drives the owner's workflow through a real Chromium against a served bundle: create a
project, attach the inputs, run, wait for the checkpoint, answer the owner decisions, accept,
wait for `finished`, check the model graphs, the artefacts and the log. It is evidence for a
recorded run, not a CI test — it needs a server (`vault-agent ui`, or the stub-agent server
from `docs/log.md` 2026-10-11) and, against the real agents, an API key.

```bash
npm i -D playwright && npx playwright install chromium
node e2e/walk.mjs http://127.0.0.1:8765 ../examples/inputs/health_insurance_requirements.md "" ./shots
```
