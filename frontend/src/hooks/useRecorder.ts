import { useCallback, useEffect, useRef, useState } from "react";

type RecorderState = "idle" | "ready" | "recording" | "stopping" | "stopped" | "error";

export interface RecordedClip {
  blob: Blob;
  filename: string;
  mimeType: string;
  durationSeconds: number;
}

interface UseRecorderResult {
  state: RecorderState;
  audioLevel: number;
  error: string | null;
  start: () => Promise<void>;
  stop: () => Promise<RecordedClip | null>;
  release: () => void;
}

export function useRecorder(): UseRecorderResult {
  const [state, setState] = useState<RecorderState>("idle");
  const [audioLevel, setAudioLevel] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const streamRef = useRef<MediaStream | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const muteGainRef = useRef<GainNode | null>(null);
  const pcmChunksRef = useRef<Float32Array[]>([]);
  const rafRef = useRef<number | null>(null);
  const startedAtRef = useRef<number>(0);

  const cleanup = useCallback(() => {
    if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    rafRef.current = null;

    analyserRef.current?.disconnect();
    analyserRef.current = null;

    processorRef.current?.disconnect();
    processorRef.current = null;

    sourceRef.current?.disconnect();
    sourceRef.current = null;

    muteGainRef.current?.disconnect();
    muteGainRef.current = null;

    audioCtxRef.current?.close().catch(() => {});
    audioCtxRef.current = null;

    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;

    pcmChunksRef.current = [];
  }, []);

  useEffect(() => () => cleanup(), [cleanup]);

  const tickLevel = useCallback(() => {
    const analyser = analyserRef.current;
    if (!analyser) return;
    const buf = new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteTimeDomainData(buf);
    let sum = 0;
    for (let i = 0; i < buf.length; i++) {
      const d = buf[i] - 128;
      sum += d * d;
    }
    const rms = Math.sqrt(sum / buf.length) / 128;
    setAudioLevel(Math.min(1, rms * 1.8));
    rafRef.current = requestAnimationFrame(tickLevel);
  }, []);

  const start = useCallback(async () => {
    setError(null);

    try {
      cleanup();

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const AudioCtx =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const ctx = new AudioCtx();
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      const processor = ctx.createScriptProcessor(4096, 1, 1);
      const muteGain = ctx.createGain();
      muteGain.gain.value = 0;

      analyser.fftSize = 1024;
      source.connect(analyser);
      source.connect(processor);
      processor.connect(muteGain);
      muteGain.connect(ctx.destination);

      pcmChunksRef.current = [];
      processor.onaudioprocess = (event) => {
        const channel = event.inputBuffer.getChannelData(0);
        pcmChunksRef.current.push(new Float32Array(channel));
      };

      audioCtxRef.current = ctx;
      analyserRef.current = analyser;
      sourceRef.current = source;
      processorRef.current = processor;
      muteGainRef.current = muteGain;

      startedAtRef.current = performance.now();
      setState("recording");
      rafRef.current = requestAnimationFrame(tickLevel);
    } catch (e) {
      cleanup();
      setAudioLevel(0);
      setError((e as Error).message ?? "Microphone access failed");
      setState("error");
      throw e;
    }
  }, [cleanup, tickLevel]);

  const stop = useCallback((): Promise<RecordedClip | null> => {
    return new Promise((resolve) => {
      const ctx = audioCtxRef.current;
      const chunks = pcmChunksRef.current;
      if (!ctx || chunks.length === 0) {
        resolve(null);
        return;
      }

      setState("stopping");
      const wavBytes = encodeWav(chunks, ctx.sampleRate);
      const blob = new Blob([wavBytes], { type: "audio/wav" });
      const durationSeconds = Math.max(
        1,
        Math.round((performance.now() - startedAtRef.current) / 1000),
      );

      cleanup();
      setState("stopped");
      setAudioLevel(0);
      resolve({
        blob,
        filename: "answer.wav",
        mimeType: "audio/wav",
        durationSeconds,
      });
    });
  }, [cleanup]);

  const release = useCallback(() => {
    cleanup();
    setState("idle");
    setAudioLevel(0);
  }, [cleanup]);

  return { state, audioLevel, error, start, stop, release };
}

function encodeWav(chunks: Float32Array[], sampleRate: number): ArrayBuffer {
  const totalLength = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const pcm = new Int16Array(totalLength);
  let offset = 0;

  for (const chunk of chunks) {
    for (let i = 0; i < chunk.length; i++) {
      const sample = Math.max(-1, Math.min(1, chunk[i]));
      pcm[offset++] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
    }
  }

  const buffer = new ArrayBuffer(44 + pcm.byteLength);
  const view = new DataView(buffer);

  writeAscii(view, 0, "RIFF");
  view.setUint32(4, 36 + pcm.byteLength, true);
  writeAscii(view, 8, "WAVE");
  writeAscii(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeAscii(view, 36, "data");
  view.setUint32(40, pcm.byteLength, true);

  let byteOffset = 44;
  for (let i = 0; i < pcm.length; i++) {
    view.setInt16(byteOffset, pcm[i], true);
    byteOffset += 2;
  }

  return buffer;
}

function writeAscii(view: DataView, offset: number, value: string) {
  for (let i = 0; i < value.length; i++) {
    view.setUint8(offset + i, value.charCodeAt(i));
  }
}
