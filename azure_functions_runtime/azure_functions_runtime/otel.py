# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os

from .logging import logger

from .utils.app_setting_manager import get_app_setting
from .utils.constants import (APPLICATIONINSIGHTS_CONNECTION_STRING,
                              PYTHON_APPLICATIONINSIGHTS_LOGGER_NAME,
                              PYTHON_APPLICATIONINSIGHTS_LOGGER_NAME_DEFAULT,
                              TRACESTATE, TRACEPARENT)
from .utils.tracing import serialize_exception_as_str


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

        otel_manager.set_context_api(context_api)
        otel_manager.set_trace_context_propagator(TraceContextTextMapPropagator())

    except ImportError as e:
        logger.exception(
            "Cannot import OpenTelemetry libraries. Exception: %s",
            serialize_exception_as_str(e)
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
        otel_manager.set_azure_monitor_available(azure_monitor_available=True)

        logger.info("Successfully configured Azure monitor distro.")
    except ImportError as e:
        logger.exception(
            "Cannot import Azure Monitor distro. Exception: %s",
            serialize_exception_as_str(e)
        )
        otel_manager.set_azure_monitor_available(False)
    except Exception as e:
        logger.exception(
            "Error initializing Azure monitor distro. Exception: %s",
            serialize_exception_as_str(e)
        )
        otel_manager.set_azure_monitor_available(False)


def configure_opentelemetry(invocation_context):
    carrier = {TRACEPARENT: invocation_context.trace_context.trace_parent,
               TRACESTATE: invocation_context.trace_context.trace_state}
    ctx = otel_manager.get_trace_context_propagator().extract(carrier)
    otel_manager.get_context_api().attach(ctx)


otel_manager = OTelManager()
