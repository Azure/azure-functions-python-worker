# Runtime Base Extension Design Proposal

## Executive Summary

This document proposes a base extension pattern for Azure Functions Python Worker that enables seamless addition of new runtime frameworks (FastAPI, Flask, Django, etc.) without requiring proxy worker code changes. The solution uses metaclass-based automatic registration, inspired by the proven `azurefunctions-extensions-base` architecture used for HTTP streaming.

---

## 1. Problem Statement

### Current Challenges

The Azure Functions Python Worker currently supports multiple programming models (V1 with function.json, V2 with decorators), but adding new runtime frameworks presents several challenges:

**1.1 Hardcoded Runtime Detection**
- The proxy worker (`dispatcher.py`) contains hardcoded logic to detect and load runtimes
- Adding FastAPI required explicit try-import statements and detection logic
- Each new runtime (Flask, Django, etc.) would require modifying `dispatcher.py`

**1.2 Maintenance Burden**
- Every new runtime necessitates proxy worker changes
- Creates tight coupling between proxy worker and runtime implementations
- Difficult to test runtimes in isolation

**1.3 Extensibility Limitations**
- Third-party runtime packages cannot be added without worker changes
- Community contributions are difficult to integrate
- No clear contract for what a runtime must implement

### Requirements

A solution must:
- Allow adding new runtimes without proxy worker changes (after initial base integration)
- Provide clear abstractions and contracts for runtime implementations
- Maintain backward compatibility with existing V1/V2 runtimes
- Support automatic runtime discovery and registration
- Ensure type safety and enforce required method implementations
- Enable third-party runtime packages
- Minimize performance overhead

---

## 2. Proposed Solution Overview

### 2.1 Solution Approach

Implement a **runtime base package** using metaclass-based automatic registration, following the proven pattern from `azurefunctions-extensions-base` used for HTTP streaming extensions.

### 2.2 Key Concepts

**Base Package (`runtimes/base/`)**
- Provides abstract base classes defining the runtime contract
- Uses metaclasses to automatically register runtime implementations at import time
- Acts as the single point of integration with the proxy worker

**Runtime Implementations** (FastAPI, Flask, etc.)
- Extend the base package's abstract classes
- Auto-register via metaclass when imported
- Implement required event handler methods

**Proxy Worker Integration**
- Imports only the base package
- Queries base for registered runtime
- Dynamically loads the appropriate runtime module

### 2.3 High-Level Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. Worker Startup                                               │
│    - Proxy worker imports runtimes.base                         │
│    - Detects which runtime to use (FastAPI, Flask, V2, V1)      │
│    - Imports that runtime package                               │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. Automatic Registration (Metaclass Magic)                     │
│    - Runtime class definition executes                          │
│    - RuntimeTrackerMeta.__new__ fires automatically             │
│    - Runtime module name stored in metaclass                    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. Runtime Discovery                                            │
│    - Proxy worker queries: RuntimeTrackerMeta.get_module()      │
│    - Base returns: "azure_functions_fastapi.runtime"    │
│    - Worker dynamically imports the runtime module              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. Event Handling                                               │
│    - Worker calls runtime.worker_init_request()                 │
│    - Runtime executes FastAPI-specific logic                    │
│    - Returns standard protobuf responses                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Design Overview

### 3.1 Architecture Components

#### 3.1.1 Runtime Base Package (`runtimes/base/`)

**File Structure:**
```
runtimes/base/
├── __init__.py       # Package exports
└── runtime.py        # Core abstractions
```

**Core Classes:**

**RuntimeTrackerMeta (Metaclass)**
```python
class RuntimeTrackerMeta(type):
    _module = None          # Stores registered module name
    _runtime_name = None    # Stores runtime identifier
    
    def __new__(cls, name, bases, dct, **kwargs):
        # Auto-registers runtime on class definition
        new_module = dct.get("__module__")
        if new_module != base_runtime_module:
            cls._module = new_module  # Store module!
            cls._runtime_name = dct.get("runtime_name")
        return new_class
```

**Key Features:**
- Automatic registration at import time (no explicit calls needed)
- Single runtime enforcement (prevents multiple runtimes)
- Zero-overhead registration (happens once at class definition)

**RuntimeBase (Abstract Base Class)**
```python
class RuntimeBase(metaclass=RuntimeTrackerMeta):
    runtime_name = None  # Must be set by subclass
    
    @abstractmethod
    async def worker_init_request(self, request): ...
    
    @abstractmethod
    async def functions_metadata_request(self, request): ...
    
    @abstractmethod
    async def function_load_request(self, request): ...
    
    @abstractmethod
    async def invocation_request(self, request): ...
    
    @abstractmethod
    async def function_environment_reload_request(self, request): ...
```

**Key Features:**
- Enforces contract via abstract methods
- Python's type system ensures implementations are complete
- Clear documentation of required methods

**RuntimeFeatureChecker (Utility)**
```python
class RuntimeFeatureChecker:
    @staticmethod
    def runtime_loaded(): ...
    
    @staticmethod
    def get_runtime_name(): ...
```

