# Integration Tests: End-to-End Testing (YAM-20 Phase 4)

## Overview

This document describes the integration test suite for the NBN Address Lookup Bot, implemented in `test_integration_e2e.py`.

## Objective

**YAM-20** requires comprehensive end-to-end integration testing that verifies:
1. Full workflow from free-text address input through Iperium API to formatted result
2. Proper data flow transformations across service boundaries
3. Graceful error handling when any component fails
4. Bot handler orchestration of the NBN service
5. Result formatting across various address types and response variations

## Test Coverage

The integration test suite contains **16 test cases** organized into 4 categories:

### 1. Full Flow Tests (3 tests)
- **`test_e2e_address_lookup_success`**: Standard address (street number + street name)
  - Verifies: geocoder → Iperium API → result parsing chain
  - Validates all result fields are correctly mapped

- **`test_e2e_unit_apartment_lookup`**: Unit/apartment address
  - Tests: unit and level components passed to Iperium
  - Ensures complex addresses handled correctly

- **`test_e2e_lot_based_address_lookup`**: Lot-based rural address
  - Tests: lot number conversion and handling
  - Verifies optional fields (street number) properly excluded

### 2. Error Handling Tests (4 tests)
- **`test_e2e_geocoding_failure`**: Geocoder returns error
  - Expects: ValueError propagated, Iperium never called
  - Validates: fail-fast on geocoding errors

- **`test_e2e_missing_required_fields`**: Geocoder returns incomplete address
  - Tests: suburb, state, postcode validation
  - Ensures: Iperium not called with invalid data

- **`test_e2e_iperium_api_error`**: Iperium API connection failure
  - Verifies: API errors propagate correctly
  - Confirms: error handling in service layer

- **`test_e2e_iperium_no_results`**: Valid address but not in NBN database
  - Tests: empty result handling (returns empty list, not error)
  - Validates: graceful degradation

### 3. Bot Handler Integration Tests (5 tests)
- **`test_bot_handler_e2e_lookup_flow`**: Standard bot message → result display
  - Verifies: handler → service → Telegram edit_text flow
  - Validates: result formatting for Telegram markdown

- **`test_bot_handler_e2e_multiple_results`**: Address matches multiple locations
  - Tests: "Result 1:", "Result 2:" formatting
  - Ensures: multiple addresses displayed clearly

- **`test_bot_handler_e2e_no_serviceable_address`**: Address not serviceable
  - Validates: user-friendly "No NBN results" message

- **`test_bot_handler_e2e_geocoding_error_handling`**: Invalid address input
  - Tests: "Could not geocode address" error message

- **`test_bot_handler_e2e_iperium_failure`**: API error during lookup
  - Verifies: generic error message + "try again later" guidance

### 4. Result Formatting Tests (3 tests)
- **`test_e2e_result_formatting_full`**: All fields populated
  - Tests: complete NBN result display (address, tech, service class, status, FOD)

- **`test_e2e_result_formatting_partial`**: Some fields missing
  - Validates: None fields omitted from output
  - Ensures: clean formatting without "None" values

- **`test_e2e_result_formatting_empty`**: All fields None
  - Tests: fallback message "No details available."

### 5. Data Transformation Tests (1 test)
- **`test_e2e_iperium_response_parsing_variants`**: Alternative Iperium field names
  - Tests: fallback field names (id → locId, address → formattedAddress, etc.)
  - Validates: robust parsing of API response variations

## Running the Tests

### Prerequisites
```bash
pip install -r requirements.txt
```

### Execute All Integration Tests
```bash
pytest tests/test_integration_e2e.py -v
```

### Run Specific Test Category
```bash
# Full flow tests
pytest tests/test_integration_e2e.py::test_e2e -v

# Error handling tests
pytest tests/test_integration_e2e.py -k "test_e2e_[geocoding|missing|iperium|no_results]" -v

# Bot handler tests
pytest tests/test_integration_e2e.py -k "test_bot_handler" -v

# Result formatting tests
pytest tests/test_integration_e2e.py -k "test_e2e_result_formatting" -v
```

### Run With Coverage
```bash
pytest tests/test_integration_e2e.py --cov=bot --cov=gmaps --cov=iperium --cov-report=html
```

## Test Architecture

### Mocking Strategy
The integration tests use **unit mocks** but test **integration flows**:
- Mock external APIs (Iperium, Google Maps) to avoid dependency on real services
- Mock Telegram Update/Context for bot handler tests
- Real NBNService and handler code executes unchanged
- Real data transformation logic verified

### Key Fixtures
- **`mock_jwt_token`**: Valid JWT token with exp claim
- **`mock_iperium_response`**: Realistic Iperium API response
- **`mock_StandardizedAddress`**: Typical geocoded address structure

### Data Flow Pattern
Each test follows:
1. **Setup**: Create mock clients and service instance
2. **Execute**: Call high-level function (service.lookup or handle_message)
3. **Verify**: Assert
   - Correct methods called with expected arguments
   - Result data correctly transformed
   - Errors handled appropriately

## Coverage Summary

✅ **Happy Path**: Standard addresses → NBN results  
✅ **Variants**: Units, apartments, lots, rural addresses  
✅ **Error Cases**: Geocoding failures, incomplete data, API errors, no results  
✅ **Bot Handler**: Message handling, error messages, Telegram integration  
✅ **Result Formatting**: Full, partial, and empty results  
✅ **API Variations**: Alternative Iperium response field names  

## Known Limitations

1. **No Real API Calls**: Mocked responses only (by design—avoids test flakiness and rate limits)
2. **No Async Concurrency Tests**: Single-threaded test flow (future enhancement)
3. **No Token Refresh Testing**: Iperium token refresh tested separately in unit tests
4. **No Network Timeout Simulation**: Would require httpx-specific mocking (future enhancement)
5. **No Telegram Rate Limiting**: Bot rate limiting not tested (Telegram SDK responsibility)

## Future Enhancements

1. Add contract tests against real Iperium/Google Maps responses (staging environment)
2. Test concurrent address lookups (async concurrency)
3. Test token refresh edge cases in integration context
4. Add performance benchmarks (response time thresholds)
5. Test full bot application (build_application + mock Telegram client)
6. Add stress tests (high volume of concurrent lookups)

## Integration Test vs. Unit Tests

| Aspect | Unit Tests | Integration Tests |
|--------|-----------|------------------|
| **Mocking** | Heavy (all dependencies) | Selective (APIs only, services real) |
| **Scope** | Single component | Multi-component workflows |
| **Files** | test_iperium.py, test_googlemaps.py, test_nbn_service.py, test_bot_handlers.py | test_integration_e2e.py |
| **Purpose** | Component correctness | Workflow correctness |
| **Failures reveal** | Bug in single component | Integration bug or data transform bug |

## Maintenance

- **Update when**: Adding new address types, response fields, error cases, or bot features
- **Keep in sync with**: NBNService, GoogleMapsGeocoder, IperiumClient, bot handlers
- **Related docs**: See README.md for setup and architecture overview
