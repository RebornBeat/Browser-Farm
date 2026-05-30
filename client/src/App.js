import React, { useState, useEffect } from "react";
import {
  HashRouter as Router,
  Routes,
  Route,
  Navigate,
} from "react-router-dom";
import Startup from "./components/Startup";
import Sidebar from "./components/Sidebar";
import Header from "./components/Header";
import Home from "./pages/Home";
import Servers from "./pages/Servers";
import Proxies from "./pages/Proxies";
import Accounts from "./pages/Accounts";
import Profiles from "./pages/Profiles";
import Monitoring from "./pages/Monitoring";
import Scripts from "./pages/Scripts";
import { ServerHealthProvider } from "./context/ServerHealthContext"; // Import the Provider

function App() {
  const [showStartup, setShowStartup] = useState(true);

  useEffect(() => {
    // Show startup animation for 3 seconds
    const timer = setTimeout(() => {
      setShowStartup(false);
    }, 3000);

    // Cleanup timer on unmount
    return () => clearTimeout(timer);
  }, []);

  if (showStartup) {
    return <Startup />;
  }

  return (
    // Wrap the entire application in the ServerHealthProvider
    // This ensures global server status is available everywhere
    <ServerHealthProvider>
      <Router>
        <div className="flex h-screen bg-dark-950 overflow-hidden">
          <Sidebar />
          <div className="flex-1 flex flex-col overflow-hidden">
            <Header />
            <main className="flex-1 overflow-auto p-6">
              <Routes>
                <Route path="/" element={<Home />} />
                {/*
                   We no longer need to pass 'servers' or 'health' as props here.
                   The ServerList component now uses the 'useServerHealth' hook
                   to get this data directly from the context.
                */}
                <Route path="/servers" element={<Servers />} />
                <Route path="/proxies" element={<Proxies />} />
                <Route path="/accounts" element={<Accounts />} />
                <Route path="/profiles" element={<Profiles />} />
                <Route path="/scripts" element={<Scripts />} />
                <Route path="/monitoring/:profileId" element={<Monitoring />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </main>
          </div>
        </div>
      </Router>
    </ServerHealthProvider>
  );
}

export default App;
