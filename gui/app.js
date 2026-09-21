// AIOrganizerPro desktop GUI — semua aksi diarahkan ke Tauri/native backend.
const $ = (id) => document.getElementById(id);
const TAURI = window.__TAURI__ || null;
const NATIVE = !!(TAURI && TAURI.core && TAURI.core.invoke);
const invoke = (cmd, args = {}) => { if(!NATIVE) throw new Error("Tauri native API tidak tersedia"); return TAURI.core.invoke(cmd, args); };
const toAssetUrl = (path) => {
  const value = String(path || "");
  if(!value) return "";
  if(NATIVE && typeof TAURI.core.convertFileSrc === "function") return TAURI.core.convertFileSrc(value, "asset");
  return "file:///" + encodeURI(value.replace(/\\/g,"/"));
};
const state = {
  lang: "id", root: localStorage.getItem("aiorg.root") || "", videos: [], photos: [], folders: [], current: null, currentPhoto: null,
  orgFiles: [], orgSel: new Set(), lastOrgReport: "", dialogResolve: null, dialogKind: "text", lastLibrary: null, lastPhotos: null,
  tabs: [], activeTabId: null
};

const esc = (v) => String(v ?? "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
const fmtBytes = (n) => { n=Number(n)||0; if(n>=1e12)return (n/1e12).toFixed(2)+" TB"; if(n>=1e9)return (n/1e9).toFixed(2)+" GB"; if(n>=1e6)return (n/1e6).toFixed(1)+" MB"; if(n>=1e3)return (n/1e3).toFixed(1)+" KB"; return n+" B"; };
const fmtDuration = (seconds) => { const n=Number(seconds); if(!Number.isFinite(n))return "—"; const s=Math.max(0,Math.floor(n)),h=Math.floor(s/3600),m=Math.floor((s%3600)/60),x=s%60; return h?`${String(h).padStart(2,"0")}:${String(m).padStart(2,"0")}:${String(x).padStart(2,"0")}`:`00:${String(m).padStart(2,"0")}:${String(x).padStart(2,"0")}`; };
const fmtDate = (ms) => { const n=Number(ms); if(!n)return "—"; const d=new Date(n); return Number.isNaN(d.getTime())?"—":d.toLocaleString(state.lang==="id"?"id-ID":"en-US",{year:"numeric",month:"short",day:"2-digit",hour:"2-digit",minute:"2-digit",second:"2-digit"}); };
const filename = (p) => String(p||"").split(/[\\/]/).pop() || "";
const dirname = (p) => { const x=String(p||"").replace(/[\\/]+$/g,""); const i=Math.max(x.lastIndexOf("\\"),x.lastIndexOf("/")); return i>=0?x.slice(0,i):x; };
const samePath = (a,b) => String(a||"").toLowerCase()===String(b||"").toLowerCase();

async function api(method,path,body){
  try{
    if(NATIVE) return await apiNative(path,body||{},method);
    const init={method,headers:{"content-type":"application/json"}};
    if(body!==undefined) init.body=JSON.stringify(body);
    const r=await fetch(path,init);
    const text=await r.text();
    try{return JSON.parse(text);}catch{return {ok:r.ok,error:text||`HTTP ${r.status}`};}
  }catch(e){ throw new Error(e?.message || String(e)); }
}
async function apiNative(path,b,m){
  const qi=path.indexOf("?");
  const q=qi<0?{}:Object.fromEntries(new URLSearchParams(path.slice(qi+1)));
  if(path==="/api/health"){const v=await invoke("app_info");return {ok:true,db:v.db,core:v.core_version,db_enabled:v.db_enabled};}
  if(path==="/api/stats")return invoke("core_stats");
  if(path==="/api/recommend")return invoke("ai_recommend");
  if(path==="/api/docs"||path.startsWith("/api/docs?"))return invoke("docs_list",{limit:Number(q.limit||200)});
  if(path==="/api/scan")return invoke("core_scan",{folder:b.folder});
  if(path==="/api/duplicates")return invoke("core_duplicates",{folder:b.folder,min_size:Number(b.minSize||1)});
  if(path==="/api/move-approved")return invoke("core_move_approved",{group:Number(b.group),keep:b.keep,to:b.to});
  if(path==="/api/ai"){const r=await invoke("ai_engine",{argv:b.argv||[]});if(r&&r.output)r.output=r.output.slice(-10000);return r;}
  if(path==="/api/jobs/enqueue")return invoke("job_enqueue",{kind:b.kind||"scan",payload:b.payload||""});
  if(path==="/api/jobs/claim")return invoke("job_claim");
  if(path==="/api/jobs/run")return invoke("job_run_once");
  if(path==="/api/jobs/list"||path.startsWith("/api/jobs/list?"))return invoke("job_list",{status:q.status||"",limit:Number(q.limit||50)});
  if(path==="/api/jobs/pause")return invoke("job_pause",{id:Number(b.id)});
  if(path==="/api/jobs/resume")return invoke("job_resume",{id:Number(b.id)});
  if(path==="/api/jobs/cancel")return invoke("job_cancel",{id:Number(b.id)});
  if(path==="/api/activity")return invoke("activity_list",{limit:Number(q.limit||200)});
  if(path==="/api/activity/clear")return invoke("activity_clear");
  if(path==="/api/activity/export")return invoke("activity_export");
  if(path==="/api/db-state"&&m==="GET")return invoke("db_state");
  if(path==="/api/db-state")return invoke("db_set_enabled",{enabled:!!b.enabled});
  if(path==="/api/doctor"||path.startsWith("/api/doctor?"))return invoke("core_doctor",{root:q.root||""});
  if(path==="/api/audit"||path.startsWith("/api/audit?"))return invoke("audit_list",{action:q.action||"",limit:Number(q.limit||100)});
  if(path==="/api/proposals/propose")return invoke("prop_propose",{group:Number(b.group),keep:b.keep,to:b.to,reasons:b.reasons||""});
  if(path==="/api/proposals/list"||path.startsWith("/api/proposals/list?"))return invoke("prop_list",{status:q.status||"pending"});
  if(path==="/api/proposals/preview"||path.startsWith("/api/proposals/preview?"))return invoke("prop_preview",{target:q.target||""});
  if(path==="/api/proposals/approve")return invoke("prop_approve",{batch:b.batch});
  if(path==="/api/proposals/reject")return invoke("prop_reject",{target:b.batch||b.target});
  if(path==="/api/videos/list"||path.startsWith("/api/videos/list?"))return invoke("videos_list",{root:q.root||"",limit:Number(q.limit||5000),kind:q.kind||"videos"});
  if(path==="/api/folders/list"||path.startsWith("/api/folders/list?"))return invoke("folders_list",{root:q.root||"",limit:Number(q.limit||5000)});
  if(path==="/api/organize")return invoke("org_run",{kind:b.kind||"videos",folder:b.folder,files:b.files||[],dest:b.dest||"",content:b.content||[],copy:!!b.copy,dated:!!b.dated,junk:!!b.junk,prune:!!b.prune,limit:Number(b.limit||0),apply:!!b.apply});
  if(path==="/api/reports/get"||path.startsWith("/api/reports/get?"))return invoke("report_export",{name:q.name||""});
  if(path==="/api/video/pick")return invoke("pick_video_file");
  if(path==="/api/photo/pick")return invoke("pick_image_file");
  if(path==="/api/folder/pick")return invoke("pick_folder");
  if(path==="/api/video/inspect")return invoke("video_inspect",{path:b.path||q.path||""});
  if(path==="/api/file/info")return invoke("file_info",{path:b.path||q.path||""});
  if(path==="/api/video/duplicate-check")return invoke("video_duplicate_check",{path:b.path||""});
  if(path==="/api/video/open")return invoke("video_open",{path:b.path||""});
  if(path==="/api/video/folder")return invoke("video_show_folder",{path:b.path||""});
  if(path==="/api/video/rename")return invoke("video_rename",{path:b.path||"",new_name:b.new_name||""});
  if(path==="/api/video/move")return invoke("video_move",{path:b.path||"",destination:b.destination||""});
  if(path==="/api/video/quarantine")return invoke("video_quarantine",{path:b.path||""});
  if(path==="/api/video/annotation")return invoke("video_save_annotation",{path:b.path||"",tags:b.tags||[],note:b.note||""});
  throw new Error("endpoint tidak dikenal: "+path);
}

function toast(message,type="info",timeout=3600){
  const el=document.createElement("div"); el.className="toast "+(type||""); el.textContent=String(message);
  $("toast-stack").appendChild(el); setTimeout(()=>el.remove(),timeout);
}
function showBusy(button,on,label){ if(!button)return; if(on){button.dataset.oldText=button.textContent;button.disabled=true;button.textContent=label||"Berjalan…";}else{button.disabled=false;if(button.dataset.oldText)button.textContent=button.dataset.oldText;} }

function closeDialog(result){const b=$("modal-backdrop");b.hidden=true;const r=state.dialogResolve;state.dialogResolve=null;if(r)r(result);}
function openDialog({title,message="",kind="text",value="",options=[],okText="Lanjut",placeholder=""}){
  closeDialog(null); state.dialogKind=kind; $("modal-title").textContent=title; $("modal-message").textContent=message; $("modal-ok").textContent=okText;
  const f=$("modal-field"); f.className="modal-field";
  if(kind==="confirm") f.innerHTML="";
  else if(kind==="select") f.innerHTML=`<select id="modal-input">${options.map(o=>`<option value="${esc(o.value)}">${esc(o.label)}</option>`).join("")}</select>`;
  else if(kind==="multiselect") f.innerHTML=`<div class="modal-options">${options.map((o,i)=>`<label class="modal-option"><input type="radio" name="modal-select" value="${esc(o.value)}" ${i===0?"checked":""}><span>${esc(o.label)}</span></label>`).join("")}</div>`;
  else if(kind==="textarea") f.innerHTML=`<textarea id="modal-input" placeholder="${esc(placeholder)}">${esc(value)}</textarea>`;
  else f.innerHTML=`<input id="modal-input" value="${esc(value)}" placeholder="${esc(placeholder)}" autocomplete="off">`;
  $("modal-backdrop").hidden=false;
  setTimeout(()=>$("modal-input")?.focus(),0);
  return new Promise(resolve=>{state.dialogResolve=resolve;});
}
function dialogValue(){const el=$("modal-input"); if(el)return el.value; const r=document.querySelector('input[name="modal-select"]:checked');return r?.value||null;}
$("modal-ok").onclick=()=>closeDialog(state.dialogKind==="confirm"?true:dialogValue()); $("modal-cancel").onclick=()=>closeDialog(null); $("modal-close").onclick=()=>closeDialog(null);
$("modal-backdrop").addEventListener("click",e=>{if(e.target.id==="modal-backdrop")closeDialog(null);});
window.addEventListener("keydown",e=>{
  if(e.key==="Escape"&&!$("modal-backdrop").hidden){closeDialog(null);return;}
  if(e.key==="Enter"&&!$("modal-backdrop").hidden&&!$("modal-input")?.tagName?.toLowerCase().includes("textarea")){$("modal-ok").click();return;}
  if($("modal-backdrop").hidden&&e.ctrlKey&&!e.shiftKey&&e.key.toLowerCase()==="t"){e.preventDefault();$("tab-menu").hidden=false;return;}
  if($("modal-backdrop").hidden&&e.ctrlKey&&!e.shiftKey&&e.key.toLowerCase()==="w"){e.preventDefault();if(state.activeTabId)closeWorkspaceTab(state.activeTabId);return;}
  if($("modal-backdrop").hidden&&e.ctrlKey&&/^\d$/.test(e.key)){const index=Number(e.key)-1;if(state.tabs[index]){e.preventDefault();switchView(state.tabs[index].view,{fromTab:true});}}
});

async function chooseFolder(targetId){
  if(NATIVE){const r=await api("GET","/api/folder/pick");if(r.ok&&r.path){$(targetId).value=r.path; if(targetId==="library-root")setRoot(r.path);return r.path;}return "";}
  const v=await openDialog({title:"Pilih folder",message:"Mode web tidak memiliki dialog filesystem native. Masukkan path folder.",value:$(targetId)?.value||"",placeholder:"D:\\Videos"});
  if(v){$(targetId).value=v;if(targetId==="library-root")setRoot(v);return v;}return "";
}
async function chooseVideo(){
  if(NATIVE){const r=await api("GET","/api/video/pick");if(r.ok&&r.path){$("video-path").value=r.path;return r.path;}return "";}
  const v=await openDialog({title:"Pilih video",message:"Masukkan path video lokal.",value:$("video-path").value,placeholder:"D:\\Videos\\video.mp4"});return v||"";
}
function setRoot(root){
  state.root=String(root||"").trim();
  if(state.root){
    localStorage.setItem("aiorg.root",state.root);
    ["library-root","scan-folder","quick-scan-folder","ai-folder","dup-folder","photo-folder"].forEach(id=>{if($(id))$(id).value=state.root;});
    $("org-folder").value ||= state.root;
    $("root-status").textContent="Folder aktif: "+state.root;
    loadFolders(state.root);
  }
}

const VIEW_META = {
  dash:{title:"Beranda",icon:"⌂"}, scan:{title:"Semua Video",icon:"▣"}, photos:{title:"Semua Foto",icon:"▧"},
  dup:{title:"Duplikat",icon:"◈"}, doc:{title:"Dokumen AI",icon:"▤"}, db:{title:"Database",icon:"◉"}, act:{title:"Aktivitas",icon:"◷"}
};
function tabId(view){return `workspace-${view}`;}
function saveTabs(){localStorage.setItem("aiorg.tabs",JSON.stringify(state.tabs));}
function ensureTabs(){
  let parsed=[];
  try{parsed=JSON.parse(localStorage.getItem("aiorg.tabs")||"[]");}catch{}
  const valid=Array.isArray(parsed)?parsed.filter(t=>VIEW_META[t.view]):[];
  state.tabs=valid.length?valid:[{id:tabId("dash"),view:"dash",title:VIEW_META.dash.title,closable:false}];
  state.tabs.forEach(t=>{t.id=t.id||tabId(t.view);t.title=VIEW_META[t.view].title;t.closable=t.view!=="dash";});
  state.activeTabId=localStorage.getItem("aiorg.activeTab")||state.tabs[0].id;
  if(!state.tabs.some(t=>t.id===state.activeTabId))state.activeTabId=state.tabs[0].id;
  renderWorkspaceTabs();
}
function renderWorkspaceTabs(){
  const host=$("workspace-tabs"); if(!host)return;
  host.innerHTML=state.tabs.map(t=>`<button class="workspace-tab ${t.id===state.activeTabId?"active":""}" data-tab-id="${esc(t.id)}" role="tab" aria-selected="${t.id===state.activeTabId}"><span class="tab-icon">${VIEW_META[t.view].icon}</span><span class="tab-title">${esc(t.title)}</span>${t.closable?`<span class="tab-close" data-tab-close="${esc(t.id)}" title="Tutup tab">×</span>`:""}</button>`).join("");
  host.querySelectorAll("[data-tab-id]").forEach(b=>b.onclick=()=>{const t=state.tabs.find(x=>x.id===b.dataset.tabId);if(t)switchView(t.view,{fromTab:true});});
  host.querySelectorAll("[data-tab-close]").forEach(b=>b.onclick=e=>{e.stopPropagation();closeWorkspaceTab(b.dataset.tabClose);});
}
function addWorkspaceTab(view){
  if(!VIEW_META[view])return;
  let tab=state.tabs.find(t=>t.view===view);
  if(!tab){tab={id:tabId(view),view,title:VIEW_META[view].title,closable:view!=="dash"};state.tabs.push(tab);saveTabs();}
  switchView(view,{fromTab:true});
}
function closeWorkspaceTab(id){
  const idx=state.tabs.findIndex(t=>t.id===id); if(idx<0||state.tabs[idx].view==="dash")return;
  const wasActive=state.activeTabId===id; state.tabs.splice(idx,1);
  if(wasActive){const next=state.tabs[Math.max(0,idx-1)]||state.tabs[0];state.activeTabId=next.id;}
  saveTabs();localStorage.setItem("aiorg.activeTab",state.activeTabId);renderWorkspaceTabs();switchView(state.tabs.find(t=>t.id===state.activeTabId)?.view||"dash",{fromTab:true});
}
function toggleTabMenu(){const m=$("tab-menu");m.hidden=!m.hidden;}
function switchView(name,opts={}){
  if(!VIEW_META[name])name="dash";
  if(!opts.fromTab){addWorkspaceTab(name);return;}
  const tab=state.tabs.find(t=>t.view===name);
  if(tab){state.activeTabId=tab.id;localStorage.setItem("aiorg.activeTab",tab.id);}
  document.querySelectorAll("#tabs button").forEach(b=>b.classList.toggle("on",b.dataset.v===name));
  document.querySelectorAll(".view").forEach(v=>v.classList.toggle("on",v.id==="v-"+name));
  $("crumb-main").textContent={dash:"Beranda",scan:"Semua Video",photos:"Semua Foto",dup:"Duplikat",doc:"Dokumen AI",db:"Database & Jobs",act:"Aktivitas"}[name]||name;
  renderWorkspaceTabs();
  if(name==="scan")loadLibrary(state.root);
  if(name==="photos")loadPhotos(state.root);
  if(name==="dup")loadProps();
  if(name==="doc")loadDocs();
  if(name==="db"){loadDbState();loadJobs();loadAudit();}
  if(name==="act")loadActivity();
}
document.querySelectorAll("#tabs button").forEach(b=>b.addEventListener("click",()=>addWorkspaceTab(b.dataset.v)));
$("tab-add").onclick=toggleTabMenu;
document.querySelectorAll("#tab-menu [data-add-view]").forEach(b=>b.onclick=()=>{addWorkspaceTab(b.dataset.addView);$("tab-menu").hidden=true;});
document.addEventListener("click",e=>{if(!e.target.closest("#tab-add")&&!e.target.closest("#tab-menu"))$("tab-menu").hidden=true;});

function updateNavStats(s){
  $("nav-videos").textContent=state.videos.length?state.videos.length:(Number(s?.files)||0);
  $("nav-photos").textContent=state.photos.length;
  $("nav-dups").textContent=Number(s?.dup_groups)||0;
  const docCount=Number($("nav-docs").textContent)||0; if(!docCount) loadDocs(true);
  $("sidebar-db").textContent=s?.db||"Database siap";
}
async function stats(){
  try{const s=await api("GET","/api/stats"); if(!s?.ok){$("db-out").textContent=JSON.stringify(s||{},null,2);updateNavStats({});return s||{};} updateNavStats(s);$("db-out").textContent=JSON.stringify(s,null,2);const r=await api("GET","/api/recommend");$("recs").innerHTML=(r?.recommendations||[]).map(x=>`<div class="rec">${esc(x.text||"")}</div>`).join("")||"<span class='mut'>Belum ada rekomendasi lokal.</span>";return s;}catch(e){toast("Stats gagal: "+e.message,"bad");return {};}}
async function health(){try{const h=await api("GET","/api/health");$("health").textContent=h.ok?"● online":"● error";$("health").style.color=h.ok?"var(--ok)":"var(--bad)";$("db-path").textContent=h.db||"";$("sidebar-db").textContent=h.db_enabled===false?"Database OFF":"Database ON";}catch(e){$("health").textContent="● offline";$("health").style.color="var(--bad)";}}

async function loadFolders(root=state.root){
  root=String(root||"").trim();
  if(!root){$("folder-tree").innerHTML='<div class="empty-side">Pilih folder library.</div>';return null;}
  try{
    const r=await api("GET","/api/folders/list?root="+encodeURIComponent(root)+"&limit=5000");
    if(!r.ok)throw new Error(r.error||"folder tidak bisa dibaca");
    state.folders=r.folders||[];
    const actualVideos=state.folders.reduce((n,f)=>n+(Number(f.videos)||0),0);
    const actualPhotos=state.folders.reduce((n,f)=>n+(Number(f.images)||0),0);
    $("nav-videos").textContent=actualVideos;$("nav-photos").textContent=actualPhotos;
    renderFolders();
    return r;
  }catch(e){$("folder-tree").innerHTML=`<div class="empty-side">Gagal membaca folder: ${esc(e.message)}</div>`;return null;}
}
function renderFolders(){
  if(!state.folders.length){$("folder-tree").innerHTML='<div class="empty-side">Folder kosong.</div>';return;}
  const rows=state.folders.map(f=>{
    const active=samePath(f.path,state.root);
    const pad=Math.min(8,Number(f.depth)||0)*12;
    const label=f.rel==='.'?'(root)':f.rel;
    return `<button class="folder-node ${active?"active":""}" data-folder-path="${esc(f.path)}" title="${esc(f.path)}" style="padding-left:${10+pad}px"><span>▰</span><span class="folder-node-name">${esc(label)}</span><small>${Number(f.videos)||0}v · ${Number(f.images)||0}p</small></button>`;
  }).join("");
  $("folder-tree").innerHTML=rows;
  $("folder-tree").querySelectorAll("[data-folder-path]").forEach(b=>b.onclick=async()=>{const path=b.dataset.folderPath;setRoot(path);const active=document.querySelector(".view.on")?.id?.slice(2);const next=active==="photos"?"photos":"scan";switchView(next);});
}
function deriveSideTree(){
  const types=new Map();
  state.videos.forEach(v=>{const ext=(filename(v.path).split(".").pop()||"VIDEO").toUpperCase();types.set(ext,(types.get(ext)||0)+1);});
  const rows=[...types.entries()].sort((a,b)=>b[1]-a[1]).map(([n,c])=>`<div class="type-node"><span>▣</span><span>${esc(n)}</span><small>${c}</small></div>`).join("");
  $("type-tree").innerHTML=rows||'<div class="empty-side">Belum ada video.</div>';
}


async function loadLibrary(root=state.root){
  root=String(root||"").trim(); if(!root){toast("Pilih folder library terlebih dahulu.","warn");return null;}
  setRoot(root); $("video-list").innerHTML='<div class="empty-state">Membaca daftar video…</div>';
  try{const r=await api("GET","/api/videos/list?root="+encodeURIComponent(root)+"&kind=videos&limit=5000"); if(!r.ok){$("video-list").innerHTML=`<div class="empty-state">${esc(r.error||"Folder tidak bisa dibaca.")}</div>`;return r;}
    state.videos=r.videos||[];state.lastLibrary=r;renderLibrary();await loadFolders(root);return r;
  }catch(e){$("video-list").innerHTML=`<div class="empty-state">Gagal: ${esc(e.message)}</div>`;toast("Library gagal dimuat: "+e.message,"bad");return null;}
}
function renderLibrary(){
  const filter=($("library-filter")?.value||$("global-search")?.value||"").trim().toLowerCase(); const rows=state.videos.filter(v=>!filter||`${v.rel} ${v.path}`.toLowerCase().includes(filter));
  $("lib-total").textContent=Number(state.lastLibrary?.video_total??state.videos.length);$("lib-files").textContent=Number(state.lastLibrary?.file_total??state.videos.length);const totalSize=state.videos.reduce((a,v)=>a+(Number(v.size)||0),0);$("lib-size").textContent=fmtBytes(totalSize);
  const nonmedia=state.lastLibrary?.junk_count;$("lib-junk").textContent=Number(nonmedia)||0;$("library-caption").textContent=`${rows.length} tampil • ${state.root||"—"}`;
  $("video-list").innerHTML=rows.length?rows.map(v=>`<button class="video-row" data-path="${esc(v.path)}"><span class="mini-play">▶</span><span><span class="vname">${esc(filename(v.path))}</span><span class="vpath">${esc(v.rel||v.path)}</span></span><span class="vsize">${fmtBytes(v.size)}</span><span class="vaction">Buka →</span></button>`).join(""):`<div class="empty-state">Tidak ada video yang cocok.</div>`;
  $("video-list").querySelectorAll("[data-path]").forEach(b=>b.addEventListener("click",()=>selectVideo(b.dataset.path)));
  deriveSideTree();
  $("nav-videos").textContent=state.videos.length;
}
$("library-filter").oninput=renderLibrary;$("global-search").oninput=()=>{const q=$("global-search").value;if($("v-photos").classList.contains("on")){$("photo-filter").value=q;renderPhotos();}else{$("library-filter").value=q;if($("v-scan").classList.contains("on"))renderLibrary();else{switchView("scan");renderLibrary();}}};
$("root-browse").onclick=()=>chooseFolder("library-root");$("library-root").addEventListener("change",()=>setRoot($("library-root").value));$("library-refresh").onclick=()=>loadLibrary(state.root);
$("scan-browse").onclick=()=>chooseFolder("scan-folder");$("dup-browse").onclick=()=>chooseFolder("dup-folder");
$("dash-library").onclick=()=>switchView("scan");$("dash-photos").onclick=()=>switchView("photos");$("dash-browse").onclick=async()=>{const p=await chooseVideo();if(p){$("video-path").value=p;await loadVideo(p);}};$("video-browse").onclick=async()=>{const p=await chooseVideo();if(p)loadVideo(p);};

function clearVideoUI(){
  state.current=null;$("crumb-file").textContent="Belum ada video dipilih";$("video-title").textContent="Belum ada video";$("video-path-label").textContent="Pilih video dari Semua Video atau Pilih Video.";$("video-path").value="";$("video-name").textContent="—";$("video-size").textContent="—";$("video-duration").textContent="—";$("video-resolution").textContent="—";$("video-codec").textContent="—";$("audio-codec").textContent="—";$("video-fps").textContent="—";$("video-aspect").textContent="—";$("video-profile").textContent="—";$("video-modified").textContent="—";$("analysis-status").textContent="Belum dianalisis";$("analysis-status").className="analysis-state";$("analysis-list").innerHTML="<li>Muat video untuk membaca metadata.</li>";$("analysis-detail").textContent="Belum ada analisis.";$("check-duplicate").textContent="Belum dicek";$("check-health").textContent="Belum dicek";$("check-metadata").textContent="Belum dicek";$("check-size").textContent="—";$("check-type").textContent="—";$("tag-list").innerHTML='<span class="mut">Belum ada tag</span>';$("note-text").textContent="Belum ada catatan.";$("video-pills").innerHTML="";$("sum-count").textContent="0";$("sum-size").textContent="0 B";$("sum-path").textContent="—";const v=$("video-player");v.pause();v.removeAttribute("src");v.load();v.hidden=true;$("video-empty-title").textContent="Belum ada video yang dipilih";$("mini-thumb").style.backgroundImage="";$("mini-thumb").innerHTML="<span>Preview</span>";
}
function updateVideoPills(r){const ext=(r.extension||"").toUpperCase();const probe=r.probe||{};const dur=probe.duration?fmtDuration(probe.duration):"—";const date=r.modified_ms?new Date(Number(r.modified_ms)).toISOString().slice(0,10):"";const good=probe.ok?"✓ Good":"! Perlu cek";$("video-pills").innerHTML=[ext&&`<span class="blue">${esc(ext)}</span>`,date&&`<span class="green">${esc(date)}</span>`,`<span class="${probe.ok?"good":"purple"}">${good}</span>`,`<span>${fmtBytes(r.size)}</span>`,`<span>${dur}</span>`].filter(Boolean).join("");}
function renderTags(){const a=state.current?.annotation||{tags:[],note:""};const tags=a.tags||[];$("tag-list").innerHTML=tags.length?tags.map((x,i)=>`<span class="${i===0?"purple":""}">${esc(x)}</span>`).join(""):'<span class="mut">Belum ada tag</span>';$("note-text").textContent=a.note||"Belum ada catatan.";}
function setAnalysis(r){const probe=r.probe||{},v=probe.video||{},a=probe.audio||{};const ok=!!probe.ok;$("video-resolution").textContent=v.width?`${v.width} × ${v.height}`:"—";$("video-codec").textContent=v.codec||"—";$("audio-codec").textContent=a.codec||"Tidak ada";$("video-fps").textContent=v.fps?`${v.fps} fps`:"—";$("video-aspect").textContent=v.aspect||"—";$("video-profile").textContent=v.profile||"—";$("video-duration").textContent=probe.duration?fmtDuration(probe.duration):"—";$("check-health").textContent=ok?"Normal":"Perlu diperiksa";$("check-metadata").textContent=(v.width&&v.height&&v.codec)?"Terbaca":"Terbatas";$("check-size").textContent=fmtBytes(r.size);$("check-type").textContent=(r.extension||"VIDEO").toUpperCase();$("analysis-status").textContent=ok?"✓ File normal":"! Metadata / stream perlu diperiksa";$("analysis-status").className=`analysis-state ${ok?"ok":"bad"}`;const items=ok?["Stream video dapat dibaca",v.codec?`Codec ${v.codec}${v.profile&&v.profile!=="—"?` (${v.profile})`:""}`:"Codec tidak tersedia",a.codec?`Audio ${a.codec}`:"Tanpa stream audio"]:[probe.error||"ffprobe tidak dapat membaca file","Gunakan player eksternal untuk pembuktian tambahan","Pastikan ffprobe tersedia di paket aplikasi"];$("analysis-list").innerHTML=items.map(x=>`<li>${esc(x)}</li>`).join("");$("analysis-detail").textContent=ok?`Durasi ${fmtDuration(probe.duration)} • ${v.width||"?"}×${v.height||"?"} • ${v.codec||"?"} • ${a.codec||"tanpa audio"}.`:`Probe gagal: ${probe.error||"tidak ada detail"}.`;
}
function showVideoInPlayer(path){
  const player=$("video-player"),empty=document.querySelector(".video-empty"),fallback=$("video-fallback-actions"),status=$("player-status");
  const src=toAssetUrl(path);
  player.hidden=false;empty.hidden=true;fallback.hidden=true;status.textContent="Memuat player internal…";
  player.onerror=()=>{
    player.hidden=true;empty.hidden=false;fallback.hidden=false;
    $("video-empty-title").textContent="Format/codec tidak bisa diputar di WebView";
    $("video-empty-help").textContent="File tetap valid; gunakan Player Windows untuk codec yang tidak didukung.";
    status.textContent="Player internal tidak mendukung stream ini.";
  };
  player.onloadedmetadata=()=>{$("video-duration").textContent=fmtDuration(player.duration);updateThumbnail(player);status.textContent=`Siap diputar • ${fmtDuration(player.duration)}`;};
  player.onplay=()=>status.textContent="Sedang diputar";
  player.onpause=()=>{if(!player.ended)status.textContent="Dijeda";};
  player.src=src;player.load();
}
function updateThumbnail(player){setTimeout(()=>{try{if(!player.videoWidth||!player.videoHeight)return;const c=$("thumb-canvas"),w=320,h=Math.round(w*player.videoHeight/player.videoWidth);c.width=w;c.height=h;c.getContext("2d").drawImage(player,0,0,w,h);const url=c.toDataURL("image/jpeg",.78);$("mini-thumb").style.backgroundImage=`url("${url}")`;$("mini-thumb").innerHTML="";}catch{ /* canvas may be blocked by WebView file origin */}},180);}
$("video-play").onclick=()=>{const v=$("video-player");if(v.paused)v.play().catch(e=>toast("Player gagal: "+e.message,"bad"));else v.pause();};
$("video-mute").onclick=()=>{const v=$("video-player");v.muted=!v.muted;$("video-mute").textContent=v.muted?"🔇":"🔊";};
$("video-fullscreen").onclick=()=>{$("video-player").requestFullscreen?.().catch?.(()=>{});};
$("video-fallback-open").onclick=()=>videoAction("open");
async function loadVideo(path=$("video-path").value.trim()){
  if(!path)return toast("Pilih atau masukkan path video terlebih dahulu.","warn");
  try{const r=await api("POST","/api/video/inspect",{path}); if(!r.ok)throw new Error(r.error||"video tidak dapat dibaca"); state.current=r;$("video-path").value=r.path;$("video-path-label").textContent=r.path;$("crumb-file").textContent=r.name;$("video-title").textContent=r.name;$("video-name").textContent=r.name;$("video-size").textContent=fmtBytes(r.size);$("video-modified").textContent=fmtDate(r.modified_ms);updateVideoPills(r);setAnalysis(r);renderTags();showVideoInPlayer(r.path);$("video-empty-title").textContent=r.name;updateFolderSummary(r.path);switchView("dash");return r;}catch(e){toast("Video tidak dapat dimuat: "+e.message,"bad");return null;}}
function updateFolderSummary(path){const folder=dirname(path);const rows=state.videos.filter(v=>samePath(dirname(v.path),folder));const size=rows.reduce((a,v)=>a+(Number(v.size)||0),0);$("sum-count").textContent=rows.length||1;$("sum-size").textContent=fmtBytes(size||state.current?.size||0);$("sum-path").textContent=folder;}
function updateCurrentPath(newPath){if(!state.current)return;state.current.path=newPath;state.current.name=filename(newPath);$("video-path").value=newPath;$("crumb-file").textContent=state.current.name;$("video-title").textContent=state.current.name;}
async function selectVideo(path){$("video-path").value=path;await loadVideo(path);}
function currentRequired(){if(!state.current?.path){toast("Muat video terlebih dahulu.","warn");return false;}return true;}

async function videoAction(action){
  if(action==="load")return loadVideo(); if(!currentRequired())return; const path=state.current.path;
  try{
    if(action==="open"){const r=await api("POST","/api/video/open",{path});if(!r.ok)throw new Error(r.error||"gagal membuka player");toast("Video dibuka di aplikasi default.","ok");}
    else if(action==="folder"){const r=await api("POST","/api/video/folder",{path});if(!r.ok)throw new Error(r.error||"gagal membuka folder");}
    else if(action==="rename"){const v=await openDialog({title:"Rename video",message:"Nama file baru. Ekstensi akan dipertahankan jika tidak ditulis.",value:filename(path),placeholder:"nama-video"});if(!v)return;const r=await api("POST","/api/video/rename",{path,new_name:v.trim()});if(!r.ok)throw new Error(r.error||"rename gagal");updateCurrentPath(r.path);await loadVideo(r.path);await loadLibrary(state.root);toast("File berhasil di-rename.","ok");}
    else if(action==="move"){const v=await openDialog({title:"Pindahkan video",message:"Folder tujuan akan dibuat bila belum ada.",value:dirname(path),placeholder:"D:\\Videos\\Baru"});if(!v)return;const r=await api("POST","/api/video/move",{path,destination:v.trim()});if(!r.ok)throw new Error(r.error||"move gagal");updateCurrentPath(r.path);await loadVideo(r.path);await loadLibrary(state.root);toast(`Video dipindahkan (${r.mode||"terverifikasi"}).`,"ok");}
    else if(action==="delete"){const ok=await openDialog({title:"Karantina video",message:"File TIDAK dihapus permanen. File dipindahkan ke 99_To-Delete agar bisa dipulihkan.",kind:"confirm",okText:"Karantina"});if(ok===null)return;const r=await api("POST","/api/video/quarantine",{path});if(!r.ok)throw new Error(r.error||"karantina gagal");state.current=null;clearVideoUI();await loadLibrary(state.root);toast("Video dipindahkan ke 99_To-Delete.","ok");}
    else if(action==="tags"){const tags=await openDialog({title:"Edit tag",message:"Pisahkan tag dengan koma.",value:(state.current.annotation?.tags||[]).join(", "),placeholder:"liburan, keluarga, 2026"});if(tags===null)return;const next=tags.split(",").map(x=>x.trim()).filter(Boolean);const r=await api("POST","/api/video/annotation",{path,tags:next,note:state.current.annotation?.note||""});if(!r.ok)throw new Error(r.error||"tag gagal disimpan");state.current.annotation={tags:next,note:state.current.annotation?.note||""};renderTags();toast("Tag disimpan.","ok");}
    else if(action==="note"){const note=await openDialog({title:"Edit catatan",message:"Catatan disimpan lokal sebagai metadata aplikasi.",kind:"textarea",value:state.current.annotation?.note||"",placeholder:"Catatan…"});if(note===null)return;const r=await api("POST","/api/video/annotation",{path,tags:state.current.annotation?.tags||[],note});if(!r.ok)throw new Error(r.error||"catatan gagal disimpan");state.current.annotation={tags:state.current.annotation?.tags||[],note};renderTags();toast("Catatan disimpan.","ok");}
  }catch(e){toast("Aksi video gagal: "+e.message,"bad",5000);}
}
document.querySelectorAll("[data-video-action]").forEach(b=>b.addEventListener("click",()=>videoAction(b.dataset.videoAction)));$("video-path").addEventListener("keydown",e=>{if(e.key==="Enter")loadVideo();});
$("video-duplicate-check").onclick=async()=>{if(!currentRequired())return;showBusy($("video-duplicate-check"),true,"Mengecek…");try{const r=await api("POST","/api/video/duplicate-check",{path:state.current.path});if(!r.ok)throw new Error(r.error||"gagal");$("check-duplicate").textContent=r.duplicate?`Duplikat • grup ${r.group?.id??"?"}`:"Tidak ada duplikat exact";$("analysis-detail").textContent = r.duplicate ? `Video masuk grup duplikat exact ${r.group?.id??"?"} dengan ${r.group?.paths?.length||0} file.` : "Tidak ditemukan anggota lain dengan hash exact pada scan folder.";toast(r.duplicate?"Video terdeteksi sebagai duplikat exact.":"Tidak ada duplikat exact pada folder yang dicek.",r.duplicate?"warn":"ok");}catch(e){toast("Cek duplikat gagal: "+e.message,"bad");}finally{showBusy($("video-duplicate-check"),false);}};
[...document.querySelectorAll("[data-relation]")].forEach(b=>b.onclick=async()=>{const a=b.dataset.relation;if(a==="dups")switchView("dup");else{if(a==="all"){$("library-filter").value="";switchView("scan");await loadLibrary(state.root);}else if(state.current){const folder=dirname(state.current.path);switchView("scan");await loadLibrary(state.root);$("library-filter").value=folder.split(/[\\/]/).pop();renderLibrary();}}});

$("scan-go").onclick=async()=>{const folder=$("scan-folder").value.trim();if(!folder)return toast("Isi folder scan.","warn");setRoot(folder);showBusy($("scan-go"),true,"Scanning…");try{const r=await api("POST","/api/scan",{folder});$("scan-out").textContent=JSON.stringify(r,null,2);await loadLibrary(folder);await stats();toast(r.ok?"Scan selesai.":(r.error||"Scan gagal"),r.ok?"ok":"bad");}catch(e){$("scan-out").textContent=e.message;toast("Scan gagal: "+e.message,"bad");}finally{showBusy($("scan-go"),false);}};
$("quick-scan-go").onclick=async()=>{$("scan-folder").value=$("quick-scan-folder").value;$("scan-go").click();};

// ---------------- Foto workspace ----------------
async function loadPhotos(root=state.root){
  root=String(root||"").trim();
  if(!root){toast("Pilih folder foto terlebih dahulu.","warn");return null;}
  $("photo-grid").innerHTML='<div class="empty-state">Membaca foto dari disk…</div>';
  try{
    const r=await api("GET","/api/videos/list?root="+encodeURIComponent(root)+"&kind=images&limit=5000");
    if(!r.ok)throw new Error(r.error||"folder foto tidak bisa dibaca");
    state.photos=r.videos||[];state.lastPhotos=r;
    $("photo-total").textContent=Number(r.video_total??state.photos.length);
    $("photo-files").textContent=Number(r.file_total??state.photos.length);
    $("photo-junk").textContent=Number(r.junk_count||0);
    $("photo-size").textContent=fmtBytes(state.photos.reduce((a,x)=>a+(Number(x.size)||0),0));
    renderPhotos();$("nav-photos").textContent=state.photos.length;
    return r;
  }catch(e){$("photo-grid").innerHTML=`<div class="empty-state">Gagal: ${esc(e.message)}</div>`;toast("Gallery gagal dimuat: "+e.message,"bad");return null;}
}
function renderPhotos(){
  const q=($("photo-filter")?.value||"").trim().toLowerCase();
  const rows=state.photos.filter(p=>!q||`${p.rel} ${p.path}`.toLowerCase().includes(q));
  $("photo-caption").textContent=`${rows.length} tampil • ${state.root||"—"}${state.lastPhotos?.truncated?" • hasil dibatasi 5000":""}`;
  $("photo-grid").innerHTML=rows.length?rows.map(p=>`<button class="photo-tile" data-photo-path="${esc(p.path)}"><img src="${toAssetUrl(p.path)}" alt="" loading="lazy"><span class="photo-tile-meta"><b>${esc(filename(p.path))}</b><small>${esc(p.rel||"")} • ${fmtBytes(p.size)}</small></span></button>`).join(""):'<div class="empty-state">Tidak ada foto yang cocok.</div>';
  $("photo-grid").querySelectorAll("[data-photo-path]").forEach(b=>b.onclick=()=>selectPhoto(b.dataset.photoPath));
}
function setPhotoZoom(value){
  const img=$("photo-image"); if(!img.src)return;
  const zoom=Math.max(25,Math.min(400,Number(value)||100));
  img.style.width=zoom===100?"auto":`${zoom}%`;img.style.height="auto";$("photo-zoom-label").textContent=`${zoom}%`;state.photoZoom=zoom;
}
function selectPhoto(path){
  const p=state.photos.find(x=>samePath(x.path,path))||{path,rel:path,size:0};state.currentPhoto=p;
  const img=$("photo-image"),empty=$("photo-empty");
  img.onload=()=>{
    img.hidden=false;empty.hidden=true;$("photo-meta-dim").textContent=`${img.naturalWidth} × ${img.naturalHeight}`;setPhotoZoom(100);
  };
  img.onerror=()=>{img.hidden=true;empty.hidden=false;$("photo-empty").querySelector("b").textContent="Format foto tidak didukung WebView";$("photo-empty").querySelector("span").textContent="Gunakan tombol Buka untuk aplikasi foto Windows.";};
  img.src=toAssetUrl(path);
  $("photo-view-name").textContent=filename(path);$("photo-meta-name").textContent=filename(path);$("photo-meta-path").textContent=path;$("photo-meta-size").textContent=fmtBytes(p.size);$("photo-meta-modified").textContent="—";$("photo-meta-type").textContent=(filename(path).split(".").pop()||"—").toUpperCase();
  if(p.path){api("POST","/api/file/info",{path:p.path}).then(r=>{$("photo-meta-modified").textContent=fmtDate(r.modified_ms);}).catch(()=>{});}
}
$("photo-filter").oninput=renderPhotos;
$("photo-folder-browse").onclick=async()=>chooseFolder("photo-folder");
$("photo-scan").onclick=async()=>{const folder=$("photo-folder").value.trim()||state.root;if(!folder)return toast("Pilih folder foto.","warn");setRoot(folder);await loadPhotos(folder);};
$("photo-refresh").onclick=()=>loadPhotos(state.root);
$("photo-browse").onclick=async()=>{const p=await chooseImage();if(p){const folder=dirname(p);setRoot(folder);await loadPhotos(folder);selectPhoto(p);}};
$("photo-fit").onclick=()=>{const img=$("photo-image");img.style.width="auto";img.style.height="auto";img.style.maxWidth="100%";img.style.maxHeight="100%";$("photo-zoom-label").textContent="Fit";};
$("photo-zoom-in").onclick=()=>setPhotoZoom((state.photoZoom||100)+25);
$("photo-zoom-out").onclick=()=>setPhotoZoom((state.photoZoom||100)-25);
$("photo-open-external").onclick=async()=>{if(!state.currentPhoto)return toast("Pilih foto dahulu.","warn");try{const r=await api("POST","/api/video/open",{path:state.currentPhoto.path});if(!r.ok)throw new Error(r.error||"gagal membuka foto");}catch(e){toast("Foto tidak bisa dibuka: "+e.message,"bad");}};

let lastGroups=[];
$("dup-go").onclick=async()=>{const folder=$("dup-folder").value.trim();if(!folder)return toast("Pilih folder duplikat.","warn");showBusy($("dup-go"),true,"Hashing…");$("dup-list").innerHTML='<div class="empty-state">Menghitung hash bertahap…</div>';try{const r=await api("POST","/api/duplicates",{folder,minSize:Number($("dup-min").value)||1});if(!r.ok)throw new Error(r.error||r.raw||"scan duplikat gagal");lastGroups=r.groups||[];renderDupGroups(folder);await stats();}catch(e){$("dup-list").innerHTML=`<div class="empty-state">Gagal: ${esc(e.message)}</div>`;toast("Duplikat gagal: "+e.message,"bad");}finally{showBusy($("dup-go"),false);}};
function renderDupGroups(folder){$("dup-list").innerHTML=lastGroups.length?lastGroups.map(g=>`<div class="dup"><div><b>Grup ${esc(g.id)}</b> · ${fmtBytes(g.size)} · <code>${esc(String(g.sha256||"").slice(0,20))}…</code></div><div class="paths">${(g.paths||[]).map(p=>`<span class="path-chip">${esc(p)}</span>`).join("")}</div><div class="row" style="margin-top:9px"><button class="btn ghost sm" data-dup-action="move" data-g="${esc(g.id)}">✓ Simpan & Karantina</button><button class="btn ghost sm" data-dup-action="propose" data-g="${esc(g.id)}">◔ Buat Proposal</button></div></div>`).join(""):'<div class="empty-state">Tidak ada duplikat exact. Semua hash unik pada scan ini.</div>';
  $("dup-list").querySelectorAll("[data-dup-action]").forEach(b=>b.onclick=()=>dupAction(b.dataset.dupAction,Number(b.dataset.g),folder));
}
async function chooseKeep(paths){return await openDialog({title:"Pilih file canonical",message:"Pilih satu file yang dipertahankan. File lain akan menjadi kandidat karantina.",kind:"select",options:paths.map(p=>({value:p,label:p})),okText:"Pilih"});}
async function dupAction(action,id,folder){
  const g=lastGroups.find(x=>Number(x.id)===Number(id));
  if(!g)return;
  const keep=await chooseKeep(g.paths||[]);
  if(!keep)return;
  const to=await openDialog({
    title:action==="move"?"Folder karantina":"Tujuan proposal",
    message:"Folder tujuan akan dibuat/digunakan sesuai engine core.",
    value:folder+"\\__duplikat__",
    placeholder:"D:\\Data\\__duplikat__"
  });
  if(!to)return;
  try{
    if(action==="move"){
      const ok=await openDialog({
        title:"Konfirmasi pemindahan",
        message:`Pertahankan:\n${keep}\n\nFile lainnya dalam grup akan DIPINDAH ke:\n${to}`,
        kind:"confirm",
        okText:"Pindahkan"
      });
      if(ok===null)return;
      const r=await api("POST","/api/move-approved",{group:id,keep,to});
      if(!r.ok)throw new Error(r.error||"move gagal");
      toast(`Selesai: ${(r.moved||[]).length} file dipindah.` ,"ok");
    }else{
      const r=await api("POST","/api/proposals/propose",{group:id,keep,to,reasons:"Exact duplicate berdasarkan SHA-256."});
      if(!r.ok)throw new Error(r.error||"proposal gagal");
      toast(`Proposal ${r.batch} dibuat. Tidak ada file yang dipindah.` ,"ok");
    }
    await $("dup-go").click();
    await loadProps();
    await stats();
    loadActivity();
  }catch(e){toast("Aksi duplikat gagal: "+e.message,"bad");}
}

let docs=[];
async function loadDocs(silent=false){try{const r=await api("GET","/api/docs?limit=500");if(!r.ok){docs=[];$("nav-docs").textContent="0";if(!silent)$("doc-rows").innerHTML=`<tr><td colspan="5" class="mut">${esc(r.error||"Belum ada doc_index")}</td></tr>`;return;}docs=r.docs||[];$("nav-docs").textContent=docs.length;renderDocs();}catch(e){if(!silent)$("doc-rows").innerHTML=`<tr><td colspan="5" class="mut">Gagal: ${esc(e.message)}</td></tr>`;}}
function renderDocs(){const q=($("doc-q").value||"").toLowerCase();const rows=docs.filter(d=>!q||`${d.kategori} ${d.saran_nama} ${d.ringkasan} ${d.path}`.toLowerCase().includes(q)).slice(0,500);$("doc-rows").innerHTML=rows.length?rows.map(d=>`<tr><td><span class="tag">${esc(d.kategori||"—")}</span></td><td>${Number(d.confidence||0).toFixed(2)}</td><td>${esc(d.saran_nama||"—")}</td><td>${esc(d.ringkasan||"—")}</td><td class="mut">${esc(d.path||"")}</td></tr>`).join(""):'<tr><td colspan="5" class="mut">Tidak ada hasil.</td></tr>';}
$("doc-reload").onclick=()=>loadDocs();$("doc-q").oninput=renderDocs;

$("org-files").onclick=async()=>{const kind=$("org-kind").value,folder=$("org-folder").value.trim();if(!folder)return toast("Isi folder organizer.","warn");$("org-sel").hidden=false;$("org-list").textContent="Membaca file…";try{const r=await api("GET","/api/videos/list?root="+encodeURIComponent(folder)+"&kind="+kind+"&limit=5000");if(!r.ok)throw new Error(r.error||"gagal");state.orgFiles=r.videos||[];state.orgSel=new Set(state.orgFiles.map(x=>x.path));$("org-count").textContent=`${state.orgSel.size}/${state.orgFiles.length}`;$("org-list").innerHTML=state.orgFiles.length?state.orgFiles.slice(0,1000).map(f=>`<label class="pick"><input type="checkbox" data-p="${esc(f.path)}" checked><span>${esc(f.rel||f.path)}</span><span>${fmtBytes(f.size)}</span></label>`).join(""):'Tidak ada media.';$("org-list").querySelectorAll("input[data-p]").forEach(c=>c.onchange=()=>{c.checked?state.orgSel.add(c.dataset.p):state.orgSel.delete(c.dataset.p);$("org-count").textContent=`${state.orgSel.size}/${state.orgFiles.length}`;});}catch(e){$("org-list").textContent="Gagal: "+e.message;}};
$("org-q").oninput=()=>{const q=$("org-q").value.toLowerCase();$("org-list").querySelectorAll("label.pick").forEach(x=>x.style.display=x.textContent.toLowerCase().includes(q)?"flex":"none");};$("org-all").onclick=()=>{state.orgFiles.forEach(f=>state.orgSel.add(f.path));$("org-list").querySelectorAll("input[data-p]").forEach(c=>c.checked=true);$("org-count").textContent=`${state.orgSel.size}/${state.orgFiles.length}`;};$("org-none").onclick=()=>{state.orgSel.clear();$("org-list").querySelectorAll("input[data-p]").forEach(c=>c.checked=false);$("org-count").textContent=`0/${state.orgFiles.length}`;};
$("org-go").onclick=async()=>{const kind=$("org-kind").value,folder=$("org-folder").value.trim();if(!folder)return toast("Isi folder organizer.","warn");const apply=$("org-apply").checked;const body={kind,folder,files:[...state.orgSel],dest:$("org-dest").value.trim(),content:$("org-content").value.split(/[;\r\n]+/).map(x=>x.trim()).filter(x=>x.includes("=>")),copy:$("org-copy").checked,dated:$("org-dated").checked,junk:$("org-junk").checked,prune:$("org-prune").checked,limit:Number($("org-limit").value)||0,apply};if(apply){const ok=await openDialog({title:"Terapkan organizer",message:`File akan dipindah sesuai rencana.\n\nFolder: ${folder}`,kind:"confirm",okText:"Terapkan"});if(ok===null)return;}showBusy($("org-go"),true,apply?"Menerapkan…":"Merencanakan…");try{const r=await api("POST","/api/organize",body);$("org-out").textContent=(r.output||r.error||JSON.stringify(r,null,2)).slice(-12000)+(r.report?`\n\nLaporan: ${r.report}`:"");state.lastOrgReport=r.report||"";$("org-dl").disabled=!state.lastOrgReport;toast(r.ok?(apply?"Organizer selesai.":"Rencana selesai."):(r.error||"Organizer gagal"),r.ok?"ok":"bad");if(apply)await loadLibrary(folder);await stats();loadActivity();}catch(e){toast("Organizer gagal: "+e.message,"bad");}finally{showBusy($("org-go"),false);}};
$("org-dl").onclick=async()=>{if(!state.lastOrgReport)return;const r=await api("GET","/api/reports/get?name="+encodeURIComponent(filename(state.lastOrgReport)));toast(r.ok?`Laporan disalin ke ${r.path}`:r.error||"Export gagal",r.ok?"ok":"bad");};

$("ai-go").onclick=async()=>{const folder=$("ai-folder").value.trim();if(!folder)return toast("Isi folder AI.","warn");const mode=$("ai-mode").value;const argv=[mode,folder];if($("dry").checked)argv.push("--dry-run");if(mode==="analyze"&&Number($("ai-limit").value)>0)argv.push("--limit",$("ai-limit").value);if(mode==="yolo-classify"){if(Number($("ai-limit").value)>0)argv.push("--limit",$("ai-limit").value);if(!$("dry").checked)argv.push("--apply");}if(mode==="karantina"&&!$("dry").checked){const ok=await openDialog({title:"Karantina duplicate",message:"Mode ini dapat MEMINDAH file. Dry-run sekarang OFF.",kind:"confirm",okText:"Jalankan"});if(ok===null)return;}showBusy($("ai-go"),true,"AI berjalan…");try{const r=await api("POST","/api/ai",{argv});$("ai-out").textContent=(r.output||r.error||JSON.stringify(r,null,2)).slice(-12000)+(r.report?`\n\nLaporan: ${r.report}`:"");toast(r.ok?"AI engine selesai.":r.error||"AI gagal",r.ok?"ok":"bad");await stats();await loadDocs();loadActivity();}catch(e){toast("AI engine gagal: "+e.message,"bad");}finally{showBusy($("ai-go"),false);}};

async function loadJobs(){try{const r=await api("GET","/api/jobs/list?limit=50");const jobs=r.jobs||[];$("job-list").innerHTML=jobs.length?jobs.map(j=>`<div class="job-item"><span class="tag">${esc(j.status)}</span><div class="grow2"><b>#${j.id} · ${esc(j.kind)}</b><small>${esc(j.payload||"")}</small></div><button class="btn ghost sm" data-j="pause" data-id="${j.id}">⏸</button><button class="btn ghost sm" data-j="resume" data-id="${j.id}">▶</button><button class="btn ghost sm" data-j="cancel" data-id="${j.id}">✕</button></div>`).join(""):'<div class="empty-state">Tidak ada job.</div>';$("job-list").querySelectorAll("[data-j]").forEach(b=>b.onclick=async()=>{const r=await api("POST","/api/jobs/"+b.dataset.j,{id:Number(b.dataset.id)});toast(r.ok?`Job ${b.dataset.j} selesai.`:r.error||"Gagal",r.ok?"ok":"bad");await loadJobs();await stats();});}catch(e){$("job-list").innerHTML=`<div class="empty-state">Gagal: ${esc(e.message)}</div>`;}}
$("job-add").onclick=async()=>{const payload=$("job-payload").value.trim();if(!payload)return toast("Isi payload JSON atau path job.","warn");try{const r=await api("POST","/api/jobs/enqueue",{kind:$("job-kind").value.trim(),payload});$("job-out").textContent=JSON.stringify(r,null,2);toast(r.ok?`Job #${r.id} ditambahkan.`:r.error||"Gagal",r.ok?"ok":"bad");await loadJobs();await stats();}catch(e){toast("Tambah job gagal: "+e.message,"bad");}};
$("job-claim").onclick=async()=>{try{const r=await api("POST","/api/jobs/claim",{});$("job-out").textContent=JSON.stringify(r,null,2);toast(r.ok?`Job #${r.id} diambil.`:"Tidak ada job yang bisa diambil.",r.ok?"ok":"warn");await loadJobs();}catch(e){toast(e.message,"bad");}};
$("job-run").onclick=async()=>{showBusy($("job-run"),true,"Menjalankan…");try{const r=await api("POST","/api/jobs/run",{});$("job-out").textContent=JSON.stringify(r,null,2);toast(r.ran?(r.ok?`Job #${r.id} selesai.`:`Job #${r.id} gagal.`):r.message||r.error||"Tidak ada job.",r.ran&&r.ok?"ok":r.ran?"bad":"warn");await loadJobs();await stats();loadActivity();}catch(e){toast("Worker gagal: "+e.message,"bad");}finally{showBusy($("job-run"),false);}};
$("job-reload").onclick=loadJobs;

async function loadDbState(){try{const s=await api("GET","/api/db-state");$("db-toggle").checked=!!s.enabled;$("db-state-label").textContent=s.enabled?"ON":"OFF";$("db-state-label").style.color=s.enabled?"var(--ok)":"var(--warn)";$("db-path-label").textContent=s.path||":memory:";}catch(e){$("db-path-label").textContent=e.message;}}
$("db-toggle").onchange=async()=>{const on=$("db-toggle").checked;const ok=await openDialog({title:on?"Aktifkan database":"Matikan database",message:on?"Hasil scan/index akan tersimpan secara permanen di SQLite.":"Mode efemeral: hasil tidak disimpan antar proses. Worker queue membutuhkan database ON.",kind:"confirm",okText:on?"Aktifkan":"Matikan"});if(ok===null){$("db-toggle").checked=!on;return;}const r=await api("POST","/api/db-state",{enabled:on});if(!r.ok)$("db-toggle").checked=!on;toast(r.ok?"Pengaturan database diperbarui.":r.error||"Gagal",r.ok?"ok":"bad");await loadDbState();await stats();};
$("db-reload").onclick=async()=>{await stats();await loadDbState();};
$("doctor-go").onclick=async()=>{$("doctor-out").innerHTML='<div class="mut">Memeriksa…</div>';try{const r=await api("GET","/api/doctor");$("doctor-out").innerHTML=(r.checks||[]).map(c=>`<div class="check ${esc(c.status)}"><b>[${esc(c.status)}]</b> ${esc(c.name)} <span class="mut">${esc(c.detail)}</span></div>`).join("")||'<div class="mut">Tidak ada hasil.</div>';}catch(e){$("doctor-out").innerHTML=`<div class="check FAIL"><b>[FAIL]</b> ${esc(e.message)}</div>`;}};
async function loadAudit(){try{const f=$("audit-q").value.trim(),r=await api("GET","/api/audit?limit=200"+(f?"&action="+encodeURIComponent(f):"")),rows=r.audit||[];$("audit-rows").innerHTML=rows.length?rows.map(a=>`<tr><td>#${a.id}</td><td>${esc(a.actor)}</td><td><span class="tag">${esc(a.action)}</span></td><td>${esc(a.result)}</td><td class="mut">${esc(a.src)}${a.dst?" → "+esc(a.dst):""}${a.detail?" · "+esc(a.detail):""}</td></tr>`).join(""):'<tr><td colspan="5" class="mut">Belum ada audit trail.</td></tr>';}catch(e){$("audit-rows").innerHTML=`<tr><td colspan="5" class="mut">Gagal: ${esc(e.message)}</td></tr>`;}}
$("audit-reload").onclick=loadAudit;$("audit-q").oninput=loadAudit;

async function loadProps(){try{const r=await api("GET","/api/proposals/list?status=pending"),ps=r.proposals||[],by={};ps.forEach(p=>(by[p.batch]??=[]).push(p));const batches=Object.keys(by);$("prop-list").innerHTML=batches.length?batches.map(batch=>{const items=by[batch];return `<div class="dup"><b>${esc(batch)}</b> · ${items.length} item<div class="paths">${items.map(p=>`<span class="path-chip">${esc(p.src)} → ${esc(p.dst)}<br><span class="why">${esc(p.reasons||"")}</span></span>`).join("")}</div><div class="row" style="margin-top:9px"><button class="btn ghost sm" data-pact="approve" data-batch="${esc(batch)}">✓ Setujui</button><button class="btn ghost sm" data-pact="preview" data-batch="${esc(batch)}">Pratinjau</button><button class="btn ghost sm" data-pact="reject" data-batch="${esc(batch)}">Tolak</button></div><pre id="prev-${esc(batch)}" class="log" hidden></pre></div>`}).join(""):'<div class="empty-state">Tidak ada proposal pending.</div>';$("prop-list").querySelectorAll("[data-pact]").forEach(b=>b.onclick=()=>proposalAction(b.dataset.pact,b.dataset.batch));}catch(e){$("prop-list").innerHTML=`<div class="empty-state">Gagal: ${esc(e.message)}</div>`;}}
async function proposalAction(action,batch){try{if(action==="preview"){const r=await api("GET","/api/proposals/preview?target="+encodeURIComponent(batch));const pre=$("prev-"+batch);pre.hidden=false;pre.textContent=JSON.stringify(r.proposals||r,null,2);return;}if(action==="approve"){const ok=await openDialog({title:`Setujui ${batch}`,message:"File dalam batch akan dipindah melalui core dengan verifikasi dan audit.",kind:"confirm",okText:"Setujui & Pindah"});if(ok===null)return;}const r=await api("POST","/api/proposals/"+action,{batch});if(!r.ok)throw new Error(r.error||"aksi gagal");toast(action==="approve"?`Batch ${batch} disetujui.`:`Batch ${batch} ditolak.`,"ok");await loadProps();await stats();loadActivity();}catch(e){toast("Proposal gagal: "+e.message,"bad");}}
$("prop-reload").onclick=loadProps;

async function loadActivity(){try{const r=await api("GET","/api/activity?limit=300"),items=r.items||[];$("act-rows").innerHTML=items.length?items.map(a=>`<tr><td class="nowrap">${esc(fmtDate(Date.parse(a.ts)))}</td><td><span class="tag">${esc(a.action)}</span></td><td class="mut">${esc(a.detail)}</td></tr>`).join(""):'<tr><td colspan="3" class="mut">Belum ada aktivitas.</td></tr>';}catch(e){$("act-rows").innerHTML=`<tr><td colspan="3" class="mut">Gagal: ${esc(e.message)}</td></tr>`;}}
$("act-reload").onclick=loadActivity;$("act-export").onclick=async()=>{const r=await api("GET","/api/activity/export");toast(r.ok?`Log diekspor ke ${r.path}`:r.error||"Export gagal",r.ok?"ok":"bad");};$("act-clear").onclick=async()=>{const ok=await openDialog({title:"Hapus log aktivitas",message:"Ini menghapus JSONL activity.log, tetapi TIDAK menghapus database.",kind:"confirm",okText:"Hapus Log"});if(ok===null)return;const r=await api("POST","/api/activity/clear",{});toast(r.ok?"Log aktivitas dihapus.":r.error||"Gagal",r.ok?"ok":"bad");loadActivity();};

ensureTabs();
const restoredView=state.tabs.find(t=>t.id===state.activeTabId)?.view||"dash";
switchView(restoredView,{fromTab:true});
if(state.root){setRoot(state.root);loadLibrary(state.root);}else clearVideoUI();
loadDocs(true);stats();loadActivity();loadJobs();loadDbState();loadAudit();loadProps();health();
setInterval(health,15000);setInterval(()=>{if($("v-db").classList.contains("on"))loadJobs();},5000);
