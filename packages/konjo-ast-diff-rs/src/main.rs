//! konjo-ast-diff: before/after AST delta for one Rust source file.
//!
//! Reads a JSON object from stdin: `{"before": "<source or null for a new file>",
//! "after": "<source or null for a deleted file>"}`. Prints a JSON `Delta` to stdout.
//! A parse failure on either side is reported in `parse_error`, not silently swallowed --
//! the caller (Phase 0 backfill) must count a file it could not parse as "unusable for
//! this measurement," not as zero delta.
//!
//! Item matching for body/signature classification is by qualified name
//! (`Mod::Type::method`, dotted through nested `mod` and `impl` blocks). A function that
//! appears only in `after` (or only in `before`) counts as a signature change from/to
//! nothing -- there is no "identical" baseline to compare it against, and folding it into
//! "identical" would hide added/removed functions from the count entirely.

use std::collections::HashMap;
use std::io::{self, Read};

use serde::{Deserialize, Serialize};
use syn::visit::{self, Visit};
use syn::{Attribute, Expr, File, ImplItem, Item, Signature};

#[derive(Deserialize)]
struct Input {
    before: Option<String>,
    after: Option<String>,
}

/// `--items` mode input: one source file, no before/after diffing.
#[derive(Deserialize)]
struct ItemsInput {
    source: String,
}

/// `--items` mode output: one entry per fn/method, real line spans, no delta.
/// Section 1's uncovered-item extraction calls this per touched file to map
/// uncovered lines to their enclosing item -- see `lib/uncovered_items.py`.
#[derive(Serialize)]
struct ItemSpanOut {
    qualified_name: String,
    start_line: usize,
    end_line: usize,
}

#[derive(Serialize)]
struct ItemsOutput {
    parse_error: Option<String>,
    items: Vec<ItemSpanOut>,
}

fn run_items_mode() {
    let mut buf = String::new();
    if io::stdin().read_to_string(&mut buf).is_err() {
        eprintln!("konjo-ast-diff --items: failed to read stdin");
        std::process::exit(2);
    }
    let input: ItemsInput = match serde_json::from_str(&buf) {
        Ok(v) => v,
        Err(e) => {
            eprintln!("konjo-ast-diff --items: invalid input JSON: {e}");
            std::process::exit(2);
        }
    };
    let parsed = match syn::parse_file(&input.source) {
        Ok(f) => f,
        Err(e) => {
            let out = ItemsOutput { parse_error: Some(e.to_string()), items: vec![] };
            println!("{}", serde_json::to_string(&out).unwrap());
            return;
        }
    };
    let mut sigs = Vec::new();
    collect_items(&parsed.items, "", &mut sigs);
    let items = sigs
        .into_iter()
        .map(|s| ItemSpanOut {
            qualified_name: s.qualified_name,
            start_line: s.start_line,
            end_line: s.end_line,
        })
        .collect();
    let out = ItemsOutput { parse_error: None, items };
    println!("{}", serde_json::to_string(&out).unwrap());
}

#[derive(Serialize, Default)]
struct Delta {
    parse_error: Option<String>,
    identical: usize,
    bodies_changed: usize,
    signatures_changed: usize,
    new_unsafe: i64,
    new_unwrap: i64,
    new_attrs_allow: i64,
    new_attrs_ignore: i64,
    removed_asserts: i64,
    removed_test_fns: i64,
    /// Known trigger-surface call paths (plan section 2.1), net-new occurrences only.
    /// Category -> count. Populated only for categories this detector actually covers;
    /// `auth` and `path_construction` are NOT covered (no syn-safe call-path signature
    /// exists for them without an unacceptable false-positive rate) -- absence from this
    /// map means "not measured," not "zero," and the backfill caller must say so.
    trigger_surface: HashMap<String, i64>,
}

/// Known call/macro paths for trigger-surface categories that a syn call-path match can
/// detect honestly (no semantic/dataflow analysis attempted). Each entry is
/// (category, path segment to match against the last 1-2 segments of a call path or
/// macro name). Intentionally conservative: a miss (false negative) is preferred to a
/// guess (false positive) here, per the plan's "not regex guesses" instruction applied
/// to syn matching too -- these are exact known API names, not fuzzy text.
const TRIGGER_PATHS: &[(&str, &[&str])] = &[
    ("subprocess", &["Command::new", "process::Command"]),
    ("deserialization", &[
        "serde_json::from_str", "serde_json::from_slice", "serde_json::from_reader",
        "serde_yaml::from_str", "toml::from_str", "bincode::deserialize",
    ]),
    ("network_egress", &[
        "reqwest::Client", "reqwest::get", "hyper::Client", "TcpStream::connect",
        "tokio::net::TcpStream",
    ]),
    ("sql", &["sqlx::query", "sqlx::query_as", "sqlx::query_scalar"]),
    ("ffi", &["extern\"C\""]),
    ("concurrency", &[
        "tokio::spawn", "thread::spawn", "std::thread::spawn", "Mutex::new", "RwLock::new",
    ]),
    ("crypto", &[
        "ring::", "rustls::", "sha2::", "sha1::", "aes::", "rsa::", "ed25519_dalek::",
        "hmac::",
    ]),
];

