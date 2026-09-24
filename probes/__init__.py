"""
Probes: one-off scripts that derive a committed number from a live or
committed source, printing their working.

This file exists so the probes are importable as a package by
tests/test_probe_invariants.py, which checks the grouping and matching
helpers directly rather than only through their printed output. The
drift check compares a document against a probe, so when the probe is
wrong the two agree and nothing fails — the invariants are what check
the probe itself.
"""
