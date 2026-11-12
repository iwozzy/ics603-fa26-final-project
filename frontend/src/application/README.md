`search-people.ts` contains F001's display summary, injected async search port, and
in-memory controller. The controller owns draft/submitted queries, validation,
loading/results, duplicate pending submissions, response sequencing, subscriptions,
and disposal. React and HTTP adapters consume this boundary; the core imports no
UI framework, browser API, provider type, or generated transport type.

Controller tests use fake promises to control response order and failure. Keep
future behavior behind this boundary only when an approved feature needs it.
