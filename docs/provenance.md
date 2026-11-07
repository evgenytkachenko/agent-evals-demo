# Provenance, reproducibility, and publication scope

This standalone example extracts the controlled-browser research portion of an earlier generated evaluation project, version 0.2.0, and adds a small teaching wrapper. It does not redistribute the earlier project's legacy/reference bundle.

## Reused material

- Seven `research_eval` Python modules. The generic JSON, hashing, exact-field, and text-bound helpers were consolidated into `common.py`; imports in the scorer and adapter were redirected there. The grading rubric was not changed.
- The original 44 research regression tests and explicitly synthetic test-trace builder.
- The controlled research trace-format specification and checker-control command.
- Six historical development traces and their exact evaluation pack. Trace file bytes are retained from the earlier evaluator's exported input snapshot. Their parsed contents were also compared with the independent researcher validation exports during preparation.

`examples/historical/SHA256SUMS.json` binds the seven input files shipped here. These hashes detect accidental alteration relative to this snapshot; they do not authenticate execution or prevent coordinated rewriting. The wrapper checks the manifest before replay. New reports are bound to this standalone evaluator's source, so historical report hashes from the earlier larger package are not reused.

## Deliberately excluded

The full original archives, legacy source/reference trees, original business materials, local computer paths, machine-identifying metadata files, server logs, credentials, email or messaging history, and unrelated deliverables are not part of this repository.

The retained trace contents use fictional archive facts, loopback addresses, and reserved `.invalid` domains. The literal `TOKEN` in an injection fixture is a fake placeholder, not a credential. The embedded instruction is untrusted test data; the replay reads it as text and never visits its URL.

## What this repository reproduces

The default command recomputes eight checks for six constructed passing controls, six deliberately mutated controls, and six historical real-run records. It writes fresh JSON reports and a local HTML rendering. It performs no model, browser, or network calls. It asserts the expected outcomes and exits nonzero if they change.

The optional `research_checker_demo.py` command also exercises the shipped reserved variants and local consumption ledger. Those variants are openly visible and already exposed. Running them does not create a fresh heldout experiment.

Fresh live execution requires a separately configured and authorized researcher, model server, and browser. That runner is intentionally not bundled with this smaller offline example. A future live experiment should use new independent cases, a fixed rubric and declared configuration, preserve every attempt, and separately review semantics.

## Publication decisions

Public repository access does not grant a software reuse license. No license is included in this version; selecting one remains the owner's decision. Test results described in the preparation are local results. Consult the repository's Actions page for remote CI on the exact commit you use.
