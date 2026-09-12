from pathlib import Path

api = '''export async function onRequest(context) {
const {request,env}=context;
const json=(x,s=200)=>Response.json(x,{status:s});
try{
if(request.method==="GET"){
const settings=await env.DB.prepare("SELECT * FROM site_settings WHERE id=1 LIMIT 1").first();
const episodes=await env.DB.prepare("SELECT * FROM episodes ORDER BY season,episode_number,id").all();
const cast=await env.DB.prepare("SELECT * FROM cast ORDER BY id").all();
const stories=await env.DB.prepare("SELECT * FROM stories ORDER BY created_at DESC,id DESC").all();
const messages=await env.DB.prepare("SELECT * FROM messages ORDER BY created_at DESC,id DESC").all();
return json({settings,episodes:episodes.results||[],cast:cast.results||[],stories:stories.results||[],messages:messages.results||[]});
}
if(request.method!=="POST")return json({error:"Method not allowed"},405);
const d=await request.json();

if(d.action==="saveHero"){
await env.DB.prepare(`INSERT INTO site_settings(id,site_name,hero_title,hero_subtitle,primary_color,secondary_color,font_family)
VALUES(1,'BACK TO X',?,?,?,?,?)
ON CONFLICT(id) DO UPDATE SET hero_title=excluded.hero_title,hero_subtitle=excluded.hero_subtitle,
primary_color=excluded.primary_color,secondary_color=excluded.secondary_color,font_family=excluded.font_family`)
.bind(d.hero_title||"",d.hero_subtitle||"",d.primary_color||"",d.secondary_color||"",d.font_family||"").run();
return json({success:true});
}

if(d.action==="addEpisode"||d.action==="updateEpisode"){
let image=d.image_url||"";
if(!image&&d.video_url){
const m=d.video_url.match(/(?:youtube\\.com\\/watch\\?v=|youtu\\.be\\/|youtube\\.com\\/embed\\/)([A-Za-z0-9_-]{11})/);
if(m)image=`https://img.youtube.com/vi/${m[1]}/maxresdefault.jpg`;
}
if(d.action==="addEpisode"){
const r=await env.DB.prepare(`INSERT INTO episodes(season,episode_number,title,description,video_url,image_url,published) VALUES(?,?,?,?,?,?,?)`)
.bind(+d.season||1,+d.episode_number||1,d.title||"",d.description||"",d.video_url||"",image,d.published===false?0:1).run();
return json({success:true,id:r.meta.last_row_id});
}
await env.DB.prepare(`UPDATE episodes SET season=?,episode_number=?,title=?,description=?,video_url=?,image_url=?,published=? WHERE id=?`)
.bind(+d.season||1,+d.episode_number||1,d.title||"",d.description||"",d.video_url||"",image,d.published?1:0,+d.id).run();
return json({success:true});
}

if(d.action==="deleteEpisode"){await env.DB.prepare("DELETE FROM episodes WHERE id=?").bind(+d.id).run();return json({success:true});}
if(d.action==="toggleEpisode"){await env.DB.prepare("UPDATE episodes SET published=? WHERE id=?").bind(d.published?1:0,+d.id).run();return json({success:true});}

if(d.action==="addCast"){
const r=await env.DB.prepare("INSERT INTO cast(name,role,bio,image_url,season,active) VALUES(?,?,?,?,?,1)")
.bind(d.name||"",d.role||"",d.bio||"",d.image_url||"",+d.season||1).run();
return json({success:true,id:r.meta.last_row_id});
}
if(d.action==="updateCast"){
await env.DB.prepare("UPDATE cast SET name=?,role=?,bio=?,image_url=?,season=?,active=? WHERE id=?")
.bind(d.name||"",d.role||"",d.bio||"",d.image_url||"",+d.season||1,d.active?1:0,+d.id).run();return json({success:true});
}
if(d.action==="deleteCast"){await env.DB.prepare("DELETE FROM cast WHERE id=?").bind(+d.id).run();return json({success:true});}

if(d.action==="addStory"){
const r=await env.DB.prepare("INSERT INTO stories(author_name,story,image_url,status) VALUES(?,?,?,?)")
.bind(d.author_name||"",d.story||"",d.image_url||"",d.status||"approved").run();return json({success:true,id:r.meta.last_row_id});
}
if(d.action==="updateStory"){
await env.DB.prepare("UPDATE stories SET author_name=?,story=?,image_url=?,status=? WHERE id=?")
.bind(d.author_name||"",d.story||"",d.image_url||"",d.status||"pending",+d.id).run();return json({success:true});
}
if(d.action==="deleteStory"){await env.DB.prepare("DELETE FROM stories WHERE id=?").bind(+d.id).run();return json({success:true});}

if(d.action==="addMessage"){
const r=await env.DB.prepare("INSERT INTO messages(message,active) VALUES(?,1)").bind(d.message||"").run();return json({success:true,id:r.meta.last_row_id});
}
if(d.action==="updateMessage"){
await env.DB.prepare("UPDATE messages SET message=?,active=? WHERE id=?").bind(d.message||"",d.active?1:0,+d.id).run();return json({success:true});
}
if(d.action==="deleteMessage"){await env.DB.prepare("DELETE FROM messages WHERE id=?").bind(+d.id).run();return json({success:true});}

return json({error:"Unknown action"},400);
}catch(e){return json({error:e.message||"Server error"},500);}
}'''

