"""Third-party integration helpers.

Each sub-module encapsulates the vendor-specific HTTP / protocol logic for one
external service.  The corresponding thin action wrapper lives in
``polymarket_watcher/actions/`` and is the only public interface that the rest
of the codebase should import.
"""
