import React, { useState, useEffect } from "react";
import {
  Plus,
  Layout,
  Play,
  Pause,
  Square,
  Trash2,
  Code,
  Circle,
  Loader, // NEW: Added for Initializing state
} from "lucide-react";
import store from "../store/db";
import { apiClient } from "../api/client";
import { useServerHealth } from "../context/ServerHealthContext";

function ProfileManager() {
  // Use Context for Servers and Health Data
  const { servers, healthData } = useServerHealth();

  const [profiles, setProfiles] = useState([]);
  const [proxies, setProxies] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [scripts, setScripts] = useState([]); // Script Library

  const [showAddModal, setShowAddModal] = useState(false);
  const [profileMode, setProfileMode] = useState("automated"); // 'manual', 'automated', 'command_center'
  const [selectedScriptIds, setSelectedScriptIds] = useState([]);

  const [newProfile, setNewProfile] = useState({
    name: "",
    serverId: "",
    proxyId: "", // Empty string means "Select..." initially
    accountIds: [],
    userAgent: "",
    timezone: "America/New_York",
    locale: "en-US",
    memoryThresholdMb: 400,
  });

  // --- DATA LOADING & SYNCING ---

  // Load data initially AND when servers context updates
  useEffect(() => {
    loadData();

    // NEW: Poll every 5 seconds to update status (e.g., Initializing -> Running)
    // This ensures the UI reflects the background task completion.
    const intervalId = setInterval(() => {
      syncProfileStatuses();
    }, 5000);

    return () => clearInterval(intervalId);
  }, [servers]);

  const loadData = async () => {
    // 1. Load Local Data First (Optimistic UI)
    const localProfiles = (await store.get("profiles")) || [];
    setProxies((await store.get("proxies")) || []);
    setAccounts((await store.get("accounts")) || []);
    setScripts((await store.get("scripts")) || []);

    // Set local profiles immediately
    setProfiles(localProfiles);

    // 2. Then sync with server in background
    await syncProfileStatuses(localProfiles);
  };

  const syncProfileStatuses = async (currentProfiles = null) => {
    const localProfiles =
      currentProfiles || (await store.get("profiles")) || [];

    if (!servers || servers.length === 0) return;

    let needsDbUpdate = false;
    const updatedProfiles = [...localProfiles];

    for (const server of servers) {
      // Only sync if server is online
      if (healthData[server.id]?.status !== "online") continue;

      try {
        const serverProfiles = await apiClient.listProfiles(server.id);
        const serverMap = new Map(serverProfiles.map((p) => [p.id, p]));

        updatedProfiles.forEach((p, index) => {
          if (p.serverId === server.id && serverMap.has(p.id)) {
            const serverVersion = serverMap.get(p.id);
            // Update status if changed
            if (p.status !== serverVersion.status) {
              updatedProfiles[index] = { ...p, status: serverVersion.status };
              needsDbUpdate = true;
            }
          }
        });
      } catch (error) {
        console.warn(`Sync failed for server ${server.name}:`, error);
      }
    }

    if (needsDbUpdate) {
      setProfiles(updatedProfiles);
      await store.set("profiles", updatedProfiles);
    }
  };

  // --- ACTIONS ---

  const createProfile = async () => {
    try {
      const server = servers.find((s) => s.id === newProfile.serverId);

      if (!server) {
        alert("Please select a valid server.");
        return;
      }

      if (profileMode === "command_center") {
        const existingCC = profiles.find((p) => p.mode === "command_center");
        if (existingCC) {
          alert(
            "A Command Center profile already exists. Only one is allowed per farm.",
          );
          return;
        }
      }

      const isNoProxy =
        newProfile.proxyId === "none" || newProfile.proxyId === "";
      const proxy = isNoProxy
        ? null
        : proxies.find((p) => p.id === newProfile.proxyId);

      if (!isNoProxy && !proxy) {
        alert("Invalid proxy selected.");
        return;
      }

      if (profileMode !== "manual" && selectedScriptIds.length === 0) {
        alert(
          "Please select at least one script for Automated/Command Center modes.",
        );
        return;
      }

      const selectedScripts = scripts.filter((s) =>
        selectedScriptIds.includes(s.id),
      );
      const scriptCodes = selectedScripts.map((s) => s.code);
      const requirements = [
        ...new Set(selectedScripts.flatMap((s) => s.requirements || [])),
      ];

      // 2. Create profile on server
      const result = await apiClient.createProfile(server.id, {
        name: newProfile.name,
        mode: profileMode,
        proxy_id: proxy ? proxy.id : null,
        user_agent: newProfile.userAgent || undefined,
        timezone: newProfile.timezone,
        locale: newProfile.locale,
        scripts: scriptCodes,
        requirements: requirements,
        memory_threshold_mb: newProfile.memoryThresholdMb,
      });

      if (proxy) {
        await apiClient.registerProxy(server.id, proxy);
      }

      const profile = {
        id: result.id,
        localId: `profile_${Date.now()}`,
        ...newProfile,
        mode: profileMode,
        proxyId: proxy ? proxy.id : null,
        scriptIds: selectedScriptIds,
        status: "idle",
        createdAt: new Date().toISOString(),
      };

      const updatedProfiles = [...profiles, profile];
      await store.set("profiles", updatedProfiles);
      setProfiles(updatedProfiles);

      setShowAddModal(false);
      resetNewProfile();
      alert("Profile created successfully!");
    } catch (error) {
      console.error("Failed to create profile:", error);
      alert("Failed to create profile: " + error.message);
    }
  };

  const resetNewProfile = () => {
    setNewProfile({
      name: "",
      serverId: "",
      proxyId: "",
      accountIds: [],
      userAgent: "",
      timezone: "America/New_York",
      locale: "en-US",
      memoryThresholdMb: 400,
    });
    setSelectedScriptIds([]);
    setProfileMode("automated");
  };

  const startProfile = async (profile) => {
    try {
      if (profile.mode === "command_center") {
        const runningCC = profiles.find(
          (p) =>
            p.mode === "command_center" &&
            ["running", "initializing"].includes(p.status) &&
            p.id !== profile.id,
        );
        if (runningCC) {
          alert(
            `Cannot start: Command Center "${runningCC.name}" is already active.`,
          );
          return;
        }
      }

      const profileAccounts = {};
      profile.accountIds.forEach((accountId) => {
        const account = accounts.find((a) => a.id === accountId);
        if (account) {
          profileAccounts[accountId] = {
            username: account.username,
            password: account.password,
            email: account.email,
            phone: account.phone,
          };
        }
      });

      await apiClient.startProfile(
        profile.serverId,
        profile.id,
        profileAccounts,
      );

      // Optimistic UI Update: Set to 'initializing' immediately
      const updatedProfiles = profiles.map((p) =>
        p.id === profile.id ? { ...p, status: "initializing" } : p,
      );
      setProfiles(updatedProfiles);
      await store.set("profiles", updatedProfiles);
    } catch (error) {
      console.error("Failed to start profile:", error);
      const errorMsg = error.response?.data?.detail || error.message;
      alert("Failed to start profile: " + errorMsg);

      // Revert to stopped on failure
      const updatedProfiles = profiles.map((p) =>
        p.id === profile.id ? { ...p, status: "stopped" } : p,
      );
      setProfiles(updatedProfiles);
    }
  };

  const pauseProfile = async (profile) => {
    try {
      await apiClient.pauseProfile(profile.serverId, profile.id);
      const updatedProfiles = profiles.map((p) =>
        p.id === profile.id ? { ...p, status: "paused" } : p,
      );
      await store.set("profiles", updatedProfiles);
      setProfiles(updatedProfiles);
    } catch (error) {
      console.error("Failed to pause profile:", error);
      alert("Failed to pause profile: " + error.message);
    }
  };

  const stopProfile = async (profile) => {
    try {
      await apiClient.stopProfile(profile.serverId, profile.id);
      const updatedProfiles = profiles.map((p) =>
        p.id === profile.id ? { ...p, status: "stopped" } : p,
      );
      await store.set("profiles", updatedProfiles);
      setProfiles(updatedProfiles);
    } catch (error) {
      console.error("Failed to stop profile:", error);
      alert("Failed to stop profile: " + error.message);
    }
  };

  const deleteProfile = async (profile) => {
    if (!window.confirm("Are you sure you want to delete this profile?"))
      return;

    try {
      await apiClient.deleteProfile(profile.serverId, profile.id);
    } catch (error) {
      console.warn(
        "Server delete failed (proceeding with local delete):",
        error,
      );
    }

    const updatedProfiles = profiles.filter((p) => p.id !== profile.id);
    await store.set("profiles", updatedProfiles);
    setProfiles(updatedProfiles);
  };

  // --- HELPERS ---

  const getServerName = (serverId) => {
    const server = servers.find((s) => s.id === serverId);
    return server?.name || "Unknown";
  };

  const getProxyName = (proxyId) => {
    if (!proxyId) return "No Proxy (Direct)";
    const proxy = proxies.find((p) => p.id === proxyId);
    return proxy ? `${proxy.host}:${proxy.port}` : "Unknown";
  };

  const getScriptNames = (scriptIds) => {
    if (!scriptIds || scriptIds.length === 0) return "None";
    return scriptIds
      .map((id) => scripts.find((s) => s.id === id)?.name || id)
      .join(", ");
  };

  const commandCenterExists = profiles.some((p) => p.mode === "command_center");

  // --- RENDER ---

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-white">Profiles</h2>
        <button
          onClick={() => setShowAddModal(true)}
          className="btn btn-primary flex items-center"
        >
          <Plus className="w-4 h-4 mr-2" />
          New Profile
        </button>
      </div>

      <div className="grid gap-4">
        {profiles.map((profile) => (
          <div key={profile.id} className="card">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center space-x-4">
                <div
                  className={`w-12 h-12 rounded-lg flex items-center justify-center ${
                    profile.mode === "command_center"
                      ? "bg-warning-500/20"
                      : profile.mode === "manual"
                        ? "bg-dark-700"
                        : "bg-primary-500/20"
                  }`}
                >
                  <Layout
                    className={`w-6 h-6 ${
                      profile.mode === "command_center"
                        ? "text-warning-500"
                        : profile.mode === "manual"
                          ? "text-dark-400"
                          : "text-primary-500"
                    }`}
                  />
                </div>

                <div>
                  <h3 className="text-lg font-semibold text-white">
                    {profile.name}
                    <span className="ml-2 text-xs font-normal text-dark-500 uppercase">
                      ({profile.mode || "automated"})
                    </span>
                  </h3>
                  <p className="text-sm text-dark-400">
                    {getServerName(profile.serverId)} •{" "}
                    {getProxyName(profile.proxyId)}
                  </p>
                </div>
              </div>

              <div className="flex items-center space-x-3">
                <span
                  className={`status-badge status-${profile.status === "initializing" ? "idle" : profile.status}`}
                >
                  {profile.status}
                </span>

                {/* ACTION BUTTONS */}
                {profile.status === "initializing" ? (
                  <button className="btn btn-secondary" disabled>
                    <Loader className="w-4 h-4 animate-spin" />
                  </button>
                ) : profile.status === "idle" ||
                  profile.status === "stopped" ||
                  profile.status === "crashed" ? (
                  <button
                    onClick={() => startProfile(profile)}
                    className="btn btn-success"
                    title="Start Profile"
                  >
                    <Play className="w-4 h-4" />
                  </button>
                ) : profile.status === "running" ? (
                  <>
                    <button
                      onClick={() => pauseProfile(profile)}
                      className="btn btn-secondary"
                    >
                      <Pause className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => stopProfile(profile)}
                      className="btn btn-error"
                    >
                      <Square className="w-4 h-4" />
                    </button>
                  </>
                ) : profile.status === "paused" ? (
                  <>
                    <button
                      onClick={() => startProfile(profile)}
                      className="btn btn-success"
                    >
                      <Play className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => stopProfile(profile)}
                      className="btn btn-error"
                    >
                      <Square className="w-4 h-4" />
                    </button>
                  </>
                ) : null}

                <button
                  onClick={() => deleteProfile(profile)}
                  className="btn btn-error"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4 text-sm">
              <div>
                <p className="text-dark-400">Memory Limit</p>
                <p className="text-white">{profile.memoryThresholdMb}MB</p>
              </div>
              <div>
                <p className="text-dark-400">Accounts</p>
                <p className="text-white">{profile.accountIds?.length || 0}</p>
              </div>
              <div>
                <p className="text-dark-400">Scripts</p>
                <p
                  className="text-white truncate"
                  title={getScriptNames(profile.scriptIds)}
                >
                  {getScriptNames(profile.scriptIds)}
                </p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Add Profile Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 overflow-y-auto">
          <div className="bg-dark-800 rounded-lg p-6 w-full max-w-2xl m-4 max-h-[90vh] overflow-y-auto">
            <h3 className="text-xl font-bold text-white mb-4">New Profile</h3>

            <div className="space-y-4">
              {/* Profile Name */}
              <div>
                <label className="block text-sm text-dark-300 mb-2">
                  Profile Name
                </label>
                <input
                  type="text"
                  className="input w-full"
                  placeholder="Instagram Bot #1"
                  value={newProfile.name}
                  onChange={(e) =>
                    setNewProfile({ ...newProfile, name: e.target.value })
                  }
                />
              </div>

              {/* Mode Selector */}
              <div>
                <label className="block text-sm text-dark-300 mb-2">
                  Profile Mode
                </label>
                <select
                  className="input w-full"
                  value={profileMode}
                  onChange={(e) => setProfileMode(e.target.value)}
                >
                  <option value="manual">Manual (Browser Only)</option>
                  <option value="automated">Automated (Script Chain)</option>
                  <option value="command_center" disabled={commandCenterExists}>
                    Command Center (Orchestrator){" "}
                    {commandCenterExists ? "- [Already Exists]" : ""}
                  </option>
                </select>
                {commandCenterExists && (
                  <p className="text-xs text-warning-500 mt-1">
                    A Command Center profile already exists. Delete it to create
                    a new one.
                  </p>
                )}
              </div>

              {/* Server Selection */}
              <div>
                <label className="block text-sm text-dark-300 mb-2">
                  Server
                </label>
                <div className="space-y-2 bg-dark-900 p-3 rounded-lg max-h-48 overflow-y-auto">
                  {servers.length === 0 && (
                    <p className="text-dark-500 text-sm text-center py-2">
                      No servers added.
                    </p>
                  )}
                  {servers.map((server) => {
                    const isOnline = healthData[server.id]?.status === "online";
                    return (
                      <label
                        key={server.id}
                        className="flex items-center justify-between p-2 bg-dark-800 rounded cursor-pointer hover:bg-dark-700"
                      >
                        <div className="flex items-center space-x-3">
                          <input
                            type="radio"
                            name="server"
                            value={server.id}
                            checked={newProfile.serverId === server.id}
                            onChange={() =>
                              setNewProfile({
                                ...newProfile,
                                serverId: server.id,
                              })
                            }
                            className="form-radio"
                          />
                          <span className="text-white">{server.name}</span>
                        </div>
                        <div className="flex items-center space-x-2">
                          <Circle
                            className={`w-3 h-3 ${
                              isOnline
                                ? "fill-success-500 text-success-500"
                                : "fill-error-500 text-error-500"
                            }`}
                          />
                          <span
                            className={`text-xs ${isOnline ? "text-success-500" : "text-error-500"}`}
                          >
                            {isOnline ? "Online" : "Offline"}
                          </span>
                        </div>
                      </label>
                    );
                  })}
                </div>
              </div>

              {/* Proxy Selection */}
              <div>
                <label className="block text-sm text-dark-300 mb-2">
                  Proxy
                </label>
                <select
                  className="input w-full"
                  value={newProfile.proxyId}
                  onChange={(e) =>
                    setNewProfile({ ...newProfile, proxyId: e.target.value })
                  }
                >
                  <option value="">Select proxy option</option>
                  <option value="none">No Proxy (Direct Connection)</option>
                  {proxies
                    .filter((p) => !p.blacklisted)
                    .map((proxy) => (
                      <option key={proxy.id} value={proxy.id}>
                        {proxy.host}:{proxy.port} ({proxy.country})
                      </option>
                    ))}
                </select>
              </div>

              {/* Script Selection */}
              {profileMode !== "manual" && (
                <div>
                  <label className="block text-sm text-dark-300 mb-2">
                    Select Scripts (In Order)
                  </label>
                  {scripts.length === 0 ? (
                    <div className="text-sm text-warning-500 bg-dark-900 p-3 rounded-lg">
                      No scripts found in library. Create scripts in the "Script
                      Library" tab first.
                    </div>
                  ) : (
                    <div className="space-y-2 bg-dark-900 p-3 rounded-lg max-h-48 overflow-y-auto">
                      {scripts.map((script) => (
                        <label
                          key={script.id}
                          className="flex items-center space-x-3 cursor-pointer p-2 hover:bg-dark-800 rounded"
                        >
                          <input
                            type="checkbox"
                            checked={selectedScriptIds.includes(script.id)}
                            onChange={(e) => {
                              if (e.target.checked) {
                                setSelectedScriptIds([
                                  ...selectedScriptIds,
                                  script.id,
                                ]);
                              } else {
                                setSelectedScriptIds(
                                  selectedScriptIds.filter(
                                    (id) => id !== script.id,
                                  ),
                                );
                              }
                            }}
                            className="rounded"
                          />
                          <Code className="w-4 h-4 text-primary-400" />
                          <div className="flex-1">
                            <span className="text-white">{script.name}</span>
                            {script.requirements?.length > 0 && (
                              <span className="text-xs text-dark-500 ml-2">
                                (Deps: {script.requirements.join(", ")})
                              </span>
                            )}
                          </div>
                        </label>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Config Grid */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-dark-300 mb-2">
                    Timezone
                  </label>
                  <input
                    type="text"
                    className="input w-full"
                    placeholder="America/New_York"
                    value={newProfile.timezone}
                    onChange={(e) =>
                      setNewProfile({ ...newProfile, timezone: e.target.value })
                    }
                  />
                </div>
                <div>
                  <label className="block text-sm text-dark-300 mb-2">
                    Locale
                  </label>
                  <input
                    type="text"
                    className="input w-full"
                    placeholder="en-US"
                    value={newProfile.locale}
                    onChange={(e) =>
                      setNewProfile({ ...newProfile, locale: e.target.value })
                    }
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm text-dark-300 mb-2">
                  User Agent (optional)
                </label>
                <input
                  type="text"
                  className="input w-full"
                  placeholder="Leave blank for auto-generate"
                  value={newProfile.userAgent}
                  onChange={(e) =>
                    setNewProfile({ ...newProfile, userAgent: e.target.value })
                  }
                />
              </div>

              <div>
                <label className="block text-sm text-dark-300 mb-2">
                  Memory Threshold (MB)
                </label>
                <input
                  type="number"
                  className="input w-full"
                  value={newProfile.memoryThresholdMb}
                  onChange={(e) =>
                    setNewProfile({
                      ...newProfile,
                      memoryThresholdMb: parseInt(e.target.value),
                    })
                  }
                />
              </div>

              <div>
                <label className="block text-sm text-dark-300 mb-2">
                  Accounts
                </label>
                <div className="space-y-2 max-h-40 overflow-y-auto">
                  {accounts
                    .filter((a) => !a.banned)
                    .map((account) => (
                      <label
                        key={account.id}
                        className="flex items-center space-x-2 cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          checked={newProfile.accountIds.includes(account.id)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setNewProfile({
                                ...newProfile,
                                accountIds: [
                                  ...newProfile.accountIds,
                                  account.id,
                                ],
                              });
                            } else {
                              setNewProfile({
                                ...newProfile,
                                accountIds: newProfile.accountIds.filter(
                                  (id) => id !== account.id,
                                ),
                              });
                            }
                          }}
                          className="rounded"
                        />
                        <span className="text-sm text-white">
                          {account.platform} - {account.username}
                        </span>
                      </label>
                    ))}
                </div>
              </div>
            </div>

            <div className="flex space-x-3 mt-6">
              <button
                onClick={() => {
                  setShowAddModal(false);
                  resetNewProfile();
                }}
                className="btn btn-secondary flex-1"
              >
                Cancel
              </button>
              <button
                onClick={createProfile}
                className="btn btn-primary flex-1"
                disabled={
                  !newProfile.name ||
                  !newProfile.serverId ||
                  (profileMode !== "manual" && selectedScriptIds.length === 0)
                }
              >
                Create Profile
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default ProfileManager;
