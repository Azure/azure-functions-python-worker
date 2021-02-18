"""
This module provides functionality for accessing shared memory maps.
These are used for transferring data between functions host and the worker proces.
The initial set of corresponding changes to enable shared memory maps in the functions host can be
found in the following Pull Request:
https://github.com/Azure/azure-functions-host/pull/6836
The issue tracking shared memory transfer related changes is:
https://github.com/Azure/azure-functions-host/issues/6791
""" 