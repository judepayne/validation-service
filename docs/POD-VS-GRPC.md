# Babashka Pods vs gRPC - Transport Protocol Comparison

## Document Purpose

This document compares babashka pods and gRPC as transport protocols for JVM-to-Python communication in the validation service. It explains how each handles arbitrary JSON data, migration considerations, and why gRPC is the likely choice for production.

---

## Executive Summary

**POC (Phase 1):** Babashka pods with bencode protocol
- ✅ Simple, works well for validation
- ✅ Minimal dependencies
- ⚠️ Process spawn overhead (50-200ms per request)
- ⚠️ Limited tooling and observability

**Production (Phase 2):** gRPC with Protocol Buffers
- ✅ Long-running service (no spawn overhead)
- ✅ Superior performance and streaming capabilities
- ✅ Rich ecosystem (monitoring, tracing, load balancing)
- ✅ Handles arbitrary JSON via `google.protobuf.Struct`
- ⚠️ More complex setup

**Migration Strategy:** Transport abstraction layer enables seamless transition with AI assistance.

---

## Babashka Pods Protocol (Current - POC)

### Overview

Babashka pods is a lightweight protocol for Clojure/Babashka to communicate with external processes over stdin/stdout using bencode encoding.

### Architecture

```
┌─────────────┐         bencode over        ┌──────────────┐
│   Clojure   │◄──────── stdin/stdout ──────►│    Python    │
│ JVM Service │         (process spawn)      │ Rule Runner  │
└─────────────┘                              └──────────────┘
     Parent                                      Child Process
```

### How It Works

1. **Process Lifecycle:**
   - JVM spawns Python process: `python3 runner.py config.yaml`
   - Python reads from stdin, writes to stdout
   - Process terminates after validation

2. **Message Format (Bencode):**
   ```python
   # Describe operation
   {"op": "describe", "id": "123"}

   # Invoke validation
   {
     "op": "invoke",
     "id": "456",
     "var": "validate",
     "args": {
       "entity_type": "loan",
       "entity_data": {...},  # Arbitrary JSON as bencode dict
       "mode": "inline",
       "required_data": {...}  # Arbitrary JSON as bencode dict
     }
   }

   # Invoke field dependency introspection
   {
     "op": "invoke",
     "id": "789",
     "var": "get-field-dependencies",
     "args": {
       "entity_type": "loan",
       "entity_data": {...},  # Used for schema-version routing
       "mode": "inline"
     }
   }

   # Response
   {
     "id": "456",
     "value": "[{\"rule_id\": \"rule_001_v1\", \"status\": \"PASS\"}]",
     "status": ["done"]
   }
   ```

3. **Handling Arbitrary JSON:**
   - Bencode natively supports dictionaries, lists, strings, integers
   - Entity data encoded as bencode dict → decoded to Python dict
   - No schema required, fully dynamic
   - JSON strings are encoded when format="json" (current implementation)

### Advantages

✅ **Simplicity:** Minimal setup, no service management
✅ **Isolation:** Each validation runs in fresh Python process
✅ **No Port Management:** Uses stdin/stdout (no network ports)
✅ **Debugging:** Easy to test with echo/cat commands
✅ **POC-Friendly:** Quick to implement and validate architecture

### Disadvantages

⚠️ **Process Spawn Overhead:** 50-200ms per request (Python startup time)
⚠️ **No Connection Reuse:** Can't amortize startup cost across requests
⚠️ **Limited Streaming:** Stdin/stdout not designed for bidirectional streaming
⚠️ **No Built-in Monitoring:** Must implement custom observability
⚠️ **No Load Balancing:** Single process per request
⚠️ **Resource Inefficient:** Spawning processes uses more memory than threads/connections

### Performance Characteristics

| Metric | Typical Value | Notes |
|--------|--------------|-------|
| Startup Overhead | 50-200ms | Python interpreter + module loading |
| Request Latency | Validation time + 50-200ms | Overhead dominates for fast rules |
| Throughput (Sequential) | 5-20 requests/sec | Limited by spawn overhead |
| Memory per Request | ~50MB | Full Python process |
| Connection Overhead | None | Uses stdin/stdout |

