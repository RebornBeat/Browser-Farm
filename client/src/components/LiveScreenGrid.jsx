import React from "react";
import { useNavigate } from "react-router-dom";
import LiveScreenCard from "./LiveScreenCard";

function LiveScreenGrid({ screens }) {
  const navigate = useNavigate();

  const handleExpand = (profileId) => {
    navigate(`/monitoring/${profileId}`);
  };

  if (!screens || screens.length === 0) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <p className="text-xl text-dark-400 mb-4">No screens to display</p>
          <p className="text-sm text-dark-500">
            Launch a profile to view live screens
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`grid gap-6 ${
        screens.length === 1
          ? "grid-cols-1"
          : screens.length === 2
            ? "grid-cols-2"
            : screens.length === 3
              ? "grid-cols-3"
              : "grid-cols-2 xl:grid-cols-4"
      }`}
    >
      {screens.map((screen) => (
        <LiveScreenCard
          key={screen.profileId}
          serverId={screen.serverId}
          profileId={screen.profileId}
          profileName={screen.profileName}
          onExpand={() => handleExpand(screen.profileId)}
        />
      ))}
    </div>
  );
}

export default LiveScreenGrid;
