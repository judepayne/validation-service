from abc import ABC, abstractmethod
from typing import Any, Dict

class TransportHandler(ABC):
    """Abstract base class for transport layer"""

    @abstractmethod
    def start(self):
        """Initialize transport and start listening for requests"""
        pass

    @abstractmethod
    def send_response(self, request_id: str, result: Any):
        """Send successful response to client"""
        pass

    @abstractmethod
    def send_error(self, request_id: str, error: str):
        """Send error response to client"""
        pass

    @abstractmethod
    def receive_request(self) -> tuple[str, str, Dict[str, Any]]:
        """
        Receive next request from client.

        Returns:
            Tuple of (request_id, function_name, arguments_dict)
        """
        pass