**Good For:**
- POC/prototype validation
- Low-volume workloads (< 100 requests/sec)
- Batch processing (spawn overhead amortized)

**Not Ideal For:**
- High-frequency inline validation (> 100 requests/sec)
- Latency-sensitive applications (< 100ms SLA)
- High-concurrency scenarios

---

## gRPC Protocol (Production - Phase 2)

### Overview

gRPC is a high-performance RPC framework using Protocol Buffers for serialization. Python runner runs as long-lived service, eliminating process spawn overhead.

### Architecture

```
┌─────────────┐       gRPC (HTTP/2)       ┌──────────────┐
│    Java     │◄─────────────────────────►│    Python    │
│ JVM Service │    Protobuf Messages      │ gRPC Server  │
└─────────────┘                            └──────────────┘
    Client                                  Long-Running
                                           Service (port 50051)
```

### How It Works

1. **Service Lifecycle:**
   - Python gRPC server starts once: `python3 grpc_server.py`
   - Listens on port (e.g., 50051)
   - Handles requests in threads/async
   - No process spawning per request

2. **Service Definition (.proto):**
   ```protobuf
   syntax = "proto3";

   import "google/protobuf/struct.proto";

   service ValidationRunner {
     rpc GetRequiredData(GetRequiredDataRequest)
         returns (GetRequiredDataResponse);
     rpc Validate(ValidateRequest)
         returns (ValidateResponse);
     rpc GetFieldDependencies(GetFieldDependenciesRequest)
         returns (GetFieldDependenciesResponse);
   }

   message ValidateRequest {
     string request_id = 1;
     string entity_type = 2;
     google.protobuf.Struct entity_data = 3;  // Arbitrary JSON
     string mode = 4;
     google.protobuf.Struct required_data = 5;  // Arbitrary JSON
   }

   message ValidateResponse {
     string request_id = 1;
     repeated RuleResult results = 2;
   }

   message RuleResult {
     string rule_id = 1;
     string status = 2;    // PASS, FAIL, NORUN, ERROR
     string message = 3;
     int64 execution_time_ms = 4;
   }
   ```

   **Status Values:**
   - `PASS`: Rule executed successfully, entity is valid
   - `FAIL`: Rule executed successfully, entity is invalid (validation error)
   - `NORUN`: Rule was skipped (parent failed, dependencies missing, or rule not found)
   - `ERROR`: Rule crashed during execution (exception thrown, bug in rule code)

3. **Handling Arbitrary JSON:**

   **Option 1: `google.protobuf.Struct` (Recommended)**
   ```python
   from google.protobuf.struct_pb2 import Struct

   # Server side - convert Struct to dict
   def Validate(self, request, context):
       entity_data = dict(request.entity_data)  # Struct → dict
       required_data = dict(request.required_data)

       # Same dict format as bencode! No code changes needed.
       result = validation_engine.validate(
           request.entity_type,
           entity_data,
           request.mode,
           required_data
       )
       return ValidateResponse(results=result)
   ```

   **Option 2: JSON String (Simpler, Less Type-Safe)**
   ```protobuf
   message ValidateRequest {
     string entity_type = 1;
     string entity_data_json = 2;  // JSON as string
     string required_data_json = 3;
   }
   ```
   ```python
   import json

   def Validate(self, request, context):
       entity_data = json.loads(request.entity_data_json)
       # Rest is same
   ```

### google.protobuf.Struct Details

**What It Is:**
- Built-in protobuf type for representing arbitrary JSON-like structures
- Supports objects, arrays, strings, numbers, booleans, null
- Preserves structure and types

**Conversion:**
```python
# Python dict → Struct
from google.protobuf.struct_pb2 import Struct

data = {
    "$schema": "https://bank.example.com/schemas/loan/v1.0.0",
    "id": "LOAN-12345",
    "financial": {
        "principal_amount": 100000,
        "currency": "USD"
    },
    "dates": {
        "origination_date": "2024-01-01",
        "maturity_date": "2025-01-01"
    }
}

struct = Struct()
struct.update(data)  # Converts dict → Struct

# Struct → Python dict
dict_back = dict(struct)  # Struct → dict
```

