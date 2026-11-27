import { render } from '@testing-library/react-native';
import type { PropsWithChildren } from 'react';
import { TimelineStore } from '../application/timeline-store';
import { ListTimeline } from '../application/use-cases/list-timeline';
import { TimelineProvider } from '../adapters/inbound/ui/TimelineProvider';
import TimelineScreen from '../adapters/inbound/ui/TimelineScreen';
import { FakeSessions } from './fakes/following';
import { DeferredTimeline } from './fakes/timeline';

export async function renderTimeline() {
  const sessions = new FakeSessions();
  const repository = new DeferredTimeline();
  const store = new TimelineStore(new ListTimeline(repository), sessions);
  const wrapper = ({ children }: PropsWithChildren) =>
    <TimelineProvider store={store} sessions={sessions}>{children}</TimelineProvider>;
  const view = await render(<TimelineScreen />, { wrapper });
  return { store, sessions, repository, view };
}
