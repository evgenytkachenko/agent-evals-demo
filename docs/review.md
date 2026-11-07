# Verification scope

The standalone package retains the original 44 research regression tests and adds showcase-specific tests for historical outcome preservation, no-network execution, output overwrite refusal, escaped HTML, and strict JSON parsing.

Use `python3 -m unittest discover -s tests -v` to obtain the current local result. The GitHub workflow is configured separately; its status is not known until it runs on a published commit.

Automated source review and regression tests are not human approval of case semantics, independent execution attestation, security certification, or production approval. The original six-case trial remains 1/6 under the unchanged strict rubric.
