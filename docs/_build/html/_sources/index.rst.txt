.. image:: https://travis-ci.org/Azure/azure-functions-python-worker.svg?branch=master
    :target: https://travis-ci.org/Azure/azure-functions-python-worker


==========================
Azure Functions for Python
==========================

Requirements
============

Azure Functions for Python support Python 3.6 or later.


Programming Model
=================

An Azure function is implemented as a global Python function ``main()`` in the
file called ``__init__.py``. The name of the Python function can be changed by
specifying the ``entryPoint`` attribute in ``function.json``, and the name of
the file can be changed by specifying the ``scriptFile`` attribute in
``function.json``.

Currently, the Azure function and its bindings must be declared in the
``function.json`` file.  Optionally, the function parameters and the
return type may also be declared as Python type annotations.  The annotations
must match the types expected by the bindings declared in ``function.json``.

Below is an example of a simple function triggerred by an HTTP request.

``function.json``:

.. code-block:: json

    {
      "scriptFile": "__init__.py",
      "disabled": false,
      "bindings": [
        {
          "authLevel": "anonymous",
          "type": "httpTrigger",
          "direction": "in",
          "name": "req"
        },
        {
          "type": "http",
          "direction": "out",
          "name": "$return"
        }
      ]
    }


``__init__.py``:

.. code-block:: python

    import azure.functions

    def main(req: azure.functions.HttpRequest) -> str:
        user = req.params.get('user', 'User')
        return f'Hello, {user}!'


The annotations are optional, so the function may also be written as:

.. code-block:: python

    def main(req):
        user = req.params.get('user', 'User')
        return f'Hello, {user}!'


Logging
=======

Azure Functions adds a root :mod:`logging <python:logging>` handler
automatically, and any log output produced using the standard logging output
is captured by the Functions runtime.


Context
=======

A function can obtain the invocation context by including the special
``context`` argument in its signature.  The context is passed as a
:class:`Context <azure.functions.Context>` instance:

.. code-block:: python

    import azure.functions

    def main(req: azure.functions.HttpRequest,
             context: azure.functions.Context) -> str:
        return f'{context.invocation_id}'


Bindings
========

Azure Functions for Python supports the following binding types:

* :ref:`HTTP and webhooks <azure-bindings-http>`: trigger, output;
* :ref:`Blob storage <azure-bindings-blob>`: trigger, input, output;
* :ref:`Queue <azure-bindings-queue>`: trigger, output;
* :ref:`Timers <azure-bindings-timer>`: trigger.


.. _azure-bindings-http:

HTTP and webhook bindings
-------------------------

The trigger binding is passed as a
:class:`HttpRequest <azure.functions.HttpRequest>` object.  Output bindings
can be returned as a ``str`` or an
:class:`HttpResponse <azure.functions.HttpResponse>` object.

Example
~~~~~~~

``function.json``:

.. code-block:: json

    {
      "scriptFile": "__init__.py",
      "disabled": false,
      "bindings": [
        {
          "authLevel": "anonymous",
          "type": "httpTrigger",
          "direction": "in",
          "name": "req"
        },
        {
          "type": "http",
          "direction": "out",
          "name": "$return"
        }
      ]
    }


``__init__.py``:

.. code-block:: python

    import azure.functions

    def main(req: azure.functions.HttpRequest) -> str:
        user = req.params.get('user', 'User')
        return f'Hello, {user}!'



.. _azure-bindings-blob:

Blob storage bindings
---------------------

The trigger and input bindings are passed as
:class:`InputStream <azure.functions.InputStream>` instances.  Output can
be a ``bytes``, ``str`` or a :term:`file-like object <python:file object>`.

Blob storage trigger example
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``function.json``:

.. code-block:: json

    {
      "disabled": false,
      "bindings": [
        {
          "type": "blobTrigger",
          "direction": "in",
          "name": "file",
          "connection": "AzureWebJobsStorage",
          "path": "file.txt"
        },
        {
          "type": "http",
          "direction": "out",
          "name": "$return",
        }
      ]
    }


``__init__.py``:


.. code-block:: python

    import azure.functions

    def main(file: azure.functions.InputStream) -> bytes:
        return file.read()


Blob storage output example
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``function.json``:

.. code-block:: json

    {
      "disabled": false,
      "bindings": [
        {
          "authLevel": "anonymous",
          "type": "httpTrigger",
          "direction": "in",
          "name": "req"
        },
        {
          "type": "blob",
          "direction": "out",
          "name": "file",
          "connection": "AzureWebJobsStorage",
          "path": "test-file.txt"
        },
        {
          "type": "http",
          "direction": "out",
          "name": "$return",
        }
      ]
    }


