import { useCallback, useEffect, useRef, useState } from "react";

interface UseDeviceCheckResult {
  micActive: boolean;
  cameraActive: boolean;
  audioLevel: number;
  error: string | null;
  request: () => Promise<void>;
  release: () => void;
  attachVideo: (el: HTMLVideoElement | null) => void;
}

/**
 * 카메라/마이크 권한 요청 + 실시간 음성 레벨 표시.
 *
 * 모든 가변 자원(stream, audio context, RAF, video element)은 ref 로 관리한다.
 * release 콜백은 어떤 state 도 클로저로 캡쳐하지 않으므로, stream 이 갱신돼도
 * release 의 identity 가 바뀌지 않아 효과 정리(useEffect cleanup) 가 부수적으로
 * 폭주하지 않는다.
 */
export function useDeviceCheck(): UseDeviceCheckResult {
  const [micActive, setMicActive] = useState(false);
  const [cameraActive, setCameraActive] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const streamRef = useRef<MediaStream | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const rafRef = useRef<number | null>(null);

  const tick = useCallback(() => {
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
    setAudioLevel(Math.min(1, rms * 2));
    rafRef.current = requestAnimationFrame(tick);
  }, []);

  const release = useCallback(() => {
    if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    rafRef.current = null;

    analyserRef.current?.disconnect();
    analyserRef.current = null;

    audioCtxRef.current?.close().catch(() => {});
    audioCtxRef.current = null;

    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;

    if (videoRef.current) videoRef.current.srcObject = null;

    setMicActive(false);
    setCameraActive(false);
    setAudioLevel(0);
  }, []);

  // 컴포넌트 unmount 시 한 번만 정리.
  useEffect(() => () => release(), [release]);

  const attachVideo = useCallback((el: HTMLVideoElement | null) => {
    videoRef.current = el;
    if (el && streamRef.current) {
      el.srcObject = streamRef.current;
      el.play().catch(() => {});
    }
  }, []);

  const request = useCallback(async () => {
    setError(null);

    // 이미 활성 stream 이 있으면 재요청하지 않는다 (StrictMode 이중 호출 방어).
    if (streamRef.current) {
      setMicActive(streamRef.current.getAudioTracks().length > 0);
      setCameraActive(streamRef.current.getVideoTracks().length > 0);
      return;
    }

    try {
      const next = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480 },
        audio: true,
      });
      streamRef.current = next;
      setMicActive(next.getAudioTracks().length > 0);
      setCameraActive(next.getVideoTracks().length > 0);

      if (videoRef.current) {
        videoRef.current.srcObject = next;
        await videoRef.current.play().catch(() => {});
      }

      const AudioCtx =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext })
          .webkitAudioContext;
      const ctx = new AudioCtx();
      const src = ctx.createMediaStreamSource(next);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 1024;
      src.connect(analyser);
      audioCtxRef.current = ctx;
      analyserRef.current = analyser;
      rafRef.current = requestAnimationFrame(tick);
    } catch (e) {
      setError((e as Error).message ?? "장치 접근에 실패했습니다.");
    }
  }, [tick]);

  return { micActive, cameraActive, audioLevel, error, request, release, attachVideo };
}
