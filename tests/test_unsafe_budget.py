"""Tests for the unsafe-budget diff scanner (lib/unsafe_budget)."""

from __future__ import annotations

from lib import unsafe_budget

_ADD_UNSAFE = """@@ -1,2 +1,4 @@
 fn f() {
+    unsafe {
+        ptr.read();
+    }
 }
"""

_ADD_UNSAFE_WITH_SAFETY = """@@ -1,2 +1,5 @@
 fn f() {
+    // SAFETY: ptr is valid and aligned for this call
+    unsafe {
+        ptr.read();
+    }
 }
"""

_REMOVE_UNSAFE = """@@ -1,4 +1,2 @@
 fn f() {
-    unsafe {
-        ptr.read();
-    }
 }
"""

_UNSAFE_IMPL = """@@ -1,1 +1,2 @@
 struct S;
+unsafe impl Send for S {}
"""


def test_net_new_unjustified_unsafe_fails() -> None:
    b = unsafe_budget.scan(_ADD_UNSAFE)
    assert b.added_unjustified == 1 and b.removed == 0
    assert b.fails


def test_safety_comment_justifies_unsafe() -> None:
    b = unsafe_budget.scan(_ADD_UNSAFE_WITH_SAFETY)
    assert b.added_unjustified == 0
    assert not b.fails


def test_removing_unsafe_lowers_budget() -> None:
    b = unsafe_budget.scan(_REMOVE_UNSAFE)
    assert b.removed == 1 and b.added_unjustified == 0
    assert not b.fails


def test_swapping_unsafe_for_unsafe_is_net_zero() -> None:
    # Remove one unjustified unsafe and add another unjustified one: net zero, no fail.
    diff = _REMOVE_UNSAFE + _ADD_UNSAFE
    b = unsafe_budget.scan(diff)
    assert b.net == 0 and not b.fails


def test_unsafe_impl_without_safety_is_a_finding() -> None:
    b = unsafe_budget.scan(_UNSAFE_IMPL)
    assert b.added_unjustified == 1 and b.fails


def test_identifier_named_unsafe_does_not_trip() -> None:
    diff = "@@ -1 +1,2 @@\n fn f() {\n+    let unsafe_count = 0;\n"
    b = unsafe_budget.scan(diff)
    assert b.added_unjustified == 0 and not b.fails
