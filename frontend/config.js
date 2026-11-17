const localHosts = ["localhost", "127.0.0.1"];
window.TASKFLOW_API_URL = localHosts.includes(window.location.hostname)
  ? ""
  : "https://taskflow-qa-api.onrender.com";
