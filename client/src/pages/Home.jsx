import React, { useState, useEffect } from "react";
import { Settings } from "lucide-react";
import LiveScreenGrid from "../components/LiveScreenGrid";
import store from "../store/db";

function Home() {
  const [screens, setScreens] = useState([]);
  const [screenCount, setScreenCount] = useState(4);
  const [showSettings, setShowSettings] = useState(false);
  const [profiles, setProfiles] = useState([]);

  useEffect(() => {
    loadSettings();
    loadProfiles();
  }, []);

  const loadSettings = async () => {
    const settings = (await store.get("settings")) || {};
    setScreenCount(settings.homeScreenCount || 4);
    setScreens(settings.homeScreens || []);
  };

  const loadProfiles = async () => {
    const storedProfiles = (await store.get("profiles")) || [];
    setProfiles(storedProfiles.filter((p) => p.status === "running"));
  };

  const saveSettings = async () => {
    const settings = (await store.get("settings")) || {};
    settings.homeScreenCount = screenCount;
    settings.homeScreens = screens;
    await store.set("settings", settings);
    setShowSettings(false);
  };

  const addScreen = (profileId) => {
    const profile = profiles.find((p) => p.id === profileId);
    if (!profile || screens.some((s) => s.profileId === profileId)) return;

    const newScreen = {
      serverId: profile.serverId,
      profileId: profile.id,
      profileName: profile.name,
    };

    const updatedScreens = [...screens, newScreen];
    setScreens(updatedScreens);
  };

  const removeScreen = (profileId) => {
    const updatedScreens = screens.filter((s) => s.profileId !== profileId);
    setScreens(updatedScreens);
  };

  const hasEnoughProfiles = profiles.length >= screenCount;

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

      {screens.length === 0 ? (
        <div className="card text-center py-16">
          <h3 className="text-xl font-semibold text-white mb-2">
            No screens configured
          </h3>
          <p className="text-dark-400 mb-6">
            {profiles.length === 0
              ? "Launch a profile to view live screens"
              : 'Click "Configure Screens" to select which profiles to display'}
          </p>
          {profiles.length > 0 && (
            <button
              onClick={() => setShowSettings(true)}
              className="btn btn-primary"
            >
              Configure Screens
            </button>
          )}
        </div>
      ) : (
        <LiveScreenGrid screens={screens} />
      )}

      {/* Settings Modal */}
      {showSettings && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-dark-800 rounded-lg p-6 w-full max-w-2xl">
            <h3 className="text-xl font-bold text-white mb-4">
              Configure Home Screens
            </h3>

            <div className="space-y-6">
              <div>
                <label className="block text-sm text-dark-300 mb-2">
                  Number of screens to display (minimum 4)
                </label>
                <input
                  type="number"
                  min="4"
                  max="12"
                  className="input w-full"
                  value={screenCount}
                  onChange={(e) => setScreenCount(parseInt(e.target.value))}
                />
              </div>

              <div>
                <label className="block text-sm text-dark-300 mb-2">
                  Select profiles to display ({screens.length}/{screenCount})
                </label>

                {profiles.length === 0 ? (
                  <p className="text-dark-500 text-sm">
                    No running profiles available
                  </p>
                ) : (
                  <div className="space-y-2 max-h-96 overflow-y-auto">
                    {profiles.map((profile) => {
                      const isSelected = screens.some(
                        (s) => s.profileId === profile.id,
                      );
                      const canAdd = screens.length < screenCount;

                      return (
                        <div
                          key={profile.id}
                          className="flex items-center justify-between p-3 bg-dark-900 rounded-lg"
                        >
                          <div>
                            <p className="text-white font-medium">
                              {profile.name}
                            </p>
                            <p className="text-sm text-dark-400">
                              {profile.id}
                            </p>
                          </div>

                          {isSelected ? (
                            <button
                              onClick={() => removeScreen(profile.id)}
                              className="btn btn-error btn-sm"
                            >
                              Remove
                            </button>
                          ) : (
                            <button
                              onClick={() => addScreen(profile.id)}
                              className="btn btn-primary btn-sm"
                              disabled={!canAdd}
                            >
                              {canAdd ? "Add" : "Full"}
                            </button>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {screens.length < screenCount && profiles.length > 0 && (
                <p className="text-sm text-warning-500">
                  ⚠️ You have fewer screens selected than the minimum (
                  {screens.length}/{screenCount})
                </p>
              )}
            </div>

            <div className="flex space-x-3 mt-6">
              <button
                onClick={() => setShowSettings(false)}
                className="btn btn-secondary flex-1"
              >
                Cancel
              </button>
              <button onClick={saveSettings} className="btn btn-primary flex-1">
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default Home;
