let key = localStorage.getItem("urumi_key") || "";
const GATEWAY_KEY_PREFIX = "urumi_live_";
export const isGatewayApiKey = (candidate: string) => candidate.startsWith(GATEWAY_KEY_PREFIX);
export const setKey = (k: string) => {
  key = k;
  if (k) localStorage.setItem("urumi_key", k);
  else localStorage.removeItem("urumi_key");
};
export const getKey = () => key;
export class ApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}
export async function api(path: string, method = "GET", body?: unknown, authKey = key) {
  const r = await fetch(path, { method, headers: { "Content-Type": "application/json", Authorization: `Bearer ${authKey}` },
    body: body ? JSON.stringify(body) : undefined });
  if (!r.ok) throw new ApiError(r.status, `${r.status} ${await r.text()}`);
  return r.json();
}
