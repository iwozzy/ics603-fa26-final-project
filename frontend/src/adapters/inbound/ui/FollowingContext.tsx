import { createContext } from 'react';
import type { FollowingStore } from '../../../application/following-store';
export const FollowingContext = createContext<FollowingStore | null>(null);
