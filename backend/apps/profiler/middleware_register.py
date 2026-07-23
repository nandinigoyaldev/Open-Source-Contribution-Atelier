"""
Register profiler middleware.
"""

from .middleware import SlowEndpointProfiler

# Export to be added to MIDDLEWARE
profiler_middleware = "apps.profiler.middleware.SlowEndpointProfiler"
