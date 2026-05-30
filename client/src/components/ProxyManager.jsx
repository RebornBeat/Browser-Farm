import React, { useState, useEffect } from "react";
import { Plus, Globe, Trash2, AlertCircle } from "lucide-react";
import store from "../store/db";

function ProxyManager() {
  const [proxies, setProxies] = useState([]);
  const [showAddModal, setShowAddModal] = useState(false);
  const [filter, setFilter] = useState("all"); // all, active, blacklisted
  const [newProxy, setNewProxy] = useState({
    host: "",
    port: "",
    protocol: "http",
    username: "",
    password: "",
    country: "",
    blacklisted: false,
    blacklistedSites: [],
  });

  useEffect(() => {
    loadProxies();
  }, []);

  const loadProxies = async () => {
    const storedProxies = (await store.get("proxies")) || [];
    setProxies(storedProxies);
  };

  const addProxy = async () => {
    const proxy = {
      id: `proxy_${Date.now()}`,
      ...newProxy,
      port: parseInt(newProxy.port),
      status: "active",
      createdAt: new Date().toISOString(),
    };

    const updatedProxies = [...proxies, proxy];
    await store.set("proxies", updatedProxies);
    setProxies(updatedProxies);

    setShowAddModal(false);
    setNewProxy({
      host: "",
      port: "",
      protocol: "http",
      username: "",
      password: "",
      country: "",
      blacklisted: false,
      blacklistedSites: [],
    });
  };

  const deleteProxy = async (proxyId) => {
    if (!window.confirm("Are you sure you want to delete this proxy?")) return;

    const updatedProxies = proxies.filter((p) => p.id !== proxyId);
    await store.set("proxies", updatedProxies);
    setProxies(updatedProxies);
  };

  const toggleBlacklist = async (proxyId, site) => {
    const updatedProxies = proxies.map((p) => {
      if (p.id === proxyId) {
        const blacklistedSites = [...(p.blacklistedSites || [])];
        if (blacklistedSites.includes(site)) {
          return {
            ...p,
            blacklistedSites: blacklistedSites.filter((s) => s !== site),
            blacklisted: blacklistedSites.length === 1 ? false : p.blacklisted,
          };
        } else {
          return {
            ...p,
            blacklistedSites: [...blacklistedSites, site],
            blacklisted: true,
          };
        }
      }
      return p;
    });

    await store.set("proxies", updatedProxies);
    setProxies(updatedProxies);
  };

  const filteredProxies = proxies.filter((p) => {
    if (filter === "active") return !p.blacklisted;
    if (filter === "blacklisted") return p.blacklisted;
    return true;
  });

  return (
    <div>
      {/* Header Section - Fixed Layout */}
      <div className="flex justify-between items-center mb-6 gap-4">
        <h2 className="text-2xl font-bold text-white">Proxies</h2>

        <div className="flex items-center space-x-3">
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="input w-auto" // Changed from default to w-auto to prevent over-expanding
          >
            <option value="all">All Proxies</option>
            <option value="active">Active Only</option>
            <option value="blacklisted">Blacklisted Only</option>
          </select>

          <button
            onClick={() => setShowAddModal(true)}
            className="btn btn-primary flex items-center whitespace-nowrap" // Added whitespace-nowrap to keep text on one line
          >
            <Plus className="w-4 h-4 mr-2" />
            Add Proxy
          </button>
        </div>
      </div>

      <div className="grid gap-4">
        {filteredProxies.map((proxy) => (
          <div key={proxy.id} className="card">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center space-x-4">
                <div
                  className={`w-12 h-12 rounded-lg flex items-center justify-center ${
                    proxy.blacklisted ? "bg-error-500/20" : "bg-success-500/20"
                  }`}
                >
                  <Globe
                    className={`w-6 h-6 ${
                      proxy.blacklisted ? "text-error-500" : "text-success-500"
                    }`}
                  />
                </div>

                <div>
                  <h3 className="text-lg font-semibold text-white">
                    {proxy.host}:{proxy.port}
                  </h3>
                  <p className="text-sm text-dark-400">
                    {proxy.protocol.toUpperCase()} •{" "}
                    {proxy.country || "Unknown"}
                  </p>
                </div>
              </div>

              <div className="flex items-center space-x-3">
                <span
                  className={`status-badge ${
                    proxy.blacklisted ? "status-stopped" : "status-running"
                  }`}
                >
                  {proxy.blacklisted ? "Blacklisted" : "Active"}
                </span>
                <button
                  onClick={() => deleteProxy(proxy.id)}
                  className="btn btn-error"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>

            {proxy.blacklisted && proxy.blacklistedSites?.length > 0 && (
              <div className="flex items-start space-x-2 text-sm">
                <AlertCircle className="w-4 h-4 text-error-500 mt-0.5" />
                <div>
                  <p className="text-dark-400">Blacklisted on:</p>
                  <div className="flex flex-wrap gap-2 mt-1">
                    {proxy.blacklistedSites.map((site) => (
                      <span
                        key={site}
                        className="px-2 py-1 bg-error-500/20 text-error-500 rounded text-xs"
                      >
                        {site}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Add Proxy Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-dark-800 rounded-lg p-6 w-full max-w-md">
            <h3 className="text-xl font-bold text-white mb-4">Add Proxy</h3>

            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-dark-300 mb-2">
                    Host
                  </label>
                  <input
                    type="text"
                    className="input w-full"
                    placeholder="1.2.3.4"
                    value={newProxy.host}
                    onChange={(e) =>
                      setNewProxy({ ...newProxy, host: e.target.value })
                    }
                  />
                </div>
                <div>
                  <label className="block text-sm text-dark-300 mb-2">
                    Port
                  </label>
                  <input
                    type="number"
                    className="input w-full"
                    placeholder="8080"
                    value={newProxy.port}
                    onChange={(e) =>
                      setNewProxy({ ...newProxy, port: e.target.value })
                    }
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm text-dark-300 mb-2">
                  Protocol
                </label>
                <select
                  className="input w-full"
                  value={newProxy.protocol}
                  onChange={(e) =>
                    setNewProxy({ ...newProxy, protocol: e.target.value })
                  }
                >
                  <option value="http">HTTP</option>
                  <option value="https">HTTPS</option>
                  <option value="socks5">SOCKS5</option>
                </select>
              </div>

              <div>
                <label className="block text-sm text-dark-300 mb-2">
                  Country
                </label>
                <input
                  type="text"
                  className="input w-full"
                  placeholder="US"
                  value={newProxy.country}
                  onChange={(e) =>
                    setNewProxy({ ...newProxy, country: e.target.value })
                  }
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-dark-300 mb-2">
                    Username (optional)
                  </label>
                  <input
                    type="text"
                    className="input w-full"
                    value={newProxy.username}
                    onChange={(e) =>
                      setNewProxy({ ...newProxy, username: e.target.value })
                    }
                  />
                </div>
                <div>
                  <label className="block text-sm text-dark-300 mb-2">
                    Password (optional)
                  </label>
                  <input
                    type="password"
                    className="input w-full"
                    value={newProxy.password}
                    onChange={(e) =>
                      setNewProxy({ ...newProxy, password: e.target.value })
                    }
                  />
                </div>
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
                onClick={addProxy}
                className="btn btn-primary flex-1"
                disabled={!newProxy.host || !newProxy.port}
              >
                Add Proxy
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default ProxyManager;
