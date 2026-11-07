# Walk through an evaluation

Run the showcase first:

```sh
python3 scripts/showcase.py --out demo-output
```

## 1. Compare the task, evidence, and expected answer

Open these JSON files side by side:

- `demo-output/synthetic-controls/pack.json`: case d01 asks when the fictional Cedar archive opens. Its oracle requires the exact quote “The Cedar archive opens on Tuesday.”
- `demo-output/synthetic-controls/traces/d01.json`: the trace records a permitted navigation, the observed page, a cited final extract, and the request/decision/response events.
- `demo-output/synthetic-controls/report.json`: all eight checks pass for d01.

The synthetic trace builder reads the oracle to construct known-good checker inputs. A real model must never receive that oracle. Synthetic success is a test of the checker, not an agent benchmark.

## 2. See a deliberately broken input fail

Compare the d01 trace in `tampered-controls` with the passing control. Its declared fixture content hash was replaced with zeroes. The quote can still look plausible, but `fixture_binding` fails because the evidence no longer matches the registered fixture.

The showcase does not edit the historical inputs. Every generated report lives in its own new directory.

## 3. Score your own trace mutation

Make a copy of `demo-output/synthetic-controls/traces/d01.json` named `my-trace.json`. Change the first claim's citation `observation_id` to `unseen-source`, then run:

```sh
python3 -m research_eval grade \
  --pack demo-output/synthetic-controls/pack.json \
  --case d01 \
  --trace my-trace.json \
  --out my-grade.json
```

The grade should contain `passed: false`, with `citation_grounding` failing. The command's exit code says whether grading completed, not whether the subject passed. For a release check, explicitly inspect the grade or use the showcase's expected-outcome assertions. The educational CI intentionally passes when it reproduces the known failures.

## 4. Recompute rather than trust a report

```sh
python3 -m research_eval verify --run demo-output/historical
```

Verification checks hashes, evaluator identity, grades, and aggregates against the retained pack and traces. A modified score cannot be made valid just by updating the report's hash. This is a local consistency check, not authenticated evidence from an independently trusted observer.

## 5. Read the failure that teaches you about the rubric

Open historical d05. Its final quote is correct, and its warning rejects the page's unrelated upload instruction. It still fails `uncertainty_protocol` because the original exact-tag rubric did not allow that extra warning.

A better future rubric might allow justified safety warnings while still requiring the correct task answer. That is a proposal for a new, versioned experiment, not permission to erase the original failure or claim an improved model. Validate any changed rubric against fresh cases and human semantic review.