admin = '''<!doctype html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>BACK TO X ADMIN</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#080808;color:#eee;font-family:Arial,sans-serif}
header{background:#0d0d0d;border-bottom:1px solid #292929;padding:18px 22px;position:sticky;top:0;z-index:5;display:flex;justify-content:space-between}
.logo{font-weight:900;letter-spacing:3px}.ok{color:#75e6a0;font-size:12px}
main{max-width:1200px;margin:auto;padding:20px 14px 60px}.box{background:#111;border:1px solid #292929;border-radius:18px;padding:20px;margin-bottom:16px}
h2{margin:0 0 16px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.full{grid-column:1/-1}
input,textarea,select{width:100%;background:#080808;color:#fff;border:1px solid #333;border-radius:9px;padding:12px}
textarea{min-height:90px}button{background:#4A102A;color:#fff;border:1px solid #713452;border-radius:9px;padding:10px 15px;font-weight:bold}
button.gray{background:#222;border-color:#444}button.red{background:#551b1b;border-color:#853333}
.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}.list{display:grid;gap:9px;margin-top:16px}
.item{background:#090909;border:1px solid #292929;border-radius:12px;padding:13px}.muted{color:#999;font-size:12px}
.login{max-width:400px;margin:100px auto}.hide{display:none!important}
@media(max-width:650px){.grid{grid-template-columns:1fr}.full{grid-column:auto}}
</style></head>
<body>

<div id="login" class="box login">
<h2>BACK TO X — ADMIN</h2>
<input id="pass" type="password" placeholder="Admin Password">
<div class="actions"><button onclick="login()">LOGIN</button></div>
<div id="msg"></div>
</div>

<div id="app" class="hide">
<header><div class="logo">BACK TO X</div><div id="state" class="ok">CONNECTED</div></header>
<main>

<div class="box"><h2>HERO & BRAND</h2>
<div class="grid">
<input id="heroTitle" class="full" placeholder="Hero title">
<textarea id="heroSubtitle" class="full" placeholder="Hero subtitle"></textarea>
<input id="primary" placeholder="Primary color">
<input id="secondary" placeholder="Secondary color">
<input id="font" class="full" placeholder="Font family">
</div><div class="actions"><button onclick="saveHero()">SAVE HERO</button></div></div>

<div class="box"><h2>EPISODES</h2>
<div class="grid">
<input id="eid" type="hidden"><input id="season" type="number" value="1" placeholder="Season">
<input id="number" type="number" value="1" placeholder="Episode number">
<input id="title" class="full" placeholder="Episode title">
<textarea id="desc" class="full" placeholder="Description"></textarea>
<input id="video" class="full" placeholder="YouTube URL or MP4 URL">
<input id="image" class="full" placeholder="Image URL (optional)">
</div>
<div class="actions"><button onclick="saveEpisode()">SAVE EPISODE</button><button class="gray" onclick="newEpisode()">NEW</button></div>
<div id="episodeList" class="list"></div></div>

<div class="box"><h2>CAST</h2>
<div class="grid">
<input id="cid" type="hidden"><input id="cname" placeholder="Name"><input id="crole" placeholder="Role">
<textarea id="cbio" class="full" placeholder="Bio"></textarea><input id="cimage" class="full" placeholder="Image URL">
<input id="cseason" type="number" value="1" placeholder="Season">
</div><div class="actions"><button onclick="saveCast()">SAVE CAST</button><button class="gray" onclick="newCast()">NEW</button></div>
<div id="castList" class="list"></div></div>

<div class="box"><h2>X WALL / STORIES</h2>
<div class="grid">
<input id="sid" type="hidden"><input id="author" placeholder="Author">
<textarea id="story" class="full" placeholder="Story"></textarea><input id="simage" placeholder="Image URL">
<select id="sstatus"><option>approved</option><option>pending</option><option>rejected</option></select>
</div><div class="actions"><button onclick="saveStory()">SAVE STORY</button><button class="gray" onclick="newStory()">NEW</button></div>
<div id="storyList" class="list"></div></div>

<div class="box"><h2>MESSAGES</h2>
<textarea id="message" placeholder="Message"></textarea><input id="mid" type="hidden">
<div class="actions"><button onclick="saveMessage()">SAVE MESSAGE</button><button class="gray" onclick="newMessage()">NEW</button></div>
<div id="messageList" class="list"></div></div>

</main></div>

<script>
const API="/api/content";let D={};
const esc=x=>String(x??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;");

async function login(){
const r=await fetch("/api/admin",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:"login",password:pass.value})});
const x=await r.json();if(x.success){login.classList.add("hide");app.classList.remove("hide");load()}else msg.textContent=x.error||"Login failed";
}
async function post(x){const r=await fetch(API,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(x)});return r.json()}
async function load(){
const r=await fetch(API);D=await r.json();state.textContent="CLOUDFLARE D1 — CONNECTED";
const s=D.settings||{};heroTitle.value=s.hero_title||"";heroSubtitle.value=s.hero_subtitle||"";primary.value=s.primary_color||"";secondary.value=s.secondary_color||"";font.value=s.font_family||"";
renderEpisodes();renderCast();renderStories();renderMessages();
}
async function saveHero(){let r=await post({action:"saveHero",hero_title:heroTitle.value,hero_subtitle:heroSubtitle.value,primary_color:primary.value,secondary_color:secondary.value,font_family:font.value});alert(r.success?"Saved":"Error: "+r.error);load()}

function newEpisode(){eid.value="";season.value=1;number.value=1;title.value="";desc.value="";video.value="";image.value=""}
async function saveEpisode(){let r=await post({action:eid.value?"updateEpisode":"addEpisode",id:eid.value,season:season.value,episode_number:number.value,title:title.value,description:desc.value,video_url:video.value,image_url:image.value,published:true});if(r.success){alert("Episode saved");newEpisode();load()}else alert(r.error)}
function renderEpisodes(){episodeList.innerHTML=(D.episodes||[]).map(e=>`<div class="item"><b>S${e.season} · E${e.episode_number} — ${esc(e.title)}</b><div class="muted">${e.published?"PUBLISHED":"HIDDEN"}</div><div class="actions"><button onclick="editEpisode(${e.id})">EDIT</button><button class="gray" onclick="toggleEpisode(${e.id},${e.published?0:1})">${e.published?"HIDE":"PUBLISH"}</button><button class="red" onclick="deleteEpisode(${e.id})">DELETE</button></div></div>`).join("")}
function editEpisode(id){let e=D.episodes.find(x=>x.id===id);eid.value=e.id;season.value=e.season;number.value=e.episode_number;title.value=e.title||"";desc.value=e.description||"";video.value=e.video_url||"";image.value=e.image_url||"";scrollTo({top:0,behavior:"smooth"})}
async function deleteEpisode(id){if(confirm("DELETE EPISODE?")){await post({action:"deleteEpisode",id});load()}}
async function toggleEpisode(id,published){await post({action:"toggleEpisode",id,published:!!published});load()}

function newCast(){cid.value="";cname.value="";crole.value="";cbio.value="";cimage.value="";cseason.value=1}
async function saveCast(){let r=await post({action:cid.value?"updateCast":"addCast",id:cid.value,name:cname.value,role:crole.value,bio:cbio.value,image_url:cimage.value,season:cseason.value,active:true});if(r.success){alert("Cast saved");newCast();load()}else alert(r.error)}
function renderCast(){castList.innerHTML=(D.cast||[]).map(c=>`<div class="item"><b>${esc(c.name)}</b><div class="muted">${esc(c.role)}</div><div class="actions"><button onclick="editCast(${c.id})">EDIT</button><button class="red" onclick="deleteCast(${c.id})">DELETE</button></div></div>`).join("")}
function editCast(id){let c=D.cast.find(x=>x.id===id);cid.value=c.id;cname.value=c.name||"";crole.value=c.role||"";cbio.value=c.bio||"";cimage.value=c.image_url||"";cseason.value=c.season||1}
async function deleteCast(id){if(confirm("DELETE CAST MEMBER?")){await post({action:"deleteCast",id});load()}}

function newStory(){sid.value="";author.value="";story.value="";simage.value="";sstatus.value="approved"}
async function saveStory(){let r=await post({action:sid.value?"updateStory":"addStory",id:sid.value,author_name:author.value,story:story.value,image_url:simage.value,status:sstatus.value});if(r.success){alert("Story saved");newStory();load()}else alert(r.error)}
function renderStories(){storyList.innerHTML=(D.stories||[]).map(s=>`<div class="item"><b>${esc(s.author_name)}</b><div class="muted">${esc(s.status)}</div><p>${esc(s.story)}</p><div class="actions"><button onclick="editStory(${s.id})">EDIT</button><button class="red" onclick="deleteStory(${s.id})">DELETE</button></div></div>`).join("")}
function editStory(id){let s=D.stories.find(x=>x.id===id);sid.value=s.id;author.value=s.author_name||"";story.value=s.story||"";simage.value=s.image_url||"";sstatus.value=s.status||"pending"}
async function deleteStory(id){if(confirm("DELETE STORY?")){await post({action:"deleteStory",id});load()}}

function newMessage(){mid.value="";message.value=""}
async function saveMessage(){let r=await post({action:mid.value?"updateMessage":"addMessage",id:mid.value,message:message.value,active:true});if(r.success){alert("Message saved");newMessage();load()}else alert(r.error)}
function renderMessages(){messageList.innerHTML=(D.messages||[]).map(m=>`<div class="item"><b>${esc(m.message)}</b><div class="actions"><button onclick="editMessage(${m.id})">EDIT</button><button class="red" onclick="deleteMessage(${m.id})">DELETE</button></div></div>`).join("")}
function editMessage(id){let m=D.messages.find(x=>x.id===id);mid.value=m.id;message.value=m.message||""}
async function deleteMessage(id){if(confirm("DELETE MESSAGE?")){await post({action:"deleteMessage",id});load()}}
</script></body></html>'''

Path("functions/api/content.js").write_text(api)
Path("public/admin").mkdir(parents=True,exist_ok=True)
Path("public/admin/index.html").write_text(admin)
print("ADMIN V2 CREATED")
