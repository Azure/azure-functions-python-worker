Release Instructions
====================

Please follow these steps in order to make a release:

1. Ensure that buildbots in the dev branch are green.
2. Increase the version field in `setup.py`.
3. Push the version update to the dev branch.
4. Merge the dev branch into master.
5. Verify that the buildbots are still green.
6. Create a git tag corresponding to the new version and push it.
7. Make a PyPI release:

   ```shell
   $ rm dist/*
   $ python setup.py sdist bdist_wheel
   $ twine upload dist/*
   ```

[Twine](https://github.com/pypa/twine) is a PyPI upload tool that can be
installed with pip:

```shell
$ pip install twine
```