``__init__.py``:


.. code-block:: python

    import azure.functions

    def main(req: azure.functions.HttpRequest,
             file: azure.functions.Out[bytes]) -> azure.functions.HttpResponse:
        # write the request body into the output blob
        file.set(req.get_body())

        return azure.functions.HttpResponse(
            content_type='application/json',
            body='{"status": "OK"}'
        )

Note that in the above example we use the :class:`Out <azure.functions.Out>`
interface to set the value of the output binding.


.. _azure-bindings-queue:

Queue storage bindings
----------------------

Queue storage trigger bindings are passed as
:class:`QueueMessage <azure.functions.QueueMessage>` instances.  Output
bindings can be returned as a ``str``, ``bytes`` or a
:class:`QueueMessage <azure.functions.QueueMessage>` instance.


Example
~~~~~~~

``function.json``:

.. code-block:: json

    {
      "scriptFile": "__init__.py",

      "bindings": [
        {
          "type": "queueTrigger",
          "direction": "in",
          "name": "msg",
          "queueName": "inputqueue",
          "connection": "AzureWebJobsStorage",
        },
        {
          "type": "blob",
          "direction": "out",
          "name": "$return",
          "queueName": "outputqueue",
          "connection": "AzureWebJobsStorage",
        }
      ]
    }


``__init__.py``:

.. code-block:: python

    import azure.functions

    def main(
            msg: azure.functions.QueueMessage) -> azure.functions.QueueMessage:
        body = msg.get_body()
        # ... process message
        # Put a message into the output queue signaling that this message
        # was processed.
        return azure.functions.QueueMessage(
            body=f'Processed: {msg.id}'
        )


.. _azure-bindings-timer:

Timer bindings
--------------

Timer trigger bindings are passwd as
:class:`TimerRequest <azure.functions.TimerRequest>` instances.

Example
~~~~~~~

``function.json``:

.. code-block:: json

    {
      "scriptFile": "__init__.py",

      "bindings": [
        {
          "type": "timerTrigger",
          "direction": "in",
          "name": "timer",
          "schedule": "*/5 * * * * *"
        },
        {
          "type": "blob",
          "direction": "out",
          "name": "$return",
          "queueName": "outputqueue",
          "connection": "AzureWebJobsStorage",
        }
      ]
    }


``__init__.py``:

.. code-block:: python

    import datetime
    import azure.functions

    def main(timer: azure.functions.TimerRequest) -> str:
        # process timer event...
        # put the current timestamp into the output queue.
        return f'{datetime.datetime.now().timestamp()}'


.. _azure-bindings-cosmosdb:

CosmosDB Bindings
-----------------

The trigger and input CosmosDB bindings are passed as
:class:`DocumentList <azure.functions.DocumentList>` instances.  Output can
be a :class:`Document <azure.functions.Document>` instance, a
:class:`DocumentList <azure.functions.DocumentList>` instance or an iterable
containing ``Document`` instances.

CosmosDB Trigger Example
~~~~~~~~~~~~~~~~~~~~~~~~

``function.json``:

.. code-block:: json

    {
      "disabled": false,
      "bindings": [
        {
          "direction": "in",
          "type": "cosmosDBTrigger",
          "name": "docs",
          "databaseName": "test",
          "collectionName": "items",
          "leaseCollectionName": "leases",
        },
        {
          "type": "http",
          "direction": "out",
          "name": "$return",
        }
      ]
    }


``__init__.py``:


.. code-block:: python

    import azure.functions as func

    def main(docs: func.DocumentList) -> str:
        return docs[0].to_json()


CosmosDB Output Example
~~~~~~~~~~~~~~~~~~~~~~~

``function.json``:

.. code-block:: json

    {
      "scriptFile": "__init__.py",
      "disabled": false,

      "bindings": [
        {
          "authLevel": "anonymous",
          "type": "httpTrigger",
          "direction": "in",
          "name": "req"
        },
        {
          "direction": "out",
          "type": "cosmosDB",
          "name": "doc",
          "databaseName": "test",
          "collectionName": "items",
          "leaseCollectionName": "leases",
          "createIfNotExists": true
        },
        {
          "direction": "out",
          "name": "$return",
          "type": "http"
        }
      ]
    }


``__init__.py``:


.. code-block:: python

    import azure.functions as func


    def main(req: func.HttpRequest, doc: func.Out[func.Document]):
        doc.set(func.Document.from_json(req.get_body()))

        return 'OK'


Reference
---------

:ref:`Azure Functions for Python Reference <azure-functions-reference>`.


.. toctree::
   :maxdepth: 2
   :hidden:

   usage
   api
