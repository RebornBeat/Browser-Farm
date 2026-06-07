import React, { useState, useEffect, useRef } from "react";
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
} from "lucide-react";
import { apiClient } from "../api/client";
import { useServerHealth } from "../context/ServerHealthContext";
import store from "../store/db";

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
  const controlWsRef = useRef(null);
  const canvasRef = useRef(null);

  // --- Media Modal State ---
  const [viewingImage, setViewingImage] = useState(null);
  const [playingVideo, setPlayingVideo] = useState(null);

  // 1. Initialization: Find Profile and Server
  useEffect(() => {
    const init = async () => {
      if (!profileId || servers.length === 0) return;

      let foundProfile = null;
      let foundServer = null;

      // Strategy: Check local store first (fastest)
      const localProfiles = (await store.get("profiles")) || [];
      const localP = localProfiles.find((p) => p.id === profileId);

      if (localP) {
        const s = servers.find((srv) => srv.id === localP.serverId);
        if (s) {
          foundProfile = localP;
          foundServer = s;
        }
      }

      // Fallback: Iterate servers if not found locally (e.g., deep link)
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

      setProfile(foundProfile);
      setServer(foundServer);
      setIsLoadingMeta(false);
    };

    init();
  }, [profileId, servers, healthData]);

  // 2. Data Polling
  useEffect(() => {
    if (!server || !profile || profile.status !== "running") return;

    const interval = setInterval(() => {
      loadCurrentScreenshot();
      loadMetrics();
      loadMedia();
      syncUrl();
    }, 3000); // Poll every 3 seconds

    return () => clearInterval(interval);
  }, [server, profile]);

  // 3. Manual Control WebSocket Lifecycle
  useEffect(() => {
    if (manualControl && server && profile) {
      startManualControl();
    } else {
      stopManualControl();
    }
    // Cleanup on unmount
    return () => stopManualControl();
  }, [manualControl, server, profile]);

  // --- Data Loaders ---

  const loadCurrentScreenshot = async () => {
    if (!server || !profile) return;
    try {
      const url = await apiClient.getScreenshot(server.id, profile.id);
      setScreenshot(url);
    } catch (e) {
      // Silent fail for polling
    }
  };

  const loadMetrics = async () => {
    if (!server || !profile) return;
    try {
      const data = await apiClient.getMetrics(server.id, profile.id);
      setMetrics(data);
    } catch (e) {}
  };

  // FIX: Fetch media as Blob to support Auth Headers for thumbnails
  const loadMedia = async () => {
    if (!server || !profile) return;
    try {
      const client = apiClient.getClient(server.id);

      // 1. Screenshots - Fetch List
      const ssRes = await client.get(`/profiles/${profile.id}/screenshots`);
      const ssData = ssRes.data.screenshots || [];

      // 2. Create Blob URLs for Screenshots (Thumbnails)
      // This prevents broken images due to Auth headers required on <img> src
      const ssWithBlobs = await Promise.all(
        ssData.map(async (ss) => {
          try {
            const resp = await client.get(ss.url, { responseType: "blob" });
            return { ...ss, blobUrl: URL.createObjectURL(resp.data) };
          } catch {
            return { ...ss, blobUrl: null };
          }
        }),
      );
      setScreenshots(ssWithBlobs);

      // 3. Videos - Fetch List Only (Metadata)
      // We do not download video files for the list, just metadata.
      const vidRes = await client.get(`/profiles/${profile.id}/videos`);
      setVideos(vidRes.data.videos || []);
    } catch (e) {
      console.error("Failed to load media", e);
    }
  };

  // FIX: Sync URL from Server
  const syncUrl = async () => {
    if (!server || !profile) return;
    try {
      const data = await apiClient.getProfile(server.id, profile.id);
      if (data.current_url) {
        setUrlInput(data.current_url);
      }
    } catch (e) {}
  };

  // --- Navigation Actions ---

  const handleNavigate = async (e) => {
    if (e) e.preventDefault();
    if (!server || !profile || !urlInput) return;
    try {
      let url = urlInput;
      // Auto-prefix protocol
      if (!url.startsWith("http://") && !url.startsWith("https://")) {
        url = "https://" + url;
      }
      await apiClient.navigateTo(server.id, profile.id, url);
      setUrlInput(url); // Update with normalized URL
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

  const takeScreenshot = async () => {
    if (!server || !profile) return;
    try {
      await apiClient.takeScreenshot(server.id, profile.id);
      loadMedia(); // Refresh list
    } catch (error) {
      alert("Failed to take screenshot: " + error.message);
    }
  };

  // --- Manual Control Logic ---

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
  };

  const stopManualControl = () => {
    if (controlWsRef.current) {
      controlWsRef.current.close();
      controlWsRef.current = null;
    }
  };

  const sendControlAction = (action) => {
    if (
      controlWsRef.current &&
      controlWsRef.current.readyState === WebSocket.OPEN
    ) {
      controlWsRef.current.send(JSON.stringify(action));
    }
  };

  // FIX: Robust Coordinate Mapping
  const getCoords = (e) => {
    if (!canvasRef.current) return { x: 0, y: 0 };

    // Use the image element for bounds if possible, fallback to container
    // This ensures clicks are accurate even with letterboxing (object-contain)
    const img = canvasRef.current.querySelector("img");
    const target = img || canvasRef.current;

    const rect = target.getBoundingClientRect();

    // Calculate scale
    const scaleX = 1920 / rect.width;
    const scaleY = 1080 / rect.height;

    const x = Math.round((e.clientX - rect.left) * scaleX);
    const y = Math.round((e.clientY - rect.top) * scaleY);

    return { x, y };
  };

  const handleMouseMove = (e) => {
    if (!manualControl) return;
    const { x, y } = getCoords(e);
    sendControlAction({ type: "mouse_move", x, y });
  };

  const handleClick = (e) => {
    if (!manualControl) return;
    const { x, y } = getCoords(e);
    sendControlAction({ type: "mouse_click", x, y, button: "left" });
  };

  const handleKeyDown = (e) => {
    if (!manualControl) return;
    // Map special keys for the server
    const keyMap = {
      " ": "Space",
      ArrowUp: "ArrowUp",
      ArrowDown: "ArrowDown",
      ArrowLeft: "ArrowLeft",
      ArrowRight: "ArrowRight",
    };
    const key = keyMap[e.key] || e.key;
    sendControlAction({ type: "keyboard", text: key });
  };

  // --- Media Helpers ---

  const handleDownloadMedia = async (url, filename) => {
    if (!server) return;
    try {
      // Fetch as blob with auth headers
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
      console.error("Download failed", e);
      alert("Failed to download media.");
    }
  };

  // FIX: Load video as blob when opening player
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

  // --- Render ---

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

  return (
    <div className="animate-fade-in flex flex-col h-full">
      {/* Header Bar */}
      <div className="flex items-center mb-4 flex-shrink-0 gap-2">
        <button onClick={() => navigate(-1)} className="btn btn-secondary">
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div className="flex-1">
          <h1 className="text-xl font-bold text-white">{profile.name}</h1>
          <p className="text-xs text-dark-400">{profile.id}</p>
        </div>

        {/* Navigation Controls */}
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

        <button onClick={takeScreenshot} className="btn btn-primary ml-2">
          <Camera className="w-4 h-4 mr-2" /> Screenshot
        </button>

        <button
          onClick={() => setManualControl(!manualControl)}
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
      </div>

      {/* Main Layout */}
      <div className="flex-1 grid grid-cols-3 gap-6 min-h-0">
        {/* Left Column: Live View */}
        <div className="col-span-2 flex flex-col min-h-0">
          <div className="card flex-1 flex flex-col relative">
            <h3 className="font-semibold text-white mb-2">Live View</h3>

            {manualControl && (
              <div className="absolute top-1 right-1 z-20 bg-success-500/80 text-white text-xs px-2 py-1 rounded animate-pulse pointer-events-none">
                Control Active - Click or Type to interact
              </div>
            )}

            <div
              ref={canvasRef}
              className={`flex-1 bg-dark-900 rounded-lg overflow-hidden relative border border-dark-700 ${
                manualControl ? "cursor-crosshair" : ""
              }`}
              onMouseMove={handleMouseMove}
              onClick={handleClick}
              onKeyDown={handleKeyDown}
              tabIndex={manualControl ? 0 : -1} // Focus required for keyboard events
            >
              {screenshot ? (
                <img
                  src={screenshot}
                  alt="Live screen"
                  className="w-full h-full object-contain"
                  draggable="false"
                />
              ) : (
                <div className="flex items-center justify-center h-full text-dark-500">
                  <div className="text-center">
                    <Loader className="w-6 h-6 animate-spin mx-auto mb-2" />
                    Waiting for screen...
                    <p className="text-xs mt-1">(Ensure profile is running)</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Metrics & Media */}
        <div className="flex flex-col space-y-4 min-h-0 overflow-y-auto pr-2">
          {/* Metrics */}
          {metrics && (
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
              {screenshots.slice(0, 6).map((ss) =>
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
                    <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-all gap-2">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDownloadMedia(ss.url, `${ss.id}.png`);
                        }}
                        className="p-1 bg-dark-800 rounded hover:bg-primary-600"
                      >
                        <Download className="w-4 h-4 text-white" />
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
                  Videos are recorded automatically.
                </p>
              ) : (
                videos.slice(0, 4).map((vid) => (
                  <div
                    key={vid.id}
                    className="flex items-center justify-between p-2 bg-dark-700 rounded hover:bg-dark-600 transition-colors cursor-pointer"
                    onClick={() => openVideoPlayer(vid)}
                  >
                    <div className="flex items-center space-x-2">
                      <Video className="w-4 h-4 text-primary-400" />
                      <span className="text-xs text-white">
                        {new Date(vid.timestamp * 1000).toLocaleString()}
                      </span>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation(); // Prevent opening player
                        handleDownloadMedia(vid.url, `${vid.id}.webm`);
                      }}
                      className="btn btn-xs btn-secondary"
                    >
                      <Download className="w-3 h-3" />
                    </button>
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
            onClick={(e) => e.stopPropagation()} // Prevent closing when clicking inside video
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
                    `${playingVideo.id}.webm`,
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
