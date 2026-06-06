import React, { useState, useEffect, useRef } from "react";
import { Maximize2, AlertTriangle, Loader } from "lucide-react";
import { apiClient } from "../api/client";

function LiveScreenCard({ serverId, profileId, profileName, onExpand }) {
  const [imageUrl, setImageUrl] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);
  const intervalRef = useRef(null);

  useEffect(() => {
    fetchScreenshot();
    // Poll every 2 seconds for updates
    intervalRef.current = setInterval(fetchScreenshot, 2000);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [serverId, profileId]);

  const fetchScreenshot = async () => {
    try {
      // Revoke old URL to prevent memory leaks
      if (imageUrl && imageUrl.startsWith("blob:")) {
        URL.revokeObjectURL(imageUrl);
      }

      const url = await apiClient.getScreenshot(serverId, profileId);
      setImageUrl(url);
      setHasError(false);
      setIsLoading(false);
    } catch (error) {
      console.error("Screenshot fetch failed:", error);
      setHasError(true);
      setIsLoading(false);
    }
  };

  return (
    <div className="card group relative overflow-hidden flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-2 px-1">
        <h3 className="text-sm font-medium text-white truncate">
          {profileName}
        </h3>
        <button
          onClick={onExpand}
          className="p-1 text-dark-400 hover:text-white transition-colors opacity-0 group-hover:opacity-100"
          title="Open Full Monitor"
        >
          <Maximize2 className="w-4 h-4" />
        </button>
      </div>

      {/* Screen Area */}
      <div className="relative flex-1 bg-dark-900 rounded-lg overflow-hidden border border-dark-700 min-h-[200px]">
        {/* Loading State */}
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-dark-800 z-10">
            <Loader className="w-6 h-6 text-primary-500 animate-spin" />
          </div>
        )}

        {/* Error State */}
        {hasError && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-dark-900 p-4 z-10">
            <AlertTriangle className="w-8 h-8 text-error-500 mb-2" />
            <p className="text-xs text-dark-400 text-center">
              Connection Failed
            </p>
          </div>
        )}

        {/* Success State */}
        {!isLoading && !hasError && imageUrl && (
          <img
            src={imageUrl}
            alt="Live screen"
            className="w-full h-full object-contain"
            onError={() => setHasError(true)} // Handle image decoding errors
          />
        )}
      </div>
    </div>
  );
}

export default LiveScreenCard;