#### 3.1.2 Runtime Implementation (Example: FastAPI)

**File Structure:**
```
runtimes/fastapi/azure_functions_fastapi/
├── __init__.py           # Imports Runtime class
├── runtime.py            # Runtime class extending base
├── handle_event.py       # Event handler implementations
├── handler.py            # Request/response handling
├── indexer.py            # FastAPI app indexing
└── ...                   # Other modules
```

**Runtime Class:**
```python
from runtimes.base import RuntimeBase

class Runtime(RuntimeBase):
    runtime_name = "fastapi"  # Identifies this runtime
    
    async def worker_init_request(self, request):
        return await worker_init_request(request)
    
    # ... other methods delegate to existing handlers
```

**Registration Flow:**
```
import azure_functions_fastapi
    ↓
Runtime class is defined
    ↓
RuntimeTrackerMeta.__new__ executes
    ↓
Module "azure_functions_fastapi.runtime" stored
    ↓
Runtime is now registered! ✓
```

#### 3.1.3 Proxy Worker Integration

**Updated `dispatcher.py`:**
```python
def reload_library_worker(directory: str):
    import runtimes.base as runtime_base
    
    # Detect which runtime to use
    if is_fastapi_app(directory):
        import azure_functions_fastapi  # Auto-registers!
    elif is_v2_app(directory):
        import azure_functions_runtime
    else:
        import azure_functions_runtime_v1
    
    # Check if runtime registered
    if runtime_base.RuntimeFeatureChecker.runtime_loaded():
        module_name = runtime_base.RuntimeTrackerMeta.get_module()
        runtime_module = importlib.import_module(module_name)
        _library_worker = runtime_module
```

### 3.2 Registration Mechanism

**How Metaclass Registration Works:**

1. **Class Definition Phase** (Import Time)
   ```python
   class Runtime(RuntimeBase):  # Metaclass is RuntimeTrackerMeta
       runtime_name = "fastapi"
   ```

2. **Metaclass `__new__` Fires**
   - Python calls `RuntimeTrackerMeta.__new__()` automatically
   - Extracts `__module__` from class definition
   - Stores in class variable `_module`

3. **Discovery Phase** (Runtime)
   ```python
   RuntimeTrackerMeta.get_module()  # Returns stored module name
   ```

**Why This Works:**
- No explicit registration calls needed
- Happens automatically at import time
- Zero runtime overhead (registration is one-time)
- Thread-safe (class definition is atomic)

### 3.3 Event Handler Contract

All runtimes must implement these async methods:

| Method | Purpose | Input | Output |
|--------|---------|-------|--------|
| `worker_init_request()` | Initialize runtime, discover functions | WorkerInitRequest | WorkerInitResponse |
| `functions_metadata_request()` | Return discovered function metadata | FunctionMetadataRequest | FunctionMetadataResponse |
| `function_load_request()` | Verify/load specific function | FunctionLoadRequest | FunctionLoadResponse |
| `invocation_request()` | Execute function invocation | InvocationRequest | InvocationResponse |
| `function_environment_reload_request()` | Reload environment (Linux Consumption) | FunctionEnvironmentReloadRequest | FunctionEnvironmentReloadResponse |

### 3.4 Sequence Diagrams

**Runtime Loading Sequence:**
```
Proxy Worker          Base Package          Runtime Package
     |                     |                        |
     |--import runtimes.base--->|                   |
     |<----[base loaded]-------|                    |
     |                     |                        |
     |--import azure_functions_fastapi---->|
     |                     |<--metaclass registers--|
     |                     |   (auto-registration)  |
     |                     |                        |
     |--get_module()------>|                        |
     |<--"...fastapi.runtime"-|                     |
     |                     |                        |
     |--importlib.import_module("...runtime")----->|
     |<--runtime module-----------------------------|
```

**Function Invocation Sequence:**
```
Proxy Worker          Runtime Module         FastAPI App
     |                     |                        |
     |--invocation_request()-->|                    |
     |                     |--parse request----     |
     |                     |--extract path params-  |
     |                     |--execute_fastapi_route()-->|
     |                     |                    |--route handler-->
     |                     |                    |<--result---------|
     |                     |<--response-------------|
     |<--InvocationResponse-|                        |
```

---

## 4. Benefits

### 4.1 Extensibility
✅ **Add New Runtimes Without Worker Changes**
- Flask, Django, Bottle, etc. can be added by creating new packages
- No modifications to `dispatcher.py` after initial base integration
- Third-party runtimes possible

✅ **Clear Contract**
- `RuntimeBase` defines exact interface
- Abstract methods enforce implementation
- Type hints provide IDE support

### 4.2 Maintainability
✅ **Separation of Concerns**
- Runtime logic isolated in runtime packages
- Proxy worker only handles orchestration
- Each runtime can be tested independently

✅ **Reduced Coupling**
- Proxy worker depends only on base package
- Runtimes are interchangeable
- Changes to one runtime don't affect others

✅ **Code Reuse**
- Common patterns abstracted in base
- Utilities can be shared across runtimes
- Consistent error handling

