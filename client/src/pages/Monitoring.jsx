import React, { useState, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  Download,
  Play,
  Pause,
  Square,
  Maximize2,
} from "lucide-react";
import { apiClient } from "../api/client";
import store from "../store/db";

function Monitoring() {
  const { profileId } = useParams();
  const navigate = useNavigate();
  const [profile, setProfile] = useState(null);
  const [screenshot, setScreenshot] = useState(null);
  const [screenshots, setScreenshots] = useState([]);
  const [logs, setLogs] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [manualControl, setManualControl] = useState(false);
  const wsRef = useRef(null);
  const controlWsRef = useRef(null);
  const canvasRef = useRef(null);

  useEffect(() => {
    loadProfile();
    const interval = setInterval(loadData, 2000);
    return () => clearInterval(interval);
  }, [profileId]);

  useEffect(() => {
    if (manualControl) {
      startManualControl();
    } else {
      stopManualControl();
    }
    return () => stopManualControl();
  }, [manualControl]);

  const loadProfile = () => {
    const profiles = store.get("profiles") || [];
    const p = profiles.find((p) => p.id === profileId);
    setProfile(p);
  };

  const loadData = async () => {
    if (!profile) return;

    try {
      // Load screenshot
      const screenshotUrl = await apiClient.getScreenshot(
        profile.serverId,
        profile.id,
      );
      setScreenshot(screenshotUrl);

      // Load metrics
      const metricsData = await apiClient.getMetrics(
        profile.serverId,
        profile.id,
      );
      setMetrics(metricsData);

      // Load screenshots list
      const screenshotsList = await apiClient.listScreenshots(
        profile.serverId,
        profile.id,
      );
      setScreenshots(screenshotsList);
    } catch (error) {
      console.error("Failed to load data:", error);
    }
  };

  const startManualControl = () => {
    if (!profile) return;

    const url = apiClient.getControlUrl(profile.serverId, profile.id);
    controlWsRef.current = new WebSocket(url);

    controlWsRef.current.onopen = () => {
      console.log("Manual control connected");
    };

    controlWsRef.current.onerror = (error) => {
      console.error("Control WebSocket error:", error);
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

  const handleMouseMove = (e) => {
    if (!manualControl || !canvasRef.current) return;

    const rect = canvasRef.current.getBoundingClientRect();
    const x = (e.clientX - rect.left) * (1920 / rect.width);
    const y = (e.clientY - rect.top) * (1080 / rect.height);

    sendControlAction({ type: "mouse_move", x, y });
  };

  const handleClick = (e) => {
    if (!manualControl || !canvasRef.current) return;

    const rect = canvasRef.current.getBoundingClientRect();
    const x = (e.clientX - rect.left) * (1920 / rect.width);
    const y = (e.clientY - rect.top) * (1080 / rect.height);

    sendControlAction({ type: "mouse_click", x, y, button: "left" });
  };

  const handleKeyPress = (e) => {
    if (!manualControl) return;
    sendControlAction({ type: "keyboard", text: e.key });
  };

  const takeScreenshot = async () => {
    try {
      await apiClient.takeScreenshot(profile.serverId, profile.id);
      loadData();
      alert("Screenshot saved!");
    } catch (error) {
      alert("Failed to take screenshot: " + error.message);
    }
  };

  const downloadScreenshot = (url) => {
    const link = document.createElement("a");
    link.href = url;
    link.download = `screenshot_${Date.now()}.png`;
    link.click();
  };

  if (!profile) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-dark-400">Profile not found</p>
      </div>
    );
  }

  return (
    <div className="animate-fade-in">
      <div className="flex items-center mb-6">
        <button onClick={() => navigate(-1)} className="btn btn-secondary mr-4">
          <ArrowLeft className="w-4 h-4" />
        </button>

        <div className="flex-1">
          <h1 className="text-2xl font-bold text-white">{profile.name}</h1>
          <p className="text-dark-400">Profile ID: {profile.id}</p>
        </div>

        <div className="flex items-center space-x-3">
          <span className={`status-badge status-${profile.status}`}>
            {profile.status}
          </span>
          <button onClick={takeScreenshot} className="btn btn-primary">
            <Download className="w-4 h-4 mr-2" />
            Screenshot
          </button>
          <button
            onClick={() => setManualControl(!manualControl)}
            className={`btn ${manualControl ? "btn-error" : "btn-success"}`}
          >
            {manualControl ? "Release Control" : "Take Control"}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Main Screen */}
        <div className="col-span-2 space-y-6">
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-white">Live Screen</h3>
              {manualControl && (
                <span className="text-sm text-success-500 animate-pulse">
                  ● Manual Control Active
                </span>
              )}
            </div>

            <div
              ref={canvasRef}
              className={`relative aspect-video bg-dark-900 rounded-lg overflow-hidden ${
                manualControl ? "cursor-none" : ""
              }`}
              onMouseMove={handleMouseMove}
              onClick={handleClick}
              onKeyDown={handleKeyPress}
              tabIndex={manualControl ? 0 : -1}
            >
              {screenshot ? (
                <img
                  src={screenshot}
                  alt="Live screen"
                  className="w-full h-full object-contain"
                />
              ) : (
                <div className="flex items-center justify-center h-full">
                  <div className="text-center">
                    <div className="animate-spin w-8 h-8 border-4 border-primary-500 border-t-transparent rounded-full mx-auto mb-2"></div>
                    <p className="text-sm text-dark-400">Loading...</p>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Screenshots Gallery */}
          <div className="card">
            <h3 className="font-semibold text-white mb-4">Screenshots</h3>

            <div className="grid grid-cols-4 gap-3">
              {screenshots.slice(0, 8).map((ss) => (
                <div key={ss.id} className="relative group">
                  <img
                    src={ss.url}
                    alt="Screenshot"
                    className="w-full aspect-video object-cover rounded-lg cursor-pointer"
                    onClick={() => setScreenshot(ss.url)}
                  />
                  <button
                    onClick={() => downloadScreenshot(ss.url)}
                    className="absolute top-2 right-2 p-1 bg-dark-900/80 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    <Download className="w-4 h-4 text-white" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Metrics */}
          {metrics && (
            <div className="card">
              <h3 className="font-semibold text-white mb-4">Metrics</h3>

              <div className="space-y-4">
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-dark-400">Memory</span>
                    <span className="text-white">
                      {metrics.memory_mb}MB / {metrics.memory_limit_mb}MB
                    </span>
                  </div>
                  <div className="w-full h-2 bg-dark-700 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-primary-500 transition-all"
                      style={{
                        width: `${(metrics.memory_mb / metrics.memory_limit_mb) * 100}%`,
                      }}
                    />
                  </div>
                </div>

                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-dark-400">CPU</span>
                    <span className="text-white">
                      {metrics.cpu_percent?.toFixed(1)}%
                    </span>
                  </div>
                  <div className="w-full h-2 bg-dark-700 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-success-500 transition-all"
                      style={{ width: `${metrics.cpu_percent}%` }}
                    />
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Logs */}
          <div className="card">
            <h3 className="font-semibold text-white mb-4">Logs</h3>

            <div className="space-y-2 max-h-96 overflow-y-auto font-mono text-xs">
              {logs.length === 0 ? (
                <p className="text-dark-500">No logs yet</p>
              ) : (
                logs.map((log, i) => (
                  <div key={i} className="text-dark-300">
                    <span className="text-dark-500">{log.timestamp}</span>{" "}
                    <span
                      className={`${
                        log.level === "error"
                          ? "text-error-500"
                          : log.level === "warning"
                            ? "text-warning-500"
                            : "text-dark-300"
                      }`}
                    >
                      {log.message}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Monitoring;
