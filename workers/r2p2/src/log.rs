// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.
//
// Console logging that matches the Python proxy worker so the Functions Host
// ingests Rust-worker logs identically. The Python worker formats every console
// line as `LanguageWorkerConsoleLog <LEVEL>: <message>` and splits streams
// (errors -> stderr, everything else -> stdout). See
// `workers/proxy_worker/logging.py`.

const CONSOLE_LOG_PREFIX: &str = "LanguageWorkerConsoleLog";

/// Informational log line (stdout), matching the Python worker's `logger.info`.
pub fn info(msg: &str) {
    println!("{CONSOLE_LOG_PREFIX} INFO: {msg}");
}

/// Warning log line (stdout), matching the Python worker's `logger.warning`.
#[expect(
    dead_code,
    reason = "completes the info/warning/error stream trio mirroring the Python worker; \
              retained as a stable logging API even though no caller emits WARNING yet"
)]
pub fn warning(msg: &str) {
    println!("{CONSOLE_LOG_PREFIX} WARNING: {msg}");
}

/// Error log line (stderr), matching the Python worker's `error_logger`.
pub fn error(msg: &str) {
    eprintln!("{CONSOLE_LOG_PREFIX} ERROR: {msg}");
}
