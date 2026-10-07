# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
#
# Launcher shim for the native R2P2 (Python 3.15+).
#
# The Functions Host launches this file using the standard Python worker
# contract from the shared worker.config.json (defaultExecutablePath="python",
# defaultWorkerPath="%FUNCTIONS_WORKER_RUNTIME_VERSION%/{os}/{architecture}/worker.py")
# and passes the transport arguments (--host, --port, --workerId, --requestId,
# --grpcMaxMessageLength, ...). This shim replaces the current process image in
# place with the native `r2p2` binary that sits next to this file,
# forwarding every argument unchanged. The R2P2 parses the flags it needs
# and ignores the rest.
#
# os.execv does not fork: no extra process and no additional memory linger after
# the hand-off. The only cost is a one-time interpreter startup at worker
# initialization; there is zero per-invocation overhead, so worker throughput is
# unaffected.
import os
import sys

worker_dir = os.path.dirname(os.path.abspath(__file__))
# The native binary is r2p2.exe on Windows, r2p2 elsewhere.
binary = "r2p2.exe" if os.name == "nt" else "r2p2"
executable = os.path.join(worker_dir, binary)
os.execv(executable, [executable] + sys.argv[1:])
