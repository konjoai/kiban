// konjo-gates-rs (phase-1 stub)
//
// The working runner shells out to clippy and cargo-mutants per the consuming repo's
// profile, selecting gates by changed-file scope, and exits nonzero on a blocking
// failure. The CI plane never reads ~/.konjo; the gate logic is this pinned crate.
//
// TODO(phase-1): load profile, run clippy + cargo-mutants, report, exit on failure.

fn main() {
    println!("konjo-gates-rs: phase 1");
}
