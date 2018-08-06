.. _azure-functions-reference:

=============
API Reference
=============

.. module:: azure.functions
    :synopsis: Azure Functions bindings.

.. currentmodule:: azure.functions


.. _azure-functions-bindings-blob:

Blob Bindings
=============

.. autoclass:: azure.functions.InputStream
   :members:


.. _azure-functions-bindings-http:

HTTP Bindings
=============

.. autoclass:: azure.functions.HttpRequest
   :members:

.. autoclass:: azure.functions.HttpResponse
   :members:


.. _azure-functions-bindings-queue:

Queue Bindings
==============

.. autoclass:: azure.functions.QueueMessage
   :members:


.. _azure-functions-bindings-timer:

Timer Bindings
==============

.. autoclass:: azure.functions.TimerRequest
   :members:


.. _azure-functions-bindings-cosmosdb:

CosmosDB Bindings
=================

.. autoclass:: azure.functions.Document
   :members:

   .. describe:: doc[field]

      Return the field of *doc* with field name *field*.

   .. describe:: doc[field] = value

      Set field of *doc* with field name *field* to *value*.

.. autoclass:: azure.functions.DocumentList
   :members:


.. _azure-functions-bindings-context:

Function Context
================

.. autoclass:: azure.functions.Context
   :members:


Out Parameters
==============

.. autoclass:: azure.functions.Out
   :members:
