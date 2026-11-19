// Platform APIs used by adapters; Node supplies these in browser tests.
if (!AbortSignal.any) AbortSignal.any = (signals) => { const controller = new AbortController(); for (const signal of signals) { if (signal.aborted) controller.abort(); signal.addEventListener('abort', () => controller.abort(), { once: true }); } return controller.signal; };
