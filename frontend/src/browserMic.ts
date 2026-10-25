import { Endpointer, FRAME } from './vad';
import { toRate16k } from './wav';

export type MicState = 'loading' | 'listening' | 'hearing';

/** The phone's own microphone: cuts what you say into sentences on the phone and hands each one over as 16 kHz samples. Nothing leaves the phone from here. */
export class BrowserMic {
  private ctx?: AudioContext; private stream?: MediaStream; private node?: ScriptProcessorNode; private src?: MediaStreamAudioSourceNode;
  private ep = new Endpointer(); private pending = new Float32Array(0); private carry = { pos: 0 };
  private paused = false; private resumedAt = 0; private last: MicState = 'loading';

  async start(onState: (s: MicState) => void, onUtterance: (audio: Float32Array) => void) {
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 } });
    const AC = window.AudioContext || (window as any).webkitAudioContext; this.ctx = new AC();
    if (this.ctx.state === 'suspended') await this.ctx.resume();
    this.src = this.ctx.createMediaStreamSource(this.stream);
    this.node = this.ctx.createScriptProcessor(4096, 1, 1);
    const rate = this.ctx.sampleRate;
    const set = (s: MicState) => { if (s !== this.last) { this.last = s; onState(s); } };
    this.node.onaudioprocess = e => {
      const block = new Float32Array(e.inputBuffer.getChannelData(0));       // copy: the browser reuses the buffer
      if (this.paused || Date.now() - this.resumedAt < 500) { if (this.ep.hearing) this.ep.reset(); this.pending = new Float32Array(0); set('listening'); return; }
      const mono = toRate16k(block, rate, this.carry);
      const all = new Float32Array(this.pending.length + mono.length); all.set(this.pending); all.set(mono, this.pending.length);
      let i = 0;
      for (; i + FRAME <= all.length; i += FRAME) {
        const ev = this.ep.feed(all.subarray(i, i + FRAME).slice());
        if (!ev) continue;
        if (ev.type === 'start') set('hearing'); else { set('listening'); if (ev.audio) onUtterance(ev.audio); }
      }
      this.pending = all.slice(i);
    };
    this.src.connect(this.node); this.node.connect(this.ctx.destination);   // the processor only runs when connected; it writes silence
    set('listening');
  }

  pause() { this.paused = true; }
  resume() { this.resumedAt = Date.now(); this.paused = false; }

  /** Releases the microphone (the browser's recording indicator goes off). */
  stop() {
    try { this.node && (this.node.onaudioprocess = null); this.src?.disconnect(); this.node?.disconnect(); } catch { /* already gone */ }
    this.stream?.getTracks().forEach(t => t.stop()); void this.ctx?.close().catch(() => {});
    this.stream = undefined; this.ctx = undefined; this.node = undefined; this.src = undefined;
  }
}
