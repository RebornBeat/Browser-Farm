import React, { useState, useEffect } from "react";
import { Plus, Server, Trash2, CheckCircle, XCircle } from "lucide-react";
import store from "../store/db";
import { apiClient } from "../api/client";

function ServerList() {
  const [servers, setServers] = useState([]);
  const [showAddModal, setShowAddModal] = useState(false);
  const [newServer, setNewServer] = useState({
    name: "",
    url: "",
    apiKey: "",
  });
  const [serverHealth, setServerHealth] = useState({});

  useEffect(() => {
    loadServers();
    const interval = setInterval(() => checkHealth(), 30000);
    return () => clearInterval(interval);
  }, []);

  const loadServers = async () => {
    const storedServers = (await store.get("servers")) || [];
    setServers(storedServers);

    // Add servers to API client
    storedServers.forEach((server) => {
      apiClient.addServer(server.id, server.url, server.apiKey);
    });

    // Check health with loaded servers
    checkHealth(storedServers);
  };

  const checkHealth = async (serversToCheck) => {
    const serverList = serversToCheck || servers;
    const health = {};

    console.log("🔍 Checking health for servers:", serverList);

    for (const server of serverList) {
      console.log(`📡 Pinging ${server.name} at ${server.url}`);
      try {
        const data = await apiClient.getHealth(server.id);
        console.log(`✅ ${server.name} is ONLINE:`, data);
        health[server.id] = { status: "online", ...data };
      } catch (error) {
        console.error(`❌ ${server.name} is OFFLINE:`, error.message);
        health[server.id] = { status: "offline" };
      }
    }

    console.log("📊 Final health status:", health);
    setServerHealth(health);
  };

  const addServer = async () => {
    const server = {
      id: `server_${Date.now()}`,
      ...newServer,
      createdAt: new Date().toISOString(),
    };

    const updatedServers = [...servers, server];
    await store.set("servers", updatedServers);
    setServers(updatedServers);

    apiClient.addServer(server.id, server.url, server.apiKey);

    setShowAddModal(false);
    setNewServer({ name: "", url: "", apiKey: "" });

    // Check health with new server list
    checkHealth(updatedServers);
  };

  const deleteServer = async (serverId) => {
    if (!window.confirm("Are you sure you want to delete this server?")) return;

    const updatedServers = servers.filter((s) => s.id !== serverId);
    await store.set("servers", updatedServers);
    setServers(updatedServers);
    apiClient.removeServer(serverId);
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-white">Servers</h2>
        <button
          onClick={() => setShowAddModal(true)}
          className="btn btn-primary flex items-center"
        >
          <Plus className="w-4 h-4 mr-2" />
          Add Server
        </button>
      </div>

      <div className="grid gap-4">
        {servers.map((server) => {
          const health = serverHealth[server.id];
          const isOnline = health?.status === "online";

          return (
            <div
              key={server.id}
              className="card flex items-center justify-between"
            >
              <div className="flex items-center space-x-4">
                <div
                  className={`w-12 h-12 rounded-lg flex items-center justify-center ${
                    isOnline ? "bg-success-500/20" : "bg-error-500/20"
                  }`}
                >
                  <Server
                    className={`w-6 h-6 ${
                      isOnline ? "text-success-500" : "text-error-500"
                    }`}
                  />
                </div>

                <div>
                  <h3 className="text-lg font-semibold text-white flex items-center">
                    {server.name}
                    {isOnline ? (
                      <CheckCircle className="w-4 h-4 text-success-500 ml-2" />
                    ) : (
                      <XCircle className="w-4 h-4 text-error-500 ml-2" />
                    )}
                  </h3>
                  <p className="text-sm text-dark-400">{server.url}</p>
                </div>
              </div>

              {health && isOnline && (
                <div className="flex items-center space-x-6 text-sm">
                  <div>
                    <p className="text-dark-400">Profiles</p>
                    <p className="text-white font-medium">
                      {health.current_contexts}/{health.max_contexts}
                    </p>
                  </div>
                  <div>
                    <p className="text-dark-400">Memory</p>
                    <p className="text-white font-medium">
                      {health.memory_used_mb}MB / {health.memory_total_mb}MB
                    </p>
                  </div>
                  <div>
                    <p className="text-dark-400">CPU</p>
                    <p className="text-white font-medium">
                      {health.cpu_usage?.toFixed(1)}%
                    </p>
                  </div>
                </div>
              )}

              <button
                onClick={() => deleteServer(server.id)}
                className="btn btn-error"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          );
        })}
      </div>

      {/* Add Server Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-dark-800 rounded-lg p-6 w-full max-w-md">
            <h3 className="text-xl font-bold text-white mb-4">Add Server</h3>

            <div className="space-y-4">
              <div>
                <label className="block text-sm text-dark-300 mb-2">
                  Server Name
                </label>
                <input
                  type="text"
                  className="input w-full"
                  placeholder="My Server"
                  value={newServer.name}
                  onChange={(e) =>
                    setNewServer({ ...newServer, name: e.target.value })
                  }
                />
              </div>

              <div>
                <label className="block text-sm text-dark-300 mb-2">
                  Server URL
                </label>
                <input
                  type="text"
                  className="input w-full"
                  placeholder="http://localhost:8080"
                  value={newServer.url}
                  onChange={(e) =>
                    setNewServer({ ...newServer, url: e.target.value })
                  }
                />
              </div>

              <div>
                <label className="block text-sm text-dark-300 mb-2">
                  API Key
                </label>
                <input
                  type="text"
                  className="input w-full font-mono text-sm"
                  placeholder="bf_abc123xyz789"
                  value={newServer.apiKey}
                  onChange={(e) =>
                    setNewServer({ ...newServer, apiKey: e.target.value })
                  }
                />
              </div>
            </div>

            <div className="flex space-x-3 mt-6">
              <button
                onClick={() => setShowAddModal(false)}
                className="btn btn-secondary flex-1"
              >
                Cancel
              </button>
              <button
                onClick={addServer}
                className="btn btn-primary flex-1"
                disabled={
                  !newServer.name || !newServer.url || !newServer.apiKey
                }
              >
                Add Server
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default ServerList;
