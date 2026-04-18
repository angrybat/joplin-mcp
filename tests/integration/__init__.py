"""
Integration test suite for joplin-mcp.

Tests in this directory run against a live MCP server backed by a seeded Joplin
instance. They are executed exclusively by the Dagger `integration-tests` stage
and are the sole blocking gate for `publish-image`.

All tests MUST:
  - Use fixture data from fixtures/definitions/ (do not hardcode data)
  - Assert against expected outputs from fixtures/expected/
  - Fail if fixture.lock does not match (checked by conftest.py)
  - Be deterministic and idempotent

See PLAN.md Stage: integration-tests for the full test contract.
"""
