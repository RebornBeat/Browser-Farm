import React from "react";
import { Link, useLocation } from "react-router-dom";
import {
  Home,
  Server,
  Globe,
  Users,
  Layout,
  Activity,
  Code,
} from "lucide-react";

const menuItems = [
  { path: "/", icon: Home, label: "Home" },
  { path: "/servers", icon: Server, label: "Servers" },
  { path: "/proxies", icon: Globe, label: "Proxies" },
  { path: "/accounts", icon: Users, label: "Accounts" },
  { path: "/profiles", icon: Layout, label: "Profiles" },
  { path: "/scripts", icon: Code, label: "Scripts" },
];

function Sidebar() {
  const location = useLocation();

  return (
    <div className="w-60 bg-dark-900 border-r border-dark-700 flex flex-col">
      {/* Logo */}
      <div className="h-16 flex items-center px-6 border-b border-dark-700">
        <Activity className="w-8 h-8 text-primary-500 mr-3" />
        <span className="text-xl font-bold text-white">Browser Farm</span>
      </div>

      {/* Menu */}
      <nav className="flex-1 py-6">
        {menuItems.map((item) => {
          const Icon = item.icon;
          const isActive = location.pathname === item.path;

          return (
            <Link
              key={item.path}
              to={item.path}
              className={`
                flex items-center px-6 py-3 mb-1 transition-colors duration-200
                ${
                  isActive
                    ? "bg-primary-600 text-white border-l-4 border-primary-400"
                    : "text-dark-300 hover:bg-dark-800 hover:text-white"
                }
              `}
            >
              <Icon className="w-5 h-5 mr-3" />
              <span className="font-medium">{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-dark-700">
        <div className="text-xs text-dark-500 text-center">v1.0.0</div>
      </div>
    </div>
  );
}

export default Sidebar;