struct ItemSig {
    qualified_name: String,
    signature_tokens: String,
    body_tokens: String,
    /// 1-indexed, inclusive, covering the whole item (attrs through closing brace).
    /// Populated via `syn`'s `Spanned` trait, which needs proc-macro2's
    /// `span-locations` feature to return real line numbers outside a proc-macro
    /// (confirmed live, Sprint P2b PF-1b -- see this crate's Cargo.toml comment).
    start_line: usize,
    end_line: usize,
}

fn sig_tokens(sig: &Signature) -> String {
    quote::quote!(#sig).to_string()
}

fn collect_items(items: &[Item], prefix: &str, out: &mut Vec<ItemSig>) {
    use syn::spanned::Spanned;
    for item in items {
        match item {
            Item::Fn(f) => {
                let stmts = &f.block.stmts;
                let span = f.span();
                out.push(ItemSig {
                    qualified_name: format!("{prefix}{}", f.sig.ident),
                    signature_tokens: sig_tokens(&f.sig),
                    body_tokens: quote::quote!(#(#stmts)*).to_string(),
                    start_line: span.start().line,
                    end_line: span.end().line,
                });
            }
            Item::Impl(imp) => {
                let ty = &*imp.self_ty;
                let ty_name = quote::quote!(#ty).to_string().replace(' ', "");
                for ii in &imp.items {
                    if let ImplItem::Fn(m) = ii {
                        let stmts = &m.block.stmts;
                        let span = m.span();
                        out.push(ItemSig {
                            qualified_name: format!("{prefix}{ty_name}::{}", m.sig.ident),
                            signature_tokens: sig_tokens(&m.sig),
                            body_tokens: quote::quote!(#(#stmts)*).to_string(),
                            start_line: span.start().line,
                            end_line: span.end().line,
                        });
                    }
                }
            }
            Item::Mod(m) => {
                if let Some((_, inner)) = &m.content {
                    let new_prefix = format!("{prefix}{}::", m.ident);
                    collect_items(inner, &new_prefix, out);
                }
            }
            _ => {}
        }
    }
}

fn path_string(path: &syn::Path) -> String {
    path.segments.iter().map(|s| s.ident.to_string()).collect::<Vec<_>>().join("::")
}

#[derive(Default)]
struct TriggerVisitor {
    unsafe_count: i64,
    unwrap_count: i64,
    attrs_allow: i64,
    attrs_ignore: i64,
    assert_count: i64,
    test_fn_count: i64,
    trigger_surface: HashMap<String, i64>,
}

impl TriggerVisitor {
    fn bump_trigger(&mut self, category: &str) {
        *self.trigger_surface.entry(category.to_string()).or_insert(0) += 1;
    }

    fn match_call_path(&mut self, joined: &str) {
        for (category, needles) in TRIGGER_PATHS {
            if needles.iter().any(|n| joined == *n || joined.ends_with(n) || joined.starts_with(n)) {
                self.bump_trigger(category);
            }
        }
    }
}

impl<'ast> Visit<'ast> for TriggerVisitor {
    fn visit_expr(&mut self, expr: &'ast Expr) {
        match expr {
            Expr::Unsafe(_) => self.unsafe_count += 1,
            Expr::MethodCall(mc) => {
                let name = mc.method.to_string();
                if name == "unwrap" || name == "expect" {
                    self.unwrap_count += 1;
                }
            }
            Expr::Call(call) => {
                if let Expr::Path(p) = &*call.func {
                    self.match_call_path(&path_string(&p.path));
                }
            }
            _ => {}
        }
        visit::visit_expr(self, expr);
    }

    /// Catches macro invocations regardless of syntactic position: `Expr::Macro`
    /// (`let x = assert!(...)` -- unusual but legal), `Stmt::Macro` (the normal
    /// `assert!(true);` statement form), and macros nested inside either. Matching only
    /// `Expr::Macro` in `visit_expr` would miss the statement form entirely, since
    /// `assert!(true);` parses as `Stmt::Macro`, not `Stmt::Expr(Expr::Macro(..))`.
    fn visit_macro(&mut self, mac: &'ast syn::Macro) {
        let name = path_string(&mac.path);
        if matches!(name.as_str(), "assert" | "assert_eq" | "assert_ne" | "debug_assert"
            | "debug_assert_eq" | "debug_assert_ne")
        {
            self.assert_count += 1;
        }
        visit::visit_macro(self, mac);
    }

    fn visit_signature(&mut self, sig: &'ast Signature) {
        if sig.unsafety.is_some() {
            self.unsafe_count += 1;
        }
        visit::visit_signature(self, sig);
    }

    fn visit_item_fn(&mut self, f: &'ast syn::ItemFn) {
        if f.attrs.iter().any(|a| {
            let s = path_string(a.path());
            s == "test" || s.ends_with("::test")
        }) {
            self.test_fn_count += 1;
        }
        visit::visit_item_fn(self, f);
    }

    fn visit_item_impl(&mut self, i: &'ast syn::ItemImpl) {
        if i.unsafety.is_some() {
            self.unsafe_count += 1;
        }
        visit::visit_item_impl(self, i);
    }

    fn visit_item_trait(&mut self, i: &'ast syn::ItemTrait) {
        if i.unsafety.is_some() {
            self.unsafe_count += 1;
        }
        visit::visit_item_trait(self, i);
    }

    fn visit_item_foreign_mod(&mut self, i: &'ast syn::ItemForeignMod) {
        self.bump_trigger("ffi");
        visit::visit_item_foreign_mod(self, i);
    }

    fn visit_attribute(&mut self, attr: &'ast Attribute) {
        if attr.path().is_ident("allow") {
            self.attrs_allow += 1;
        }
        if attr.path().is_ident("ignore") {
            self.attrs_ignore += 1;
        }
        visit::visit_attribute(self, attr);
    }
}

fn scan_triggers(file: &File) -> TriggerVisitor {
    let mut v = TriggerVisitor::default();
    v.visit_file(file);
    v
}

fn main() {
    // `--items` is a separate mode (single-file item+span listing, no before/after
    // diffing) rather than a second binary: section 1 needs exactly the item-span
    // extraction `collect_items` already does, and the plan's own instruction is to
    // extend this crate rather than write a second walker. Default (no flag) behavior
    // is unchanged, so the existing `lib/ast_diff.py` caller needs no changes.
    if std::env::args().nth(1).as_deref() == Some("--items") {
        run_items_mode();
        return;
    }

    let mut buf = String::new();
    if io::stdin().read_to_string(&mut buf).is_err() {
        eprintln!("konjo-ast-diff: failed to read stdin");
        std::process::exit(2);
    }
    let input: Input = match serde_json::from_str(&buf) {
        Ok(v) => v,
        Err(e) => {
            eprintln!("konjo-ast-diff: invalid input JSON: {e}");
            std::process::exit(2);
        }
    };

    let mut delta = Delta::default();

    let before_src = input.before.unwrap_or_default();
    let after_src = input.after.unwrap_or_default();

    let before_parsed = syn::parse_file(&before_src);
    let after_parsed = syn::parse_file(&after_src);

    let (before_file, after_file) = match (before_parsed, after_parsed) {
        (Ok(b), Ok(a)) => (b, a),
        (Err(e), _) => {
            delta.parse_error = Some(format!("before: {e}"));
            println!("{}", serde_json::to_string(&delta).unwrap());
            return;
        }
        (_, Err(e)) => {
            delta.parse_error = Some(format!("after: {e}"));
            println!("{}", serde_json::to_string(&delta).unwrap());
            return;
        }
    };

    let mut before_items = Vec::new();
    collect_items(&before_file.items, "", &mut before_items);
    let mut after_items = Vec::new();
    collect_items(&after_file.items, "", &mut after_items);

    let before_map: std::collections::HashMap<_, _> =
        before_items.iter().map(|i| (i.qualified_name.clone(), i)).collect();
    let after_map: std::collections::HashMap<_, _> =
        after_items.iter().map(|i| (i.qualified_name.clone(), i)).collect();

    for (name, a) in &after_map {
        match before_map.get(name) {
            None => delta.signatures_changed += 1, // new item: signature change from nothing
            Some(b) => {
                if b.signature_tokens != a.signature_tokens {
                    delta.signatures_changed += 1;
                } else if b.body_tokens != a.body_tokens {
                    delta.bodies_changed += 1;
                } else {
                    delta.identical += 1;
                }
            }
        }
    }
    for name in before_map.keys() {
        if !after_map.contains_key(name) {
            delta.signatures_changed += 1; // removed item: signature change to nothing
        }
    }

    let before_triggers = scan_triggers(&before_file);
    let after_triggers = scan_triggers(&after_file);
    delta.new_unsafe = (after_triggers.unsafe_count - before_triggers.unsafe_count).max(0);
    delta.new_unwrap = (after_triggers.unwrap_count - before_triggers.unwrap_count).max(0);
    delta.new_attrs_allow = (after_triggers.attrs_allow - before_triggers.attrs_allow).max(0);
    delta.new_attrs_ignore = (after_triggers.attrs_ignore - before_triggers.attrs_ignore).max(0);
    delta.removed_asserts =
        (before_triggers.assert_count - after_triggers.assert_count).max(0);
    delta.removed_test_fns =
        (before_triggers.test_fn_count - after_triggers.test_fn_count).max(0);

    let mut categories: Vec<&String> = before_triggers.trigger_surface.keys()
        .chain(after_triggers.trigger_surface.keys())
        .collect();
    categories.sort();
    categories.dedup();
    for cat in categories {
        let before_n = *before_triggers.trigger_surface.get(cat).unwrap_or(&0);
        let after_n = *after_triggers.trigger_surface.get(cat).unwrap_or(&0);
        let net_new = (after_n - before_n).max(0);
        if net_new > 0 {
            delta.trigger_surface.insert(cat.clone(), net_new);
        }
    }

    println!("{}", serde_json::to_string(&delta).unwrap());
}