**Performance:**
- Slightly more overhead than raw JSON strings
- But preserves type information
- Better schema validation at message boundaries

**Compatibility:**
- Supported in all gRPC languages (Python, Java, Go, etc.)
- Can serialize to/from JSON for debugging
- Standard practice in gRPC for dynamic data

### Advantages

✅ **Performance:** No process spawn, ~1-5ms latency for validation
✅ **Connection Reuse:** Single TCP connection, HTTP/2 multiplexing
✅ **Streaming:** Bidirectional streaming for batch processing
✅ **Load Balancing:** Built-in client-side load balancing
✅ **Monitoring:** Prometheus metrics, OpenTelemetry tracing
✅ **Type Safety:** Protobuf schema at boundaries (with Struct for dynamic data)
✅ **Rich Ecosystem:** Interceptors, health checks, reflection
✅ **Multi-Language:** Same .proto works for Java, Python, Go, etc.

### Disadvantages

⚠️ **Complexity:** Requires service management (deployment, health checks)
⚠️ **Port Management:** Need to allocate and manage network ports
⚠️ **Learning Curve:** Protobuf syntax, gRPC concepts
⚠️ **Stateful Service:** Must handle crashes, restarts, graceful shutdown

### Performance Characteristics

| Metric | Typical Value | Notes |
|--------|--------------|-------|
| Startup Overhead | 0ms | Service already running |
| Request Latency | Validation time + 1-5ms | Minimal RPC overhead |
| Throughput (Single Service) | 1,000-10,000 requests/sec | Limited by validation, not transport |
| Memory per Request | ~1KB | Just message overhead |
| Connection Overhead | ~10KB | HTTP/2 connection reuse |

**Good For:**
- High-frequency inline validation
- Low-latency requirements (< 50ms SLA)
- High-concurrency scenarios
- Production deployments

---

## Migration Path

### Transport Abstraction Layer

The Python runner already implements transport abstraction:

```python
# transport/base.py (Already exists!)
class TransportHandler(ABC):
    @abstractmethod
    def receive_request(self) -> tuple[str, str, Dict[str, Any]]:
        """Returns (request_id, function_name, args_dict)"""
        pass

    @abstractmethod
    def send_response(self, request_id: str, result: Any):
        pass
```

### Current Implementation (Pods)

```python
# transport/pods_transport.py
class PodsTransportHandler(TransportHandler):
    def receive_request(self):
        msg = read_message(sys.stdin.buffer)
        return (msg['id'], msg['var'], msg['args'])

    def send_response(self, request_id, result):
        response = {"id": request_id, "value": json.dumps(result)}
        sys.stdout.buffer.write(bencode.encode(response))
```

### Future Implementation (gRPC)

```python
# transport/grpc_transport.py (To be created)
import grpc
from validation_runner_pb2 import ValidateRequest

class GrpcTransportHandler(TransportHandler):
    def __init__(self, grpc_context):
        self.context = grpc_context

    def receive_request(self):
        request = self.context.request

        # Convert Struct → dict (same format as bencode!)
        args = {
            'entity_type': request.entity_type,
            'entity_data': dict(request.entity_data),
            'mode': request.mode,
            'required_data': dict(request.required_data)
        }

        return (request.request_id, 'validate', args)

    def send_response(self, request_id, result):
        # Convert to protobuf response
        return ValidateResponse(request_id=request_id, results=result)
```

### Validation Engine (Unchanged!)

```python
# validation_engine.py - No changes needed
class ValidationEngine:
    def validate(self, entity_type, entity_data, mode, required_data):
        # Works identically regardless of transport
        # Receives dict from bencode or Struct - doesn't care!
        ...
```

**Key Point:** The validation engine receives the same dict structure whether from bencode or gRPC. Only the transport layer changes.

### Migration Steps

