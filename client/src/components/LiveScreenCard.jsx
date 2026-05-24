import React, { useState, useEffect, useRef } from "react";
import { Maximize2, Pause, Play, Square } from "lucide-react";
import { apiClient } from "../api/client";

function LiveScreenCard({ serverId, profileId, profileName, onExpand }) {
  const [imageUrl, setImageUrl] = useState(null);
  const [status, setStatus] = useState("idle");
  const wsRef = useRef(null);
  const intervalRef = useRef(null);

  useEffect(() => {
    startStreaming();
    return () => stopStreaming();
  }, [serverId, profileId]);

  const startStreaming = () => {
    // Use periodic screenshots instead of WebSocket for simplicity
    intervalRef.current = setInterval(async () => {
      try {
        const url = await apiClient.getScreenshot(serverId, profileId);
        setImageUrl(url);
      } catch (error) {
        console.error("Failed to fetch screenshot:", error);
      }
    }, 1000); // Update every second
  };

  const stopStreaming = () => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
    }
  };

  return (
    <div className="card group relative overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-medium text-white">{profileName}</h3>
          <p className="text-xs text-dark-400">Profile ID: {profileId}</p>
        </div>
        <div className="flex items-center space-x-2">
          <span className={`status-badge status-${status}`}>{status}</span>
          <button
            onClick={onExpand}
            className="p-1 text-dark-400 hover:text-white transition-colors opacity-0 group-hover:opacity-100"
          >
            <Maximize2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Screen */}
      <div className="relative aspect-video bg-dark-900 rounded-lg overflow-hidden">
        {imageUrl ? (
          <img
            src={imageUrl}
            alt="Live screen"
            className="w-full h-full object-contain"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <div className="text-center">
              <div className="animate-spin w-8 h-8 border-4 border-primary-500 border-t-transparent rounded-full mx-auto mb-2"></div>
              <p className="text-sm text-dark-400">Loading...</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default LiveScreenCard;
