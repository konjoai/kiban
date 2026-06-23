# konjo-gates-rs

CI-plane gate runner for Konjo Rust repos. **Phase-1 stub (spec only).**

The working crate shells out to `clippy` and `cargo-mutants` per the consuming repo's
profile, selecting gates by changed-file scope, and exits nonzero on a blocking failure.
The CI plane is self-contained and never reads `~/.konjo`; the gate logic is this pinned
crate.

## Planned use (in a consuming repo's CI)

```bash
cargo install --git https://github.com/konjoai/kiban.git --tag v0.1.0 konjo-gates-rs
konjo-gates-rs --profile .konjo/profile.yml
```

## Status

`main` prints `phase 1`. The working runner lands in Phase 1.
