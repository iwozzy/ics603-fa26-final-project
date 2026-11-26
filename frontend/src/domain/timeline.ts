export interface MovieSummary {
  readonly id: number;
  readonly title: string;
  readonly overview: string | null;
  readonly posterImageUrl: string | null;
  readonly releaseDate: string;
}

export interface TimelinePosition {
  releaseDate: string;
  id: number;
}

export interface TimelineAnchor extends TimelinePosition {
  offset: number;
}

export type TimelineQuery =
  | { mode: 'initial'; limit?: number }
  | { mode: 'page'; direction: 'older' | 'newer'; cursor: string; limit?: number }
  | { mode: 'anchor'; anchor: TimelinePosition; limit?: number };

export interface TimelinePage {
  items: readonly MovieSummary[];
  olderCursor: string | null;
  newerCursor: string | null;
  asOf: string | null;
  anchorIndex: number | null;
}
