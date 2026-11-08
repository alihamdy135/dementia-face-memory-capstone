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
  known: "شخص معروف", unknown: "شخص غير معروف", ambiguous: "تطابق غير حاسم",
  no_face: "لم يُعثر على وجه", multiple_faces: "توجد وجوه متعددة", invalid_image: "الصورة غير صالحة",
};

function errorLabel(code: string) {
  const labels: Record<string, string> = {
    invalid_credentials_format: "استخدم بريدًا صحيحًا وكلمة مرور من 10 أحرف على الأقل.",
    email_already_registered: "هذا البريد مسجّل بالفعل. سجّل الدخول بدلًا من ذلك.",
    invalid_email_or_password: "البريد الإلكتروني أو كلمة المرور غير صحيحة.",
    no_face: "لم يظهر وجه واحد واضح في الصورة.", multiple_faces: "تحتوي الصورة على أكثر من وجه.",
    invalid_image: "تعذّر قراءة الصورة. استخدم JPEG أو PNG أو WebP.", model_unavailable: "خدمة الموديل غير متاحة الآن. شغّل خدمة Python أولًا.",
    transcription_unavailable: "التفريغ العربي المحلي غير مُثبّت. راجع تعليمات إعداد Whisper.",
    transcription_failed: "لم ينجح تفريغ التسجيل. جرّب تسجيلًا أوضح وأقصر.",
    model_version_mismatch_re_enroll_required: "إصدار البصمة قديم. يلزم إعادة تسجيل صور هذا الشخص.",
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
  };
  return <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d={paths[name] ?? paths.home} /></svg>;
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
      await loadWorkspace(); setNotice("تم تسجيل الدخول بأمان.");
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
        setNotice(`قُبلت ${accepted} صورة ورُفضت ${rejected.length}. ${rejected.join(" · ")}`);
      } else setNotice(editing ? "تم تحديث بيانات الشخص." : "تمت إضافة الشخص. أضف صورًا لتفعيل التعرّف عليه.");
      setPhotoFiles([]); setEditing(null); setPersonName(""); setRelationship("");
      await refreshData();
    } catch (error) { setNotice(errorLabel(error instanceof Error ? error.message : "unknown_error")); }
    finally { setBusy(false); }
  }

  async function deletePerson(person: Person) {
    if (!window.confirm(`حذف ${person.name} وبصماته وسجلاته؟`)) return;
    try { await api(`/api/people/${person.id}`, { method: "DELETE" }); setNotice("تم الحذف مع السجلات المرتبطة."); await refreshData(); }
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
    } catch { setCameraError("إذن الكاميرا مرفوض أو لا توجد كاميرا متاحة. يمكنك استخدام رفع صورة."); }
  }

  function stopCamera() {
    cameraRef.current?.getTracks().forEach((track) => track.stop());
    cameraRef.current = null; setCameraActive(false);
  }

  async function captureFrame() {
    const video = videoRef.current;
    if (!video || !video.videoWidth) { setCameraError("انتظر حتى تظهر معاينة الكاميرا."); return; }
    const canvas = document.createElement("canvas"); canvas.width = video.videoWidth; canvas.height = video.videoHeight;
    canvas.getContext("2d")?.drawImage(video, 0, 0);
    canvas.toBlob((blob) => { if (blob) void recognizeImage(blob, "camera-frame.jpg"); }, "image/jpeg", 0.9);
  }

  async function confirmRecognition() {
    if (!result?.person) return;
    setConfirmedPerson(result.person); setNotice("أكدت هوية الشخص. يمكنك الآن اختيار تسجيل ملاحظة بموافقته.");
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
          setTranscript(response.text); setNotice("راجع النص وعدّله قبل الحفظ.");
        } catch (error) { setNotice(errorLabel(error instanceof Error ? error.message : "transcription_unavailable")); }
        finally { audioChunksRef.current = []; setBusy(false); }
      };
      recorder.start(); setRecording(true); setNotice("التسجيل جارٍ. اضغط إيقاف عند الانتهاء.");
    } catch { setNotice("تعذّر الوصول إلى الميكروفون. راجع إذن المتصفح."); }
  }

  function stopRecording() { if (recorderRef.current?.state === "recording") recorderRef.current.stop(); }

  async function saveTranscript() {
    if (!confirmedPerson || !transcript.trim()) return;
    setBusy(true);
    try {
      await api("/api/memories", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ personId: confirmedPerson.id, content: transcript.trim() }) });
      setTranscript(""); setConfirmedPerson(null); setConsent(false); setNotice("حُفظ النص في سجل الشخص الصحيح. ملف الصوت المؤقت لم يُحفظ."); await refreshData();
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
      setNotice("تم تنزيل ملف تصدير خاص بهذا الشخص لاستخدامه على Pi.");
    } catch (error) { setNotice(errorLabel(error instanceof Error ? error.message : "export_failed")); }
  }

  if (!user) return <main className="auth-screen">
    <section className="auth-copy">
      <div className="brand-mark"><span className="brand-icon">ذ</span><span>ذاكرة</span></div>
      <span className="eyebrow">مساعد التذكّر الشخصي</span>
      <h1>الوجوه المألوفة،<br /><em>قريبة دائمًا.</em></h1>
      <p>تجربة محلية تساعد على تذكّر الأشخاص والعلاقات. تُعالج الصور لاستخراج بصمة الوجه فقط، ولا يُحتفظ بالصورة الأصلية.</p>
      <div className="trust-note"><Icon name="shield" /><span>صورك وبصمات الوجوه تبقى في قاعدة بيانات حسابك المحلية.</span></div>
      <div className="auth-orbit orbit-one" /><div className="auth-orbit orbit-two" />
    </section>
    <section className="auth-panel">
      <div className="auth-card">
        <span className="eyebrow">أهلًا بك</span>
        <h2>{authMode === "register" ? "أنشئ حسابك" : "سجّل الدخول"}</h2>
        <p className="muted">{authMode === "register" ? "ابدأ مساحة خاصة لك ولأفراد أسرتك." : "أكمل إلى مساحة التذكّر الخاصة بك."}</p>
        <form onSubmit={submitAuth} className="stack-form">
          <label>البريد الإلكتروني<input required type="email" autoComplete="email" value={authEmail} onChange={(event) => setAuthEmail(event.target.value)} placeholder="name@example.com" /></label>
          <label>كلمة المرور<input required type="password" minLength={10} autoComplete={authMode === "register" ? "new-password" : "current-password"} value={authPassword} onChange={(event) => setAuthPassword(event.target.value)} placeholder="10 أحرف على الأقل" /></label>
          <button className="button primary wide" disabled={busy}>{busy ? "جارٍ التحقق…" : authMode === "register" ? "إنشاء حساب خاص" : "دخول آمن"}<Icon name="arrow" /></button>
        </form>
        {notice && <p className="notice" role="status">{notice}</p>}
        <button className="text-button auth-toggle" onClick={() => { setAuthMode(authMode === "register" ? "login" : "register"); setNotice(""); }}>
          {authMode === "register" ? "لديك حساب؟ سجّل الدخول" : "مستخدم جديد؟ أنشئ حسابًا"}
        </button>
        <p className="auth-foot">أول تسجيل ينشئ حسابًا مستقلًا. لا توجد صور أو بيانات تجريبية مسبقة.</p>
      </div>
    </section>
  </main>;

  const title = page === "home" ? "مساحة التذكّر" : page === "people" ? "الأشخاص" : page === "recognize" ? "تعرّف على شخص" : "سجل المحادثات";
  const menu = [{ id: "home", label: "نظرة عامة", icon: "home" }, { id: "people", label: "الأشخاص", icon: "people" }, { id: "recognize", label: "التعرّف", icon: "camera" }, { id: "memories", label: "المحادثات", icon: "notes" }];

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand-mark"><span className="brand-icon">ذ</span><span>ذاكرة</span><span className="brand-dot" /></div>
      <div className="side-caption">مساحتك</div>
      <nav aria-label="التنقل الرئيسي">{menu.map((item) => <button key={item.id} className={`nav-item ${page === item.id ? "active" : ""}`} onClick={() => { setPage(item.id); setNotice(""); if (item.id !== "recognize") stopCamera(); }}><Icon name={item.icon} />{item.label}{item.id === "people" && <span className="nav-count">{data.people.length}</span>}</button>)}</nav>
      <div className="sidebar-bottom">
        <div className="privacy-card"><div className="privacy-icon"><Icon name="shield" /></div><strong>خصوصيتك أولًا</strong><p>البصمات محلية ومقيدة بحسابك.</p></div>
        <div className="user-row"><div className="avatar">{user.slice(0, 1).toUpperCase()}</div><div className="user-copy"><strong>حسابي</strong><span>{user}</span></div><button className="icon-button" aria-label="تسجيل الخروج" onClick={() => void logout()}><Icon name="logout" /></button></div>
      </div>
    </aside>
    <main className="main-area">
      <header className="topbar"><div><div className="breadcrumb">ذاكرة <span>/</span> {title}</div><h1>{title}</h1></div><div className="top-actions"><div className="local-pill"><i /> مساحة محلية</div><button className="button primary top-add" onClick={() => { setPage("people"); setEditing(null); setPersonName(""); setRelationship(""); }}><Icon name="plus" /> إضافة شخص</button></div></header>
      {notice && <div className="notice global-notice" role="status">{notice}<button className="notice-close" aria-label="إغلاق" onClick={() => setNotice("")}><Icon name="close" /></button></div>}

      {page === "home" && <section className="content-grid">
        <div className="welcome-banner"><div className="welcome-art"><div className="art-halo"><span>ذ</span></div><span className="spark spark-a">✦</span><span className="spark spark-b">✳</span><span className="art-caption">لحظات تبقى</span></div><div className="welcome-text"><span className="eyebrow">مساحة آمنة وخاصة</span><h2>الألفة تبدأ<br /><em>بوجه نعرفه.</em></h2><p>أضف صورًا واضحة للأشخاص المقرّبين، ثم استخدم الكاميرا أو ارفع صورة للتعرّف.</p><button className="button light" onClick={() => setPage("recognize")}>ابدأ التعرّف <Icon name="arrow" /></button></div><span className="banner-index">01 / 03</span></div>
        <div className="stats-row"><article className="stat-card"><div className="stat-icon peach"><Icon name="people" /></div><span className="stat-label">أشخاص مسجّلون</span><strong>{data.people.length.toString().padStart(2, "0")}</strong><span className="stat-foot">في مساحتك الخاصة</span></article><article className="stat-card"><div className="stat-icon mint"><Icon name="camera" /></div><span className="stat-label">صور محفوظة كبصمات</span><strong>{data.people.reduce((sum, person) => sum + person.photoCount, 0).toString().padStart(2, "0")}</strong><span className="stat-foot">الصورة الأصلية لا تُخزّن</span></article><article className="stat-card"><div className="stat-icon lilac"><Icon name="notes" /></div><span className="stat-label">ملاحظات مؤكدة</span><strong>{data.memories.length.toString().padStart(2, "0")}</strong><span className="stat-foot">يمكن مراجعتها وحذفها</span></article></div>
        <div className="lower-grid"><section className="panel people-panel"><div className="panel-heading"><div><span className="eyebrow">دائرتك القريبة</span><h2>الأشخاص</h2></div><button className="text-button" onClick={() => setPage("people")}>عرض الكل <Icon name="arrow" /></button></div>{data.people.length ? <div className="mini-people">{data.people.slice(0, 4).map((person, index) => <button className="mini-person" key={person.id} onClick={() => { setEditing(person); setPersonName(person.name); setRelationship(person.relationship); setPage("people"); }}><span className={`person-avatar tone-${index % 4}`}>{person.name.slice(0, 1)}</span><span><strong>{person.name}</strong><small>{person.relationship}</small></span><span className="mini-count">{person.photoCount} صور</span></button>)}</div> : <div className="empty-state"><div className="empty-illustration"><Icon name="people" /></div><strong>مساحتك تبدأ بشخص واحد</strong><span>أضف شخصًا وصورًا واضحة بإذنه.</span><button className="button secondary" onClick={() => setPage("people")}><Icon name="plus" /> أضف شخصًا</button></div>}</section>
          <section className="panel activity-panel"><div className="panel-heading"><div><span className="eyebrow">آخر النشاط</span><h2>محاولات التعرّف</h2></div><span className="tiny-counter">{data.recognitions.length} حديثة</span></div>{data.recognitions.length ? <div className="activity-list">{data.recognitions.slice(0, 5).map((row) => <div className="activity-item" key={row.id}><span className={`activity-dot ${row.status === "known" ? "success" : "muted-dot"}`} /><span><strong>{row.personName ?? statusLabels[row.status] ?? "نتيجة"}</strong><small>{new Date(row.createdAt).toLocaleString("ar-EG", { dateStyle: "medium", timeStyle: "short" })}</small></span><span className={`tag ${row.status === "known" ? "tag-green" : "tag-gray"}`}>{statusLabels[row.status] ?? row.status}</span></div>)}</div> : <div className="activity-empty"><span>◷</span><p>ستظهر النتائج هنا بعد أول تجربة.</p></div>}</section></div>
        <section className="safety-strip"><div className="safety-mark"><Icon name="shield" /></div><div><strong>التعرّف لا يستنتج صلة القرابة</strong><p>الاسم والصلة يضيفهما مقدم الرعاية، والمطابقة غير المؤكدة لا تُعلن كهوية.</p></div><span className="safety-badge">خصوصية مدمجة</span></section>
      </section>}

      {page === "people" && <section className="people-layout"><div className="panel person-form-panel"><div className="panel-heading"><div><span className="eyebrow">إدارة آمنة</span><h2>{editing ? "تعديل بيانات الشخص" : "إضافة شخص جديد"}</h2></div>{editing && <button className="icon-button" aria-label="إلغاء التعديل" onClick={() => { setEditing(null); setPersonName(""); setRelationship(""); }}><Icon name="close" /></button>}</div><p className="muted">الصور تُعالج في الذاكرة. سيظهر قبول أو رفض لكل صورة على حدة.</p><form className="stack-form person-form" onSubmit={submitPerson}><label>الاسم<input required maxLength={80} value={personName} onChange={(event) => setPersonName(event.target.value)} placeholder="مثال: ماما" /></label><label>صلة القرابة<input required maxLength={80} value={relationship} onChange={(event) => setRelationship(event.target.value)} placeholder="مثال: الأم" /></label><label className="upload-box"><span className="upload-symbol"><Icon name="plus" /></span><span><strong>اختر صور الوجه</strong><small>من 1 إلى 8 صور · JPG أو PNG أو WebP · كل صورة بوجه واحد</small></span><input type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={(event) => { setPhotoFiles(Array.from(event.target.files ?? [])); setPhotoResults([]); event.target.value = ""; }} /></label>{photoFiles.length > 0 && <div className="selected-files">{photoFiles.map((file) => <span key={`${file.name}-${file.lastModified}`}>{file.name}</span>)}</div>}{photoResults.length > 0 && <div className="photo-results" aria-live="polite">{photoResults.map((item, index) => <div className="photo-result" key={`${item.name}-${index}`}><span className={item.accepted ? "accepted-mark" : "rejected-mark"}>{item.accepted ? "✓" : "×"}</span><span>{item.name}</span><strong>{item.accepted ? "مقبولة" : `مرفوضة · ${errorLabel(item.reason ?? "invalid_image")}`}</strong></div>)}</div>}<button className="button primary wide" disabled={busy}>{busy ? "جارٍ المعالجة…" : editing ? "حفظ التعديلات والصور" : "إضافة الشخص وفحص الصور"}<Icon name="arrow" /></button></form><div className="privacy-inline"><Icon name="shield" /><span>لا تحفظ الخدمة الملفات الأصلية أو مسارها. تحفظ بصمة الوجه فقط.</span></div></div>
        <div className="people-list-area"><div className="section-title-row"><div><span className="eyebrow">دليل الأشخاص</span><h2>{data.people.length} أشخاص</h2></div><span className="tiny-counter">خاص بحسابك</span></div>{data.people.length ? <div className="people-cards">{data.people.map((person, index) => <article className="person-card" key={person.id}><div className="person-card-head"><span className={`person-avatar large tone-${index % 4}`}>{person.name.slice(0, 1)}</span><div className="person-main"><h3>{person.name}</h3><span>{person.relationship}</span></div><span className="photo-chip">{person.photoCount} بصمة</span></div><p className="person-description">{person.photoCount ? "جاهز للتعرّف. تُطابق الصور بعد التحقق من الوجه الواحد." : "أضف صورة وجه واحدة أو أكثر لتفعيل التعرّف."}</p><div className="person-actions"><button className="text-button" onClick={() => void openMemories(person)}>المحادثات</button><button className="text-button" onClick={() => void exportPerson(person)}><Icon name="download" /> تصدير Pi</button><button className="text-button" onClick={() => { setEditing(person); setPersonName(person.name); setRelationship(person.relationship); window.scrollTo({ top: 0, behavior: "smooth" }); }}>تعديل</button><button className="text-button danger-text" onClick={() => void deletePerson(person)}>حذف</button></div></article>)}</div> : <div className="empty-state list-empty"><div className="empty-illustration"><Icon name="people" /></div><strong>لا يوجد أشخاص بعد</strong><span>أضف الاسم والصلة ثم ارفع صورًا منفصلة.</span></div>}
          {selectedPerson && <section className="panel selected-memories"><div className="panel-heading"><div><span className="eyebrow">سجل الشخص</span><h2>{data.people.find((person) => person.id === selectedPerson)?.name}</h2></div><button className="icon-button" aria-label="إغلاق السجل" onClick={() => setSelectedPerson("")}><Icon name="close" /></button></div>{selectedMemories.length ? selectedMemories.map((memory) => <p className="memory-row" key={memory.id}>{memory.content}<small>{new Date(memory.createdAt).toLocaleString("ar-EG")}</small></p>) : <p className="muted">لا توجد محادثات محفوظة لهذا الشخص.</p>}</section>}
        </div></section>}

      {page === "recognize" && <section className="recognition-layout"><div className="panel recognition-panel"><div className="panel-heading"><div><span className="eyebrow">لقطة واحدة في كل مرة</span><h2>من صورة أو كاميرا</h2></div><span className="model-chip">YuNet · SFace</span></div><p className="muted">ابدأ بمعاينة، ثم اضغط «تعرّف» لالتقاط إطار واحد. لا يعمل التصوير التلقائي.</p><div className={`camera-stage ${cameraActive ? "live" : ""}`}><video ref={videoRef} autoPlay muted playsInline aria-label="معاينة الكاميرا" />{!cameraActive && <div className="camera-placeholder"><div className="camera-ring"><Icon name="camera" /></div><strong>المعاينة ستظهر هنا</strong><span>الكاميرا لا تعمل حتى تضغط زر البدء.</span></div>}<div className="frame-corners"><i /><i /><i /><i /></div></div>{cameraError && <p className="inline-error" role="alert">{cameraError}</p>}<div className="camera-actions">{!cameraActive ? <button className="button secondary" onClick={() => void startCamera()}><Icon name="camera" /> تشغيل الكاميرا</button> : <><button className="button primary" disabled={busy} onClick={() => void captureFrame()}>{busy ? "جارٍ التعرّف…" : "تعرّف على الشخص"}<Icon name="arrow" /></button><button className="button quiet" onClick={stopCamera}>إيقاف المعاينة</button></>}</div><div className="or-divider"><span>أو ارفع صورة</span></div><label className="upload-box recognition-upload"><span className="upload-symbol"><Icon name="plus" /></span><span><strong>اختر صورة للتعرّف</strong><small>ملف واحد · وجه واحد واضح</small></span><input type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => { const file = event.target.files?.[0]; if (file) void recognizeImage(file, file.name); }} /></label>
          {result && <div className={`result-card result-${result.status}`} role="status"><span className="result-symbol">{result.status === "known" ? "✓" : result.status === "unknown" ? "?" : "!"}</span><div className="result-copy"><span className="eyebrow">نتيجة التعرّف</span><h3>{statusLabels[result.status] ?? errorLabel(result.status)}</h3>{result.person && <><strong>{result.person.name}</strong><p>الصلة المسجلة: {result.person.relationship}</p>{result.thresholdStatus === "provisional_not_calibrated" && <small className="warning-note">حدّ المطابقة تجريبي وغير معاير ببيانات تحقق بعد.</small>}</>}</div>{result.person && !confirmedPerson && <button className="button secondary" onClick={() => void confirmRecognition()}>تأكيد الشخص</button>}</div>}
          {confirmedPerson && <section className="record-card"><div className="record-heading"><div className="record-icon"><Icon name="mic" /></div><div><h3>تسجيل ملاحظة صوتية</h3><p>للشخص المؤكد: {confirmedPerson.name} · يحتاج التسجيل إلى موافقة واضحة.</p></div></div><label className="consent-row"><input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} /> أوافق على تسجيل هذا المقطع القصير لتفريغه محليًا.</label><div className="record-actions">{!recording ? <button className="button primary" disabled={!consent || busy} onClick={() => void beginRecording()}><Icon name="mic" /> ابدأ التسجيل</button> : <button className="button danger" onClick={stopRecording}>إيقاف التسجيل</button>}{transcript && <button className="button secondary" disabled={busy} onClick={() => void saveTranscript()}>تأكيد النص وحفظه</button>}</div>{transcript && <label className="transcript-label">النص للمراجعة والتعديل<textarea rows={4} value={transcript} onChange={(event) => setTranscript(event.target.value)} /></label>}<small className="muted">لا يُحفظ ملف الصوت. يُحفظ النص فقط بعد مراجعتك وتأكيده.</small></section>}
        </div><aside className="recognition-aside"><div className="aside-illustration"><div className="face-orbit"><span>ذ</span><i /><i /><i /></div><span className="aside-spark">✦</span></div><span className="eyebrow">كيف تعمل المطابقة؟</span><h2>قرار هادئ<br />وخصوصية واضحة.</h2><ul className="steps-list"><li><span>١</span><div><strong>اكتشاف الوجه</strong><small>يشترط وجهًا واحدًا في الصورة.</small></div></li><li><span>٢</span><div><strong>استخراج البصمة</strong><small>يُعالج الإطار في الذاكرة.</small></div></li><li><span>٣</span><div><strong>التحقق من التطابق</strong><small>التطابق الملتبس لا يُعلن كهوية.</small></div></li></ul><div className="threshold-box"><span className="tiny-dot" /> وضع العرض · حد غير معاير</div></aside></section>}

      {page === "memories" && <section className="panel conversations-page"><div className="panel-heading"><div><span className="eyebrow">نصوص راجعتها بنفسك</span><h2>المحادثات والملاحظات</h2></div><span className="tiny-counter">{data.memories.length} محفوظة</span></div>{data.memories.length ? <div className="conversation-list">{data.memories.map((item) => <article className="conversation-item" key={item.id}><span className="conversation-wave"><Icon name="mic" /></span><div><strong>{item.personName ?? "شخص"}</strong><p>{item.content}</p><small>{new Date(item.createdAt).toLocaleString("ar-EG", { dateStyle: "medium", timeStyle: "short" })}</small></div></article>)}</div> : <div className="empty-state"><div className="empty-illustration"><Icon name="notes" /></div><strong>لا توجد ملاحظات بعد</strong><span>بعد تأكيد شخص معروف، يمكنك تسجيل ملاحظة صوتية بموافقته.</span><button className="button secondary" onClick={() => setPage("recognize")}>ابدأ من التعرّف <Icon name="arrow" /></button></div>}</section>}
      <footer className="page-footer"><span>ذاكرة <i /> تجربة جامعية محلية</span><span>المطابقة الموثوقة لا تُفعّل إلا بعد معايرة بيانات التحقق.</span></footer>
    </main>
  </div>;
}
