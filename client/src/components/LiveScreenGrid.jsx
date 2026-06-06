import React from "react";
import { useNavigate } from "react-router-dom";
import LiveScreenCard from "./LiveScreenCard";
import { MonitorOff } from "lucide-react";

function LiveScreenGrid({ screens, onRefresh }) {
  const navigate = useNavigate();

  const handleExpand = (profileId) => {
    navigate(`/monitoring/${profileId}`);
  };

  // Create a fixed array of 4 slots to maintain grid layout
  // We pad the screens array to have a minimum length of 4
  const displaySlots = [...screens];
  while (displaySlots.length < 4) {
    displaySlots.push(null);
  }
  // Optional: Slice to exactly 4 for the main dashboard view
  const viewSlots = displaySlots.slice(0, 4);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {viewSlots.map((screen, index) => {
        // Render Placeholder for empty slots
        if (!screen) {
          return (
            <div
              key={`placeholder-${index}`}
              className="card aspect-video flex flex-col items-center justify-center border-2 border-dashed border-dark-700 bg-dark-900/50"
            >
              <MonitorOff className="w-10 h-10 text-dark-600 mb-3" />
              <p className="text-dark-400 text-center text-sm">
                Empty Slot #{index + 1}
                <br />
                <span className="text-xs text-dark-500">
                  Start a profile to view here
                </span>
              </p>
            </div>
          );
        }

        // Render Live Card for valid slots
        return (
          <LiveScreenCard
            key={screen.profileId}
            serverId={screen.serverId}
            profileId={screen.profileId}
            profileName={screen.profileName}
            onExpand={() => handleExpand(screen.profileId)}
          />
        );
      })}
    </div>
  );
}

export default LiveScreenGrid;
