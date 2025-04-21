# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import os

from .logging import logger

from .utils.env_state import get_app_setting
from .utils.constants import (APPLICATIONINSIGHTS_CONNECTION_STRING,
                              PYTHON_APPLICATIONINSIGHTS_LOGGER_NAME,
                              PYTHON_APPLICATIONINSIGHTS_LOGGER_NAME_DEFAULT,
                              TRACESTATE, TRACEPARENT)


class OTelManager:
    def __init__(self):
        self._azure_monitor_available = False
        self._otel_libs_available = False
        self._context_api = None
        self._trace_context_propagator = None

    def set_azure_monitor_available(self, azure_monitor_available):
        self._azure_monitor_available = azure_monitor_available

    def get_azure_monitor_available(self):
        return self._azure_monitor_available

    def set_otel_libs_available(self, otel_libs_available):
        self._aotel_libs_available = otel_libs_available

    def get_otel_libs_available(self):
        return self._otel_libs_available

    def set_context_api(self, context_api):
        self._context_api = context_api

    def get_context_api(self):
        return self._context_api

    def set_trace_context_propagator(self, trace_context_propagator):
        self._trace_context_propagator = trace_context_propagator

    def get_trace_context_propagator(self):
        return self._trace_context_propagator


def update_opentelemetry_status():
    """Check for OpenTelemetry library availability and
    update the status attribute."""
    try:
        from opentelemetry import context as context_api
        from opentelemetry.trace.propagation.tracecontext import (
            TraceContextTextMapPropagator,
        )

        OTelManager.set_context_api(context_api)
        OTelManager.set_trace_context_propagator(TraceContextTextMapPropagator())

    except ImportError:
        logger.exception(
            "Cannot import OpenTelemetry libraries."
        )


def initialize_azure_monitor():
    """Initializes OpenTelemetry and Azure monitor distro
    """
    update_opentelemetry_status()
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor

        # Set functions resource detector manually until officially
        # include in Azure monitor distro
        os.environ.setdefault(
            "OTEL_EXPERIMENTAL_RESOURCE_DETECTORS",
            "azure_functions",
        )

        configure_azure_monitor(
            # Connection string can be explicitly specified in Appsetting
            # If not set, defaults to env var
            # APPLICATIONINSIGHTS_CONNECTION_STRING
            connection_string=get_app_setting(
                setting=APPLICATIONINSIGHTS_CONNECTION_STRING
            ),
            logger_name=get_app_setting(
                setting=PYTHON_APPLICATIONINSIGHTS_LOGGER_NAME,
                default_value=PYTHON_APPLICATIONINSIGHTS_LOGGER_NAME_DEFAULT
            ),
        )
        OTelManager.set_azure_monitor_available(True)

        logger.info("Successfully configured Azure monitor distro.")
    except ImportError:
        logger.exception(
            "Cannot import Azure Monitor distro."
        )
        OTelManager.set_azure_monitor_available(False)
    except Exception:
        logger.exception(
            "Error initializing Azure monitor distro."
        )
        OTelManager.set_azure_monitor_available(False)


def configure_opentelemetry(invocation_context):
    carrier = {TRACEPARENT: invocation_context.trace_context.trace_parent,
               TRACESTATE: invocation_context.trace_context.trace_state}
    ctx = OTelManager.get_trace_context_propagator().extract(carrier)
    OTelManager.get_context_api().attach(ctx)


otel_manager = OTelManager()
