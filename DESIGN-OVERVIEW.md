# Validation Service - Functional Design

## Overview

This document describes the functional design of a validation service for commercial bank loan data. The service will validate data quality and business rules for deals, facilities, and loans.

This is a high-level design document intended for both business and technical audiences. The companion document TECHNICAL-DESIGN.md will contain detailed technical implementation specifications.

## Implementation Approach

### Phased Delivery

The validation service will be implemented in two phases:

**Phase 1 - Proof of Concept (POC)**

The POC phase will validate the architecture and test key assumptions about performance and usability. This phase will:
- Implement core functionality for deals, facilities, and loans
- Validate that sub-second response times are achievable for inline mode
- Test batch processing performance with realistic data volumes
- Prove that the rule framework is flexible and maintainable
- Gather feedback from rule authors on ease of rule development

**Lessons to be Learned from POC:**
- Performance characteristics: Is the architecture fast enough for production use?
- Operational patterns: How frequently do rules change? How often do validations fail?
- Scale requirements: What are typical batch file sizes? How many concurrent validations needed?
- Integration challenges: How reliable is the coordination service? Are there data quality issues?
- User experience: Is the error reporting clear? Are validation results actionable?

**Phase 2 - Production Implementation**

Based on POC learnings, the production implementation will:
- Incorporate performance optimizations if needed
- Add enterprise-grade operational tooling (monitoring, alerting, dashboards)
- Implement configuration management and rule deployment processes
- Scale to support production transaction volumes
- Integrate with enterprise security and access control systems

This phased approach reduces risk by validating assumptions before committing to full production deployment.

## Data Model

The service validates data within the following hierarchical structure:

- **Client**: A customer of the bank
  - **Deal**: An agreement between the client and the bank
    - **Facility**: A credit arrangement under the deal (a deal may have one or more facilities)
      - **Loan**: A specific loan instrument under a facility (a facility may have one or more loans)

In the first phase, the service will validate deals, facilities, and loans. Future phases will extend coverage to other data types such as client reference data.

A standardized data model will be used for all interactions with the service. The specific format (e.g., JSON Schema, Pydantic models) will be determined during technical design.

### Data Model Change Management

**Challenge**: The enterprise data models for deals, facilities, and loans evolve over time under their own governance processes. Model changes include:
- Field renaming (e.g., "amount" → "principal_amount")
- Restructuring (e.g., moving fields into nested objects)
- Data type changes (e.g., string → numeric)
- Adding new fields
- Removing deprecated fields

**Impact Without Protection**: If validation rules directly access the raw data model, every model restructuring would require updating all affected rules - potentially hundreds of rules needing simultaneous changes.

**Solution - Data Access Abstraction Layer**

The validation service implements an abstraction layer that isolates rules from internal model structure changes:

**How it Works**:
1. Each entity type (Deal, Facility, Loan) has a corresponding helper class
2. Helper classes provide stable property names (e.g., `loan.amount`, `facility.limit`)
3. Rules access data through these properties, not directly from the model
4. When the model structure changes, only the helper class is updated - rules remain unchanged

**Example Scenario**:

*Initial model structure*:
```
Loan data: { "amount": 500000, "currency": "USD" }
Rule code: loan.amount  (returns 500000)
```

*Model restructured* (moved to nested "financial" object):
```
Loan data: { "financial": { "principal_amount": 500000, "currency_code": "USD" } }
Rule code: loan.amount  (still returns 500000 - helper class updated internally)
```

**When Rules Must Change**:

Rules only need updating when:
- **New data added**: New model fields enable new validation rules (expected and desirable)
- **Data removed**: Deprecated fields removed from model require rules checking those fields to be retired

Rules do NOT need updating when:
- Model internally restructured (fields moved, renamed, reorganized)
- Data types changed (as long as business meaning is preserved)

**Benefits**:
- **Reduced maintenance**: Model restructuring doesn't trigger rule changes
- **Independent governance**: Model changes and rule changes can proceed on separate timelines
- **Lower risk**: Fewer changes reduce the chance of introducing errors
- **Faster model evolution**: Data model team can restructure without coordinating with all rule authors

This design recognizes that the enterprise data models and validation rules serve different purposes and should evolve independently. The abstraction layer acts as a stable contract between them.

## Operating Modes

The service operates in two distinct modes to support different business needs:

### Inline Mode

**Purpose**: Real-time validation during business processes

**Use Case Example**: A loan officer is entering a new facility into the system. Before submitting the facility for approval, they trigger validation to check for data quality issues. The service returns results within seconds, allowing the loan officer to correct any errors before proceeding.

**Characteristics**:
- Validates a single entity (one deal, facility, or loan)
- Returns results quickly for immediate feedback
- Typically uses a "quick" rule set with essential checks only

### Batch Mode

**Purpose**: Scheduled validation of multiple records

**Use Case Example**: The operations team runs a nightly validation job on all deals modified during the day. The service processes a file containing hundreds of deals and their related facilities and loans, validating each against the full rule set. Results are logged for reporting and remediation.

**Characteristics**:
- Validates multiple entities from file input
- Designed for overnight/scheduled processing
- Typically uses a "thorough" rule set with comprehensive checks

**Architectural Note**: Inline/batch mode controls **when** and **how** the JVM service calls validation (single vs. bulk, real-time vs. background). Separately, the JVM service specifies **which rule set** to execute (e.g., "quick", "thorough", "audit"). The Python runner is rule-set agnostic and simply executes the named rule set it receives.

## Validation Rules

### What is a Validation Rule?

