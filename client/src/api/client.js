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

  // Health
  async getHealth(serverId) {
    const client = this.getClient(serverId);
    const { data } = await client.get("/health");
    return data;
  }

  // Proxies
  async registerProxy(serverId, proxy) {
    const client = this.getClient(serverId);
    const { data } = await client.post("/proxies", proxy);
    return data;
  }

  // Profiles
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

  // Screenshots
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

  // Metrics
  async getMetrics(serverId, profileId) {
    const client = this.getClient(serverId);
    const { data } = await client.get(`/profiles/${profileId}/metrics`);
    return data;
  }

  // WebSocket URLs
  getStreamUrl(serverId, profileId) {
    const server = this.servers.get(serverId);
    const wsUrl = server.url.replace("http", "ws");
    return `${wsUrl}/profiles/${profileId}/stream`;
  }

  getControlUrl(serverId, profileId) {
    const server = this.servers.get(serverId);
    const wsUrl = server.url.replace("http", "ws");
    return `${wsUrl}/profiles/${profileId}/control`;
  }
}

export const apiClient = new BrowserFarmClient();
export default apiClient;
