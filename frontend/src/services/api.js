import axios from "axios";

export const TOKEN_KEY = "token";

// Training and large imports can take a while, hence the generous timeout.
const api = axios.create({ baseURL: "/api", timeout: 180000 });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const url = err.config?.url || "";
    const isAuthCall = url.includes("/auth/login") || url.includes("/auth/register");
    if (err.response?.status === 401 && !isAuthCall) {
      window.dispatchEvent(new Event("auth:expired"));
    }
    return Promise.reject(err);
  },
);

/** GET helper returning the unwrapped `data` field plus the full body for pagination etc. */
export async function get(path, params) {
  const { data } = await api.get(path, { params });
  return data;
}

/** Download an authenticated file (CSV/PDF) through the browser. */
export async function downloadFile(path, filename, params) {
  const res = await api.get(path, { params, responseType: "blob" });
  const url = URL.createObjectURL(res.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export default api;
