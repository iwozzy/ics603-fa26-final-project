# Configurable search cache lifetime

Approved in conversation on 2026-11-15: make the search cache lifetime configurable and use 10 seconds for expiry tests.

Use the positive integer setting `SEARCH_CACHE_MAX_AGE_SECONDS`, defaulting to 300. Pass it through the composition root to HTTP services and use it for successful search response headers, including empty results. Errors remain `no-store`. Values above 10,000 seconds are supported.

## Approaches

Use runtime configuration rather than rewriting response headers in the browser or mocking time. This exercises the real backend and browser cache. Keeping the production duration in the expiry test would make future long lifetimes impractical to test.

The dedicated expiry command supplies a test-only Compose override of 10 seconds. Other browser tests retain 300 seconds. Check immediate reuse, wait 12 real seconds, then check a second provider dispatch. Keep the test opt-in and shorten its timeout. Document the setting and update the CI input description.
