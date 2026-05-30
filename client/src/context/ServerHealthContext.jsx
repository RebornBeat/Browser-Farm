import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
} from "react";
import store from "../store/db";
import { apiClient } from "../api/client";

// Create the Context
const ServerHealthContext = createContext();

// Custom Hook to use the Context
export const useServerHealth = () => {
  return useContext(ServerHealthContext);
};

// The Provider Component
export const ServerHealthProvider = ({ children }) => {
  const [servers, setServers] = useState([]);
  const [healthData, setHealthData] = useState({});
  // Structure: { "server_id": { status: "online", cpu: 10, ... }, ... }

  // 1. Load Servers from Store on Mount
  useEffect(() => {
    const loadInitialServers = async () => {
      try {
        const storedServers = (await store.get("servers")) || [];
        setServers(storedServers);

        // Register all loaded servers with the API Client
        storedServers.forEach((server) => {
          apiClient.addServer(server.id, server.url, server.apiKey);
        });

        // Trigger initial health check immediately
        performHealthCheck(storedServers);
      } catch (error) {
        console.error("Failed to load servers from store:", error);
      }
    };

    loadInitialServers();
  }, []);

  // 2. Health Check Logic
  const performHealthCheck = useCallback(async (currentServers) => {
    const newHealthData = {};

    // Use Promise.all to check all servers in parallel
    await Promise.all(
      currentServers.map(async (server) => {
        try {
          // Call the health endpoint via apiClient
          const data = await apiClient.getHealth(server.id);
          newHealthData[server.id] = {
            status: "online",
            ...data,
          };
        } catch (error) {
          // If error (timeout, network, 500), mark as offline
          newHealthData[server.id] = {
            status: "offline",
          };
        }
      }),
    );

    setHealthData(newHealthData);
  }, []);

  // 3. Setup Global Polling Interval (runs regardless of active tab)
  useEffect(() => {
    // Only poll if we have servers
    if (servers.length === 0) return;

    const intervalId = setInterval(() => {
      performHealthCheck(servers);
    }, 30000); // Check every 30 seconds

    // Cleanup interval on component unmount
    return () => clearInterval(intervalId);
  }, [servers, performHealthCheck]);

  // 4. Method to refresh servers manually (used after Add/Delete)
  const refreshServers = async () => {
    const storedServers = (await store.get("servers")) || [];
    setServers(storedServers);

    // Re-register servers with API client
    storedServers.forEach((server) => {
      apiClient.addServer(server.id, server.url, server.apiKey);
    });

    // Force immediate health check after refresh
    await performHealthCheck(storedServers);
  };

  // Value provided to consumers
  const value = {
    servers,
    healthData,
    refreshServers,
  };

  return (
    <ServerHealthContext.Provider value={value}>
      {children}
    </ServerHealthContext.Provider>
  );
};

export default ServerHealthContext;
