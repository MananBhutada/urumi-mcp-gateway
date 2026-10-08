let key = localStorage.getItem("urumi_key") || "";
export const setKey = (k: string) => { key = k; localStorage.setItem("urumi_key", k); };
export const getKey = () => key;
export async function api(path: string, method = "GET", body?: unknown) {
  const r = await fetch(path, { method, headers: { "Content-Type": "application/json", Authorization: `Bearer ${key}` },
    body: body ? JSON.stringify(body) : undefined });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}
