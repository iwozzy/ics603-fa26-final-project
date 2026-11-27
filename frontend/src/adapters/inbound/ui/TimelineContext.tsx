import { createContext } from 'react';
import type { TimelineStore } from '../../../application/timeline-store';
import type { GuestSessionRepository } from '../../../application/ports/guest-session-repository';

export interface TimelineServices {
  store: TimelineStore;
  sessions: Pick<GuestSessionRepository, 'identityGeneration'>;
}

export const TimelineContext = createContext<TimelineServices | null>(null);