1. **Write .proto definition** (1-2 hours)
2. **Generate Python gRPC stubs** (`python -m grpc_tools.protoc ...`)
3. **Implement GrpcTransportHandler** (2-4 hours)
4. **Create gRPC server wrapper** (2-4 hours)
5. **Update runner.py to use gRPC transport** (1 hour)
6. **Test end-to-end** (2-4 hours)

**Total Effort:** 1-2 days for Python side

**AI Assistance:** Can generate most boilerplate code (proto definition, transport handler, server setup)

---

## Why gRPC for Production?

### Performance Requirements

Modern banking systems require:
- **Inline Validation:** < 100ms latency for UX
- **High Throughput:** 100-1000 validations/sec during peak
- **Batch Processing:** Stream results as they complete

**Process Spawn Analysis:**
```
Scenario: 100 loan validations/sec inline

Pods Approach:
- 100 process spawns/sec × 100ms spawn overhead = 10 seconds of CPU time/sec
- Impossible to sustain without massive parallelism

gRPC Approach:
- 100 requests/sec × 5ms validation = 500ms of CPU time/sec
- Single Python service handles load easily
```

**Verdict:** Process spawn overhead makes pods unsuitable for high-frequency inline validation.

### Operational Maturity

Production systems need:

| Capability | Pods | gRPC |
|------------|------|------|
| Health Checks | Custom | Built-in (`grpc.health.v1.Health`) |
| Metrics | Custom | Prometheus interceptors |
| Distributed Tracing | Custom | OpenTelemetry support |
| Load Balancing | Manual | Client-side built-in |
| Circuit Breaking | Custom | Interceptor libraries |
| Rate Limiting | Custom | Interceptor libraries |
| Graceful Shutdown | Manual | Built-in |

**Verdict:** gRPC provides production-grade features out of the box.

### Ecosystem & Tooling

**gRPC Advantages:**
- ✅ **grpcurl:** Debug/test services from command line
- ✅ **grpc-gateway:** Auto-generate REST API alongside gRPC
- ✅ **Buf:** Protobuf linting, formatting, breaking change detection
- ✅ **BloomRPC/Postman:** GUI tools for testing
- ✅ **gRPC reflection:** Introspect services without .proto files

**Pods Advantages:**
- ✅ **Simplicity:** No extra tools needed for POC

**Verdict:** gRPC's rich ecosystem improves developer productivity.

### Scalability & Deployment

**Horizontal Scaling:**

Pods:
```
┌─────────┐      spawn      ┌────────┐
│ JVM 1   │────────────────►│ Python │ (spawned)
└─────────┘                 └────────┘

┌─────────┐      spawn      ┌────────┐
│ JVM 2   │────────────────►│ Python │ (spawned)
└─────────┘                 └────────┘

Each JVM spawns its own Python processes
```

gRPC:
```
┌─────────┐                 ┌────────────┐
│ JVM 1   │────┐            │  Python 1  │
└─────────┘    │            └────────────┘
               │   gRPC          ▲
┌─────────┐    ├────────────────┤
│ JVM 2   │────┤ Load Balancer  │
└─────────┘    │                ▼
               │            ┌────────────┐
┌─────────┐    │            │  Python 2  │
│ JVM 3   │────┘            └────────────┘
└─────────┘

Multiple JVMs share Python service pool
```

**Verdict:** gRPC enables better resource utilization and true service-oriented architecture.

### Streaming & Future Features

**Current:** Single request/response

**Future Possibilities with gRPC:**
- **Server Streaming:** Stream rule results as they execute
  ```protobuf
  rpc ValidateStream(ValidateRequest) returns (stream RuleResult);
  ```

- **Bidirectional Streaming:** Batch validation with streaming results
  ```protobuf
  rpc ValidateBatch(stream ValidateRequest) returns (stream ValidateResponse);
  ```

- **Async Processing:** Return immediately, notify on completion

**Verdict:** gRPC enables advanced patterns that pods cannot support.

### Cost & Resource Efficiency

