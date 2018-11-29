import textwrap


def write_worker_cfg(cmd, basename, filename):
    config = textwrap.dedent('''\
    {
        "description": {
            "language": "python",
            "extensions": [".py"],
            "defaultExecutablePath": "python",
            "arguments": ["-m", "azure.functions_worker"]
        }
    }
    ''').strip()

    cmd.write_file(config, filename, config)
