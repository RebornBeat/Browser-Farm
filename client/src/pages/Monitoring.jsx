import React, { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  Camera,
  Video,
  Loader,
  Download,
  Cpu,
  HardDrive,
  RefreshCw,
  ArrowLeftCircle,
  Globe,
  X,
  Play,
  MousePointer,
  Circle,
  Square,
  Trash2,
  AlertCircle,
} from "lucide-react";
import { apiClient } from "../api/client";
import { useServerHealth } from "../context/ServerHealthContext";
import store from "../store/db";
import { useMouseBatcher } from "../hooks/useMouseBatcher";
import GhostCursor from "../components/GhostCursor";

function Monitoring() {
  const { profileId } = useParams();
  const navigate = useNavigate();
  const { servers, healthData } = useServerHealth();

  // --- Core State ---
  const [profile, setProfile] = useState(null);
  const [server, setServer] = useState(null);
  const [isLoadingMeta, setIsLoadingMeta] = useState(true);

  // --- View State ---
  const [screenshot, setScreenshot] = useState(null);
  const [screenshots, setScreenshots] = useState([]);
  const [videos, setVideos] = useState([]);
  const [metrics, setMetrics] = useState(null);

  // --- Navigation State ---
  const [urlInput, setUrlInput] = useState("");

  // --- Control State ---
  const [manualControl, setManualControl] = useState(false);
  const [isHovering, setIsHovering] = useState(false); // NEW: Track if mouse is over the screen
  const controlWsRef = useRef(null);
  const canvasRef = useRef(null);
  const isDraggingRef = useRef(false);
  const modifiersRef = useRef({ ctrl: false, shift: false, alt: false });

  // --- Recording State ---
  const [isRecording, setIsRecording] = useState(false);
  const [recordingDuration, setRecordingDuration] = useState(0);

  // --- Media Modal State ---
  const [viewingImage, setViewingImage] = useState(null);
  const [playingVideo, setPlayingVideo] = useState(null);

  // --- Screenshot cleanup refs ---
  const screenshotUrlRef = useRef(null);

  // ==========================================
  // 1. INITIALIZATION
  // ==========================================
  useEffect(() => {
    const init = async () => {
      if (!profileId || servers.length === 0) return;

      let foundProfile = null;
      let foundServer = null;

      const localProfiles = (await store.get("profiles")) || [];
      const localP = localProfiles.find((p) => p.id === profileId);

      if (localP) {
        const s = servers.find((srv) => srv.id === localP.serverId);
        if (s) {
          foundProfile = localP;
          foundServer = s;
        }
      }

      if (!foundProfile) {
        for (const s of servers) {
          if (healthData[s.id]?.status !== "online") continue;
          try {
            const data = await apiClient.getProfile(s.id, profileId);
            if (data) {
              foundProfile = data;
              foundServer = s;
              break;
            }
          } catch (e) {
            continue;
          }
        }
      }

      if (!foundProfile || !foundServer) {
        setIsLoadingMeta(false);
        return;
      }

      // Sync profile status from server
      try {
        const serverData = await apiClient.getProfile(
          foundServer.id,
          profileId,
        );
        if (serverData) {
          foundProfile = { ...foundProfile, ...serverData };
        }
      } catch (e) {}

      setProfile(foundProfile);
      setServer(foundServer);
      setIsLoadingMeta(false);
    };

    init();
  }, [profileId, servers, healthData]);

  // ==========================================
  // 2. SPLIT POLLING INTERVALS
  // ==========================================

  // Fast poll: Screenshot (1.5s)
  useEffect(() => {
    if (!server || !profile || profile.status !== "running") return;

    const interval = setInterval(async () => {
      try {
        const url = await apiClient.getScreenshot(server.id, profile.id);
        // Revoke old URL
        if (
          screenshotUrlRef.current &&
          screenshotUrlRef.current.startsWith("blob:")
        ) {
          URL.revokeObjectURL(screenshotUrlRef.current);
        }
        screenshotUrlRef.current = url;
        setScreenshot(url);
      } catch (e) {
        // Silent fail
      }
    }, 1500);

    return () => {
      clearInterval(interval);
      if (
        screenshotUrlRef.current &&
        screenshotUrlRef.current.startsWith("blob:")
      ) {
        URL.revokeObjectURL(screenshotUrlRef.current);
      }
    };
  }, [server, profile?.id, profile?.status]);

  // Medium poll: Metrics & Profile Status (5s)
  useEffect(() => {
    if (!server || !profile) return;

    const interval = setInterval(async () => {
      // Check profile status
      try {
        const data = await apiClient.getProfile(server.id, profile.id);
        if (data.status !== profile.status) {
          setProfile((prev) => ({ ...prev, status: data.status }));
        }
        if (data.current_url) {
          setUrlInput(data.current_url);
        }
      } catch (e) {}

      // Metrics (only if running)
      if (profile.status === "running") {
        try {
          const data = await apiClient.getMetrics(server.id, profile.id);
          setMetrics(data);
        } catch (e) {}
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [server, profile?.id, profile?.status]);

  // Slow poll: Media Lists (15s)
  useEffect(() => {
    if (!server || !profile) return;

    const loadMedia = async () => {
      try {
        const client = apiClient.getClient(server.id);

        // Screenshots
        const ssRes = await client.get(`/profiles/${profile.id}/screenshots`);
        const ssData = ssRes.data.screenshots || [];

        const ssWithBlobs = await Promise.all(
          ssData.slice(0, 12).map(async (ss) => {
            try {
              const resp = await client.get(ss.url, { responseType: "blob" });
              return { ...ss, blobUrl: URL.createObjectURL(resp.data) };
            } catch {
              return { ...ss, blobUrl: null };
            }
          }),
        );
        setScreenshots(ssWithBlobs);

        // Videos
        const vidRes = await client.get(`/profiles/${profile.id}/videos`);
        setVideos(vidRes.data.videos || []);
      } catch (e) {
        console.error("Failed to load media", e);
      }
    };

    loadMedia(); // Initial load
    const interval = setInterval(loadMedia, 15000);

    return () => clearInterval(interval);
  }, [server, profile?.id]);

  // Recording status poll (3s, only if recording)
  useEffect(() => {
    if (!server || !profile || !isRecording) return;

    const interval = setInterval(async () => {
      try {
        const data = await apiClient.getRecordingStatus(server.id, profile.id);
        if (data.recording) {
          setRecordingDuration(data.duration_seconds);
        } else {
          setIsRecording(false);
          setRecordingDuration(0);
        }
      } catch (e) {}
    }, 3000);

    return () => clearInterval(interval);
  }, [server, profile?.id, isRecording]);

  // ==========================================
  // 3. MANUAL CONTROL WEBSOCKET
  // ==========================================
  useEffect(() => {
    if (manualControl && server && profile && profile.status === "running") {
      startManualControl();
    } else {
      stopManualControl();
    }
    return () => stopManualControl();
  }, [manualControl, server, profile?.id, profile?.status]);

  const startManualControl = () => {
    if (!server || !profile) return;
    const wsUrl = apiClient.getControlUrl(server.id, profile.id);
    if (!wsUrl) return;

    controlWsRef.current = new WebSocket(wsUrl);
    controlWsRef.current.onopen = () => {
      console.log("Manual control connected");
    };
    controlWsRef.current.onerror = (err) => {
      console.error("Control error", err);
      setManualControl(false);
    };
    controlWsRef.current.onclose = () => {
      // Reset drag state
      isDraggingRef.current = false;
    };
  };

  const stopManualControl = () => {
    if (controlWsRef.current) {
      controlWsRef.current.close();
      controlWsRef.current = null;
    }
    isDraggingRef.current = false;
  };

  const sendControlAction = useCallback((action) => {
    if (
      controlWsRef.current &&
      controlWsRef.current.readyState === WebSocket.OPEN
    ) {
      controlWsRef.current.send(JSON.stringify(action));
    }
  }, []);

  // ==========================================
  // 4. MOUSE BATCHING (Ghost Trail)
  // ==========================================
  const { addPoint, pendingPoints, sentPoints, clearGhost } = useMouseBatcher(
    sendControlAction,
    50,
    100,
  );

  // ==========================================
  // 5. COORDINATE MAPPING
  // ==========================================
  const getCoords = (e) => {
    if (!canvasRef.current) return { x: 0, y: 0 };

    const img = canvasRef.current.querySelector("img");
    const target = img || canvasRef.current;
    const rect = target.getBoundingClientRect();

    // Calculate scale (image may be letterboxed)
    const scaleX = 1920 / rect.width;
    const scaleY = 1080 / rect.height;

    const x = Math.round((e.clientX - rect.left) * scaleX);
    const y = Math.round((e.clientY - rect.top) * scaleY);

    // Clamp to viewport
    return {
      x: Math.max(0, Math.min(1920, x)),
      y: Math.max(0, Math.min(1080, y)),
    };
  };

  // ==========================================
  // 6. MOUSE EVENT HANDLERS
  // ==========================================
  const handleMouseMove = (e) => {
    if (!manualControl || !isHovering) return;
    const { x, y } = getCoords(e);
    addPoint(x, y);
  };

  const handleMouseDown = (e) => {
    if (!manualControl || !isHovering) return;
    e.preventDefault();
    const { x, y } = getCoords(e);
    const button =
      e.button === 2 ? "right" : e.button === 1 ? "middle" : "left";

    if (button === "left") {
      isDraggingRef.current = true;
    }

    // Send immediately, don't wait for batch
    sendControlAction({
      type: "mouse_down",
      x,
      y,
      button,
      modifiers: getActiveModifiers(e),
    });
  };

  const handleMouseUp = (e) => {
    if (!manualControl) return; // Allow mouseup even if slightly off-hover to prevent stuck drags
    e.preventDefault();
    const { x, y } = getCoords(e);
    const button =
      e.button === 2 ? "right" : e.button === 1 ? "middle" : "left";

    if (button === "left") {
      isDraggingRef.current = false;
      clearGhost();
    }

    sendControlAction({
      type: "mouse_up",
      x,
      y,
      button,
      modifiers: getActiveModifiers(e),
    });
  };

  const handleContextMenu = (e) => {
    if (!manualControl) return;
    e.preventDefault(); // Prevent browser context menu
    // Right-click is handled by mousedown/mouseup with button="right"
  };

  const handleClick = (e) => {
    // Click is handled by mousedown+mouseup, but we prevent double-firing
    if (!manualControl) return;
    e.preventDefault();
  };

  const handleMouseLeave = (e) => {
    if (!manualControl) return;
    // If dragging, send mouse_up to prevent stuck drag
    if (isDraggingRef.current) {
      const { x, y } = getCoords(e);
      sendControlAction({ type: "mouse_up", x, y, button: "left" });
      isDraggingRef.current = false;
    }
  };

  // ==========================================
  // 7. KEYBOARD HANDLERS
  // ==========================================
  const handleKeyDown = (e) => {
    // Only capture keyboard if manual control is ON AND mouse is hovering over screen
    if (!manualControl || !isHovering) return;

    // Track modifiers
    if (e.key === "Control") modifiersRef.current.ctrl = true;
    if (e.key === "Shift") modifiersRef.current.shift = true;
    if (e.key === "Alt") modifiersRef.current.alt = true;

    // Strictly prevent common browser shortcuts from affecting the Electron app
    const blockedCombos = ["t", "w", "n", "r", "f", "l"];
    if (e.ctrlKey && blockedCombos.includes(e.key.toLowerCase())) {
      e.preventDefault();
    }

    const keyMap = {
      " ": "space",
      Enter: "Return",
      Backspace: "BackSpace",
      Tab: "Tab",
      Escape: "Escape",
      ArrowUp: "Up",
      ArrowDown: "Down",
      ArrowLeft: "Left",
      ArrowRight: "Right",
    };

    const key = keyMap[e.key] || e.key;
    sendControlAction({ type: "key_down", key });
  };

  const handleKeyUp = (e) => {
    if (!manualControl) return;

    if (e.key === "Control") modifiersRef.current.ctrl = false;
    if (e.key === "Shift") modifiersRef.current.shift = false;
    if (e.key === "Alt") modifiersRef.current.alt = false;

    const keyMap = {
      " ": "space",
      Enter: "Return",
      Backspace: "BackSpace",
      Tab: "Tab",
      Escape: "Escape",
      ArrowUp: "Up",
      ArrowDown: "Down",
      ArrowLeft: "Left",
      ArrowRight: "Right",
    };

    const key = keyMap[e.key] || e.key;
    sendControlAction({ type: "key_up", key });
  };

  const getActiveModifiers = (e) => {
    const mods = [];
    if (e.ctrlKey) mods.push("ctrl");
    if (e.shiftKey) mods.push("shift");
    if (e.altKey) mods.push("alt");
    if (e.metaKey) mods.push("meta");
    return mods;
  };

  // ==========================================
  // 8. SCROLL HANDLER
  // ==========================================
  const handleWheel = (e) => {
    if (!manualControl) return;
    e.preventDefault();
    sendControlAction({ type: "scroll", delta_y: e.deltaY });
  };

  // ==========================================
  // 9. NAVIGATION ACTIONS
  // ==========================================
  const handleNavigate = async (e) => {
    if (e) e.preventDefault();
    if (!server || !profile || !urlInput) return;
    try {
      let url = urlInput;
      if (!url.startsWith("http://") && !url.startsWith("https://")) {
        url = "https://" + url;
      }
      await apiClient.navigateTo(server.id, profile.id, url);
      setUrlInput(url);
    } catch (err) {
      alert(
        "Navigation failed: " + (err.response?.data?.detail || err.message),
      );
    }
  };

  const handleRefresh = async () => {
    if (!server || !profile) return;
    try {
      await apiClient.refreshPage(server.id, profile.id);
    } catch (err) {}
  };

  const handleBack = async () => {
    if (!server || !profile) return;
    try {
      await apiClient.goBack(server.id, profile.id);
    } catch (err) {}
  };

  // ==========================================
  // 10. SCREENSHOT ACTION
  // ==========================================
  const takeScreenshot = async () => {
    if (!server || !profile) return;
    try {
      await apiClient.takeScreenshot(server.id, profile.id);
      // Refresh media list
      setTimeout(() => {
        const client = apiClient.getClient(server.id);
        client.get(`/profiles/${profile.id}/screenshots`).then((res) => {
          setScreenshots(
            (res.data.screenshots || []).slice(0, 12).map((ss) => ({
              ...ss,
              blobUrl: null,
            })),
          );
        });
      }, 500);
    } catch (error) {
      alert("Failed to take screenshot: " + error.message);
    }
  };

  // ==========================================
  // 11. RECORDING ACTIONS
  // ==========================================
  const toggleRecording = async () => {
    if (!server || !profile) return;
    try {
      if (isRecording) {
        await apiClient.stopRecording(server.id, profile.id);
        setIsRecording(false);
        setRecordingDuration(0);
        // Refresh video list
        const client = apiClient.getClient(server.id);
        const vidRes = await client.get(`/profiles/${profile.id}/videos`);
        setVideos(vidRes.data.videos || []);
      } else {
        await apiClient.startRecording(server.id, profile.id);
        setIsRecording(true);
        setRecordingDuration(0);
      }
    } catch (error) {
      alert("Recording toggle failed: " + error.message);
    }
  };

  const formatDuration = (seconds) => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    if (h > 0)
      return `${h}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  // ==========================================
  // 12. MEDIA HELPERS
  // ==========================================
  const handleDownloadMedia = async (url, filename) => {
    if (!server) return;
    try {
      const response = await apiClient.getClient(server.id).get(url, {
        responseType: "blob",
      });
      const downloadUrl = window.URL.createObjectURL(response.data);
      const a = document.createElement("a");
      a.href = downloadUrl;
      a.download = filename;
      a.click();
      window.URL.revokeObjectURL(downloadUrl);
    } catch (e) {
      alert("Failed to download media.");
    }
  };

  const handleDeleteScreenshot = async (filename, id) => {
    if (!server) return;
    if (!window.confirm("Delete this screenshot?")) return;
    try {
      await apiClient.deleteScreenshot(server.id, filename);
      setScreenshots((prev) => prev.filter((s) => s.id !== id));
    } catch (e) {
      alert("Failed to delete screenshot.");
    }
  };

  const handleDeleteVideo = async (filename, id) => {
    if (!server || !profile) return;
    if (!window.confirm("Delete this video?")) return;
    try {
      await apiClient.deleteVideo(server.id, profile.id, filename);
      setVideos((prev) => prev.filter((v) => v.id !== id));
    } catch (e) {
      alert("Failed to delete video.");
    }
  };

  const openVideoPlayer = async (vid) => {
    if (!server) return;
    try {
      const client = apiClient.getClient(server.id);
      const response = await client.get(vid.url, { responseType: "blob" });
      const blobUrl = URL.createObjectURL(response.data);
      setPlayingVideo({ ...vid, blobUrl });
    } catch (e) {
      alert("Failed to load video.");
    }
  };

  // ==========================================
  // RENDER
  // ==========================================
  if (isLoadingMeta) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader className="w-8 h-8 text-primary-500 animate-spin" />
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="flex flex-col items-center justify-center h-full">
        <p className="text-dark-400 mb-4">
          Profile not found or server offline.
        </p>
        <button onClick={() => navigate("/")} className="btn btn-primary">
          Go Home
        </button>
      </div>
    );
  }

  const isRunning = profile.status === "running";

  return (
    <div className="animate-fade-in flex flex-col h-full">
      {/* Header Bar */}
      <div className="flex items-center mb-4 flex-shrink-0 gap-2 flex-wrap">
        <button onClick={() => navigate(-1)} className="btn btn-secondary">
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div className="flex-1 min-w-0">
          <h1 className="text-xl font-bold text-white truncate">
            {profile.name}
          </h1>
          <p className="text-xs text-dark-400">{profile.id}</p>
        </div>

        {/* Navigation Controls */}
        {isRunning && (
          <div className="flex items-center space-x-2 bg-dark-800 p-1 rounded-lg">
            <button
              onClick={handleBack}
              className="p-2 hover:bg-dark-700 rounded text-dark-300 hover:text-white"
              title="Go Back"
            >
              <ArrowLeftCircle className="w-4 h-4" />
            </button>
            <button
              onClick={handleRefresh}
              className="p-2 hover:bg-dark-700 rounded text-dark-300 hover:text-white"
              title="Refresh"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
            <form onSubmit={handleNavigate} className="flex items-center">
              <Globe className="w-4 h-4 text-dark-500 mx-2" />
              <input
                type="text"
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                placeholder="https://google.com"
                className="bg-dark-900 border-none text-sm text-white rounded px-2 py-1 w-64 focus:outline-none focus:ring-1 focus:ring-primary-500"
              />
            </form>
          </div>
        )}

        {/* Action Buttons */}
        {isRunning && (
          <>
            <button onClick={takeScreenshot} className="btn btn-primary ml-2">
              <Camera className="w-4 h-4 mr-2" /> Screenshot
            </button>

            <button
              onClick={toggleRecording}
              className={`btn ${isRecording ? "btn-error" : "btn-secondary"} ml-2`}
              title={isRecording ? "Stop Recording" : "Start Recording"}
            >
              {isRecording ? (
                <>
                  <Square className="w-4 h-4 mr-2" /> Stop (
                  {formatDuration(recordingDuration)})
                </>
              ) : (
                <>
                  <Circle className="w-4 h-4 mr-2 fill-current" /> Record
                </>
              )}
            </button>

            <button
              onClick={(e) => {
                e.stopPropagation(); // Prevent click from reaching canvas
                setManualControl(!manualControl);
              }}
              className={`btn ${manualControl ? "btn-success" : "btn-secondary"} ml-2`}
            >
              {manualControl ? (
                <>
                  <MousePointer className="w-4 h-4 mr-2" /> Controlling
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 mr-2" /> Take Control
                </>
              )}
            </button>
          </>
        )}
      </div>

      {/* Stopped Profile Banner */}
      {!isRunning && (
        <div className="mb-4 p-4 bg-warning-500/10 border border-warning-500/30 rounded-lg flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-warning-500" />
          <div>
            <p className="text-white font-medium">
              Profile is {profile.status}. Start it from the Profiles tab to
              view live screen.
            </p>
          </div>
        </div>
      )}

      {/* Main Layout */}
      <div className="flex-1 grid grid-cols-3 gap-6 min-h-0">
        {/* Left Column: Live View */}
        <div className="col-span-2 flex flex-col min-h-0">
          <div className="card flex-1 flex flex-col relative">
            <h3 className="font-semibold text-white mb-2">Live View</h3>

            {manualControl && isRunning && (
              <div className="absolute top-1 right-1 z-20 bg-success-500/80 text-white text-xs px-2 py-1 rounded animate-pulse pointer-events-none">
                Control Active • Drag: Hold & Move • Right-Click: Right button
              </div>
            )}

            {isRecording && (
              <div className="absolute top-1 left-1 z-20 bg-error-500/80 text-white text-xs px-2 py-1 rounded flex items-center gap-1 animate-pulse">
                <Circle className="w-3 h-3 fill-current" /> REC{" "}
                {formatDuration(recordingDuration)}
              </div>
            )}

            <div
              ref={canvasRef}
              className={`flex-1 bg-dark-900 rounded-lg overflow-hidden relative border border-dark-700 ${
                manualControl ? "cursor-crosshair" : ""
              }`}
              onMouseMove={handleMouseMove}
              onMouseDown={handleMouseDown}
              onMouseUp={handleMouseUp}
              onMouseEnter={() => setIsHovering(true)} // NEW: Track hover
              onMouseLeave={(e) => {
                setIsHovering(false); // NEW: Clear hover
                handleMouseLeave(e);
              }}
              onContextMenu={handleContextMenu}
              onClick={handleClick}
              onWheel={handleWheel}
              onKeyDown={handleKeyDown}
              onKeyUp={handleKeyUp}
              tabIndex={manualControl ? 0 : -1}
            >
              {screenshot && isRunning ? (
                <>
                  <img
                    src={screenshot}
                    alt="Live screen"
                    className="w-full h-full object-contain"
                    draggable="false"
                  />
                  {manualControl && (
                    <GhostCursor
                      pendingPoints={pendingPoints}
                      sentPoints={sentPoints}
                    />
                  )}
                </>
              ) : (
                <div className="flex items-center justify-center h-full text-dark-500">
                  <div className="text-center">
                    {isRunning ? (
                      <>
                        <Loader className="w-6 h-6 animate-spin mx-auto mb-2" />
                        Waiting for screen...
                      </>
                    ) : (
                      <>
                        <AlertCircle className="w-6 h-6 mx-auto mb-2" />
                        Profile is not running.
                      </>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Metrics & Media */}
        <div className="flex flex-col space-y-4 min-h-0 overflow-y-auto pr-2">
          {/* Metrics */}
          {metrics && isRunning && (
            <div className="card flex-shrink-0">
              <h3 className="font-semibold text-white mb-3">Resources</h3>
              <div className="space-y-3">
                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-dark-400 flex items-center">
                      <HardDrive className="w-3 h-3 mr-1" /> Memory
                    </span>
                    <span className="text-white">
                      {metrics.memory_mb} / {metrics.memory_limit_mb} MB
                    </span>
                  </div>
                  <div className="w-full h-2 bg-dark-700 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-primary-500 transition-all"
                      style={{
                        width: `${Math.min(100, (metrics.memory_mb / metrics.memory_limit_mb) * 100)}%`,
                      }}
                    />
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-dark-400 flex items-center">
                      <Cpu className="w-3 h-3 mr-1" /> CPU
                    </span>
                    <span className="text-white">
                      {metrics.cpu_percent?.toFixed(1)}%
                    </span>
                  </div>
                  <div className="w-full h-2 bg-dark-700 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-success-500 transition-all"
                      style={{
                        width: `${Math.min(100, metrics.cpu_percent)}%`,
                      }}
                    />
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Screenshots Gallery */}
          <div className="card flex-shrink-0">
            <div className="flex justify-between items-center mb-3">
              <h3 className="font-semibold text-white">Screenshots</h3>
              <span className="text-xs text-dark-400">
                {screenshots.length}
              </span>
            </div>
            <div className="grid grid-cols-3 gap-2">
              {screenshots.slice(0, 9).map((ss) =>
                ss.blobUrl ? (
                  <div
                    key={ss.id}
                    className="aspect-video bg-dark-700 rounded overflow-hidden relative group cursor-pointer"
                    onClick={() => setViewingImage(ss.blobUrl)}
                  >
                    <img
                      src={ss.blobUrl}
                      alt="Thumb"
                      className="w-full h-full object-cover"
                    />
                    <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-all gap-1">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDownloadMedia(ss.url, `${ss.id}.png`);
                        }}
                        className="p-1 bg-dark-800 rounded hover:bg-primary-600"
                        title="Download"
                      >
                        <Download className="w-4 h-4 text-white" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteScreenshot(ss.id + ".png", ss.id);
                        }}
                        className="p-1 bg-dark-800 rounded hover:bg-error-600"
                        title="Delete"
                      >
                        <Trash2 className="w-4 h-4 text-white" />
                      </button>
                    </div>
                  </div>
                ) : null,
              )}
              {screenshots.length === 0 && (
                <div className="col-span-3 text-center py-4 text-xs text-dark-500">
                  No screenshots yet. Click the button above.
                </div>
              )}
            </div>
          </div>

          {/* Videos Gallery */}
          <div className="card flex-shrink-0">
            <div className="flex justify-between items-center mb-3">
              <h3 className="font-semibold text-white">Session Videos</h3>
              <span className="text-xs text-dark-400">{videos.length}</span>
            </div>
            <div className="space-y-2">
              {videos.length === 0 ? (
                <p className="text-xs text-dark-500 text-center py-4">
                  Use the Record button to capture video.
                </p>
              ) : (
                videos.slice(0, 6).map((vid) => (
                  <div
                    key={vid.id}
                    className="flex items-center justify-between p-2 bg-dark-700 rounded hover:bg-dark-600 transition-colors cursor-pointer"
                    onClick={() => openVideoPlayer(vid)}
                  >
                    <div className="flex items-center space-x-2">
                      <Video className="w-4 h-4 text-primary-400" />
                      <div>
                        <span className="text-xs text-white block">
                          {new Date(vid.timestamp * 1000).toLocaleString()}
                        </span>
                        <span className="text-xs text-dark-500">
                          {(vid.size_bytes / 1024 / 1024).toFixed(1)} MB
                        </span>
                      </div>
                    </div>
                    <div className="flex gap-1">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDownloadMedia(
                            vid.url,
                            vid.filename || `${vid.id}.mp4`,
                          );
                        }}
                        className="btn btn-xs btn-secondary"
                        title="Download"
                      >
                        <Download className="w-3 h-3" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteVideo(
                            vid.filename || `${vid.id}.mp4`,
                            vid.id,
                          );
                        }}
                        className="btn btn-xs btn-error"
                        title="Delete"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>

      {/* --- Modals --- */}

      {/* Image Viewer Modal */}
      {viewingImage && (
        <div
          className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-8"
          onClick={() => setViewingImage(null)}
        >
          <button
            className="absolute top-4 right-4 text-white hover:text-primary-400 transition-colors"
            onClick={() => setViewingImage(null)}
          >
            <X className="w-8 h-8" />
          </button>
          <img
            src={viewingImage}
            alt="Screenshot"
            className="max-w-full max-h-full object-contain shadow-2xl rounded"
          />
        </div>
      )}

      {/* Video Player Modal */}
      {playingVideo && (
        <div
          className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-8"
          onClick={() => {
            URL.revokeObjectURL(playingVideo.blobUrl);
            setPlayingVideo(null);
          }}
        >
          <div
            className="bg-dark-900 rounded-lg p-4 w-full max-w-4xl shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex justify-between items-center mb-2">
              <h3 className="text-white font-medium">Recording Playback</h3>
              <button
                onClick={() => {
                  URL.revokeObjectURL(playingVideo.blobUrl);
                  setPlayingVideo(null);
                }}
                className="text-dark-400 hover:text-white transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            {playingVideo.blobUrl ? (
              <video
                controls
                autoPlay
                className="w-full bg-black rounded"
                src={playingVideo.blobUrl}
              >
                Your browser does not support the video tag.
              </video>
            ) : (
              <div className="text-center text-white py-10">
                Loading video...
              </div>
            )}
            <div className="flex justify-end mt-3 gap-2">
              <button
                onClick={() =>
                  handleDownloadMedia(
                    playingVideo.url,
                    playingVideo.filename || `${playingVideo.id}.mp4`,
                  )
                }
                className="btn btn-sm btn-primary"
              >
                <Download className="w-3 h-3 mr-2" />
                Download Video
              </button>
              <button
                onClick={() => {
                  URL.revokeObjectURL(playingVideo.blobUrl);
                  setPlayingVideo(null);
                }}
                className="btn btn-sm btn-secondary"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default Monitoring;
