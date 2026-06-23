# konjo-gates-py

CI-plane gate runner for Konjo Python and ML repos. **Phase-1 stub.**

This is the pip-installable package a consuming repo's CI pins and installs. It runs the
repo's profile gates in CI using the same `lib/` engine kiban ships. The CI plane is
self-contained: it never reads `~/.konjo`. The gate logic is the pinned package.

## Install (in a consuming repo's CI)

```bash
pip install "konjo-gates-py @ git+https://github.com/konjoai/kiban.git@v0.1.0#subdirectory=packages/konjo-gates-py"
konjo-gates --profile .konjo/profile.yml
```

## Status

The `konjo-gates` entry point currently prints `phase 1` and exits 0. The working runner
(profile load, scope-based gate selection, prove baseline, meta-gate self-test) lands in
Phase 1.
