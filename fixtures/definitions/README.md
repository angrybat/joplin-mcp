# Fixture Definitions
#
# JSON or YAML files in this directory define the canonical set of notes,
# notebooks, and tags used for both Postgres seeding and integration assertions.
#
# All definitions MUST be:
#   - Deterministically ordered (alphabetically by key)
#   - Free of wall-clock timestamps (use sentinel values like "2000-01-01T00:00:00Z")
#   - Validated against fixture.lock before each test run
#
# See PLAN.md Stage: fixture-data for the full fixture contract.
