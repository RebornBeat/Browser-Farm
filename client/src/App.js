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
import Scripts from "./pages/Scripts"; // NEW: Import Scripts Page

function App() {
  const [showStartup, setShowStartup] = useState(true);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Show startup animation for 3 seconds
    setTimeout(() => {
      setShowStartup(false);
      setLoading(false);
    }, 3000);
  }, []);

  if (showStartup) {
    return <Startup />;
  }

  return (
    <Router>
      <div className="flex h-screen bg-dark-950 overflow-hidden">
        <Sidebar />
        <div className="flex-1 flex flex-col overflow-hidden">
          <Header />
          <main className="flex-1 overflow-auto p-6">
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/servers" element={<Servers />} />
              <Route path="/proxies" element={<Proxies />} />
              <Route path="/accounts" element={<Accounts />} />
              <Route path="/profiles" element={<Profiles />} />
              <Route path="/scripts" element={<Scripts />} />{" "}
              {/* NEW: Scripts Route */}
              <Route path="/monitoring/:profileId" element={<Monitoring />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
        </div>
      </div>
    </Router>
  );
}

export default App;
