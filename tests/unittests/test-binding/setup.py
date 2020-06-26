# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
from setuptools import setup


setup(
    name='foo-binding',
    version='1.0',
    packages=['foo'],
    entry_points={
        'azure.functions.bindings': [
            'foo=foo.binding:Binding',
        ]
    },
)
