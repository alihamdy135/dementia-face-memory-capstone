"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";

type Person = { id: string; name: string; relationship: string; photoCount: number; createdAt?: string };
type Recognition = {
  status: string; person: { id: string; name: string; relationship: string } | null; score: number;
  model_version: string; thresholdStatus?: string;
};
type Memory = { id: string; personName?: string; content: string; createdAt: string };
type AppData = { people: Person[]; recognitions: Array<{ id: string; status: string; personName: string | null; createdAt: string }>; memories: Memory[] };

const emptyData: AppData = { people: [], recognitions: [], memories: [] };
const statusLabels: Record<string, string> = {
  known: "Known person", unknown: "Unknown person", ambiguous: "Uncertain match",
  no_face: "No face detected", multiple_faces: "Multiple faces detected", invalid_image: "Invalid image",
};

function errorLabel(code: string) {
  const labels: Record<string, string> = {
    invalid_credentials_format: "Enter a valid email and a password with at least 10 characters.",
    email_already_registered: "An account already exists for this email. Please sign in.",
    invalid_email_or_password: "The email or password is incorrect.",
    unauthorized: "Please sign in again to continue.",
    upload_between_1_and_8_photos: "Choose between 1 and 8 photos.",
    image_too_large: "This image is too large. Choose a smaller file.",
    person_has_no_compatible_photos: "Add a face photo before exporting this profile.",
    no_face: "Try an image with one clearly visible face.", multiple_faces: "This image contains more than one face.",
    invalid_image: "We could not read this image. Use JPEG, PNG, or WebP.", model_unavailable: "The recognition service is offline. Start the local Python service and try again.",
    transcription_unavailable: "Local Arabic transcription is unavailable. See the Whisper setup guide.",
    transcription_failed: "We could not transcribe this audio. Try a shorter, clearer recording.",
    model_version_mismatch_re_enroll_required: "These face templates use an older model. Add new photos for this person.",
  };
  return labels[code] ?? code.replaceAll("_", " ");
}

async function api<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { ...init, cache: "no-store" });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error ?? payload.detail ?? `http_${response.status}`);
  return payload as T;
}

function Icon({ name }: { name: string }) {
  const paths: Record<string, string> = {
    home: "M3 10.5 12 3l9 7.5M5.5 9v11h13V9M9 20v-6h6v6",
    people: "M16 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2m6-10a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm7-3a4 4 0 0 1 0 7.7M20 21v-2a4 4 0 0 0-3-3.87",
    camera: "M14 5 15.5 7H20a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h4.5L10 5h4Zm-2 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z",
    notes: "M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01",
    plus: "M12 5v14M5 12h14",
    arrow: "M5 12h14m-7-7 7 7-7 7",
    mic: "M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Zm-7 9a7 7 0 0 0 14 0M12 18v4m-4 0h8",
    shield: "M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Zm-3-11 2 2 4-4",
    logout: "M10 17l5-5-5-5m5 5H3m9-9h7a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-7",
    close: "M18 6 6 18M6 6l12 12",
    download: "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4m4-5 5 5 5-5m-5 5V3",
    focus: "M8 3H5a2 2 0 0 0-2 2v3m13-5h3a2 2 0 0 1 2 2v3M3 16v3a2 2 0 0 0 2 2h3m13-5v3a2 2 0 0 1-2 2h-3M9 10h.01m5.99 0h.01M9 14.5a4 4 0 0 0 6 0",
  };
  return <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d={paths[name] ?? paths.home} /></svg>;
}

function Brand() {
  return <div className="brand-mark"><span className="brand-icon"><Icon name="focus" /></span><span>Memento</span></div>;
}

