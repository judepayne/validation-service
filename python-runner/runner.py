#!/usr/bin/env python3
"""
Python Validation Runner - Main Entry Point

This is the main entry point for the Python validation runner.
It connects the transport layer (babashka pods) to the validation engine.

Usage:
    python runner.py [config_path]

Default config path: ./local-config.yaml
"""

import sys
import os

# Change to script's directory so relative paths in config work
# This allows the runner to be invoked from any directory
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

# Resolve logic directory before importing anything that needs it.
# Supports both local paths (development) and remote URLs (production).
config_path = sys.argv[1] if len(sys.argv) > 1 else "./local-config.yaml"

from core.logic_fetcher import LogicPackageFetcher

fetcher = LogicPackageFetcher()
logic_dir = fetcher.resolve_logic_dir(config_path)

if logic_dir and logic_dir not in sys.path:
    sys.path.insert(0, logic_dir)

from transport.pods_transport import PodsTransportHandler
from core.validation_engine import ValidationEngine


def main():
    """Main entry point with pluggable transport"""

    # Initialize components
    engine = ValidationEngine(config_path)
    transport = PodsTransportHandler()  # Pluggable: could be GrpcTransportHandler

    transport.start()

    # Main request loop
    while True:
        request_id = None
        try:
            request_id, function_name, args = transport.receive_request()

            # Dispatch to validation engine
            if function_name == "describe":
                # Babashka pods describe operation
                # Note: describe response is sent raw, not wrapped in id/value
                describe_response = {
                    "format": "json",
                    "namespaces": [{
                        "name": "pod.validation-runner",
                        "vars": [
                            {"name": "get-required-data"},
                            {"name": "validate"},
                            {"name": "discover-rules"}
                        ]
                    }],
                    "ops": {
                        "shutdown": {}
                    }
                }
                transport.send_raw_response(describe_response)
                continue  # Skip the normal send_response at the end
            elif function_name == "shutdown":
                # Handle graceful shutdown
                transport.send_response(request_id, {})
                break  # Exit the main loop
            elif function_name == "get_required_data":
                result = engine.get_required_data(
                    args["entity_type"],
                    args["schema_url"],
                    args["ruleset_name"]
                )
            elif function_name == "discover_rules":
                result = engine.discover_rules(
                    args["entity_type"],
                    args["entity_data"],
                    args["ruleset_name"]
                )
            elif function_name == "validate":
                result = engine.validate(
                    args["entity_type"],
                    args["entity_data"],
                    args["ruleset_name"],
                    args["required_data"]
                )
            else:
                raise ValueError(f"Unknown function: {function_name}")

            transport.send_response(request_id, result)

        except EOFError:
            # Clean EOF - babashka closed the connection
            break

        except Exception as e:
            if request_id:
                transport.send_error(request_id, str(e))
            else:
                # Fatal error before we could read request_id
                import traceback
                traceback.print_exc()
                break


if __name__ == "__main__":
    main()
