import React from "react";
import { motion } from "framer-motion";
import { Activity } from "lucide-react";

function Startup() {
  return (
    <div className="h-screen w-screen bg-gradient-to-br from-dark-950 via-dark-900 to-primary-950 flex items-center justify-center">
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5 }}
        className="text-center"
      >
        {/* Logo */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2, duration: 0.5 }}
          className="mb-8"
        >
          <div className="inline-flex items-center justify-center w-24 h-24 bg-primary-600 rounded-2xl shadow-glow-lg mb-4">
            <Activity className="w-12 h-12 text-white" />
          </div>
        </motion.div>

        {/* Title */}
        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4, duration: 0.5 }}
          className="text-5xl font-bold text-white mb-4"
        >
          Browser Farm
        </motion.h1>

        {/* Subtitle */}
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.6, duration: 0.5 }}
          className="text-xl text-dark-300 mb-12"
        >
          Distributed Browser Automation Platform
        </motion.p>

        {/* Loading Animation */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.8, duration: 0.5 }}
          className="flex items-center justify-center space-x-2"
        >
          <div
            className="w-3 h-3 bg-primary-500 rounded-full animate-pulse"
            style={{ animationDelay: "0ms" }}
          ></div>
          <div
            className="w-3 h-3 bg-primary-500 rounded-full animate-pulse"
            style={{ animationDelay: "150ms" }}
          ></div>
          <div
            className="w-3 h-3 bg-primary-500 rounded-full animate-pulse"
            style={{ animationDelay: "300ms" }}
          ></div>
        </motion.div>

        {/* Version */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1.2, duration: 0.5 }}
          className="mt-12 text-dark-500 text-sm"
        >
          Version 1.0.0
        </motion.div>
      </motion.div>
    </div>
  );
}

export default Startup;
