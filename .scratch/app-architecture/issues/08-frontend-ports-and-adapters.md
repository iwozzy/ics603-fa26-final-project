# Define shared frontend boundaries and platform adapters

Type: grilling
Labels: wayfinder:grilling
Status: open
Parent: [Architecture for a shared web and native movie-discovery app](../map.md)
Blocked by: 05, 07

## Question

Given the client-platform direction and backend boundaries, what frontend domain/application logic, state, contracts, and presentation can be shared, and which browser/iOS/Android concerns need adapters? Decide how validation, API access, session storage, camera/photo access, navigation, and platform lifecycle concerns relate to ports and adapters. Establish a package/dependency direction that supports future native apps without implementing them now or assuming Python Pydantic models execute on every client.
