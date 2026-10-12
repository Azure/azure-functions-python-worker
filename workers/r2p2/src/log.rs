// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.
//
// Console logging that matches the Python proxy worker so the Functions Host
// ingests Rust-worker logs identically. The Python worker formats every console
// line as `LanguageWorkerConsoleLog <LEVEL>: <message>` and splits streams
// (errors -> stderr, everything else -> stdout). See
// `workers/proxy_worker/logging.py`.

const CONSOLE_LOG_PREFIX: &str = "LanguageWorkerConsoleLog";

fn format_line(level: &str, msg: &str) -> String {
    format!("{CONSOLE_LOG_PREFIX} {level}: {msg}")
}

/// Informational log line (stdout), matching the Python worker's `logger.info`.
pub fn info(msg: &str) {
    println!("{}", format_line("INFO", msg));
}

/// Warning log line (stdout), matching the Python worker's `logger.warning`.
#[cfg_attr(
    not(test),
    expect(
        dead_code,
        reason = "completes the info/warning/error stream trio mirroring the Python worker; \
              retained as a stable logging API even though no caller emits WARNING yet"
    )
)]
pub fn warning(msg: &str) {
    println!("{}", format_line("WARNING", msg));
}

/// Error log line (stderr), matching the Python worker's `error_logger`.
pub fn error(msg: &str) {
    eprintln!("{}", format_line("ERROR", msg));
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn formats_host_console_log_contract() {
        assert_eq!(
            format_line("INFO", "worker started"),
            "LanguageWorkerConsoleLog INFO: worker started"
        );
        assert_eq!(
            format_line("WARNING", "slow invocation"),
            "LanguageWorkerConsoleLog WARNING: slow invocation"
        );
        assert_eq!(
            format_line("ERROR", "handler failed"),
            "LanguageWorkerConsoleLog ERROR: handler failed"
        );
    }

    #[test]
    fn logging_functions_accept_messages() {
        info("info");
        warning("warning");
        error("error");
    }
}
