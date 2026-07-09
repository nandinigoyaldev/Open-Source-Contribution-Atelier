import React, { useEffect, useRef, useState } from "react";

interface AudioRoomProps {
  roomId: string;
  onEndCall: () => void;
}

type ConnectionState =
  | "Connecting"
  | "Connected"
  | "Disconnected"
  | "Reconnecting"
  | "Call Ended";

export function AudioRoom({ roomId, onEndCall }: AudioRoomProps) {
  const [connectionState, setConnectionState] =
    useState<ConnectionState>("Connecting");
  const [isMuted, setIsMuted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const remoteAudioRef = useRef<HTMLAudioElement>(null);
  const localStreamRef = useRef<MediaStream | null>(null);
  const peerConnectionRef = useRef<RTCPeerConnection | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let isCleanup = false;

    const initWebRTC = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: true,
          video: false,
        });
        if (isCleanup) return;
        localStreamRef.current = stream;

        // Initialize PeerConnection
        const pc = new RTCPeerConnection({
          iceServers: [
            { urls: "stun:stun.l.google.com:19302" },
          ],
        });
        peerConnectionRef.current = pc;

        stream.getTracks().forEach((track) => pc.addTrack(track, stream));

        pc.ontrack = (event) => {
          if (remoteAudioRef.current && event.streams[0]) {
            remoteAudioRef.current.srcObject = event.streams[0];
          }
        };

        pc.oniceconnectionstatechange = () => {
          if (pc.iceConnectionState === "disconnected" || pc.iceConnectionState === "failed") {
            setConnectionState("Disconnected");
          } else if (pc.iceConnectionState === "connected") {
            setConnectionState("Connected");
          }
        };

        // Initialize WebSocket
        const token = localStorage.getItem("token"); // Assuming token is here
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = `${protocol}//${window.location.host}/ws/webrtc/${roomId}/${token ? `?token=${token}` : ""}`;
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          console.log("WebSocket connected");
        };

        ws.onmessage = async (event) => {
          const message = JSON.parse(event.data);

          if (message.type === "peer_joined") {
            // Initiate call when someone joins
            setConnectionState("Connecting");
            const offer = await pc.createOffer();
            await pc.setLocalDescription(offer);
            ws.send(JSON.stringify({ action: "offer", data: offer }));
          } else if (message.type === "webrtc_signal") {
            if (message.action === "offer") {
              await pc.setRemoteDescription(new RTCSessionDescription(message.data));
              const answer = await pc.createAnswer();
              await pc.setLocalDescription(answer);
              ws.send(JSON.stringify({ action: "answer", data: answer }));
              setConnectionState("Connecting");
            } else if (message.action === "answer") {
              await pc.setRemoteDescription(new RTCSessionDescription(message.data));
              setConnectionState("Connected");
            } else if (message.action === "ice-candidate") {
              try {
                await pc.addIceCandidate(new RTCIceCandidate(message.data));
              } catch (e) {
                console.error("Error adding received ice candidate", e);
              }
            }
          } else if (message.type === "peer_left") {
            setConnectionState("Disconnected");
          }
        };

        pc.onicecandidate = (event) => {
          if (event.candidate && ws.readyState === WebSocket.OPEN) {
            ws.send(
              JSON.stringify({ action: "ice-candidate", data: event.candidate })
            );
          }
        };

        ws.onclose = () => {
          if (!isCleanup) setConnectionState("Disconnected");
        };
      } catch (err: unknown) {
        if (!isCleanup) {
          const errorMessage = err instanceof Error ? err.message : "Failed to access microphone.";
          setError(errorMessage);
          setConnectionState("Disconnected");
        }
      }
    };

    initWebRTC();

    return () => {
      isCleanup = true;
      if (localStreamRef.current) {
        localStreamRef.current.getTracks().forEach((track) => track.stop());
      }
      if (peerConnectionRef.current) {
        peerConnectionRef.current.close();
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [roomId]);

  const toggleMute = () => {
    if (localStreamRef.current) {
      const audioTrack = localStreamRef.current.getAudioTracks()[0];
      if (audioTrack) {
        audioTrack.enabled = !audioTrack.enabled;
        setIsMuted(!audioTrack.enabled);
      }
    }
  };

  const handleEndCall = () => {
    setConnectionState("Call Ended");
    if (localStreamRef.current) {
      localStreamRef.current.getTracks().forEach((track) => track.stop());
    }
    if (peerConnectionRef.current) {
      peerConnectionRef.current.close();
    }
    if (wsRef.current) {
      wsRef.current.close();
    }
    onEndCall();
  };

  return (
    <div className="bg-surface-low border-2 border-black rounded-xl p-4 flex items-center justify-between shadow-card-sm dark:bg-[#1a1816] dark:border-[#2e2924] mb-4">
      <div className="flex items-center gap-4">
        <div className="font-bold">
          Audio Review:{" "}
          <span
            className={
              connectionState === "Connected"
                ? "text-green-600 dark:text-green-400"
                : connectionState === "Connecting"
                ? "text-yellow-600 dark:text-yellow-400"
                : "text-red-600 dark:text-red-400"
            }
          >
            {connectionState}
          </span>
        </div>
        {error && <div className="text-red-500 text-sm">{error}</div>}
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={toggleMute}
          className={`px-4 py-2 font-bold rounded border-2 border-black transition-all ${
            isMuted
              ? "bg-red-500 text-white"
              : "bg-surface hover:bg-black/5 dark:bg-[#2e2924]"
          }`}
        >
          {isMuted ? "Unmute" : "Mute"}
        </button>
        <button
          onClick={handleEndCall}
          className="px-4 py-2 font-bold rounded border-2 border-red-500 bg-red-100 text-red-800 hover:bg-red-200 transition-all"
        >
          End Call
        </button>
      </div>

      <audio ref={remoteAudioRef} autoPlay />
    </div>
  );
}
