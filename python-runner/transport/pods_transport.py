import sys
import json
import bencodepy as bencode
from transport.base import TransportHandler
from typing import Any, Dict
from .bencode_reader import read_message
from .case_conversion import kebab_to_snake

class PodsTransportHandler(TransportHandler):
    """Babashka pods transport implementation using bencode over stdin/stdout"""

    def start(self):
        """Pods transport is ready as soon as process starts"""
        pass

    def send_response(self, request_id: str, result: Any):
        """Encode and send response via stdout

        Note: For JSON format pods, the result must be JSON-encoded first,
        then the whole response is bencode-encoded for transport.
        """
        # Convert result to JSON string (babashka expects this for format="json")
        value_json = json.dumps(result)

        response = {"id": request_id, "value": value_json, "status": ["done"]}
        sys.stdout.buffer.write(bencode.encode(response))
        sys.stdout.buffer.flush()

    def send_raw_response(self, data: Dict[str, Any]):
        """Send raw response without id/value wrapping (for describe operation)"""
        sys.stdout.buffer.write(bencode.encode(data))
        sys.stdout.buffer.flush()

    def send_error(self, request_id: str, error: str):
        """Encode and send error via stdout"""
        response = {"id": request_id, "error": error}
        sys.stdout.buffer.write(bencode.encode(response))
        sys.stdout.buffer.flush()

    def receive_request(self) -> tuple[str, str, Dict[str, Any]]:
        """Read and decode request from stdin using structure-aware reader"""
        msg = read_message(sys.stdin.buffer)

        if msg is None:
            raise EOFError("No data received")

        return self._extract_request_info(msg)

    def _extract_request_info(self, msg: dict) -> tuple[str, str, Dict[str, Any]]:
        """Extract request information from decoded message (all string keys now)"""
        op = msg.get("op")

        # Handle describe operation
        if op == "describe":
            request_id = msg.get("id", "unknown")
            return (request_id, "describe", {})

        # Handle shutdown operation
        if op == "shutdown":
            request_id = msg.get("id", "unknown")
            return (request_id, "shutdown", {})

        if op != "invoke":
            raise ValueError(f"Unsupported operation: {op}")

        # Extract invoke details
        request_id = msg.get("id", "unknown")
        var_name_kebab = msg.get("var", "")

        # Strip namespace prefix if present (e.g. "pod.validation-runner/get-required-data" -> "get-required-data")
        if "/" in var_name_kebab:
            var_name_kebab = var_name_kebab.split("/", 1)[1]

        # Convert kebab-case to snake_case for Python
        var_name_snake = kebab_to_snake(var_name_kebab)

        # Get args - babashka sends args as a JSON string that needs to be parsed
        args_raw = msg.get("args", "{}")
        try:
            if isinstance(args_raw, str):
                args = json.loads(args_raw)
            else:
                args = args_raw
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in args: {str(e)[:100]}")

        # JVM babashka.pods wraps args in an array [arg1, arg2, ...], we expect single map
        # Native babashka might send just the map directly
        if isinstance(args, list) and len(args) > 0:
            args = args[0]  # Extract first argument

        return (request_id, var_name_snake, args)
