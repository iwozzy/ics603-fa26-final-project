// React Aria's test-only initialization expects screen.orientation even in RN tests.
if (typeof window !== 'undefined' && !window.screen) {
  window.screen = { orientation: {} };
}

// Native component tests do not run Metro's generated style engine.
// The browser suite verifies the actual theme and layout.
jest.mock('uniwind', () => ({ Uniwind: { setTheme: jest.fn() } }));
/* global jest */