A validation rule is executable code that checks a specific data quality or business rule condition. Each rule tests a single condition and returns one of four results:
- **PASS**: The data meets the rule's requirements
- **FAIL**: The data violates the rule (includes a meaningful error message)
- **NORUN**: The rule could not be executed (e.g., required data was unavailable, or parent rule failed)
- **ERROR**: The rule crashed during execution (exception thrown, indicates a bug in the rule code)

### Example Rules

To illustrate the scope and types of validation, here are representative examples:

1. **Facility Limit Check**
   - Description: "Loan amount must not exceed the facility limit"
   - Validates: Loan
   - Required data: Parent facility's limit amount

2. **Date Consistency Check**
   - Description: "Facility maturity date must be after deal origination date"
   - Validates: Facility
   - Required data: Parent deal's origination date

3. **Currency Consistency Check**
   - Description: "All loans under a facility must use the same currency as the facility"
   - Validates: Facility
   - Required data: All child loans

4. **Reference Data Freshness Check**
   - Description: "Client credit rating must have been updated within the last 90 days"
   - Validates: Deal
   - Required data: Related client reference data

### Rule Structure

Each rule is implemented with the following methods:

- `get_id()`: Returns a unique identifier for the rule (automatically provided by base class from filename)
- `validates()`: Specifies which entity type(s) the rule applies to (e.g., 'deal', 'facility', 'loan')
- `required_data()`: Declares what additional data is needed to run the rule
- `description()`: Returns a plain English description of what the rule checks
- `set_required_data()`: Receives the data needed to execute the rule
- `run()`: Executes the validation and returns the result

Rules inherit from `ValidationRule` base class which provides `get_id()`. The rule ID is automatically derived from the filename (e.g., `rule_001_v1.py` → rule ID `rule_001_v1`).

### Required Data Vocabulary

Rules may need data beyond the entity being validated. To ensure consistency, rules reference additional data using a fixed vocabulary:

**Hierarchical relationships**: `parent`, `all_children`, `all_siblings`, `parent's parent`, etc.

**Related entities**: `related_parties`, `parent's_legal_document`, `client_reference_data`, etc.

The vocabulary is strictly enforced by the service - rules cannot use free-form data references.

### Rule Configuration

The validation service uses configuration files to define named rule sets:

- **Quick Rules**: Essential checks for real-time validation (typically used during inline mode)
- **Thorough Rules**: Comprehensive checks for batch validation (typically used during batch mode)
- **Custom Rule Sets**: Audit rules, regulatory rules, or other specialized rule sets

The JVM service controls which rule set to use based on its orchestration mode and business requirements. The Python runner simply executes the requested rule set.

Rules can be organized hierarchically in configuration, where child rules only execute if their parent rule passes. For example:
- Parent rule: "Deal must have at least one facility"
- Child rule: "Each facility must have valid maturity date"

If the parent rule fails (no facilities exist), the child rule will not run.

### Rules Governance

**Ownership**: Validation rules are owned and maintained by the Commercial Bank's Data Team in consultation with their business partners.

**Change Process**:
1. **Proposal**: Business partners or the Data Team identify a need for a new rule or change to an existing rule
2. **Review**: The Data Team reviews the proposed rule for technical feasibility and alignment with data standards
3. **Approval**: Business stakeholders approve the rule definition and priority
4. **Implementation**: The Data Team implements and tests the rule
5. **Deployment**: The rule is deployed to the validation service and added to the appropriate configuration (inline and/or batch)
6. **Monitoring**: The Data Team monitors rule execution and effectiveness, adjusting as needed

**Rule Versioning and Updates**:

Rules are versioned to enable safe updates and rollbacks:
- Each rule has a version number (e.g., Rule 001 Version 1, Rule 001 Version 2)
- When a rule needs updating, a new version is created while the old version remains available
- The service configuration specifies which version of each rule to use
- This allows testing new rule versions in staging before promoting to production
- If a new rule version causes issues, the configuration can be quickly rolled back to the previous version

This versioning approach ensures that rule updates can be deployed safely with minimal risk to production operations.

Rule changes follow a controlled release process to ensure stability and traceability.

## How Validation Works

### Single Entity Validation (Inline Mode)

1. A request is made to validate a specific entity (deal, facility, or loan)
2. The service identifies which rules apply to that entity type based on the inline configuration
3. For each rule, the service:
   - Determines what additional data is required
   - Fetches that data from the coordination service
   - Provides the data to the rule
   - Executes the rule
4. Rules are executed sequentially, respecting hierarchical dependencies
5. Results are collected for all rules (PASS/FAIL/NORUN/ERROR plus error messages)
6. Results are returned to the caller and logged

### Batch Validation

1. A file containing multiple entities is provided to the service
2. The service processes each entity using the batch configuration
3. The validation process for each entity follows the same steps as inline mode
4. Results are aggregated and logged
5. Summary results are made available for reporting

### Data Fetching

The validation service retrieves additional data through the **Coordination Service**, which provides access to:
- Related entities in the hierarchy (parents, children, siblings)
- Associated reference data (client information, legal documents, etc.)
- Historical data when needed for temporal checks

### Results and Logging

All validation results are persisted in a centralized log, capturing:
- Entity validated (type and identifier)
- Rules executed
- Results for each rule (PASS/FAIL/NORUN/ERROR)
- Error messages for failures and rule crashes
- Timestamp and validation mode (inline or batch)

This log provides an audit trail and supports operational reporting on data quality.

## Scalability

The service is designed to support multiple concurrent instances, allowing horizontal scaling to handle increased validation volume as needed.

## Future Phases

After the initial implementation covering deals, facilities, and loans, the service will be extended to validate additional data types such as:
- Client reference data
- Legal documents
- Collateral information
- Other commercial banking entities as requirements emerge
