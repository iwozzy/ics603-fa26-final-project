import type { ViewProps } from 'react-native';

export type TimelineDirection = 'newer' | 'older';
export interface TimelineGestureHandlers {
  attach(node: unknown): () => void;
  touchHandlers: Pick<ViewProps, 'onTouchStart' | 'onTouchMove' | 'onTouchEnd' | 'onTouchCancel'>;
}

export function createTimelineGestures(onIntent: (direction: TimelineDirection) => void): TimelineGestureHandlers {
  let lastY: number | null = null;
  const finish = () => { lastY = null; };
  return {
    attach: () => () => {},
    touchHandlers: {
      onTouchStart: event => { lastY = event.nativeEvent.pageY; },
      onTouchMove: event => {
        const y = event.nativeEvent.pageY;
        if (lastY !== null && Math.abs(y - lastY) >= 4) {
          onIntent(y > lastY ? 'newer' : 'older');
          lastY = y;
        }
      },
      onTouchEnd: finish,
      onTouchCancel: finish,
    },
  };
}
