import React, { useMemo } from "react";

/**
 * SVG overlay that renders a fading "ghost trail" of mouse movements.
 *
 * @param {Array} pendingPoints - Points buffered but not yet sent (Cyan)
 * @param {Array} sentPoints - Points just sent to server (Blue, fading)
 * @param {number} width - SVG viewBox width
 * @param {number} height - SVG viewBox height
 */
function GhostCursor({
  pendingPoints = [],
  sentPoints = [],
  width = 1920,
  height = 1080,
}) {
  const { pendingPath, sentPath, lastPoint } = useMemo(() => {
    const buildPath = (pts) => {
      if (pts.length === 0) return "";
      return pts
        .map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`)
        .join(" ");
    };

    const lastPending =
      pendingPoints.length > 0 ? pendingPoints[pendingPoints.length - 1] : null;
    const lastSent =
      sentPoints.length > 0 ? sentPoints[sentPoints.length - 1] : null;

    // The "head" is always the most recent point overall
    const last = lastPending || lastSent;

    return {
      pendingPath: buildPath(pendingPoints),
      sentPath: buildPath(sentPoints),
      lastPoint: last,
    };
  }, [pendingPoints, sentPoints]);

  if (!lastPoint && pendingPoints.length === 0 && sentPoints.length === 0)
    return null;

  return (
    <svg
      className="absolute inset-0 pointer-events-none w-full h-full"
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      style={{ zIndex: 30 }}
    >
      <defs>
        <filter id="ghost-glow">
          <feGaussianBlur stdDeviation="2" result="coloredBlur" />
          <feMerge>
            <feMergeNode in="coloredBlur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* Sent Trail (Fading Blue) */}
      {sentPath && (
        <path
          d={sentPath}
          stroke="rgba(59, 130, 246, 0.4)" // Faded blue
          strokeWidth="2"
          fill="none"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      )}

      {/* Pending Trail (Bright Cyan) - What is buffered to be sent */}
      {pendingPath && (
        <path
          d={pendingPath}
          stroke="rgba(34, 211, 238, 0.9)" // Bright cyan
          strokeWidth="3"
          fill="none"
          strokeLinecap="round"
          strokeLinejoin="round"
          filter="url(#ghost-glow)"
        />
      )}

      {/* Head dot (Most recent position) */}
      {lastPoint && (
        <>
          <circle
            cx={lastPoint.x}
            cy={lastPoint.y}
            r="12"
            fill="rgba(34, 211, 238, 0.2)"
          />
          <circle
            cx={lastPoint.x}
            cy={lastPoint.y}
            r="6"
            fill="rgba(34, 211, 238, 0.6)"
          />
          <circle
            cx={lastPoint.x}
            cy={lastPoint.y}
            r="3"
            fill="rgba(255, 255, 255, 0.9)"
          />
        </>
      )}
    </svg>
  );
}

export default GhostCursor;
