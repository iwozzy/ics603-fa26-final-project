export interface GuestSessionRepository { ensure(signal: AbortSignal): Promise<void>; invalidate(): void; }
