import React, { useState } from "react";
import { generateProject } from "./api";
import ProjectPreview from "./components/ProjectPreview";
import "./index.css";
import "./App.css";

export default function App() {
  const [description, setDescription] = useState("");
  const [projectId, setProjectId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleGenerate = async () => {
    if (!description.trim()) return;
    setLoading(true);
    setError("");
    setProjectId(null);

    try {
      const result = await generateProject(description);
      setProjectId(result.project_id);
    } catch (err) {
      setError("⚠️ Error generating project. Check backend logs.");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-container">
      <div className="left-panel">
        <h1 className="title">🚀 AI Project Orchestrator</h1>

        <div className="input-box">
          <textarea
            placeholder="Describe your project idea (e.g. Task management app with login and sharing)"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />

          <button onClick={handleGenerate} disabled={loading}>
            {loading ? "Generating..." : "✨ Generate Project"}
          </button>

          {error && <p className="error-text">{error}</p>}
        </div>
      </div>

      <div className="right-panel">
        {projectId ? (
          <ProjectPreview projectId={projectId} />
        ) : (
          <div className="placeholder">
            <p>💡 Your project preview will appear here once generated.</p>
          </div>
        )}
      </div>
    </div>
  );
}
