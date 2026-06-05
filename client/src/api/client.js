import axios from "axios";

class BrowserFarmClient {
  constructor() {
    this.servers = new Map();
  }

  addServer(id, url, apiKey) {
    const client = axios.create({
      baseURL: url,
      headers: {
        "X-API-Key": apiKey,
      },
      timeout: 300000, // 5 min timeout to accommodate Xvfb/Browser startup
    });
    this.servers.set(id, { url, apiKey, client });
  }

  removeServer(id) {
    this.servers.delete(id);
  }

  getClient(serverId) {
    const server = this.servers.get(serverId);
    if (!server) throw new Error("Server not found");
    return server.client;
  }

  // -----------------------------------------------------------
  // Health & Global Status
  // -----------------------------------------------------------

  /**
   * Get health status of a single server.
   * Returns health data or throws error if unreachable.
   */
  async getHealth(serverId) {
    const client = this.getClient(serverId);
    // Use a short timeout for health checks to prevent UI freezing
    const { data } = await client.get("/health", { timeout: 5000 });
    return data;
  }

  /**
   * Checks health of ALL registered servers.
   * Used by the Global Context for polling.
   * Returns a map: { serverId: { status: 'online'|'offline', ...data } }
   */
  async checkAllServersHealth() {
    const results = {};
    const promises = [];

    for (const [serverId, server] of this.servers.entries()) {
      promises.push(
        this.getHealth(serverId)
          .then((data) => {
            results[serverId] = { status: "online", ...data };
          })
          .catch((error) => {
            results[serverId] = {
              status: "offline",
              error: error.message || "Connection failed",
            };
          }),
      );
    }

    await Promise.all(promises);
    return results;
  }

  // -----------------------------------------------------------
  // Command Center
  // -----------------------------------------------------------

  async getCommandCenter(serverId) {
    const client = this.getClient(serverId);
    try {
      const { data } = await client.get("/command-center");
      return data;
    } catch (error) {
      // If 404, no command center is running
      if (error.response && error.response.status === 404) {
        return null;
      }
      throw error;
    }
  }

  // -----------------------------------------------------------
  // Proxies
  // -----------------------------------------------------------

  async registerProxy(serverId, proxy) {
    const client = this.getClient(serverId);
    const { data } = await client.post("/proxies", proxy);
    return data;
  }

  // -----------------------------------------------------------
  // Profiles
  // -----------------------------------------------------------

  async listProfiles(serverId) {
    const client = this.getClient(serverId);
    const { data } = await client.get("/profiles");
    return data.profiles;
  }

  async createProfile(serverId, profile) {
    const client = this.getClient(serverId);
    const { data } = await client.post("/profiles", profile);
    return data;
  }

  async getProfile(serverId, profileId) {
    const client = this.getClient(serverId);
    const { data } = await client.get(`/profiles/${profileId}`);
    return data;
  }

  async startProfile(serverId, profileId, accounts) {
    const client = this.getClient(serverId);
    const { data } = await client.post(
      `/profiles/${profileId}/start`,
      accounts,
    );
    return data;
  }

  async pauseProfile(serverId, profileId) {
    const client = this.getClient(serverId);
    const { data } = await client.post(`/profiles/${profileId}/pause`);
    return data;
  }

  async stopProfile(serverId, profileId) {
    const client = this.getClient(serverId);
    const { data } = await client.post(`/profiles/${profileId}/stop`);
    return data;
  }

  async deleteProfile(serverId, profileId) {
    const client = this.getClient(serverId);
    const { data } = await client.delete(`/profiles/${profileId}`);
    return data;
  }

  // -----------------------------------------------------------
  // Screenshots
  // -----------------------------------------------------------

  async getScreenshot(serverId, profileId) {
    const client = this.getClient(serverId);
    const response = await client.get(`/profiles/${profileId}/screen`, {
      responseType: "blob",
    });
    return URL.createObjectURL(response.data);
  }

  async listScreenshots(serverId, profileId) {
    const client = this.getClient(serverId);
    const { data } = await client.get(`/profiles/${profileId}/screenshots`);
    return data.screenshots;
  }

  async takeScreenshot(serverId, profileId) {
    const client = this.getClient(serverId);
    const { data } = await client.post(`/profiles/${profileId}/screenshot`);
    return data;
  }

  // -----------------------------------------------------------
  // Metrics
  // -----------------------------------------------------------

  async getMetrics(serverId, profileId) {
    const client = this.getClient(serverId);
    const { data } = await client.get(`/profiles/${profileId}/metrics`);
    return data;
  }

  // -----------------------------------------------------------
  // Shared State
  // -----------------------------------------------------------

  async getState(serverId, key) {
    const client = this.getClient(serverId);
    const { data } = await client.get(`/state/${key}`);
    return data;
  }

  async setState(serverId, key, value) {
    const client = this.getClient(serverId);
    const { data } = await client.post(`/state/${key}`, value);
    return data;
  }

  async deleteState(serverId, key) {
    const client = this.getClient(serverId);
    const { data } = await client.delete(`/state/${key}`);
    return data;
  }

  // -----------------------------------------------------------
  // Accounts & Proxy History
  // -----------------------------------------------------------

  async syncAccounts(serverId, accounts) {
    const client = this.getClient(serverId);
    const { data } = await client.post("/accounts/sync", { accounts });
    return data;
  }

  async getProxyHistory(serverId, accountId) {
    const client = this.getClient(serverId);
    const { data } = await client.get(`/accounts/${accountId}/proxy-history`);
    return data;
  }

  /**
   * NEW: Record that an account is using a specific proxy for a specific website.
   * Used for enforcing "1 Account per Website per Proxy" compliance.
   */
  async recordProxyHistory(serverId, accountId, proxyId, website) {
    const client = this.getClient(serverId);
    // Sending as query params or body depending on server implementation.
    // Server expects query params based on the endpoint defined:
    // @app.post("/history/record")
    // async def record_proxy_history(account_id: str, proxy_id: str, website: str, ...)
    // Note: FastAPI with query params needs them passed in the URL or config.
    const { data } = await client.post(`/history/record`, null, {
      params: {
        account_id: accountId,
        proxy_id: proxyId,
        website: website,
      },
    });
    return data;
  }

  // -----------------------------------------------------------
  // WebSocket URLs
  // -----------------------------------------------------------

  getStreamUrl(serverId, profileId) {
    const server = this.servers.get(serverId);
    if (!server) return null;
    const wsUrl = server.url.replace("http", "ws");
    return `${wsUrl}/profiles/${profileId}/stream`;
  }

  getControlUrl(serverId, profileId) {
    const server = this.servers.get(serverId);
    if (!server) return null;
    const wsUrl = server.url.replace("http", "ws");
    return `${wsUrl}/profiles/${profileId}/control`;
  }
}

export const apiClient = new BrowserFarmClient();
export default apiClient;
