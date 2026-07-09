import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { AudioRoom } from "../../../components/ui/AudioRoom";

describe("AudioRoom Component", () => {
  const mockOnEndCall = vi.fn();
  let mockWebSocket: any;
  let mockPeerConnection: any;

  beforeEach(() => {
    mockOnEndCall.mockClear();

    // Mock WebSocket
    mockWebSocket = {
      send: vi.fn(),
      close: vi.fn(),
      readyState: WebSocket.OPEN,
    };
    global.WebSocket = vi.fn().mockImplementation(() => mockWebSocket) as any;

    // Mock getUserMedia
    const mockTrack = { stop: vi.fn(), enabled: true };
    const mockStream = {
      getTracks: vi.fn().mockReturnValue([mockTrack]),
      getAudioTracks: vi.fn().mockReturnValue([mockTrack]),
    };
    Object.defineProperty(global.navigator, "mediaDevices", {
      value: {
        getUserMedia: vi.fn().mockResolvedValue(mockStream),
      },
      configurable: true,
    });

    // Mock RTCPeerConnection
    mockPeerConnection = {
      addTrack: vi.fn(),
      createOffer: vi.fn().mockResolvedValue({ type: "offer", sdp: "sdp" }),
      createAnswer: vi.fn().mockResolvedValue({ type: "answer", sdp: "sdp" }),
      setLocalDescription: vi.fn().mockResolvedValue(undefined),
      setRemoteDescription: vi.fn().mockResolvedValue(undefined),
      addIceCandidate: vi.fn().mockResolvedValue(undefined),
      close: vi.fn(),
    };
    global.RTCPeerConnection = vi.fn().mockImplementation(() => mockPeerConnection) as any;
    global.RTCSessionDescription = vi.fn().mockImplementation((desc) => desc) as any;
    global.RTCIceCandidate = vi.fn().mockImplementation((cand) => cand) as any;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("should initialize WebRTC and WebSocket on mount", async () => {
    render(<AudioRoom roomId="test_room" onEndCall={mockOnEndCall} />);

    await waitFor(() => {
      expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalledWith({
        audio: true,
        video: false,
      });
      expect(global.WebSocket).toHaveBeenCalled();
      expect(global.RTCPeerConnection).toHaveBeenCalled();
    });

    expect(screen.getByText(/Audio Review:/)).toBeDefined();
    expect(screen.getByText("Connecting")).toBeDefined();
  });

  it("should handle mute toggle", async () => {
    render(<AudioRoom roomId="test_room" onEndCall={mockOnEndCall} />);

    await waitFor(() => {
      expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalled();
    });

    const muteButton = screen.getByText("Mute");
    fireEvent.click(muteButton);

    expect(muteButton.textContent).toBe("Unmute");

    fireEvent.click(muteButton);
    expect(muteButton.textContent).toBe("Mute");
  });

  it("should handle end call button", async () => {
    render(<AudioRoom roomId="test_room" onEndCall={mockOnEndCall} />);

    await waitFor(() => {
      expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalled();
    });

    const endCallButton = screen.getByText("End Call");
    fireEvent.click(endCallButton);

    expect(screen.getByText("Call Ended")).toBeDefined();
    expect(mockPeerConnection.close).toHaveBeenCalled();
    expect(mockWebSocket.close).toHaveBeenCalled();
    expect(mockOnEndCall).toHaveBeenCalled();
  });

  it("should handle microphone access denial", async () => {
    Object.defineProperty(global.navigator, "mediaDevices", {
      value: {
        getUserMedia: vi.fn().mockRejectedValue(new Error("Permission denied")),
      },
      configurable: true,
    });

    render(<AudioRoom roomId="test_room" onEndCall={mockOnEndCall} />);

    await waitFor(() => {
      expect(screen.getByText("Permission denied")).toBeDefined();
      expect(screen.getByText("Disconnected")).toBeDefined();
    });
  });

  it("should respond to peer_joined message by sending an offer", async () => {
    render(<AudioRoom roomId="test_room" onEndCall={mockOnEndCall} />);

    await waitFor(() => {
      expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalled();
    });

    // Simulate WebSocket message
    await waitFor(() => {
      if (mockWebSocket.onmessage) {
        mockWebSocket.onmessage({
          data: JSON.stringify({ type: "peer_joined" }),
        } as MessageEvent);
      }
    });

    await waitFor(() => {
      expect(mockPeerConnection.createOffer).toHaveBeenCalled();
      expect(mockPeerConnection.setLocalDescription).toHaveBeenCalled();
      expect(mockWebSocket.send).toHaveBeenCalledWith(
        JSON.stringify({ action: "offer", data: { type: "offer", sdp: "sdp" } })
      );
    });
  });
});
