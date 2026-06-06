import React, { useState, useEffect, useCallback } from "react";
import { Settings, MonitorPlay, X } from "lucide-react";
import LiveScreenGrid from "../components/LiveScreenGrid";
import store from "../store/db";
import { useServerHealth } from "../context/ServerHealthContext";
import { apiClient } from "../api/client";

function Home() {
  const { servers, healthData } = useServerHealth();
  const [screens, setScreens] = useState([]);
  const [showSettings, setShowSettings] = useState(false);
  const [availableProfiles, setAvailableProfiles] = useState([]);
  const [selectedProfileIds, setSelectedProfileIds] = useState([]);

  // 1. Load, Sync, and Auto-Populate Logic
  const loadAndSync = useCallback(async () => {
    const settings = (await store.get("settings")) || {};
    let currentScreens = settings.homeScreens || [];
    const localProfiles = (await store.get("profiles")) || [];

    // Build list of RUNNING profiles from all connected servers
    const runningProfiles = [];

    for (const server of servers) {
      // Only query online servers
      if (healthData[server.id]?.status !== "online") continue;

      try {
        const serverProfiles = await apiClient.listProfiles(server.id);
        serverProfiles.forEach((p) => {
          if (p.status === "running") {
            // Merge with local data to get friendly name
            const local = localProfiles.find((lp) => lp.id === p.id);
            runningProfiles.push({
              id: p.id,
              serverId: server.id,
              name: local?.name || p.id,
            });
          }
        });
      } catch (e) {
        console.warn(`Failed to sync profiles for server ${server.name}`);
      }
    }

    setAvailableProfiles(runningProfiles);

    // AUTO-POPULATE LOGIC
    // If screens are empty, fill with first 4 running profiles found
    if (currentScreens.length === 0 && runningProfiles.length > 0) {
      currentScreens = runningProfiles.slice(0, 4).map((p) => ({
        serverId: p.serverId,
        profileId: p.id,
        profileName: p.name,
      }));

      // Save to store immediately so it persists
      await store.set("settings", { ...settings, homeScreens: currentScreens });
    }

    setScreens(currentScreens);

    // Update selection state for the modal
    setSelectedProfileIds(currentScreens.map((s) => s.profileId));
  }, [servers, healthData]);

  useEffect(() => {
    loadAndSync();
    // Refresh every 15 seconds to catch new profiles
    const interval = setInterval(loadAndSync, 15000);
    return () => clearInterval(interval);
  }, [loadAndSync]);

  // 2. Modal Actions
  const handleToggleProfile = (profile) => {
    const exists = selectedProfileIds.includes(profile.id);
    if (exists) {
      setSelectedProfileIds((prev) => prev.filter((id) => id !== profile.id));
    } else {
      if (selectedProfileIds.length >= 12) {
        alert("Maximum 12 screens allowed.");
        return;
      }
      setSelectedProfileIds((prev) => [...prev, profile.id]);
    }
  };

  const saveSettings = async () => {
    const newScreens = availableProfiles
      .filter((p) => selectedProfileIds.includes(p.id))
      .map((p) => ({
        serverId: p.serverId,
        profileId: p.id,
        profileName: p.name,
      }));

    const settings = (await store.get("settings")) || {};
    await store.set("settings", { ...settings, homeScreens: newScreens });
    setScreens(newScreens);
    setShowSettings(false);
  };

  return (
    <div className="animate-fade-in">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Home</h1>
          <p className="text-dark-400">Monitor your live browser contexts</p>
        </div>

        <button
          onClick={() => setShowSettings(true)}
          className="btn btn-secondary flex items-center"
        >
          <Settings className="w-4 h-4 mr-2" />
          Configure Screens
        </button>
      </div>

      {/* Render Grid - Component handles the 4-slot logic */}
      <LiveScreenGrid screens={screens} onRefresh={loadAndSync} />

      {/* Settings Modal - Updated UI */}
      {showSettings && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-dark-800 rounded-lg p-6 w-full max-w-2xl max-h-[90vh] flex flex-col border border-dark-700 shadow-xl">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-xl font-bold text-white">
                Configure Screens
              </h3>
              <button
                onClick={() => setShowSettings(false)}
                className="text-dark-400 hover:text-white transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="mb-4 text-sm text-dark-400 border-b border-dark-700 pb-3">
              <span className="text-white font-medium">
                {selectedProfileIds.length}
              </span>{" "}
              screens selected (Min 4 recommended)
            </div>

            <div className="flex-1 overflow-y-auto space-y-2 pr-2">
              {availableProfiles.length === 0 ? (
                <div className="text-center text-dark-500 py-12 bg-dark-900 rounded-lg mt-2">
                  <MonitorPlay className="w-8 h-8 mx-auto mb-3 opacity-50" />
                  No running profiles found.
                  <p className="text-xs mt-1">
                    Start a profile from the Profiles tab.
                  </p>
                </div>
              ) : (
                availableProfiles.map((profile) => {
                  const isSelected = selectedProfileIds.includes(profile.id);
                  return (
                    <div
                      key={profile.id}
                      onClick={() => handleToggleProfile(profile)}
                      className={`p-3 rounded-lg flex items-center justify-between cursor-pointer transition-all border ${
                        isSelected
                          ? "bg-primary-900/30 border-primary-500"
                          : "bg-dark-900 border-transparent hover:border-dark-600"
                      }`}
                    >
                      <div className="flex items-center space-x-3">
                        <MonitorPlay
                          className={`w-5 h-5 ${
                            isSelected ? "text-primary-400" : "text-dark-500"
                          }`}
                        />
                        <div>
                          <p className="text-white font-medium">
                            {profile.name}
                          </p>
                          <p className="text-xs text-dark-400">{profile.id}</p>
                        </div>
                      </div>
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => {}}
                        className="h-5 w-5 rounded border-dark-500 text-primary-600 focus:ring-primary-500 cursor-pointer bg-dark-700"
                      />
                    </div>
                  );
                })
              )}
            </div>

            <div className="flex space-x-3 mt-6 pt-4 border-t border-dark-700">
              <button
                onClick={() => setShowSettings(false)}
                className="btn btn-secondary flex-1"
              >
                Cancel
              </button>
              <button onClick={saveSettings} className="btn btn-primary flex-1">
                Save Layout
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default Home;
