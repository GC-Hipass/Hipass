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
  audioLevel: number; // 0~1, 실시간 음성 입력 레벨
  error: string | null;
  start: () => Promise<void>;
  stop: () => Promise<RecordedClip | null>;
  release: () => void;
}

/** MediaRecorder + AnalyserNode 기반 음성 녹음. AudioContext로 실시간 레벨 추출. */
export function useRecorder(): UseRecorderResult {
  const [state, setState] = useState<RecorderState>("idle");
  const [audioLevel, setAudioLevel] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const rafRef = useRef<number | null>(null);
  const startedAtRef = useRef<number>(0);

  const cleanup = useCallback(() => {
    if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    rafRef.current = null;

    analyserRef.current?.disconnect();
    analyserRef.current = null;

    audioCtxRef.current?.close().catch(() => {});
    audioCtxRef.current = null;

    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;

    recorderRef.current = null;
    chunksRef.current = [];
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
    const rms = Math.sqrt(sum / buf.length) / 128; // 0~1
    setAudioLevel(Math.min(1, rms * 1.8)); // 시각적으로 잘 보이게 약간 증폭
    rafRef.current = requestAnimationFrame(tickLevel);
  }, []);

  const start = useCallback(async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      // MIME 결정. webm/opus는 Chrome/Edge/Firefox 표준. Safari는 mp4.
      const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
      const mimeType =
        candidates.find((m) => MediaRecorder.isTypeSupported(m)) || "";

      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorderRef.current = recorder;

      // AudioContext: 음성 레벨 시각화용
      const AudioCtx =
        window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const ctx = new AudioCtx();
      const src = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 1024;
      src.connect(analyser);
      audioCtxRef.current = ctx;
      analyserRef.current = analyser;

      startedAtRef.current = performance.now();
      recorder.start(250);
      setState("recording");
      rafRef.current = requestAnimationFrame(tickLevel);
    } catch (e) {
      setError((e as Error).message ?? "마이크 접근 실패");
      setState("error");
    }
  }, [tickLevel]);

  const stop = useCallback((): Promise<RecordedClip | null> => {
    return new Promise((resolve) => {
      const recorder = recorderRef.current;
      if (!recorder || recorder.state === "inactive") {
        resolve(null);
        return;
      }
      setState("stopping");
      recorder.onstop = () => {
        const mimeType = recorder.mimeType || "audio/webm";
        const blob = new Blob(chunksRef.current, { type: mimeType });
        const ext = mimeType.includes("mp4") ? "mp4" : mimeType.includes("ogg") ? "ogg" : "webm";
        const durationSeconds = Math.max(
          1,
          Math.round((performance.now() - startedAtRef.current) / 1000),
        );
        const clip: RecordedClip = {
          blob,
          filename: `answer.${ext}`,
          mimeType,
          durationSeconds,
        };
        cleanup();
        setState("stopped");
        setAudioLevel(0);
        resolve(clip);
      };
      recorder.stop();
    });
  }, [cleanup]);

  const release = useCallback(() => {
    cleanup();
    setState("idle");
    setAudioLevel(0);
  }, [cleanup]);

  return { state, audioLevel, error, start, stop, release };
}
