import { describe, expect, it } from 'vitest';
import { runTechnicalAnalysisMode } from '../utils/technicalAnalysisModes';

describe('runTechnicalAnalysisMode livePrice sync', () => {
  it('usa livePrice en lugar del cierre diario previo en la explicación de AT', () => {
    const startMs = Date.UTC(2026, 0, 1);
    const candles = Array.from({ length: 90 }, (_, i) => {
      const base = 550 + Math.sin(i / 2.2) * 35 + i * 0.4;
      const dt = new Date(startMs + i * 86_400_000).toISOString().slice(0, 10);
      return {
        time: dt,
        open: base - 2,
        high: base + 5,
        low: base - 5,
        close: i === 89 ? 589.82 : base,
        volume: 1_000_000 + i * 10_000,
      };
    });

    const res = runTechnicalAnalysisMode(candles, 'elliott', { livePrice: 609.89 });
    expect(res).not.toBeNull();
    expect(res.explanation.drawnElements).toContain('Precio actual: $609.89');
    expect(res.explanation.drawnElements).not.toContain('Precio actual: $589.82');
  });
});