**Pod Process Spawning:**
- 100 validations/sec × 50MB per process = 5GB memory churn
- CPU overhead for process creation/destruction

**gRPC Service:**
- 1 Python service × 200MB baseline = 200MB constant
- Request memory: 1KB per request

**Savings:** 95%+ memory reduction, significant CPU savings

**Verdict:** gRPC dramatically reduces infrastructure costs.

---

## Decision Framework

### When to Use Pods

✅ **POC/Prototype Phase**
- Validating architecture and rule interface
- < 10 requests/sec throughput
- Developer familiarity with Clojure/Babashka

✅ **Isolation Requirements**
- Need guaranteed process isolation per request
- Security boundary between requests

✅ **Simplicity Over Performance**
- Quick implementation more valuable than optimization
- Testing/staging environments with low load

### When to Use gRPC

✅ **Production Deployment**
- > 100 requests/sec throughput
- Latency requirements < 100ms
- Need for monitoring, tracing, metrics

✅ **High Availability Requirements**
- Service health checks
- Graceful degradation
- Load balancing across instances

✅ **Streaming Capabilities**
- Real-time result streaming
- Batch processing with progress updates

✅ **Enterprise Integration**
- Multi-language clients (Java, Go, etc.)
- Service mesh integration (Istio, Linkerd)
- API gateway compatibility

---

## Recommendation

### For Validation Service

**Phase 1 (POC):** Use Babashka Pods ✅
- Already implemented and working
- Validates architecture successfully
- Simple enough for POC scope

**Phase 2 (Production):** Migrate to gRPC ✅
- Performance requirements demand it
- Operational maturity needed for production
- Better long-term maintainability

### Migration Timeline

1. **Complete JVM Service POC with Pods** (Current)
   - Validate architecture
   - Measure actual performance
   - Identify bottlenecks

2. **Performance Analysis** (After POC)
   - Measure process spawn overhead impact
   - Determine throughput requirements
   - Calculate cost/benefit of gRPC migration

3. **gRPC Migration** (Phase 2)
   - AI-assisted .proto generation
   - AI-assisted GrpcTransportHandler implementation
   - AI-assisted Java client migration
   - Parallel deployment validation

### Decision Criteria

**Proceed with gRPC Migration if:**
- Process spawn overhead > 5% of total latency (likely yes)
- Inline validation throughput requirement > 50 requests/sec (likely yes)
- Batch processing needs streaming (possible future need)

**Stay with Pods if:**
- Throughput < 10 requests/sec (unlikely for production)
- No latency requirements (unlikely for UX-facing features)
- Isolation requirement outweighs performance (unlikely)

---

## Conclusion

**Both protocols support arbitrary JSON**, making them functionally equivalent for the validation service. The choice comes down to operational characteristics:

- **Pods:** Simple, isolated, but limited performance
- **gRPC:** Complex setup, but production-grade performance and features

The transport abstraction layer enables starting with pods (POC validation) and migrating to gRPC (production scaling) without changing the validation engine or rules.

**AI-assisted migration** will minimize implementation effort, making gRPC the clear choice for production deployment.

---

## References

**Babashka Pods:**
- Specification: https://github.com/babashka/pods
- Bencode Format: https://en.wikipedia.org/wiki/Bencode

**gRPC:**
- Official Docs: https://grpc.io/docs/
- Python Guide: https://grpc.io/docs/languages/python/
- Java Guide: https://grpc.io/docs/languages/java/
- Protobuf Struct: https://developers.google.com/protocol-buffers/docs/reference/google.protobuf#struct

**Related Documents:**
- [`../TECHNICAL-DESIGN.md`](../TECHNICAL-DESIGN.md) - Transport abstraction layer design
- [`PRODUCTIONIZATION.md`](./PRODUCTIONIZATION.md) - Section 8: JVM Service Migration
- [`CAPABILITIES.md`](./CAPABILITIES.md) - Component responsibilities

---

**Document Version:** 1.1
**Last Updated:** 2026-02-08
**Author:** Architecture Team
**Status:** Decision Guide - Active Planning
