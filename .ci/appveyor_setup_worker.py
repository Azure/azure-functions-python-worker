import json
import os
import pathlib
import shutil
import sys
import tempfile


def main():
    worker_dir = pathlib.Path(tempfile.mkdtemp())
    os.makedirs(worker_dir)
    worker_src = pathlib.Path(__file__).parent.parent / 'worker.py'

    shutil.copyfile(worker_src, worker_dir / 'worker.py')
    with open(worker_dir / 'worker.config.json', 'w') as f:
        json.dump({
            "description": {
                "language": "python",
                "extensions": [".py"],
                "defaultExecutablePath": sys.executable,
                "defaultWorkerPath": "worker.py"
            }
        }, f)

    print(worker_dir.parent)


if __name__ == '__main__':
    main()
