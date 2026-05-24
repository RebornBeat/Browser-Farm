import React, { useState, useEffect } from "react";
import { Plus, Layout, Play, Pause, Square, Trash2 } from "lucide-react";
import store from "../store/db";
import { apiClient } from "../api/client";

function ProfileManager() {
  const [profiles, setProfiles] = useState([]);
  const [servers, setServers] = useState([]);
  const [proxies, setProxies] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [showAddModal, setShowAddModal] = useState(false);
  const [newProfile, setNewProfile] = useState({
    name: "",
    serverId: "",
    proxyId: "",
    accountIds: [],
    userAgent: "",
    timezone: "America/New_York",
    locale: "en-US",
    scriptCode: "",
    restartScriptCode: "",
    memoryThresholdMb: 400,
  });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setProfiles((await store.get("profiles")) || []);
    setServers((await store.get("servers")) || []);
    setProxies((await store.get("proxies")) || []);
    setAccounts((await store.get("accounts")) || []);
  };

  const createProfile = async () => {
    try {
      const server = servers.find((s) => s.id === newProfile.serverId);
      const proxy = proxies.find((p) => p.id === newProfile.proxyId);

      if (!server || !proxy) {
        alert("Please select valid server and proxy");
        return;
      }

      // Create profile on server
      const result = await apiClient.createProfile(server.id, {
        name: newProfile.name,
        proxy_id: proxy.id,
        user_agent: newProfile.userAgent || undefined,
        timezone: newProfile.timezone,
        locale: newProfile.locale,
        script_code: newProfile.scriptCode,
        restart_script_code: newProfile.restartScriptCode || undefined,
        memory_threshold_mb: newProfile.memoryThresholdMb,
      });

      // Register proxy with server
      await apiClient.registerProxy(server.id, proxy);

      // Save locally
      const profile = {
        id: result.id,
        localId: `profile_${Date.now()}`,
        ...newProfile,
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
      scriptCode: "",
      restartScriptCode: "",
      memoryThresholdMb: 400,
    });
  };

  const startProfile = async (profile) => {
    try {
      // Get accounts for this profile
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

      // Update local status
      const updatedProfiles = profiles.map((p) =>
        p.id === profile.id ? { ...p, status: "running" } : p,
      );
      await store.set("profiles", updatedProfiles);
      setProfiles(updatedProfiles);
    } catch (error) {
      console.error("Failed to start profile:", error);
      alert("Failed to start profile: " + error.message);
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

      const updatedProfiles = profiles.filter((p) => p.id !== profile.id);
      await store.set("profiles", updatedProfiles);
      setProfiles(updatedProfiles);
    } catch (error) {
      console.error("Failed to delete profile:", error);
      alert("Failed to delete profile: " + error.message);
    }
  };

  const getServerName = (serverId) => {
    const server = servers.find((s) => s.id === serverId);
    return server?.name || "Unknown";
  };

  const getProxyName = (proxyId) => {
    const proxy = proxies.find((p) => p.id === proxyId);
    return proxy ? `${proxy.host}:${proxy.port}` : "Unknown";
  };

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
                <div className="w-12 h-12 rounded-lg bg-primary-500/20 flex items-center justify-center">
                  <Layout className="w-6 h-6 text-primary-500" />
                </div>

                <div>
                  <h3 className="text-lg font-semibold text-white">
                    {profile.name}
                  </h3>
                  <p className="text-sm text-dark-400">
                    {getServerName(profile.serverId)} •{" "}
                    {getProxyName(profile.proxyId)}
                  </p>
                </div>
              </div>

              <div className="flex items-center space-x-3">
                <span className={`status-badge status-${profile.status}`}>
                  {profile.status}
                </span>

                {profile.status === "idle" || profile.status === "stopped" ? (
                  <button
                    onClick={() => startProfile(profile)}
                    className="btn btn-success"
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
                <p className="text-dark-400">Timezone</p>
                <p className="text-white">{profile.timezone}</p>
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

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-dark-300 mb-2">
                    Server
                  </label>
                  <select
                    className="input w-full"
                    value={newProfile.serverId}
                    onChange={(e) =>
                      setNewProfile({ ...newProfile, serverId: e.target.value })
                    }
                  >
                    <option value="">Select server</option>
                    {servers.map((server) => (
                      <option key={server.id} value={server.id}>
                        {server.name}
                      </option>
                    ))}
                  </select>
                </div>

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
                    <option value="">Select proxy</option>
                    {proxies
                      .filter((p) => !p.blacklisted)
                      .map((proxy) => (
                        <option key={proxy.id} value={proxy.id}>
                          {proxy.host}:{proxy.port} ({proxy.country})
                        </option>
                      ))}
                  </select>
                </div>
              </div>

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
                  Script Code
                </label>
                <textarea
                  className="input w-full font-mono text-sm"
                  rows="10"
                  placeholder="# Python script here"
                  value={newProfile.scriptCode}
                  onChange={(e) =>
                    setNewProfile({ ...newProfile, scriptCode: e.target.value })
                  }
                />
              </div>

              <div>
                <label className="block text-sm text-dark-300 mb-2">
                  Restart Script (optional)
                </label>
                <textarea
                  className="input w-full font-mono text-sm"
                  rows="5"
                  placeholder="# Restart script here"
                  value={newProfile.restartScriptCode}
                  onChange={(e) =>
                    setNewProfile({
                      ...newProfile,
                      restartScriptCode: e.target.value,
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
                  !newProfile.proxyId ||
                  !newProfile.scriptCode
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
