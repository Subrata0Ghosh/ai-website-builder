import axios from "axios";

const API_BASE = "http://127.0.0.1:8000";

export const generateProject = async (description) => {
  const res = await axios.post(`${API_BASE}/generate/`, { description });
  return res.data;
};

export const getPreviewUrl = (projectId) => {
  return `${API_BASE}/generated_projects/${projectId}/index_preview.html`;
};

export const getDownloadUrl = (projectId) => {
  return `${API_BASE}/download/${projectId}.zip`;
};
