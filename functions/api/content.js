export async function onRequest(context) {
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
const m=d.video_url.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([A-Za-z0-9_-]{11})/);
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
}