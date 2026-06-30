"""The long-run pack: the checkpoint/resume protocol and its helper.

A run long enough to be interrupted must resume from a checkpoint with minimal loss. This
pack ships `konjo_longrun`, the small helper a benchmark or training script adopts in about
five lines, on the same `jsonl_store` substrate the Ledger uses. The `gate_longrun` CI gate
(in the orchestrator) statically checks that a long-run script wires the resume contract.
"""
