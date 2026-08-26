# Future Refactoring Tasks

This document tracks technical debt, refactoring tasks, and improvements that were identified but skipped in previous iterations. They are documented here for future consideration.

## REST API (`digitaltwins-api`)

The following items were identified during the REST API restructuring (`docs/features/2026-08-21-140800-rest-api-refactor`):

### 1. URL Path Consistency
* **Description**: The API paths currently use a mix of singular nouns and actions (e.g., `POST /assay`, `POST /dataset`). These should be updated to standard RESTful resource paths (e.g., `POST /assays`, `POST /datasets`).
* **Why skipped**: To avoid breaking existing platform tooling and frontend clients.
* **Mitigation Strategy**: Implement redirect aliases for old paths (e.g., `POST /assay` redirects to `POST /assays`) with deprecation warnings to ensure a smooth transition.

### 2. API Versioning
* **Description**: Add versioning to the API route prefixes (e.g., `/api/v1/...`).
* **Why skipped**: Considered an internal API, so versioning was deemed unnecessary for the initial refactoring scope.

### 3. Response Models
* **Description**: The API currently returns raw Python dictionaries for responses. These should be formalized into Pydantic models (e.g., `DatasetResponse`, `AssayResponse`) for automatic validation, OpenAPI documentation generation, and stricter contract enforcement.
* **Why skipped**: To keep the scope focused on router reorganization.

### 4. Service Layer Extraction
* **Description**: Route handlers in `assays.py` contain private helper functions (e.g., `_fetch_assay_configs`, `_discover_samples`, etc.). These could be extracted to a dedicated `services/` layer to decouple business logic from HTTP routing.
* **Why skipped**: Helpers were determined to be router-specific, and the `src/digitaltwins/core/` layer already acts as the primary service layer.

### 5. Async Handler Conversion
* **Description**: Many route handlers in the API are synchronous (`def` instead of `async def`). Converting them to `async` would improve concurrency and performance.
* **Why skipped**: Requires auditing underlying database and network dependencies (e.g., `requests`, synchronous DB drivers) to ensure they are async-compatible to prevent blocking the event loop.

### 6. Configuration Consolidation
* **Description**: Environment variables are currently accessed via scattered `os.getenv()` calls throughout the codebase. Consolidate these into a centralized configuration module (e.g., using `pydantic-settings`).
* **Why skipped**: Left as-is to minimize the scope of the routing refactor.

### 7. CORS Hardening
* **Description**: Review and restrict the Cross-Origin Resource Sharing (CORS) policy.
* **Why skipped**: Left as-is for the initial refactor.
