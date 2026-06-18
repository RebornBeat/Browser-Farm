"""
Comprehensive stealth injection script.
Replaces weak inline overrides with prototype-correct spoofing.
Configurable via PROFILE_CONFIG injected before script runs.
"""

def generate_stealth_script(config: dict) -> str:
    """
    Generate a stealth injection script tailored to the profile config.

    Args:
        config: Dict containing:
            - languages: list (e.g., ['en-US', 'en'])
            - hardware_concurrency: int
            - device_memory: int
            - platform: str (e.g., 'Win32')
            - gpu_vendor: str
            - gpu_renderer: str
            - os_fingerprint: str (windows/macos/linux)

    Returns:
        JavaScript string to inject via context.add_init_script()
    """
    import json

    config_json = json.dumps(config)

    return f"""
(() => {{
  // Inject profile configuration
  globalThis.__PROFILE_CONFIG__ = {config_json};
  const config = globalThis.__PROFILE_CONFIG__;
  const languages = config.languages || ['en-US', 'en'];
  const hardwareConcurrency = config.hardware_concurrency || 8;
  const deviceMemory = config.device_memory || 8;
  const platform = config.platform || 'Win32';
  const gpuVendor = config.gpu_vendor || 'Google Inc. (NVIDIA)';
  const gpuRenderer = config.gpu_renderer || 'ANGLE (NVIDIA, NVIDIA GeForce GTX 1060 Direct3D11 vs_5_0 ps_5_0, D3D11)';

  // ============================================
  // 1. navigator.webdriver
  // ============================================
  try {{
    Object.defineProperty(navigator, 'webdriver', {{
      get: () => undefined,
      configurable: true
    }});
    // Also delete if it exists as own property
    delete navigator.__proto__.webdriver;
  }} catch (e) {{}}

  // ============================================
  // 2. Plugins - Proper PluginArray prototype
  // ============================================
  try {{
    const fakePluginData = [
      {{ name: 'PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' }},
      {{ name: 'Chrome PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' }},
      {{ name: 'Chromium PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' }},
      {{ name: 'Microsoft Edge PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' }},
      {{ name: 'WebKit built-in PDF', filename: 'internal-pdf-viewer', description: 'Portable Document Format' }}
    ];

    Object.defineProperty(navigator, 'plugins', {{
      get: () => {{
        const plugins = Object.create(PluginArray.prototype);
        fakePluginData.forEach((p, i) => {{
          const plugin = Object.create(Plugin.prototype);
          Object.defineProperties(plugin, {{
            name: {{ value: p.name, enumerable: true }},
            filename: {{ value: p.filename, enumerable: true }},
            description: {{ value: p.description, enumerable: true }},
            length: {{ value: 0, enumerable: true }}
          }});
          Object.defineProperty(plugins, i, {{ value: plugin, enumerable: true }});
        }});
        Object.defineProperty(plugins, 'length', {{ value: fakePluginData.length }});
        plugins.item = (i) => plugins[i] || null;
        plugins.namedItem = (n) => {{
          for (let i = 0; i < plugins.length; i++) {{
            if (plugins[i].name === n) return plugins[i];
          }}
          return null;
        }};
        plugins.refresh = () => {{}};
        return plugins;
      }},
      configurable: true
    }});
  }} catch (e) {{}}

  // ============================================
  // 3. Mime Types - Proper MimeTypeArray
  // ============================================
  try {{
    const fakeMimes = [
      {{ type: 'application/pdf', suffixes: 'pdf', description: 'Portable Document Format' }},
      {{ type: 'text/pdf', suffixes: 'pdf', description: 'Portable Document Format' }}
    ];

    Object.defineProperty(navigator, 'mimeTypes', {{
      get: () => {{
        const mimes = Object.create(MimeTypeArray.prototype);
        fakeMimes.forEach((m, i) => {{
          const mime = Object.create(MimeType.prototype);
          Object.defineProperties(mime, {{
            type: {{ value: m.type, enumerable: true }},
            suffixes: {{ value: m.suffixes, enumerable: true }},
            description: {{ value: m.description, enumerable: true }},
            enabledPlugin: {{ value: navigator.plugins[i] || null, enumerable: true }}
          }});
          Object.defineProperty(mimes, i, {{ value: mime, enumerable: true }});
        }});
        Object.defineProperty(mimes, 'length', {{ value: fakeMimes.length }});
        mimes.item = (i) => mimes[i] || null;
        mimes.namedItem = (n) => {{
          for (let i = 0; i < mimes.length; i++) {{
            if (mimes[i].type === n) return mimes[i];
          }}
          return null;
        }};
        return mimes;
      }},
      configurable: true
    }});
  }} catch (e) {{}}

  // ============================================
  // 4. Languages (from profile locale)
  // ============================================
  try {{
    Object.defineProperty(navigator, 'languages', {{
      get: () => Object.freeze([...languages]),
      configurable: true
    }});
  }} catch (e) {{}}

  // ============================================
  // 5. Hardware Concurrency
  // ============================================
  try {{
    Object.defineProperty(navigator, 'hardwareConcurrency', {{
      get: () => hardwareConcurrency,
      configurable: true
    }});
  }} catch (e) {{}}

  // ============================================
  // 6. Device Memory
  // ============================================
  try {{
    Object.defineProperty(navigator, 'deviceMemory', {{
      get: () => deviceMemory,
      configurable: true
    }});
  }} catch (e) {{}}

  // ============================================
  // 7. Platform
  // ============================================
  try {{
    Object.defineProperty(navigator, 'platform', {{
      get: () => platform,
      configurable: true
    }});
  }} catch (e) {{}}

  // ============================================
  // 8. window.chrome (comprehensive)
  // ============================================
  try {{
    if (!window.chrome) {{
      window.chrome = {{}};
    }}

    // runtime
    window.chrome.runtime = window.chrome.runtime || {{
      OnInstalledReason: {{ CHROME_UPDATE: 'chrome_update', INSTALL: 'install', SHARED_MODULE_UPDATE: 'shared_module_update', UPDATE: 'update' }},
      OnRestartRequiredReason: {{ APP_UPDATE: 'app_update', OS_UPDATE: 'os_update', PERIODIC: 'periodic' }},
      PlatformArch: {{ ARM: 'arm', ARM64: 'arm64', MIPS: 'mips', MIPS64: 'mips64', X86_32: 'x86-32', X86_64: 'x86-64' }},
      PlatformNaclArch: {{ ARM: 'arm', MIPS: 'mips', MIPS64: 'mips64', X86_32: 'x86-32', X86_64: 'x86-64' }},
      PlatformOs: {{ ANDROID: 'android', CROS: 'cros', LINUX: 'linux', MAC: 'mac', OPENBSD: 'openbsd', WIN: 'win' }},
      RequestUpdateCheckStatus: {{ NO_UPDATE: 'no_update', THROTTLED: 'throttled', UPDATE_AVAILABLE: 'update_available' }},
      connect: () => {{}},
      sendMessage: () => {{}},
    }};

    // app
    window.chrome.app = {{
      isInstalled: false,
      InstallState: {{ DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' }},
      RunningState: {{ CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' }},
      getDetails: () => null,
      getIsInstalled: () => false,
      runningState: () => 'cannot_run'
    }};

    // csi
    window.chrome.csi = () => ({{
      onloadT: Date.now(),
      startE: Date.now(),
      pageT: Math.random() * 1000 + 500,
      tran: 15
    }});

    // loadTimes
    window.chrome.loadTimes = () => ({{
      commitLoadTime: Date.now() / 1000 - 2,
      connectionInfo: 'h2',
      finishDocumentLoadTime: Date.now() / 1000 - 1,
      finishLoadTime: Date.now() / 1000 - 0.5,
      firstPaintAfterLoadTime: Date.now() / 1000 - 0.4,
      firstPaintTime: Date.now() / 1000 - 1.5,
      navigationType: 'Other',
      npnNegotiatedProtocol: 'h2',
      requestTime: Date.now() / 1000 - 3,
      startLoadTime: Date.now() / 1000 - 2.5,
      wasAlternateProtocolAvailable: false,
      wasFetchedViaSpdy: true,
      wasNpnNegotiated: true
    }});
  }} catch (e) {{}}

  // ============================================
  // 9. WebGL Spoofing
  // ============================================
  try {{
    const getParameterProto = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(param) {{
      // UNMASKED_VENDOR_WEBGL = 37445
      if (param === 37445) return gpuVendor;
      // UNMASKED_RENDERER_WEBGL = 37446
      if (param === 37446) return gpuRenderer;
      // VENDOR = 7936
      if (param === 7936) return 'WebKit';
      // RENDERER = 7937
      if (param === 7937) return 'WebKit WebGL';
      return getParameterProto.call(this, param);
    }};

    if (window.WebGL2RenderingContext) {{
      const getParameter2Proto = WebGL2RenderingContext.prototype.getParameter;
      WebGL2RenderingContext.prototype.getParameter = function(param) {{
        if (param === 37445) return gpuVendor;
        if (param === 37446) return gpuRenderer;
        if (param === 7936) return 'WebKit';
        if (param === 7937) return 'WebKit WebGL';
        return getParameter2Proto.call(this, param);
      }};
    }}
  }} catch (e) {{}}

  // ============================================
  // 10. Permissions API consistency
  // ============================================
  try {{
    if (navigator.permissions && navigator.permissions.query) {{
      const originalQuery = navigator.permissions.query.bind(navigator.permissions);
      navigator.permissions.query = (params) => {{
        if (params.name === 'notifications') {{
          return Promise.resolve({{
            state: Notification.permission,
            onchange: null
          }});
        }}
        return originalQuery(params);
      }};
    }}
  }} catch (e) {{}}

  // ============================================
  // 11. Battery API spoofing
  // ============================================
  try {{
    if (navigator.getBattery) {{
      const batteryLevel = 0.85 + Math.random() * 0.1;
      navigator.getBattery = () => Promise.resolve({{
        charging: true,
        chargingTime: 0,
        dischargingTime: Infinity,
        level: batteryLevel,
        addEventListener: () => {{}},
        removeEventListener: () => {{}},
        dispatchEvent: () => false
      }});
    }}
  }} catch (e) {{}}

  // ============================================
  // 12. iframe contentWindow.chrome injection
  // ============================================
  try {{
    const iframeDescriptor = Object.getOwnPropertyDescriptor(
      HTMLIFrameElement.prototype, 'contentWindow'
    );
    if (iframeDescriptor) {{
      Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {{
        get: function() {{
          const result = iframeDescriptor.get.call(this);
          if (result) {{
            try {{
              // Inject chrome object into iframe
              if (!result.chrome) {{
                result.chrome = window.chrome;
              }}
            }} catch (e) {{
              // Cross-origin iframe, skip
            }}
          }}
          return result;
        }},
        configurable: true
      }});
    }}
  }} catch (e) {{}}

  // ============================================
  // 13. Notification consistency
  // ============================================
  try {{
    if (window.Notification) {{
      const notifPermission = Notification.permission;
      Object.defineProperty(Notification, 'permission', {{
        get: () => notifPermission,
        configurable: true
      }});
    }}
  }} catch (e) {{}}

  // ============================================
  // 14. Media Devices spoofing
  // ============================================
  try {{
    if (navigator.mediaDevices && navigator.mediaDevices.enumerateDevices) {{
      const originalEnumerate = navigator.mediaDevices.enumerateDevices.bind(navigator.mediaDevices);
      navigator.mediaDevices.enumerateDevices = () => {{
        return originalEnumerate().then(devices => {{
          return devices.map(d => {{
            const spoofed = {{ ...d }};
            if (d.kind === 'audioinput') {{
              spoofed.label = 'Default - Microphone Array (Realtek(R) Audio)';
              spoofed.groupId = 'default-audio-input-group';
            }} else if (d.kind === 'audiooutput') {{
              spoofed.label = 'Default - Speakers (Realtek(R) Audio)';
              spoofed.groupId = 'default-audio-output-group';
            }} else if (d.kind === 'videoinput') {{
              spoofed.label = 'Integrated Camera';
              spoofed.groupId = 'default-video-input-group';
            }}
            return spoofed;
          }});
        }});
      }};
    }}
  }} catch (e) {{}}

  // ============================================
  // 15. Screen properties
  // ============================================
  try {{
    Object.defineProperty(screen, 'colorDepth', {{ get: () => 24, configurable: true }});
    Object.defineProperty(screen, 'pixelDepth', {{ get: () => 24, configurable: true }});
    Object.defineProperty(screen, 'availWidth', {{ get: () => screen.width, configurable: true }});
    Object.defineProperty(screen, 'availHeight', {{ get: () => screen.height - 40, configurable: true }});
  }} catch (e) {{}}

  // ============================================
  // 16. Speech Synthesis (often checked)
  // ============================================
  try {{
    if (window.speechSynthesis) {{
      // Trigger population of voice list
      window.speechSynthesis.getVoices();
    }}
  }} catch (e) {{}}

  // ============================================
  // 17. navigator.connection (if available)
  // ============================================
  try {{
    if (navigator.connection) {{
      Object.defineProperty(navigator.connection, 'effectiveType', {{
        get: () => '4g',
        configurable: true
      }});
      Object.defineProperty(navigator.connection, 'rtt', {{
        get: () => 50,
        configurable: true
      }});
      Object.defineProperty(navigator.connection, 'downlink', {{
        get: () => 10,
        configurable: true
      }});
      Object.defineProperty(navigator.connection, 'saveData', {{
        get: () => false,
        configurable: true
      }});
    }}
  }} catch (e) {{}}

}})();
"""
