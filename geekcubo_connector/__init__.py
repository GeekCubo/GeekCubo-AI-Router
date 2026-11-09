"""GeekCubo Local AI Connect connector.

Runs next to an inference server (Ollama, LM Studio, vLLM, llama.cpp or any
OpenAI-compatible endpoint) and opens an OUTBOUND WebSocket to a GeekCubo
instance. No inbound port, tunnel or VPN is required: the connector dials out,
so a laptop behind NAT can serve models to the dashboard.

The connector has two commands:

``enroll``
    Redeem a one-time enrollment code minted in the dashboard, receive the
    per-machine credential, and store it locally.

``run``
    Connect with that credential, publish the model catalog, answer discovery,
    stream chat completions, and heartbeat until stopped.

The wire protocol lives in :mod:`geekcubo_connector.protocol`, a verbatim copy
of the server's module so both sides cannot drift.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
