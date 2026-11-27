import { TimelineStore } from '../application/timeline-store';
import { ListTimeline } from '../application/use-cases/list-timeline';
import { HttpTimelineRepository } from '../adapters/outbound/api/timeline-repository';
import { FollowingStore } from '../application/following-store';
import { FollowPerson } from '../application/use-cases/follow-person';
import { UnfollowPerson } from '../application/use-cases/unfollow-person';
import { ListFollowing } from '../application/use-cases/list-following';
import { HttpFollowingRepository } from '../adapters/outbound/api/following-repository';
import { SearchPeople } from '../application/use-cases/search-people';
import { HttpGuestSessionRepository } from '../adapters/outbound/api/guest-session-repository';
import { HttpPeopleSearchRepository } from '../adapters/outbound/api/people-search-repository';
export function createContainer(fetchImpl: typeof fetch) {
  const sessions = new HttpGuestSessionRepository(fetchImpl);
  const following = new HttpFollowingRepository(fetchImpl, sessions);
  const followingStore = new FollowingStore(new ListFollowing(following), new FollowPerson(following), new UnfollowPerson(following), sessions);
  const timelineStore = new TimelineStore(new ListTimeline(new HttpTimelineRepository(fetchImpl, sessions)), sessions);
  return { followingStore, timelineStore, sessions, searchPeople: new SearchPeople(new HttpPeopleSearchRepository(fetchImpl, sessions)) };
}
