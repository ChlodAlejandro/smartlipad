window.SMARTLIPAD = {
  API_BASE: "http://localhost:8000/api"
};

function toIATA(label) {
  const match = (label || "").match(/–\s*([A-Z]{3})\)?$/);
  return match ? match[1] : "";
}

function q(params) {
  return Object.entries(params)
    .filter(([, value]) => value !== undefined && value !== null && value !== "")
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
    .join("&");
}

console.log("SmartLipad Config Loaded:", window.SMARTLIPAD.API_BASE);
