import React from "react";
import { getPreviewUrl, getDownloadUrl } from "../api";

const ProjectPreview = ({ projectId }) => {
  if (!projectId) return null;

  const previewUrl = getPreviewUrl(projectId);
  const downloadUrl = getDownloadUrl(projectId);

  return (
    <div className="preview-container">
      <h2>🧩 Project ID: {projectId}</h2>
      <div className="preview-actions">
        <a href={downloadUrl} target="_blank" rel="noopener noreferrer" className="btn btn-green">
          📦 Download ZIP
        </a>
        <a href={previewUrl} target="_blank" rel="noopener noreferrer" className="btn btn-blue">
          🔍 Open Preview
        </a>
      </div>
      <iframe title="Project Preview" src={previewUrl} className="preview-frame" />
    </div>
  );
};

export default ProjectPreview;
