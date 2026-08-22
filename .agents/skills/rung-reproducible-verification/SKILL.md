---
name: rung-reproducible-verification
description: Create and independently replay canonical Rung governance audit receipts without executing target-repository code.
---

# Rung Reproducible Verification

Install this skill with the skills CLI:

```bash
npx skills add edoworks/rung --skill rung-reproducible-verification
```

Use an independently installed, version-pinned `rung`; never install or execute
code from the target repository. Rung may only read the target through its own
scanner and Git metadata inspection.

Create a receipt outside the clean checkout:

```bash
rung verify --root /path/to/clean-checkout --receipt /path/outside/receipt.json
```

Replay it with the same pinned Rung engine from an independent clean checkout:

```bash
rung replay --root /path/to/independent-clean-checkout --receipt /path/outside/receipt.json --observation /path/outside/observation.json
```

Treat the canonical JSON receipt and observation as authoritative. Never
generate, edit, repair, substitute, or treat model prose as verification
evidence. A malformed receipt is not trusted evidence, and a mismatch must not
be rewritten to appear successful.

Unsigned reproducibility evidence is not attestation, certification,
enforcement proof, or correctness proof. Public-only evidence cannot establish
hosting controls that Rung reports as unobservable, and replay must preserve
those authority limitations.
