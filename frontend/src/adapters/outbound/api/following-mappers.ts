import type { FollowingSnapshot } from '../../../domain/following';
import { zFollowingResponse } from './generated/zod.gen';
import { mapPerson } from './mappers';
export function mapFollowingSnapshot(value: unknown): FollowingSnapshot {
  const dto = zFollowingResponse.parse(value);
  return { limit: dto.limit, people: dto.people.map(mapPerson) };
}