### 4.3 Developer Experience
✅ **Simple Runtime Creation**
```python
# Just extend RuntimeBase and implement methods!
from runtimes.base import RuntimeBase

class Runtime(RuntimeBase):
    runtime_name = "flask"
    async def worker_init_request(self, request): ...
```

✅ **Auto-Discovery**
- No registration boilerplate
- Import = registration (metaclass magic)
- Intuitive for developers

✅ **Type Safety**
- Abstract base ensures all methods implemented
- Python type system catches missing methods
- Better IDE autocomplete and error detection

### 4.4 Performance
✅ **Zero Runtime Overhead**
- Registration happens once at import time
- No performance penalty during function execution
- Metaclass overhead is negligible (one-time)

✅ **Lazy Loading**
- Only the detected runtime is imported
- Other runtimes stay unloaded
- Minimal memory footprint

### 4.5 Backward Compatibility
✅ **Gradual Migration**
- V1 and V2 runtimes work unchanged
- Can extend them with base later
- Fallback logic for non-base runtimes

✅ **No Breaking Changes**
- Existing function apps continue working
- Optional adoption of base pattern
- Transparent to end users

---

## 5. Potential Issues and Mitigations

### 5.1 Metaclass Complexity

**Issue:** Metaclasses can be difficult to understand and debug.

**Mitigation:**
- Comprehensive documentation with examples
- Clear logging of registration events
- Well-tested base package
- Inspired by proven pattern (`azurefunctions-extensions-base`)

### 5.2 Single Runtime Limitation

**Issue:** Only one runtime can be registered at a time (enforced by metaclass).

**Mitigation:**
- This is intentional and desired behavior
- Function apps should use one runtime consistently
- Clear error message if multiple runtimes imported
- Matches behavior of HTTP streaming extensions

### 5.3 Import-Time Side Effects

**Issue:** Registration happens at import time (not explicit).

**Mitigation:**
- This is standard Python practice for plugins
- Similar to how decorators and metaclasses work
- Well-documented in code and guides
- Predictable behavior (always happens on import)

### 5.4 Detection Logic Still Needed

**Issue:** Proxy worker still needs logic to decide which runtime to import.

**Mitigation:**
- Detection is simple file pattern matching
- Can be improved with manifest files (future work)
- Detection happens before import (not runtime-specific)
- Much simpler than full runtime integration

### 5.5 Third-Party Runtime Security

**Issue:** Third-party runtimes could execute arbitrary code.

**Mitigation:**
- Same risk as any third-party Python package
- Runtimes must be explicitly installed
- Package signing and verification (future work)
- Trust model same as V2 programming model

---

## 6. Implementation Details

### 6.1 File Structure

```
azure-functions-python-extensions/
├── azurefunctions-extensions-bindings-base/
│   ├── azurefunctions/extensions/bindings/base/                         # Runtime base package ⭐ NEW
│   │   ├── __init__.py
        └── runtime.py
```

### 6.2 Key Code Changes

**1. Proxy Worker Update:**
- Import `azurefunctions.extensions.bindings.base` when indexing
- Query base for registered runtime
- Dynamic import using `importlib.import_module()`
- Fallback to traditional detection for backward compatibility

### 6.3 Migration Path

**Phase 1: FastAPI (Current)**
- ✅ Create base package
- ✅ Update FastAPI runtime to extend base
- ✅ Update proxy worker to use base
- ✅ Test with FastAPI apps

**Phase 2: New Runtimes (Future)**
- Flask runtime using base
- Django runtime using base
- Community-contributed runtimes

---


## 7. Conclusion

The runtime base extension pattern provides a clean, maintainable, and extensible solution for adding new runtime frameworks to Azure Functions Python Worker. By leveraging metaclass-based automatic registration (proven by `azurefunctions-extensions-base`), we achieve:

- ✅ Zero proxy worker changes for new runtimes (after initial base integration)
- ✅ Clear contract via abstract base classes
- ✅ Automatic discovery and registration
- ✅ Type safety and IDE support
- ✅ Backward compatibility with existing runtimes
- ✅ Foundation for community-contributed runtimes

The implementation is straightforward, well-tested, and ready for production use with FastAPI. It provides a clear path for adding Flask, Django, and other frameworks in the future.

---

## 8. References

- **HTTP Streaming Pattern:** `azurefunctions-extensions-base` and `azurefunctions-extensions-http-fastapi`
- **Python Metaclasses:** [PEP 3115](https://www.python.org/dev/peps/pep-3115/)
- **Abstract Base Classes:** [PEP 3119](https://www.python.org/dev/peps/pep-3119/)
- **Azure Functions Python Worker:** Current architecture and design

---

## Appendix A: Code Samples

### Complete RuntimeBase Implementation

See `runtimes/base/runtime.py` for full implementation.

### Complete FastAPI Runtime

See `runtimes/fastapi/azure_functions_fastapi/runtime.py` for full implementation.

### Proxy Worker Integration

See `workers/proxy_worker/dispatcher.py` for integration code.
