import { createTimelineGestures } from './timeline-gestures.web';

test('the web scroll node accepts wheel, key and downward finger movement even at rest', () => {
  const region = Object.assign(new EventTarget(), { style: { overflowAnchor: '' }, tabIndex: -1 });
  const onIntent = jest.fn();
  const unbind = createTimelineGestures(onIntent).attach(region);
  const emit = (type: string, props: object) => region.dispatchEvent(Object.assign(new Event(type), props));
  expect(region.tabIndex).toBe(0);
  expect(region.style.overflowAnchor).toBe('none');
  emit('wheel', { deltaY: -3 });
  emit('keydown', { key: 'ArrowUp' });
  emit('keydown', { key: 'PageUp' });
  emit('touchstart', { touches: [{ clientY: 80 }] });
  emit('touchmove', { touches: [{ clientY: 101 }] });
  emit('wheel', { deltaY: 15 });
  expect(onIntent.mock.calls.flat()).toEqual(['newer', 'newer', 'newer', 'newer', 'older']);
  unbind();
  emit('wheel', { deltaY: -3 });
  expect(onIntent).toHaveBeenCalledTimes(5);
});
