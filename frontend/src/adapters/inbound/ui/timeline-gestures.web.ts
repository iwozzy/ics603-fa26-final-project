import type { TimelineDirection, TimelineGestureHandlers } from './timeline-gestures';

export type { TimelineDirection, TimelineGestureHandlers } from './timeline-gestures';

export function createTimelineGestures(onIntent: (direction: TimelineDirection) => void): TimelineGestureHandlers {
  return {
    touchHandlers: {},
    attach(scrollNode) {
      const node = scrollNode as HTMLElement | null;
      if (!node) return () => {};
      node.style.overflowAnchor = 'none';
      node.tabIndex = 0;
      let lastY: number | null = null;
      const wheel = (event: WheelEvent) => {
        if (!event.ctrlKey && event.deltaY !== 0) onIntent(event.deltaY < 0 ? 'newer' : 'older');
      };
      const keydown = (event: KeyboardEvent) => {
        if (event.key === 'ArrowUp' || event.key === 'PageUp' || event.key === 'Home') onIntent('newer');
        if (event.key === 'ArrowDown' || event.key === 'PageDown' || event.key === 'End') onIntent('older');
      };
      const touchstart = (event: TouchEvent) => { lastY = event.touches[0]?.clientY ?? null; };
      const touchmove = (event: TouchEvent) => {
        const y = event.touches[0]?.clientY;
        if (lastY !== null && y !== undefined && Math.abs(y - lastY) >= 4) {
          onIntent(y > lastY ? 'newer' : 'older');
          lastY = y;
        }
      };
      const finish = () => { lastY = null; };
      node.addEventListener('wheel', wheel, { passive: true });
      node.addEventListener('keydown', keydown);
      node.addEventListener('touchstart', touchstart, { passive: true });
      node.addEventListener('touchmove', touchmove, { passive: true });
      node.addEventListener('touchend', finish);
      node.addEventListener('touchcancel', finish);
      return () => {
        node.removeEventListener('wheel', wheel);
        node.removeEventListener('keydown', keydown);
        node.removeEventListener('touchstart', touchstart);
        node.removeEventListener('touchmove', touchmove);
        node.removeEventListener('touchend', finish);
        node.removeEventListener('touchcancel', finish);
      };
    },
  };
}
