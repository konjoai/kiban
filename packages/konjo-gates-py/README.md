# konjo-gates-py

CI-plane gate orchestrator for Konjo Python and ML repos.

`konjo-gates` reads a repo profile, routes changed files through `lib.diff_scope`, and
runs the kiban-native gates (prose net-new, secrets, the self_test replay eval,
report-only specialist stats) plus the profile's repo-native gates, each wrapped in
`konjo-newonly` so only net-new findings block. It imports the real `lib`/`evals` engine
and reimplements none of it. The CI plane never reads `~/.konjo`.

This package's code lives here, but it is built and shipped as part of the root kiban
distribution, because it imports the sibling engine and a subdirectory-only install
cannot reach those packages without duplicating them.

## Install (in a consuming repo's CI)

```bash
pip install "kiban @ git+https://github.com/konjoai/kiban.git@v0.3.0"
konjo-gates --profile .konjo/profile.yml --base origin/main
```

The self_test gate runs the eval through the deterministic replay backend, so CI needs
no model and no network. See `templates/repo-ci.yml` for the full workflow.
