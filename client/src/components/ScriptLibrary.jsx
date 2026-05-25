import React, { useState, useEffect } from "react";
import { Plus, Code, Trash2 } from "lucide-react";
import store from "../store/db";

function ScriptLibrary() {
  const [scripts, setScripts] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [currentScript, setCurrentScript] = useState({
    name: "",
    code: "",
    requirements: [],
  });

  useEffect(() => {
    loadScripts();
  }, []);

  const loadScripts = async () => {
    const s = await store.get("scripts");
    setScripts(s || []);
  };

  const saveScript = async () => {
    const newScript = {
      id: `script_${Date.now()}`,
      name: currentScript.name,
      code: currentScript.code,
      requirements: currentScript.requirements
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
      createdAt: new Date().toISOString(),
    };

    const updated = [...scripts, newScript];
    await store.set("scripts", updated);
    setScripts(updated);
    setShowModal(false);
  };

  const deleteScript = async (id) => {
    const updated = scripts.filter((s) => s.id !== id);
    await store.set("scripts", updated);
    setScripts(updated);
  };

  return (
    <div className="animate-fade-in">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-white">Script Library</h2>
        <button onClick={() => setShowModal(true)} className="btn btn-primary">
          <Plus className="w-4 h-4 mr-2" /> New Script
        </button>
      </div>

      <div className="grid gap-4">
        {scripts.map((script) => (
          <div key={script.id} className="card">
            <div className="flex justify-between">
              <div>
                <h3 className="text-lg font-semibold text-white">
                  {script.name}
                </h3>
                <p className="text-xs text-dark-400 mt-1">
                  Requirements: {script.requirements.join(", ") || "None"}
                </p>
              </div>
              <button
                onClick={() => deleteScript(script.id)}
                className="btn btn-error btn-sm"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
            <pre className="mt-2 p-2 bg-dark-900 rounded text-xs text-dark-300 overflow-x-auto">
              {script.code.substring(0, 100)}...
            </pre>
          </div>
        ))}
      </div>

      {/* Modal for adding script */}
      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-dark-800 rounded-lg p-6 w-full max-w-2xl">
            <h3 className="text-xl font-bold mb-4 text-white">
              New Script Module
            </h3>

            <div className="space-y-4">
              <input
                type="text"
                placeholder="Script Name (e.g. Instagram Login)"
                className="input w-full"
                onChange={(e) =>
                  setCurrentScript({ ...currentScript, name: e.target.value })
                }
              />

              <input
                type="text"
                placeholder="Requirements (comma separated: pyautogui, bs4)"
                className="input w-full"
                onChange={(e) =>
                  setCurrentScript({
                    ...currentScript,
                    requirements: e.target.value,
                  })
                }
              />

              <textarea
                className="input w-full font-mono text-sm h-64"
                placeholder="async def main(context):..."
                onChange={(e) =>
                  setCurrentScript({ ...currentScript, code: e.target.value })
                }
              />
            </div>

            <div className="flex space-x-3 mt-6">
              <button
                onClick={() => setShowModal(false)}
                className="btn btn-secondary flex-1"
              >
                Cancel
              </button>
              <button onClick={saveScript} className="btn btn-primary flex-1">
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
export default ScriptLibrary;
