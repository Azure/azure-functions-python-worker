This is a folder for containing a common_module in worker dependencies.

It is used for testing import behavior with customer_deps_path.

Adding this folder to sys.path and importing common_module, printing out the
common_module.__version__ will show which module is loaded.

To test if the namespace is reloaded properly, printing out the
common_namespace.nested_common.__version__ will show which namespace is loaded.
