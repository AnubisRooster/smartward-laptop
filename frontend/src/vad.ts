/** Finds where you start and stop speaking in a stream of 20 ms frames (16 kHz, -1..1). A port of stt/vad.py: same numbers, same behaviour. */
export const RATE = 16000;
export const FRAME = 320;

export function rmsDb(frame: Float32Array): number {
  let s = 0; for (let i = 0; i < frame.length; i++) s += frame[i] * frame[i];
  return 20 * Math.log10(Math.max(Math.sqrt(s / (frame.length || 1)), 1e-9));
}

export type VadEvent = { type: 'start' } | { type: 'end'; audio: Float32Array | null };

export class Endpointer {
  private silenceFrames: number; private minSpeechFrames: number; private maxFrames: number; private margin: number; private absMin: number; private floorMin: number; private prerollMax: number;
  private floor: number; private recent: number[] = []; private preroll: Float32Array[] = [];
  private active = false; private audio: Float32Array[] = []; private quiet = 0; private loudRun = 0; private speechFrames = 0;

  constructor(o: { silenceMs?: number; minSpeechMs?: number; maxS?: number; marginDb?: number; floorMinDb?: number; absMinDb?: number; prerollMs?: number } = {}) {
    this.silenceFrames = Math.floor((o.silenceMs ?? 800) / 20); this.minSpeechFrames = Math.floor((o.minSpeechMs ?? 300) / 20); this.maxFrames = Math.floor((o.maxS ?? 30) * 50);
    this.margin = o.marginDb ?? 11; this.absMin = o.absMinDb ?? -48; this.floorMin = o.floorMinDb ?? -60; this.prerollMax = Math.floor((o.prerollMs ?? 300) / 20);
    this.floor = Math.max(this.floorMin, -55);
  }

  reset() { this.active = false; this.audio = []; this.quiet = 0; this.loudRun = 0; this.speechFrames = 0; this.preroll = []; }
  get hearing() { return this.active; }
  threshold() { return Math.max(this.floor + this.margin, this.absMin); }

  feed(frame: Float32Array): VadEvent | null {
    const db = rmsDb(frame); const loud = db > this.threshold();
    if (!loud && !this.active) {                    // learn the room only from sounds that aren't speech
      this.recent.push(db); if (this.recent.length > 100) this.recent.shift();
      if (this.recent.length >= 25) { const sorted = [...this.recent].sort((a, b) => a - b); this.floor = Math.max(this.floorMin, sorted[Math.floor((sorted.length - 1) * 0.2)]); }
    }
    if (!this.active) {
      this.preroll.push(frame); if (this.preroll.length > this.prerollMax) this.preroll.shift();
      this.loudRun = loud ? this.loudRun + 1 : 0;
      if (this.loudRun >= 3) { this.active = true; this.audio = [...this.preroll]; this.quiet = 0; this.speechFrames = this.loudRun; return { type: 'start' }; }
      return null;
    }
    this.audio.push(frame);
    if (loud) { this.quiet = 0; this.speechFrames++; } else this.quiet++;
    if (this.quiet >= this.silenceFrames || this.audio.length >= this.maxFrames) {
      const enough = this.speechFrames >= this.minSpeechFrames; const parts = this.audio; this.reset();
      if (!enough) return { type: 'end', audio: null };
      const out = new Float32Array(parts.length * FRAME); parts.forEach((p, i) => out.set(p, i * FRAME));
      return { type: 'end', audio: out };
    }
    return null;
  }
}