function MemoryArt() {
  return (
    <svg className="memory-art" viewBox="0 0 500 300" aria-hidden="true" fill="none">
      <ellipse cx="254" cy="148" rx="224" ry="104" transform="rotate(-16 254 148)" stroke="#c9b8ff" strokeOpacity=".25" />
      <ellipse cx="254" cy="148" rx="201" ry="121" transform="rotate(16 254 148)" stroke="#c9b8ff" strokeOpacity=".14" />
      <circle cx="69" cy="103" r="4" fill="#bda7ff" />
      <circle cx="416" cy="242" r="5" fill="#f9b995" />
      <path d="M414 55v26m-13-13h26M85 225v20m-10-10h20" stroke="#f9b995" strokeWidth="2" strokeLinecap="round" />
      <g transform="rotate(14 343 154)">
        <rect x="281" y="75" width="122" height="162" rx="20" fill="#7354b3" stroke="#b19ae7" strokeWidth="1.5" />
        <circle cx="341" cy="133" r="27" fill="#bca1f4" />
        <path d="M298 195c4-23 21-37 43-37s39 14 44 37v15h-87z" fill="#ad8de8" />
        <path d="M305 222h32m9 0h15" stroke="#e7dbff" strokeWidth="3" strokeLinecap="round" opacity=".58" />
      </g>
      <g transform="rotate(-13 161 168)">
        <rect x="103" y="89" width="116" height="157" rx="20" fill="#4f3a78" stroke="#9b81cf" strokeWidth="1.5" />
        <circle cx="160" cy="142" r="24" fill="#bb8ed3" />
        <path d="M119 207c5-22 22-36 41-36s36 14 42 36v13h-83z" fill="#a36fb4" />
        <path d="M124 231h34m8 0h15" stroke="#e1c8ef" strokeWidth="3" strokeLinecap="round" opacity=".6" />
      </g>
      <rect x="169" y="28" width="167" height="233" rx="27" fill="#1d1730" fillOpacity=".64" transform="translate(0 8)" />
      <rect x="169" y="28" width="167" height="233" rx="27" fill="#e9dcff" stroke="#f4ebff" strokeWidth="2" />
      <rect x="182" y="41" width="141" height="176" rx="19" fill="#a991e3" />
      <path d="M183 151c32-36 73-48 140-33v80a19 19 0 0 1-19 19H201a19 19 0 0 1-19-19z" fill="#bea8ef" />
      <path d="M199 215v-14c7-26 27-42 53-42s46 16 53 42v14z" fill="#6c4ca3" />
      <path d="M242 158v-14h22v14c0 12-22 12-22 0z" fill="#dc947f" />
      <path d="M228 102c0-18 11-30 25-30s25 12 25 30v24c0 16-11 26-25 26s-25-10-25-26z" fill="#f6b79a" />
      <path d="M224 113v-11c0-22 13-36 30-36 16 0 28 13 28 30l-1 12c-3-3-5-10-7-15-8 6-20 10-42 9l-3 14z" fill="#442d66" />
      <circle cx="245" cy="118" r="1.8" fill="#442d66" />
      <circle cx="261" cy="118" r="1.8" fill="#442d66" />
      <path d="M248 133c3 3 7 3 10 0" stroke="#7b455a" strokeWidth="1.6" strokeLinecap="round" />
      <path d="M195 70V58h12m103 12V58h-12M195 190v12h12m103-12v12h-12" stroke="#fff5ee" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="199" cy="239" r="8" fill="#7859b7" />
      <path d="m196 239 2 2 4-4" stroke="#fff" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M214 236h54m-54 7h34" stroke="#967bbd" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

export default function Home() {
  const [user, setUser] = useState<string | null>(null);
  const [data, setData] = useState<AppData>(emptyData);
  const [page, setPage] = useState("home");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [authMode, setAuthMode] = useState<"login" | "register">("register");
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [personName, setPersonName] = useState("");
  const [relationship, setRelationship] = useState("");
  const [photoFiles, setPhotoFiles] = useState<File[]>([]);
  const [photoResults, setPhotoResults] = useState<Array<{ name: string; accepted: boolean; reason?: string }>>([]);
  const [editing, setEditing] = useState<Person | null>(null);
  const [result, setResult] = useState<Recognition | null>(null);
  const [cameraError, setCameraError] = useState("");
  const [cameraActive, setCameraActive] = useState(false);
  const [confirmedPerson, setConfirmedPerson] = useState<{ id: string; name: string; relationship: string } | null>(null);
  const [consent, setConsent] = useState(false);
  const [recording, setRecording] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [selectedPerson, setSelectedPerson] = useState("");
  const [selectedMemories, setSelectedMemories] = useState<Memory[]>([]);
  const videoRef = useRef<HTMLVideoElement>(null);
  const cameraRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  const loadWorkspace = useCallback(async () => {
    const [me, dashboard] = await Promise.all([
      api<{ user: { email: string } | null }>("/api/auth/me"),
      api<AppData>("/api/dashboard").catch(() => emptyData),
    ]);
    setUser(me.user?.email ?? null);
    if (me.user) setData(dashboard);
  }, []);

  useEffect(() => { void loadWorkspace(); }, [loadWorkspace]);

  useEffect(() => () => {
    cameraRef.current?.getTracks().forEach((track) => track.stop());
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
  }, []);

  const refreshData = useCallback(async () => {
    const next = await api<AppData>("/api/dashboard");
    setData(next);
  }, []);

  async function submitAuth(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setNotice("");
    try {
      await api(`/api/auth/${authMode}`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ email: authEmail, password: authPassword }) });
      await loadWorkspace(); setNotice("You’re signed in.");
    } catch (error) { setNotice(errorLabel(error instanceof Error ? error.message : "unknown_error")); }
    finally { setBusy(false); }
  }

  async function submitPerson(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setNotice("");
    try {
      let personId = editing?.id;
      if (editing) {
        await api(`/api/people/${editing.id}`, { method: "PATCH", headers: { "content-type": "application/json" }, body: JSON.stringify({ name: personName, relationship }) });
      } else {
        const created = await api<{ person: Person }>("/api/people", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ name: personName, relationship }) });
        personId = created.person.id;
      }
      if (personId && photoFiles.length) {
        const form = new FormData(); photoFiles.forEach((file) => form.append("photos", file));
        const upload = await api<{ outcomes: Array<{ name: string; accepted: boolean; reason?: string }>; acceptedCount: number }>(`/api/people/${personId}/photos`, { method: "POST", body: form });
        setPhotoResults(upload.outcomes);
        const accepted = upload.outcomes.filter((item) => item.accepted).length;
        const rejected = upload.outcomes.filter((item) => !item.accepted).map((item) => `${item.name}: ${errorLabel(item.reason ?? "invalid_image")}`);
        setNotice(`Photos accepted: ${accepted}. Rejected: ${rejected.length}. ${rejected.join(" · ")}`);
      } else setNotice(editing ? "Profile updated." : "Person added. Add photos to enable recognition.");
      setPhotoFiles([]); setEditing(null); setPersonName(""); setRelationship("");
      await refreshData();
    } catch (error) { setNotice(errorLabel(error instanceof Error ? error.message : "unknown_error")); }
    finally { setBusy(false); }
  }

  async function deletePerson(person: Person) {
    if (!window.confirm(`Delete ${person.name}, their face templates, and related records?`)) return;
    try { await api(`/api/people/${person.id}`, { method: "DELETE" }); setNotice("Person and related records deleted."); await refreshData(); }
    catch (error) { setNotice(errorLabel(error instanceof Error ? error.message : "unknown_error")); }
  }

  async function recognizeImage(image: Blob, filename: string) {
    if (busy) return;
    setBusy(true); setResult(null); setConfirmedPerson(null); setTranscript(""); setNotice("");
    try {
      const form = new FormData(); form.append("image", image, filename);
      setResult(await api<Recognition>("/api/recognize", { method: "POST", body: form }));
      await refreshData();
    } catch (error) {
      const code = error instanceof Error ? error.message : "unknown_error";
      setResult({ status: code, person: null, score: 0, model_version: "" });
    } finally { setBusy(false); }
  }

  async function startCamera() {
    setCameraError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" }, audio: false });
      cameraRef.current = stream;
      if (videoRef.current) videoRef.current.srcObject = stream;
      setCameraActive(true);
    } catch { setCameraError("Camera access was denied or no camera is available. You can upload a photo instead."); }
  }

  function stopCamera() {
    cameraRef.current?.getTracks().forEach((track) => track.stop());
    cameraRef.current = null; setCameraActive(false);
  }

  async function captureFrame() {
    const video = videoRef.current;
    if (!video || !video.videoWidth) { setCameraError("Wait until the camera preview appears."); return; }
    const canvas = document.createElement("canvas"); canvas.width = video.videoWidth; canvas.height = video.videoHeight;
    canvas.getContext("2d")?.drawImage(video, 0, 0);
    canvas.toBlob((blob) => { if (blob) void recognizeImage(blob, "camera-frame.jpg"); }, "image/jpeg", 0.9);
  }

  async function confirmRecognition() {
    if (!result?.person) return;
    setConfirmedPerson(result.person); setNotice("Identity confirmed. You can record a note with this person’s consent.");
  }

  async function beginRecording() {
    if (!consent || !confirmedPerson || !navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream, { mimeType: MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : undefined });
      recorderRef.current = recorder; audioChunksRef.current = [];
      recorder.ondataavailable = (event) => { if (event.data.size) audioChunksRef.current.push(event.data); };
      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop()); setRecording(false); setBusy(true);
        try {
          const form = new FormData(); form.append("audio", new Blob(audioChunksRef.current, { type: recorder.mimeType }), "recording.webm");
          const response = await api<{ text: string }>("/api/transcribe", { method: "POST", body: form });
          setTranscript(response.text); setNotice("Review and edit the transcript before saving.");
        } catch (error) { setNotice(errorLabel(error instanceof Error ? error.message : "transcription_unavailable")); }
        finally { audioChunksRef.current = []; setBusy(false); }
      };
      recorder.start(); setRecording(true); setNotice("Recording. Select Stop when you’re done.");
    } catch { setNotice("We could not access the microphone. Check your browser permissions."); }
  }

  function stopRecording() { if (recorderRef.current?.state === "recording") recorderRef.current.stop(); }

  async function saveTranscript() {
    if (!confirmedPerson || !transcript.trim()) return;
    setBusy(true);
    try {
      await api("/api/memories", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ personId: confirmedPerson.id, content: transcript.trim() }) });
      setTranscript(""); setConfirmedPerson(null); setConsent(false); setNotice("Transcript saved to this person’s history."); await refreshData();
    } catch (error) { setNotice(errorLabel(error instanceof Error ? error.message : "unknown_error")); }
    finally { setBusy(false); }
  }

  async function openMemories(person: Person) {
    setSelectedPerson(person.id);
    const response = await api<{ memories: Memory[] }>(`/api/memories?personId=${encodeURIComponent(person.id)}`);
    setSelectedMemories(response.memories);
  }

  async function logout() {
    await api("/api/auth/logout", { method: "POST" }); setUser(null); setData(emptyData); setPage("home"); stopCamera();
  }

  async function exportPerson(person: Person) {
    try {
      const response = await fetch(`/api/people/${person.id}/export`, { cache: "no-store" });
      if (!response.ok) { const body = await response.json(); throw new Error(body.error ?? "export_failed"); }
      const file = new Blob([JSON.stringify(await response.json(), null, 2)], { type: "application/json" });
      const link = document.createElement("a"); link.href = URL.createObjectURL(file); link.download = `pi-person-${person.id}.json`; link.click(); URL.revokeObjectURL(link.href);
      setNotice("Private profile downloaded for your Raspberry Pi.");
    } catch (error) { setNotice(errorLabel(error instanceof Error ? error.message : "export_failed")); }
  }

  if (!user) return <main className="auth-screen">
    <section className="auth-copy">
      <Brand />
      <div className="auth-intro">
        <span className="eyebrow">Personal memory assistant</span>
        <h1>Familiar faces.<br /><em>Closer to home.</em></h1>
        <p>A quiet place to remember the people in your life, how you know them, and what you shared.</p>
      </div>
      <MemoryArt />
      <div className="trust-note"><Icon name="shield" /><span>Photos are processed locally. Face templates stay with your account.</span></div>
    </section>
    <section className="auth-panel">
      <div className="auth-card">
        <div className="local-pill"><i /> Local workspace</div>
        <h2>{authMode === "register" ? "Create your account" : "Sign in"}</h2>
        <p className="muted">{authMode === "register" ? "Set up a private space for the people and moments you want to remember." : "Welcome back. Open your private memory space."}</p>
        <form onSubmit={submitAuth} className="stack-form">
          <label>Email address<input required type="email" autoComplete="email" value={authEmail} onChange={(event) => setAuthEmail(event.target.value)} placeholder="name@example.com" /></label>
          <label>Password<input required type="password" minLength={10} autoComplete={authMode === "register" ? "new-password" : "current-password"} value={authPassword} onChange={(event) => setAuthPassword(event.target.value)} placeholder="At least 10 characters" /></label>
          <button className="button primary wide" disabled={busy}>{busy ? "Please wait…" : authMode === "register" ? "Create account" : "Sign in"}<Icon name="arrow" /></button>
        </form>
        {notice && <p className="notice" role="status">{notice}</p>}
        <div className="auth-switch">
          <span>{authMode === "register" ? "Already have an account?" : "New to Memento?"}</span>
          <button className="text-button auth-toggle" onClick={() => { setAuthMode(authMode === "register" ? "login" : "register"); setNotice(""); }}>
            {authMode === "register" ? "Sign in" : "Create an account"}
          </button>
        </div>
        <p className="auth-foot"><Icon name="shield" /> Your space starts empty and stays private to your account.</p>
      </div>
    </section>
  </main>;

  const title = page === "home" ? "Overview" : page === "people" ? "People" : page === "recognize" ? "Recognize a face" : "Conversations";
  const menu = [{ id: "home", label: "Overview", icon: "home" }, { id: "people", label: "People", icon: "people" }, { id: "recognize", label: "Recognition", icon: "camera" }, { id: "memories", label: "Conversations", icon: "notes" }];

  return <div className="app-shell">
    <aside className="sidebar">
      <Brand />
      <div className="side-caption">WORKSPACE</div>
      <nav aria-label="Main navigation">{menu.map((item) => <button key={item.id} className={`nav-item ${page === item.id ? "active" : ""}`} aria-current={page === item.id ? "page" : undefined} onClick={() => { setPage(item.id); setNotice(""); if (item.id !== "recognize") stopCamera(); }}><Icon name={item.icon} />{item.label}{item.id === "people" && <span className="nav-count">{data.people.length}</span>}</button>)}</nav>
      <div className="sidebar-bottom">
        <div className="privacy-card"><div className="privacy-icon"><Icon name="shield" /></div><strong>Private by design</strong><p>Face templates are stored locally for your account.</p></div>
        <div className="user-row"><div className="avatar">{user.slice(0, 1).toUpperCase()}</div><div className="user-copy"><strong>Your account</strong><span>{user}</span></div><button className="icon-button" aria-label="Sign out" onClick={() => void logout()}><Icon name="logout" /></button></div>
      </div>
    </aside>
    <main className="main-area">
      <header className="topbar"><div><div className="breadcrumb">Memento <span>/</span> {title}</div><h1>{title}</h1></div><div className="top-actions"><div className="local-pill"><i /> Local workspace</div><button className="icon-button mobile-sign-out" aria-label="Sign out" onClick={() => void logout()}><Icon name="logout" /></button><button className="button primary top-add" onClick={() => { setPage("people"); setEditing(null); setPersonName(""); setRelationship(""); }}><Icon name="plus" /> Add person</button></div></header>
      {notice && <div className="notice global-notice" role="status">{notice}<button className="notice-close" aria-label="Close" onClick={() => setNotice("")}><Icon name="close" /></button></div>}

      {page === "home" && <section className="content-grid">
        <div className="welcome-banner"><div className="welcome-text"><span className="eyebrow">Your memory space</span><h2>A little help<br /><em>remembering.</em></h2><p>Add someone you know, then use your camera or a photo to find their saved profile.</p><button className="button light" onClick={() => setPage("recognize")}>Recognize a face <Icon name="arrow" /></button></div><MemoryArt /></div>
        <div className="stats-row"><article className="stat-card"><div className="stat-icon peach"><Icon name="people" /></div><span className="stat-label">Saved people</span><strong>{data.people.length.toString().padStart(2, "0")}</strong><span className="stat-foot">In your private circle</span></article><article className="stat-card"><div className="stat-icon periwinkle"><Icon name="camera" /></div><span className="stat-label">Face templates</span><strong>{data.people.reduce((sum, person) => sum + person.photoCount, 0).toString().padStart(2, "0")}</strong><span className="stat-foot">Original photos are discarded</span></article><article className="stat-card"><div className="stat-icon lilac"><Icon name="notes" /></div><span className="stat-label">Saved notes</span><strong>{data.memories.length.toString().padStart(2, "0")}</strong><span className="stat-foot">Reviewed and saved by you</span></article></div>
        <div className="lower-grid"><section className="panel people-panel"><div className="panel-heading"><div><span className="eyebrow">YOUR CIRCLE</span><h2>People</h2></div><button className="text-button" onClick={() => setPage("people")}>View all <Icon name="arrow" /></button></div>{data.people.length ? <div className="mini-people">{data.people.slice(0, 4).map((person, index) => <button className="mini-person" key={person.id} onClick={() => { setEditing(person); setPersonName(person.name); setRelationship(person.relationship); setPage("people"); }}><span className={`person-avatar tone-${index % 4}`}>{person.name.slice(0, 1)}</span><span><strong>{person.name}</strong><small>{person.relationship}</small></span><span className="mini-count">{person.photoCount} photos</span></button>)}</div> : <div className="empty-state"><div className="empty-illustration"><Icon name="people" /></div><strong>Start with someone you know</strong><span>Add a name and clear photos with their permission.</span><button className="button secondary" onClick={() => setPage("people")}><Icon name="plus" /> Add someone</button></div>}</section>
          <section className="panel activity-panel"><div className="panel-heading"><div><span className="eyebrow">RECENT ACTIVITY</span><h2>Recognition history</h2></div><span className="tiny-counter">{data.recognitions.length} recent</span></div>{data.recognitions.length ? <div className="activity-list">{data.recognitions.slice(0, 5).map((row) => <div className="activity-item" key={row.id}><span className={`activity-dot ${row.status === "known" ? "success" : "muted-dot"}`} /><span><strong>{row.personName ?? statusLabels[row.status] ?? "Recognition result"}</strong><small>{new Date(row.createdAt).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" })}</small></span><span className={`tag ${row.status === "known" ? "tag-known" : "tag-gray"}`}>{statusLabels[row.status] ?? row.status}</span></div>)}</div> : <div className="activity-empty"><span>◷</span><p>Your first recognition result will appear here.</p></div>}</section></div>
        <section className="safety-strip"><div className="safety-mark"><Icon name="shield" /></div><div><strong>Relationships are added by you</strong><p>The model matches faces to saved profiles and flags uncertain matches for you to review.</p></div><span className="safety-badge">Private workspace</span></section>
      </section>}

      {page === "people" && <section className="people-layout"><div className="panel person-form-panel"><div className="panel-heading"><div><span className="eyebrow">PROFILE DETAILS</span><h2>{editing ? "Edit profile" : "Add someone"}</h2></div>{editing && <button className="icon-button" aria-label="Cancel editing" onClick={() => { setEditing(null); setPersonName(""); setRelationship(""); }}><Icon name="close" /></button>}</div><p className="muted">Each photo is processed in memory and checked for one clear face.</p><form className="stack-form person-form" onSubmit={submitPerson}><label>Name<input required maxLength={80} dir="auto" value={personName} onChange={(event) => setPersonName(event.target.value)} placeholder="e.g. Maria" /></label><label>Relationship<input required maxLength={80} dir="auto" value={relationship} onChange={(event) => setRelationship(event.target.value)} placeholder="e.g. Mother" /></label><label className="upload-box"><span className="upload-symbol"><Icon name="plus" /></span><span><strong>Choose face photos</strong><small>1–8 photos · JPG, PNG, or WebP · One face per photo</small></span><input type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={(event) => { setPhotoFiles(Array.from(event.target.files ?? [])); setPhotoResults([]); event.target.value = ""; }} /></label>{photoFiles.length > 0 && <div className="selected-files">{photoFiles.map((file) => <span key={`${file.name}-${file.lastModified}`}>{file.name}</span>)}</div>}{photoResults.length > 0 && <div className="photo-results" aria-live="polite">{photoResults.map((item, index) => <div className="photo-result" key={`${item.name}-${index}`}><span className={item.accepted ? "accepted-mark" : "rejected-mark"}>{item.accepted ? "✓" : "×"}</span><span>{item.name}</span><strong>{item.accepted ? "Accepted" : `Rejected · ${errorLabel(item.reason ?? "invalid_image")}`}</strong></div>)}</div>}<button className="button primary wide" disabled={busy}>{busy ? "Processing…" : editing ? "Save profile" : "Add person"}<Icon name="arrow" /></button></form><div className="privacy-inline"><Icon name="shield" /><span>Only face templates are saved. Original photos and file paths are discarded.</span></div></div>
        <div className="people-list-area"><div className="section-title-row"><div><span className="eyebrow">PEOPLE DIRECTORY</span><h2>{data.people.length} people</h2></div><span className="tiny-counter">Private to you</span></div>{data.people.length ? <div className="people-cards">{data.people.map((person, index) => <article className="person-card" key={person.id}><div className="person-card-head"><span className={`person-avatar large tone-${index % 4}`}>{person.name.slice(0, 1)}</span><div className="person-main"><h3>{person.name}</h3><span>{person.relationship}</span></div><span className="photo-chip">{person.photoCount} templates</span></div><p className="person-description">{person.photoCount ? "Ready for recognition." : "Add a face photo to enable recognition."}</p><div className="person-actions"><button className="text-button" onClick={() => void openMemories(person)}>Conversations</button><button className="text-button" onClick={() => void exportPerson(person)}><Icon name="download" /> Export for Pi</button><button className="text-button" onClick={() => { setEditing(person); setPersonName(person.name); setRelationship(person.relationship); window.scrollTo({ top: 0, behavior: "smooth" }); }}>Edit</button><button className="text-button danger-text" onClick={() => void deletePerson(person)}>Delete</button></div></article>)}</div> : <div className="empty-state list-empty"><div className="empty-illustration"><Icon name="people" /></div><strong>No saved people yet</strong><span>Add a name, a relationship, and at least one clear photo.</span></div>}
          {selectedPerson && <section className="panel selected-memories"><div className="panel-heading"><div><span className="eyebrow">PERSONAL HISTORY</span><h2>{data.people.find((person) => person.id === selectedPerson)?.name}</h2></div><button className="icon-button" aria-label="Close history" onClick={() => setSelectedPerson("")}><Icon name="close" /></button></div>{selectedMemories.length ? selectedMemories.map((memory) => <p className="memory-row" key={memory.id}>{memory.content}<small>{new Date(memory.createdAt).toLocaleString("en-GB")}</small></p>) : <p className="muted">No conversations saved for this person yet.</p>}</section>}
        </div></section>}

      {page === "recognize" && <section className="recognition-layout"><div className="panel recognition-panel"><div className="panel-heading"><div><span className="eyebrow">ONE FRAME AT A TIME</span><h2>Camera or photo</h2></div><span className="model-chip">YuNet · SFace</span></div><p className="muted">Start the camera, then select Recognize to capture one frame. You can also upload a photo.</p><div className={`camera-stage ${cameraActive ? "live" : ""}`}><video ref={videoRef} autoPlay muted playsInline aria-label="Camera preview" />{!cameraActive && <div className="camera-placeholder"><div className="camera-ring"><Icon name="camera" /></div><strong>Camera preview</strong><span>Select Start camera when you’re ready.</span></div>}<div className="frame-corners"><i /><i /><i /><i /></div></div>{cameraError && <p className="inline-error" role="alert">{cameraError}</p>}<div className="camera-actions">{!cameraActive ? <button className="button secondary" onClick={() => void startCamera()}><Icon name="camera" /> Start camera</button> : <><button className="button primary" disabled={busy} onClick={() => void captureFrame()}>{busy ? "Recognizing…" : "Recognize"}<Icon name="arrow" /></button><button className="button quiet" onClick={stopCamera}>Stop camera</button></>}</div><div className="or-divider"><span>or upload a photo</span></div><label className="upload-box recognition-upload"><span className="upload-symbol"><Icon name="plus" /></span><span><strong>Choose a photo</strong><small>One file · One clearly visible face</small></span><input type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => { const file = event.target.files?.[0]; if (file) void recognizeImage(file, file.name); }} /></label>
          {result && <div className={`result-card result-${result.status}`} role="status"><span className="result-symbol">{result.status === "known" ? "✓" : result.status === "unknown" ? "?" : "!"}</span><div className="result-copy"><span className="eyebrow">Recognition result</span><h3>{statusLabels[result.status] ?? errorLabel(result.status)}</h3>{result.person && <><strong>{result.person.name}</strong><p>Relationship: {result.person.relationship}</p>{result.thresholdStatus === "provisional_not_calibrated" && <small className="warning-note">This workspace uses a provisional matching threshold.</small>}</>}</div>{result.person && !confirmedPerson && <button className="button secondary" onClick={() => void confirmRecognition()}>Confirm identity</button>}</div>}
          {confirmedPerson && <section className="record-card"><div className="record-heading"><div className="record-icon"><Icon name="mic" /></div><div><h3>Record a voice note</h3><p>Ask {confirmedPerson.name} for permission before recording.</p></div></div><label className="consent-row"><input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} /> Everyone being recorded has agreed to local transcription.</label><div className="record-actions">{!recording ? <button className="button primary" disabled={!consent || busy} onClick={() => void beginRecording()}><Icon name="mic" /> Start recording</button> : <button className="button danger" onClick={stopRecording}>Stop recording</button>}{transcript && <button className="button secondary" disabled={busy} onClick={() => void saveTranscript()}>Save transcript</button>}</div>{transcript && <label className="transcript-label">Review and edit transcript<textarea rows={4} dir="auto" value={transcript} onChange={(event) => setTranscript(event.target.value)} /></label>}<small className="muted">Only the transcript is saved after you review and confirm it.</small></section>}
        </div><aside className="recognition-aside"><div className="aside-illustration"><div className="face-orbit"><span><Icon name="focus" /></span></div><span className="aside-spark">✦</span></div><span className="eyebrow">HOW IT WORKS</span><h2>From a face<br />to a name.</h2><ul className="steps-list"><li><span>1</span><div><strong>Detect a face</strong><small>Look for one clear face in the frame.</small></div></li><li><span>2</span><div><strong>Create a face template</strong><small>Process the image in memory.</small></div></li><li><span>3</span><div><strong>Check for a match</strong><small>Return a name only when the match is clear.</small></div></li></ul><div className="threshold-box"><span className="tiny-dot" /> Demo mode · Provisional threshold</div></aside></section>}

      {page === "memories" && <section className="panel conversations-page"><div className="panel-heading"><div><span className="eyebrow">REVIEWED TRANSCRIPTS</span><h2>Conversations and notes</h2></div><span className="tiny-counter">{data.memories.length} saved</span></div>{data.memories.length ? <div className="conversation-list">{data.memories.map((item) => <article className="conversation-item" key={item.id}><span className="conversation-wave"><Icon name="mic" /></span><div><strong>{item.personName ?? "Person"}</strong><p>{item.content}</p><small>{new Date(item.createdAt).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" })}</small></div></article>)}</div> : <div className="empty-state"><div className="empty-illustration"><Icon name="notes" /></div><strong>No notes yet</strong><span>After confirming a match, you can record a voice note with permission.</span><button className="button secondary" onClick={() => setPage("recognize")}>Go to recognition <Icon name="arrow" /></button></div>}</section>}
      <footer className="page-footer"><span>Memento <i /> Local Capstone prototype</span><span>Face matches are suggestions. Confirm the identity before recording.</span></footer>
    </main>
  </div>;
}
