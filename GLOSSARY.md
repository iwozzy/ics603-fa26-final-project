# Movie discovery

Shared vocabulary for discovering movies and tracking movie interests and viewing activity.

## Language

**Demo user**:
The shared user used by all visitors initially, whose saved movie activity is publicly available. Its Follows and Watchlist belong to that user, just as they do for a Personal user.
_Avoid_: Anonymous personal user, private default user

**User**:
An individual user whose Follows and Watchlist are private and belong to the same identity across devices and sign-in methods.
_Avoid_: Device user, Demo user (when referring to private personal ownership)

**Movie**:
A distinct movie whose identity is independent of its title or the catalog provider describing it.
_Avoid_: Title (when referring to the movie itself)

**Person**:
An individual who participates in movies as cast, crew, or both, regardless of the roles they hold across movies.
_Avoid_: Actor record, crew member record (as separate identities for the same person)

**Credit**:
A person's participation in a particular movie, including their role in that movie.
_Avoid_: Follow (when describing participation in a movie)

**Follow**:
A user's interest in a person across that person's cast and crew credits.
_Avoid_: Role subscription

**Seen status**:
Whether a user has marked a movie as watched, independently of their intention to watch it again.
_Avoid_: Watch status (when describing whether a movie has already been watched)

**Watchlist**:
A user's explicitly saved movies, including movies already seen and movies intended for future or repeat viewing. A saved movie remains in the Watchlist until removed, regardless of its seen status or watch status.
_Avoid_: Unseen queue, Movie tracking (as an alternative name for the same collection)

**Watchlist entry**:
A user's saved relationship with a particular movie, including its seen status and watch status.
_Avoid_: Separate seen-movie identity, Separate rewatch-movie identity

**Watch status**:
Whether a user intends to watch a movie, including watching it again, independently of its seen status.
_Avoid_: Seen status (when describing future viewing intent)

**Timeline**:
A user's chronological, deduplicated list of movies contributed by followed people's credits or the user's Watchlist. Each movie appears once even when several follows or a Watchlist entry contribute it.
Semantic search filters this list by storyline meaning while preserving its presentation and other active filters.
_Avoid_: Watchlist (when referring to the combined list)

**Timeline ruler**:
A time scale for navigating directly to a chosen part of a user's Timeline.

**Movie suggestion**:
A proposed movie for a user to watch, whether or not it is in their Timeline. A suggestion may remain unverified against a catalog.
_Avoid_: Candidate movie (for an unvalidated suggestion), Timeline search result (when referring to a suggestion)

**Extracted title**:
A movie title identified in a note or photo, used to look for matching movies in a catalog.
_Avoid_: Validated movie (before a provider match exists)

**Candidate movie**:
A movie validated against a catalog provider as a possible match for an extracted title, awaiting the user's selection.
_Avoid_: Confirmed selection (before the user chooses it)
