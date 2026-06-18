import { useRef, useEffect, useCallback, useState } from "react";

/**
 * Custom hook for batching mouse movement events.
 *
 * Captures every mousemove event into a buffer, then flushes
 * the buffer every `intervalMs` milliseconds as a single
 * batch_move WebSocket message.
 *
 * @param {Function} sendAction - WebSocket send function
 * @param {number} intervalMs - Batch flush interval (default: 50ms = 20 FPS)
 * @param {number} maxGhostPoints - Max points to keep for ghost trail
 * @returns {Object} { addPoint, pendingPoints, sentPoints, clearGhost }
 */
export function useMouseBatcher(
  sendAction,
  intervalMs = 50,
  maxGhostPoints = 100,
) {
  const bufferRef = useRef([]);
  const pendingRef = useRef([]);
  const sentRef = useRef([]);
  const [version, setVersion] = useState(0);

  // Batch sender interval
  useEffect(() => {
    const interval = setInterval(() => {
      if (bufferRef.current.length > 0) {
        // Send batch
        sendAction({
          type: "batch_move",
          points: bufferRef.current,
        });

        // Move points to "sent" for visual fading
        sentRef.current = [...sentRef.current, ...bufferRef.current].slice(
          -maxGhostPoints,
        );
        bufferRef.current = []; // Clear buffer
        pendingRef.current = [];
        setVersion((v) => v + 1);
      }
    }, intervalMs);

    return () => clearInterval(interval);
  }, [sendAction, intervalMs, maxGhostPoints]);

  // Add a point to the buffer
  const addPoint = useCallback((x, y) => {
    const point = { x, y, t: Date.now() };
    bufferRef.current.push(point);
    pendingRef.current.push(point);
    setVersion((v) => v + 1);
  }, []);

  // Clear ghost trail (e.g., on mouse up or after timeout)
  const clearGhost = useCallback(() => {
    sentRef.current = [];
    pendingRef.current = [];
    bufferRef.current = [];
    setVersion((v) => v + 1);
  }, []);

  // Auto-decay sent points after 300ms (visual fade)
  useEffect(() => {
    if (sentRef.current.length === 0) return;
    const decayInterval = setInterval(() => {
      const now = Date.now();
      const cutoff = now - 300; // Keep sent points for 300ms to show trail
      const before = sentRef.current.length;
      sentRef.current = sentRef.current.filter((p) => p.t > cutoff);
      if (sentRef.current.length !== before || pendingRef.current.length > 0) {
        setVersion((v) => v + 1);
      }
    }, 100);

    return () => clearInterval(decayInterval);
  }, []);

  return {
    addPoint,
    pendingPoints: pendingRef.current,
    sentPoints: sentRef.current,
    clearGhost,
    version, // Trigger re-render
  };
}

export default useMouseBatcher;
