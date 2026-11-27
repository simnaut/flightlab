# Vendored client libraries

Loaded directly by the browser through the import map in `../index.html`.
There is no build step: to update a library, replace its file with the one
from the new npm release and update the version here.

| File | Package | Version | Source file in the npm package | License |
|---|---|---|---|---|
| `preact.mjs` | preact | 11.2.0 | `dist/preact.mjs` | MIT |
| `preact-hooks.mjs` | preact | 11.2.0 | `hooks/dist/hooks.mjs` | MIT |
| `htm.mjs` | htm | 3.1.1 | `dist/htm.module.js` | Apache-2.0 |
| `signals-core.mjs` | @preact/signals-core | 1.14.5 | `dist/signals-core.module.js` | MIT |
| `signals.mjs` | @preact/signals | 2.11.4 | `dist/signals.module.js` | MIT |
| `uPlot.mjs`, `uPlot.min.css` | uplot | 1.6.32 | `dist/uPlot.esm.js`, `dist/uPlot.min.css` | MIT |

Source-map comments are stripped. License texts are in `licenses/`.
