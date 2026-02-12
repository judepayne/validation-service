"""
Structure-aware bencode message reader for streaming protocols.

This module provides a bencode reader that can extract complete messages from
a stream by tracking the bencode structure boundaries. Standard bencode libraries
don't provide stream-aware reading, requiring the caller to know message boundaries.

Key Features:
- Reads one complete bencode message from a stream
- Handles nested structures (dicts, lists, integers, strings)
- Converts bytes to strings recursively for Python 3 compatibility
- Used by pods_transport.py to read babashka pod protocol messages

Why This Exists:
The bencodepy library doesn't provide a "read one message from stream" function.
It expects to decode a complete byte buffer. This module fills that gap by
reading stdin byte-by-byte, tracking structure depth, and stopping at message
boundaries.

Example Usage:
    >>> from bencode_reader import read_message
    >>> import sys
    >>> msg = read_message(sys.stdin.buffer)
    >>> # Returns decoded dict with string keys/values
    >>> print(msg['op'], msg['id'])
"""
import bencodepy as bencode


def read_until_byte(stream, target_byte):
    """Read until we hit the target byte (inclusive)"""
    result = b''
    while True:
        byte = stream.read(1)
        if not byte:
            raise EOFError("Unexpected EOF")
        result += byte
        if byte == target_byte:
            break
    return result

def read_string_content(stream, first_digit):
    """Read the rest of a length-prefixed string after the first digit"""
    result = b''
    length_bytes = first_digit

    # Read remaining digits until we hit the ':'
    while True:
        byte = stream.read(1)
        if not byte:
            raise EOFError("Unexpected EOF while reading string length")
        result += byte
        if byte == b':':
            break
        if not byte.isdigit():
            raise ValueError(f"Invalid character in string length: {byte}")
        length_bytes += byte

    # Parse the length (length_bytes contains only digits, no colon)
    string_length = int(length_bytes.decode('ascii'))
    string_content = stream.read(string_length)
    if len(string_content) != string_length:
        raise EOFError(f"Expected {string_length} bytes, got {len(string_content)}")
    result += string_content

    return result

def read_list_content(stream):
    """Read list content until the closing 'e'"""
    result = b''

    while True:
        byte = stream.read(1)
        if not byte:
            raise EOFError("Unexpected EOF in list")

        if byte == b'e':  # End of list
            result += byte
            break
        else:
            # Read a complete bencode value starting with this byte
            if byte == b'd':  # Nested dictionary
                result += byte + read_dict_content(stream)
            elif byte == b'l':  # Nested list
                result += byte + read_list_content(stream)
            elif byte == b'i':  # Integer
                result += byte + read_until_byte(stream, b'e')
            elif byte.isdigit():  # String
                result += byte + read_string_content(stream, byte)
            else:
                raise ValueError(f"Invalid bencode character in list: {byte}")

    return result

def read_dict_content(stream):
    """Read dictionary content until the closing 'e'"""
    result = b''

    while True:
        byte = stream.read(1)
        if not byte:
            raise EOFError("Unexpected EOF in dictionary")

        if byte == b'e':  # End of dictionary
            result += byte
            break
        else:
            # Read a complete bencode value starting with this byte
            if byte == b'd':  # Nested dictionary
                result += byte + read_dict_content(stream)
            elif byte == b'l':  # Nested list
                result += byte + read_list_content(stream)
            elif byte == b'i':  # Integer
                result += byte + read_until_byte(stream, b'e')
            elif byte.isdigit():  # String
                result += byte + read_string_content(stream, byte)
            else:
                raise ValueError(f"Invalid bencode character in dict: {byte}")

    return result

def read_bencode_value(stream):
    """Read a single bencode value (int, string, list, or dict)"""
    first_byte = stream.read(1)
    if not first_byte:
        return None

    if first_byte == b'd':  # Dictionary
        return first_byte + read_dict_content(stream)
    elif first_byte == b'l':  # List
        return first_byte + read_list_content(stream)
    elif first_byte == b'i':  # Integer
        return first_byte + read_until_byte(stream, b'e')
    elif first_byte.isdigit():  # String
        return first_byte + read_string_content(stream, first_byte)
    else:
        raise ValueError(f"Invalid bencode start: {first_byte}")

def bytes_to_strings(obj):
    """Recursively convert bytes to strings in a data structure"""
    if isinstance(obj, bytes):
        return obj.decode('utf-8')
    elif isinstance(obj, dict):
        return {bytes_to_strings(k): bytes_to_strings(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [bytes_to_strings(item) for item in obj]
    else:
        return obj

def read_message_raw(stream):
    """Read a complete bencode message by tracking structure - returns raw bytes"""
    try:
        buffer = read_bencode_value(stream)
        if buffer is None:
            return None
        return buffer
    except EOFError:
        return None

def read_message(stream, transform=None):
    """Read and decode a complete bencode message from stream, returning strings instead of bytes

    Args:
        stream: The input stream to read from
        transform: Optional function to apply additional transformation to the decoded result

    Returns:
        Decoded and stringified bencode data, optionally transformed
    """
    try:
        # Get raw bencode bytes
        raw_bytes = read_message_raw(stream)
        if raw_bytes is None:
            return None

        # Decode bencode to Python objects
        decoded = bencode.decode(raw_bytes)

        # Convert bytes to strings recursively
        result = bytes_to_strings(decoded)

        # Apply optional transformation
        if transform is not None:
            result = transform(result)

        return result

    except bencode.BencodeDecodeError as e:
        raise ValueError(f"Invalid bencode message: {str(e)[:100]}")
    except Exception as e:
        raise ValueError(f"Error reading message: {str(e)[:100]}")
