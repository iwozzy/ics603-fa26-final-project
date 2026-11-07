# Choose identity and session boundaries for web and native clients

Type: grilling
Labels: wayfinder:grilling
Status: open
Parent: [Architecture for a shared web and native movie-discovery app](../map.md)
Blocked by: 04, 05, 06

## Question

What identity/session strategy serves V1 and allows later real accounts across web, iOS, and Android? Determine anonymous versus registered ownership, account migration/linking needs, browser and native credential storage, restart persistence, authorization enforcement, and deletion expectations. Separate long-term ownership/authentication boundaries from a replaceable provider and UI. Resolve enough to prevent expensive data ownership and client-contract changes; do not implement authentication.
