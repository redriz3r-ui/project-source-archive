# Terrain Lab north star

**Terrain Lab is a geospatial sandbox and reusable engine.**

Its purpose is to turn authorized geographic sources into structured inputs, validated spatial results, and maps people can inspect. The same computation should work in the browser and without it. Research publications are an initial proving ground for source interpretation and provenance; the engine should remain useful for other geographic problems.

## The product loop

1. **Understand the source.** Identify what a paper or dataset actually provides, including its geographic scope, coordinate system, permissions, uncertainty, and links to original files. Keep study footprints, observations, derived outputs, and model predictions distinct.
2. **Prepare trusted inputs.** Convert permitted data into a documented geographic format. Preserve the original source and every transformation. Reject missing, invalid, or sensitive data when it cannot be handled responsibly.
3. **Compute once.** Run a versioned, validated spatial operation through the reusable engine. Browser controls, scripts, and future transports call the same operation rather than implementing their own calculations.
4. **Inspect the result.** Show the source and derived result in the sandbox, with attribution, provenance, units, and limits visible. A map is a way to examine a result; it is not scientific validation by itself.
5. **Reuse the capability.** Make the operation and its contract available to other applications. Future natural-language and agent interfaces should select allowed operations and pass validated inputs to this engine.

## Current position

The sandbox loads and inspects GeoJSON, GeoTIFF, and hosted PMTiles. Point distance and polygon area have browser-independent contracts and executable workflows. The research catalog has four validated study records. Two sourced polygon datasets—solar arrays and Joshua tree mapped presence cells—have headless area results inspectable on the map. Publication discovery and a [reviewable intake pilot](research/intake/README.md) exist; the pilot has now handled a previously uncurated paper as well as a replayed case. It still requires manually sourced candidate facts and a documented approval decision. Natural-language execution, automated paper parsing, an HTTP API, and an MCP adapter are future work.

## Decision rules for new work

Prioritize a feature when it strengthens at least one part of the product loop **and** keeps the whole loop coherent. Before implementation, specify:

- The user question and geographic source it serves.
- The input, output, and error contract; required coordinate system, units, and limits.
- Which facts are source-verified, caller-supplied, inferred, or unknown.
- How correctness will be checked independently and how the result can be inspected.
- Whether the capability works without MapLibre or a browser, if it performs geographic computation.

Defer work that only adds a map layer without a clear source role or use case, duplicates a spatial algorithm in the UI, or treats an AI-generated claim as verified evidence.

## AI and scientific guardrails

AI or scripts may discover papers, extract candidate metadata, propose dataset mappings, and interpret a user's intent. Those outputs require traceable source references and validation before they enter the trusted catalog or drive a calculation. A paper image is not a coordinate dataset. A model prediction is not an observation. A derived measurement is not proof of the paper's scientific conclusion. The engine should return what it computed, the data it used, and the limits of that answer.

## Evidence of progress

Use observable measures rather than feature count alone:

- Time and manual corrections needed to bring a permitted dataset from source to inspectable layer.
- Completeness of provenance, permissions, geographic role, CRS, and uncertainty fields.
- Independent fixture checks and browser/headless parity for each operation.
- Whether new users can complete a real geographic task and understand the result's limits.
- Repeat use and willingness to pay for a specific application; these remain unproven.

## Near-term sequence

1. Make the **reviewable paper-to-data intake** process repeatable across several new sources. The first new-paper case is mapped, but source retrieval, candidate extraction, and reviewer decisions still need reusable tooling. Resolve source ambiguities before scientific interpretation.
2. Add one **natural-language pilot** that maps a narrow class of requests to existing operation descriptors, then runs the validated engine. Do not create new spatial math inside the language layer.
3. Test the complete loop with outside users in one concrete application. Use their task outcomes to choose the next operation, interface, and investment level.

The north-star check for every milestone is: **Can a person or another system trace a geographic answer from source to calculation to map, and reuse the same computation in another interface?**
