This folder contains benchmarks written using `pytest` and profiled using `pyinstrument`.

# Running the benchmarks

Open this repository in VSCode and wait for the devcontainer to start up.

Then you can run all the benchmarks with this command:

`python -m pytest tests/benchmarks`

Or use the keyword argument to run just one benchmark test:

`python -m pytest tests/benchmarks -k test_process_indexed_function`

When you run that test, a profile will also be saved in the `tests/benchmarks/.profiles` folder, in a file named after the profiled function. Open the file in a browser to see the profile.

If you run a benchmark test multiple times (either on same code or different versions of the code), you probably want to save it.

Either pass in `--benchmark-autosave` to save to an auto-generated filename or pass in `--benchmark-save=YOURNAME` to save with your specified name in the filename. All benchmark files will always start with a counter, beginning with 0001.

Once saved, compare using the `pytest-benchmark` command and the counter numbers:

`pytest-benchmark compare 0004 0005`

You can sort the comparison using `--sort`, save it to a CSV using `--csv`, or save it to a histogram with `--histogram`.
More details available in the [pytest-benchmark reference](https://pytest-benchmark.readthedocs.io/en/latest/usage.html#comparison-cli).