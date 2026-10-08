import { useEffect, useState } from "react";
import { api, setKey, getKey } from "./api";

type Any = any;
const box: React.CSSProperties = { border: "1px solid #ddd", borderRadius: 6, padding: 12, margin: "8px 0" };
const dot = (s: string) => ({ connected: "🟢", unreachable: "🔴", disabled: "⚪", unknown: "🟡" } as Any)[s] || "🟡";

function Servers({ admin }: { admin: boolean }) {
  const [rows, setRows] = useState<Any[]>([]); const [f, setF] = useState({ name: "", url: "", credential: "" });
  const load = () => api("/api/servers").then(setRows).catch(() => {});
  useEffect(() => { load(); const t = setInterval(load, 5000); return () => clearInterval(t); }, []);
  return <div>
    {rows.map(s => <div key={s.id} style={box}>{dot(s.status)} <b>{s.name}</b> — {s.status} — {s.tool_count} tools <small>{s.url}</small>
      {s.last_error && <div style={{ color: "#a00" }}>{s.last_error}</div>}
      {admin && <span style={{ float: "right" }}>
        <button onClick={() => api(`/api/servers/${s.id}`, "PATCH", { enabled: !s.enabled }).then(load)}>{s.enabled ? "Disable" : "Enable"}</button>{" "}
        <button onClick={() => api(`/api/servers/${s.id}`, "DELETE").then(load)}>Remove</button></span>}</div>)}
    {admin && <div style={box}><b>Add server</b><br />
      {(["name", "url", "credential"] as const).map(k => <input key={k} placeholder={k} type={k === "credential" ? "password" : "text"} value={f[k]} onChange={e => setF({ ...f, [k]: e.target.value })} />)}
      <button onClick={() => api("/api/servers", "POST", f).then(() => { setF({ name: "", url: "", credential: "" }); load(); }).catch(e => alert(e.message))}>Add</button></div>}
  </div>;
}
function Tools() { const [t, setT] = useState<Any[]>([]); useEffect(() => { api("/api/tools").then(setT); }, []);
  return <div>{t.map(x => <div key={x.name} style={box}><b>{x.name}</b><div>{x.description}</div></div>)}</div>; }
function Team() { const [u, setU] = useState<Any[]>([]); const [f, setF] = useState({ email: "", name: "", role: "MEMBER" }); const [shown, setShown] = useState("");
  const load = () => api("/api/users").then(setU); useEffect(() => { load(); }, []);
  return <div>{shown && <div style={{ ...box, background: "#ffd" }}>New key (shown once): <code>{shown}</code></div>}
    {u.map(x => <div key={x.id} style={box}><b>{x.email}</b> [{x.role}] {x.keys.map((k: Any) => <span key={k.id}> · {k.prefix}… {k.revoked ? "(revoked)" : <button onClick={() => api(`/api/keys/${k.id}/revoke`, "POST").then(load)}>Revoke</button>}</span>)}
      <button style={{ float: "right" }} onClick={() => api(`/api/users/${x.id}/keys`, "POST").then(r => { setShown(r.api_key); load(); })}>New API key</button></div>)}
    <div style={box}><input placeholder="email" value={f.email} onChange={e => setF({ ...f, email: e.target.value })} /><input placeholder="name" value={f.name} onChange={e => setF({ ...f, name: e.target.value })} />
      <select value={f.role} onChange={e => setF({ ...f, role: e.target.value })}><option>MEMBER</option><option>ADMIN</option></select>
      <button onClick={() => api("/api/users", "POST", f).then(load)}>Add user</button></div></div>; }
function Audit() { const [a, setA] = useState<Any[]>([]); useEffect(() => { const l = () => api("/api/audit").then(setA); l(); const t = setInterval(l, 5000); return () => clearInterval(t); }, []);
  return <table cellPadding={6}><thead><tr><th>time</th><th>user</th><th>server</th><th>tool</th><th>src</th><th>ms</th><th>ok</th><th>error</th></tr></thead>
    <tbody>{a.map(r => <tr key={r.id}><td>{r.started_at.slice(11, 19)}</td><td>{r.user}</td><td>{r.server}</td><td>{r.tool}</td><td>{r.source}</td><td>{r.duration_ms}</td><td>{r.success ? "✓" : "✗"}</td><td>{r.error}</td></tr>)}</tbody></table>; }
function Chat() { const [m, setM] = useState<Any[]>([]); const [i, setI] = useState(""); const [busy, setBusy] = useState(false); const [trace, setTrace] = useState<Any[]>([]);
  const send = async () => { const next = [...m, { role: "user", content: i }]; setM(next); setI(""); setBusy(true);
    try { const r = await api("/api/chat", "POST", { messages: next.map(x => ({ role: x.role, content: x.content })) }); setM([...next, { role: "assistant", content: r.reply }]); setTrace(r.tool_trace); }
    catch (e: Any) { setM([...next, { role: "assistant", content: "Error: " + e.message }]); } setBusy(false); };
  return <div>{m.map((x, n) => <div key={n} style={box}><b>{x.role}:</b> {x.content}</div>)}
    {trace.length > 0 && <small>tools used: {trace.map(t => t.tool).join(", ")}</small>}
    <div><input style={{ width: "70%" }} value={i} onChange={e => setI(e.target.value)} onKeyDown={e => e.key === "Enter" && send()} placeholder="Create a product called Test Shirt for 999" />
      <button disabled={busy} onClick={send}>Send</button></div></div>; }

export default function App() {
  const [me, setMe] = useState<Any>(null); const [tab, setTab] = useState("servers"); const [k, setK] = useState("");
  useEffect(() => { if (getKey()) api("/api/me").then(setMe).catch(() => {}); }, []);
  if (!me) return <div style={{ padding: 40, fontFamily: "sans-serif" }}><h2>Urumi Gateway</h2>
    <input style={{ width: 360 }} type="password" placeholder="API key (urumi_live_…)" value={k} onChange={e => setK(e.target.value)} />
    <button onClick={() => { setKey(k); api("/api/me").then(setMe).catch(() => alert("invalid key")); }}>Sign in</button></div>;
  const admin = me.role === "ADMIN";
  const tabs = ["servers", "tools", ...(admin ? ["team", "audit"] : []), "chat"];
  return <div style={{ fontFamily: "sans-serif", maxWidth: 1000, margin: "20px auto" }}>
    <h2>Urumi Gateway <small style={{ fontSize: 14 }}>— {me.email} [{me.role}] <button onClick={() => { setKey(""); setMe(null); }}>Sign out</button></small></h2>
    <div>{tabs.map(t => <button key={t} onClick={() => setTab(t)} style={{ fontWeight: tab === t ? "bold" : "normal", marginRight: 6 }}>{t}</button>)}</div><hr />
    {tab === "servers" && <Servers admin={admin} />}{tab === "tools" && <Tools />}{tab === "team" && <Team />}{tab === "audit" && <Audit />}{tab === "chat" && <Chat />}</div>;
}
