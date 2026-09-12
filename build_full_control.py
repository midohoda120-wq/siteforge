from pathlib import Path

ROOT = Path.home() / "website-app"
INDEX = ROOT / "index.html"
CONTENT = ROOT / "functions/api/content.js"
ADMIN = ROOT / "public/admin/index.html"

# -----------------------------
# CLOUDFLARE CONTENT API
# -----------------------------
CONTENT.parent.mkdir(parents=True, exist_ok=True)

CONTENT.write_text(r'''export async function onRequest(context) {
  const { request, env } = context;
  const json = (data, status = 200) =>
    Response.json(data, { status });

  try {
    if (!env.DB) return json({ error: "D1 binding DB is missing" }, 500);

    // Ensure flexible CMS tables exist.
    await env.DB.batch([
      env.DB.prepare(`CREATE TABLE IF NOT EXISTS site_content (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        section TEXT NOT NULL,
        content_key TEXT NOT NULL,
        content_value TEXT DEFAULT '',
        content_type TEXT DEFAULT 'text',
        sort_order INTEGER DEFAULT 0,
        active INTEGER DEFAULT 1,
        UNIQUE(section, content_key)
      )`),
      env.DB.prepare(`CREATE TABLE IF NOT EXISTS site_links (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        label TEXT,
        url TEXT,
        location TEXT DEFAULT 'social',
        sort_order INTEGER DEFAULT 0,
        active INTEGER DEFAULT 1
      )`),
      env.DB.prepare(`CREATE TABLE IF NOT EXISTS site_media (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        url TEXT,
        media_type TEXT DEFAULT 'image',
        section TEXT,
        sort_order INTEGER DEFAULT 0,
        active INTEGER DEFAULT 1
      )`),
      env.DB.prepare(`CREATE TABLE IF NOT EXISTS vote_options (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        choice_key TEXT UNIQUE NOT NULL,
        label TEXT,
        title TEXT,
        description TEXT,
        message_title TEXT,
        message_text TEXT,
        active INTEGER DEFAULT 1,
        sort_order INTEGER DEFAULT 0
      )`),
      env.DB.prepare(`CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT,
        story TEXT,
        status TEXT DEFAULT 'pending',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )`)
    ]);

    if (request.method === "GET") {
      const [
        settings,
        episodes,
        cast,
        stories,
        messages,
        content,
        links,
        media,
        voteOptions,
        applications,
        votes
      ] = await Promise.all([
        env.DB.prepare("SELECT * FROM site_settings WHERE id=1 LIMIT 1").first(),
        env.DB.prepare("SELECT * FROM episodes ORDER BY season,episode_number,id").all(),
        env.DB.prepare("SELECT * FROM cast ORDER BY season,id").all(),
        env.DB.prepare("SELECT * FROM stories ORDER BY created_at DESC,id DESC").all(),
        env.DB.prepare("SELECT * FROM messages ORDER BY created_at DESC,id DESC").all(),
        env.DB.prepare("SELECT * FROM site_content ORDER BY section,sort_order,id").all(),
        env.DB.prepare("SELECT * FROM site_links ORDER BY location,sort_order,id").all(),
        env.DB.prepare("SELECT * FROM site_media ORDER BY section,sort_order,id").all(),
        env.DB.prepare("SELECT * FROM vote_options ORDER BY sort_order,id").all(),
        env.DB.prepare("SELECT * FROM applications ORDER BY created_at DESC,id DESC").all(),
        env.DB.prepare("SELECT choice,COUNT(*) AS count FROM votes GROUP BY choice").all()
      ]);

      return json({
        settings,
        episodes: episodes.results || [],
        cast: cast.results || [],
        stories: stories.results || [],
        messages: messages.results || [],
        content: content.results || [],
        links: links.results || [],
        media: media.results || [],
        vote_options: voteOptions.results || [],
        applications: applications.results || [],
        vote_counts: votes.results || []
      });
    }

    if (request.method !== "POST")
      return json({ error: "Method not allowed" }, 405);

    const d = await request.json();

    // HERO / BRAND
    if (d.action === "saveHero") {
      await env.DB.prepare(`
        INSERT INTO site_settings
        (id,site_name,hero_title,hero_subtitle,primary_color,secondary_color,font_family)
        VALUES(1,'BACK TO X',?,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET
        hero_title=excluded.hero_title,
        hero_subtitle=excluded.hero_subtitle,
        primary_color=excluded.primary_color,
        secondary_color=excluded.secondary_color,
        font_family=excluded.font_family
      `).bind(
        d.hero_title || "",
        d.hero_subtitle || "",
        d.primary_color || "#4A102A",
        d.secondary_color || "#0B0B0B",
        d.font_family || "Montserrat, sans-serif"
      ).run();

      return json({ success: true });
    }

    // GENERIC SITE CONTENT
    if (d.action === "saveContent") {
      await env.DB.prepare(`
        INSERT INTO site_content
        (section,content_key,content_value,content_type,sort_order,active)
        VALUES(?,?,?,?,?,?)
        ON CONFLICT(section,content_key) DO UPDATE SET
        content_value=excluded.content_value,
        content_type=excluded.content_type,
        sort_order=excluded.sort_order,
        active=excluded.active
      `).bind(
        d.section || "general",
        d.content_key || "",
        d.content_value || "",
        d.content_type || "text",
        Number(d.sort_order) || 0,
        d.active === false ? 0 : 1
      ).run();

      return json({ success: true });
    }

    if (d.action === "deleteContent") {
      await env.DB.prepare("DELETE FROM site_content WHERE id=?")
        .bind(Number(d.id)).run();
      return json({ success: true });
    }

    if (d.action === "toggleContent") {
      await env.DB.prepare("UPDATE site_content SET active=? WHERE id=?")
        .bind(d.active ? 1 : 0, Number(d.id)).run();
      return json({ success: true });
    }

    // LINKS
    if (d.action === "saveLink") {
      if (d.id) {
        await env.DB.prepare(`
          UPDATE site_links
          SET label=?,url=?,location=?,sort_order=?,active=?
          WHERE id=?
        `).bind(
          d.label || "",
          d.url || "#",
          d.location || "social",
          Number(d.sort_order) || 0,
          d.active === false ? 0 : 1,
          Number(d.id)
        ).run();
      } else {
        const r = await env.DB.prepare(`
          INSERT INTO site_links(label,url,location,sort_order,active)
          VALUES(?,?,?,?,?)
        `).bind(
          d.label || "",
          d.url || "#",
          d.location || "social",
          Number(d.sort_order) || 0,
          1
        ).run();

        return json({ success: true, id: r.meta.last_row_id });
      }

      return json({ success: true });
    }

    if (d.action === "deleteLink") {
      await env.DB.prepare("DELETE FROM site_links WHERE id=?")
        .bind(Number(d.id)).run();
      return json({ success: true });
    }

    // MEDIA
    if (d.action === "saveMedia") {
      if (d.id) {
        await env.DB.prepare(`
          UPDATE site_media
          SET title=?,url=?,media_type=?,section=?,sort_order=?,active=?
          WHERE id=?
        `).bind(
          d.title || "",
          d.url || "",
          d.media_type || "image",
          d.section || "general",
          Number(d.sort_order) || 0,
          d.active === false ? 0 : 1,
          Number(d.id)
        ).run();
      } else {
        const r = await env.DB.prepare(`
          INSERT INTO site_media
          (title,url,media_type,section,sort_order,active)
          VALUES(?,?,?,?,?,?)
        `).bind(
          d.title || "",
          d.url || "",
          d.media_type || "image",
          d.section || "general",
          Number(d.sort_order) || 0,
          1
        ).run();

        return json({ success: true, id: r.meta.last_row_id });
      }

      return json({ success: true });
    }

    if (d.action === "deleteMedia") {
      await env.DB.prepare("DELETE FROM site_media WHERE id=?")
        .bind(Number(d.id)).run();
      return json({ success: true });
    }

    // EPISODES
    if (d.action === "addEpisode" || d.action === "updateEpisode") {
      let image = d.image_url || "";

      if (!image && d.video_url) {
        const m = d.video_url.match(
          /(?:youtube\\.com\\/watch\\?v=|youtu\\.be\\/|youtube\\.com\\/embed\\/)([A-Za-z0-9_-]{11})/
        );
        if (m)
          image = `https://img.youtube.com/vi/${m[1]}/maxresdefault.jpg`;
      }

      if (d.action === "addEpisode") {
        const r = await env.DB.prepare(`
          INSERT INTO episodes
          (season,episode_number,title,description,video_url,image_url,published)
          VALUES(?,?,?,?,?,?,?)
        `).bind(
          Number(d.season) || 1,
          Number(d.episode_number) || 1,
          d.title || "",
          d.description || "",
          d.video_url || "",
          image,
          d.published === false ? 0 : 1
        ).run();

        return json({ success: true, id: r.meta.last_row_id });
      }

      await env.DB.prepare(`
        UPDATE episodes SET
        season=?,episode_number=?,title=?,description=?,
        video_url=?,image_url=?,published=?
        WHERE id=?
      `).bind(
        Number(d.season) || 1,
        Number(d.episode_number) || 1,
        d.title || "",
        d.description || "",
        d.video_url || "",
        image,
        d.published ? 1 : 0,
        Number(d.id)
      ).run();

      return json({ success: true });
    }

    if (d.action === "deleteEpisode") {
      await env.DB.prepare("DELETE FROM episodes WHERE id=?")
        .bind(Number(d.id)).run();
      return json({ success: true });
    }

    if (d.action === "toggleEpisode") {
      await env.DB.prepare("UPDATE episodes SET published=? WHERE id=?")
        .bind(d.published ? 1 : 0, Number(d.id)).run();
      return json({ success: true });
    }

    // CAST
    if (d.action === "addCast") {
      const r = await env.DB.prepare(`
        INSERT INTO cast(name,role,bio,image_url,season,active)
        VALUES(?,?,?,?,?,1)
      `).bind(
        d.name || "",
        d.role || "",
        d.bio || "",
        d.image_url || "",
        Number(d.season) || 1
      ).run();

      return json({ success: true, id: r.meta.last_row_id });
    }

    if (d.action === "updateCast") {
      await env.DB.prepare(`
        UPDATE cast
        SET name=?,role=?,bio=?,image_url=?,season=?,active=?
        WHERE id=?
      `).bind(
        d.name || "",
        d.role || "",
        d.bio || "",
        d.image_url || "",
        Number(d.season) || 1,
        d.active ? 1 : 0,
        Number(d.id)
      ).run();

      return json({ success: true });
    }

    if (d.action === "deleteCast") {
      await env.DB.prepare("DELETE FROM cast WHERE id=?")
        .bind(Number(d.id)).run();
      return json({ success: true });
    }

    // STORIES
    if (d.action === "addStory") {
      const r = await env.DB.prepare(`
        INSERT INTO stories(author_name,story,image_url,status)
        VALUES(?,?,?,?)
      `).bind(
        d.author_name || "",
        d.story || "",
        d.image_url || "",
        d.status || "approved"
      ).run();

      return json({ success: true, id: r.meta.last_row_id });
    }

    if (d.action === "updateStory") {
      await env.DB.prepare(`
        UPDATE stories
        SET author_name=?,story=?,image_url=?,status=?
        WHERE id=?
      `).bind(
        d.author_name || "",
        d.story || "",
        d.image_url || "",
        d.status || "pending",
        Number(d.id)
      ).run();

      return json({ success: true });
    }

    if (d.action === "deleteStory") {
      await env.DB.prepare("DELETE FROM stories WHERE id=?")
        .bind(Number(d.id)).run();
      return json({ success: true });
    }

    // MESSAGES
    if (d.action === "addMessage") {
      const r = await env.DB.prepare(
        "INSERT INTO messages(message,active) VALUES(?,1)"
      ).bind(d.message || "").run();

      return json({ success: true, id: r.meta.last_row_id });
    }

    if (d.action === "updateMessage") {
      await env.DB.prepare(`
        UPDATE messages SET message=?,active=? WHERE id=?
      `).bind(
        d.message || "",
        d.active ? 1 : 0,
        Number(d.id)
      ).run();

      return json({ success: true });
    }

    if (d.action === "deleteMessage") {
      await env.DB.prepare("DELETE FROM messages WHERE id=?")
        .bind(Number(d.id)).run();
      return json({ success: true });
    }

    // VOTE OPTIONS
    if (d.action === "saveVoteOption") {
      await env.DB.prepare(`
        INSERT INTO vote_options
        (choice_key,label,title,description,message_title,message_text,active,sort_order)
        VALUES(?,?,?,?,?,?,?,?)
        ON CONFLICT(choice_key) DO UPDATE SET
        label=excluded.label,
        title=excluded.title,
        description=excluded.description,
        message_title=excluded.message_title,
        message_text=excluded.message_text,
        active=excluded.active,
        sort_order=excluded.sort_order
      `).bind(
        d.choice_key || "",
        d.label || "",
        d.title || "",
        d.description || "",
        d.message_title || "",
        d.message_text || "",
        d.active === false ? 0 : 1,
        Number(d.sort_order) || 0
      ).run();

      return json({ success: true });
    }

    if (d.action === "deleteVoteOption") {
      await env.DB.prepare("DELETE FROM vote_options WHERE id=?")
        .bind(Number(d.id)).run();
      return json({ success: true });
    }

    // APPLICATIONS
    if (d.action === "submitApplication") {
      const r = await env.DB.prepare(`
        INSERT INTO applications(name,email,story,status)
        VALUES(?,?,?,'pending')
      `).bind(
        d.name || "",
        d.email || "",
        d.story || ""
      ).run();

      return json({
        success: true,
        id: r.meta.last_row_id
      });
    }

    if (d.action === "updateApplication") {
      await env.DB.prepare(`
        UPDATE applications SET status=? WHERE id=?
      `).bind(
        d.status || "pending",
        Number(d.id)
      ).run();

      return json({ success: true });
    }

    if (d.action === "deleteApplication") {
      await env.DB.prepare("DELETE FROM applications WHERE id=?")
        .bind(Number(d.id)).run();
      return json({ success: true });
    }

    // VOTES
    if (d.action === "submitVote") {
      const choice = String(d.choice || "");
      if (!choice) return json({ error: "Missing choice" }, 400);

      const r = await env.DB.prepare(`
        INSERT INTO votes(choice) VALUES(?)
      `).bind(choice).run();

      return json({ success: true, id: r.meta.last_row_id });
    }

    return json({ error: "Unknown action" }, 400);

  } catch (e) {
    return json({
      error: e?.message || "Server error"
    }, 500);
  }
}
''')

# -----------------------------
# ADMIN PANEL
# -----------------------------
ADMIN.parent.mkdir(parents=True, exist_ok=True)

ADMIN.write_text(r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>BACK TO X — ADMIN</title>
<style>
*{box-sizing:border-box}
body{margin:0;background:#080808;color:#eee;font-family:Arial,sans-serif}
header{padding:22px 20px;border-bottom:1px solid #292929;position:sticky;top:0;background:#080808;z-index:10}
.logo{font-size:22px;font-weight:800;letter-spacing:2px}
main{max-width:1200px;margin:auto;padding:25px 16px 70px}
.panel{border:1px solid #292929;border-radius:16px;padding:20px;margin-bottom:18px;background:#101010}
h2{margin-top:0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px}
input,textarea,select{width:100%;background:#070707;border:1px solid #333;color:#fff;border-radius:10px;padding:12px;margin:5px 0 10px}
textarea{min-height:100px;resize:vertical}
button{border:0;border-radius:10px;padding:11px 15px;background:#4A102A;color:#fff;cursor:pointer;margin:4px}
button.secondary{background:#292929}
button.danger{background:#651b1b}
.item{border-top:1px solid #292929;padding:14px 0}
.small{font-size:12px;color:#aaa}
#login{max-width:420px;margin:15vh auto;padding:20px}
.hidden{display:none}
.status{margin:10px 0;color:#e9b7c8}
</style>
</head>
<body>

<div id="login" class="panel">
  <h2>BACK TO X ADMIN</h2>
  <p class="small">Secure administrator access.</p>
  <input id="password" type="password" placeholder="ADMIN PASSWORD">
  <button onclick="doLogin()">ENTER ADMIN</button>
  <p id="loginMsg" class="status"></p>
</div>

<div id="app" class="hidden">
<header>
  <div class="logo">BACK TO X / ADMIN</div>
</header>

<main>

<section class="panel">
<h2>HERO & BRAND</h2>
<div class="grid">
<input id="hero_title" placeholder="Hero title">
<input id="hero_subtitle" placeholder="Hero subtitle">
<input id="primary_color" placeholder="#4A102A">
<input id="secondary_color" placeholder="#0B0B0B">
<input id="font_family" placeholder="Montserrat, sans-serif">
</div>
<button onclick="saveHero()">SAVE HERO</button>
</section>

<section class="panel">
<h2>SITE CONTENT</h2>
<p class="small">Control text and configurable values throughout the site.</p>
<div class="grid">
<input id="c_section" placeholder="Section e.g. concept">
<input id="c_key" placeholder="Key e.g. title">
<select id="c_type">
<option value="text">Text</option>
<option value="html">HTML</option>
<option value="url">URL</option>
</select>
<input id="c_order" type="number" placeholder="Order">
</div>
<textarea id="c_value" placeholder="Content value"></textarea>
<button onclick="saveContent()">SAVE CONTENT</button>
<div id="contentList"></div>
</section>

<section class="panel">
<h2>LINKS / NAVIGATION / SOCIAL</h2>
<div class="grid">
<input id="l_label" placeholder="Label">
<input id="l_url" placeholder="URL">
<select id="l_location">
<option value="social">social</option>
<option value="nav">nav</option>
<option value="footer">footer</option>
<option value="button">button</option>
</select>
<input id="l_order" type="number" placeholder="Order">
</div>
<button onclick="saveLink()">SAVE LINK</button>
<div id="linkList"></div>
</section>

<section class="panel">
<h2>MEDIA</h2>
<div class="grid">
<input id="m_title" placeholder="Media title">
<input id="m_url" placeholder="Image / video URL">
<select id="m_type">
<option value="image">image</option>
<option value="video">video</option>
</select>
<input id="m_section" placeholder="Section">
<input id="m_order" type="number" placeholder="Order">
</div>
<button onclick="saveMedia()">SAVE MEDIA</button>
<div id="mediaList"></div>
</section>

<section class="panel">
<h2>EPISODES</h2>
<div class="grid">
<input id="e_season" type="number" value="1" placeholder="Season">
<input id="e_number" type="number" value="1" placeholder="Episode">
<input id="e_title" placeholder="Title">
<input id="e_video" placeholder="Video URL">
<input id="e_image" placeholder="Image URL — leave blank for YouTube auto thumbnail">
</div>
<textarea id="e_desc" placeholder="Description"></textarea>
<button onclick="saveEpisode()">ADD EPISODE</button>
<div id="episodeList"></div>
</section>

<section class="panel">
<h2>CAST</h2>
<div class="grid">
<input id="cast_name" placeholder="Name">
<input id="cast_role" placeholder="Role">
<input id="cast_image" placeholder="Image URL">
<input id="cast_season" type="number" value="1" placeholder="Season">
</div>
<textarea id="cast_bio" placeholder="Bio"></textarea>
<button onclick="saveCast()">ADD CAST MEMBER</button>
<div id="castList"></div>
</section>

<section class="panel">
<h2>X WALL / STORIES</h2>
<div class="grid">
<input id="s_author" placeholder="Author">
<input id="s_image" placeholder="Image URL">
<select id="s_status">
<option value="approved">approved</option>
<option value="pending">pending</option>
<option value="rejected">rejected</option>
</select>
</div>
<textarea id="s_story" placeholder="Story"></textarea>
<button onclick="saveStory()">ADD STORY</button>
<div id="storyList"></div>
</section>

<section class="panel">
<h2>MESSAGES</h2>
<textarea id="messageText" placeholder="Message"></textarea>
<button onclick="saveMessage()">ADD MESSAGE</button>
<div id="messageList"></div>
</section>

<section class="panel">
<h2>VOTING OPTIONS</h2>
<div class="grid">
<input id="v_key" placeholder="choice key e.g. back">
<input id="v_label" placeholder="Label e.g. THE PAST">
<input id="v_title" placeholder="Title e.g. GO BACK">
<input id="v_order" type="number" placeholder="Order">
</div>
<textarea id="v_desc" placeholder="Description"></textarea>
<input id="v_msg_title" placeholder="Message title">
<input id="v_msg_text" placeholder="Message text">
<button onclick="saveVoteOption()">SAVE VOTE OPTION</button>
<div id="voteOptionList"></div>
</section>

<section class="panel">
<h2>APPLICATIONS</h2>
<div id="applicationList"></div>
</section>

<section class="panel">
<h2>VOTE RESULTS</h2>
<div id="voteResults"></div>
</section>

</main>
</div>

<script>
let DATA={};

async function api(body){
  const r=await fetch("/api/content",{
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify(body)
  });
  const d=await r.json();
  if(!r.ok || d.error) throw new Error(d.error||"Request failed");
  return d;
}

async function doLogin(){
  const password=document.getElementById("password").value;
  const msg=document.getElementById("loginMsg");
  msg.textContent="CHECKING...";
  const r=await fetch("/api/admin",{
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify({action:"login",password})
  });
  const d=await r.json();
  if(!r.ok || !d.success){
    msg.textContent=d.error||"Wrong password";
    return;
  }
  document.getElementById("login").classList.add("hidden");
  document.getElementById("app").classList.remove("hidden");
  load();
}

async function load(){
  const r=await fetch("/api/content");
  DATA=await r.json();

  const s=DATA.settings||{};
  hero_title.value=s.hero_title||"";
  hero_subtitle.value=s.hero_subtitle||"";
  primary_color.value=s.primary_color||"";
  secondary_color.value=s.secondary_color||"";
  font_family.value=s.font_family||"";

  renderAll();
}

async function saveHero(){
  await api({
    action:"saveHero",
    hero_title:hero_title.value,
    hero_subtitle:hero_subtitle.value,
    primary_color:primary_color.value,
    secondary_color:secondary_color.value,
    font_family:font_family.value
  });
  await load();
}

async function saveContent(){
  await api({
    action:"saveContent",
    section:c_section.value,
    content_key:c_key.value,
    content_value:c_value.value,
    content_type:c_type.value,
    sort_order:Number(c_order.value)||0
  });
  await load();
}

async function saveLink(){
  await api({
    action:"saveLink",
    label:l_label.value,
    url:l_url.value,
    location:l_location.value,
    sort_order:Number(l_order.value)||0
  });
  await load();
}

async function saveMedia(){
  await api({
    action:"saveMedia",
    title:m_title.value,
    url:m_url.value,
    media_type:m_type.value,
    section:m_section.value,
    sort_order:Number(m_order.value)||0
  });
  await load();
}

async function saveEpisode(){
  await api({
    action:"addEpisode",
    season:Number(e_season.value)||1,
    episode_number:Number(e_number.value)||1,
    title:e_title.value,
    description:e_desc.value,
    video_url:e_video.value,
    image_url:e_image.value,
    published:true
  });
  await load();
}

async function saveCast(){
  await api({
    action:"addCast",
    name:cast_name.value,
    role:cast_role.value,
    bio:cast_bio.value,
    image_url:cast_image.value,
    season:Number(cast_season.value)||1
  });
  await load();
}

async function saveStory(){
  await api({
    action:"addStory",
    author_name:s_author.value,
    story:s_story.value,
    image_url:s_image.value,
    status:s_status.value
  });
  await load();
}

async function saveMessage(){
  await api({
    action:"addMessage",
    message:messageText.value
  });
  await load();
}

async function saveVoteOption(){
  await api({
    action:"saveVoteOption",
    choice_key:v_key.value,
    label:v_label.value,
    title:v_title.value,
    description:v_desc.value,
    message_title:v_msg_title.value,
    message_text:v_msg_text.value,
    sort_order:Number(v_order.value)||0
  });
  await load();
}

async function del(action,id){
  if(!confirm("Delete this item?"))return;
  await api({action,id});
  await load();
}

function renderAll(){
  contentList.innerHTML=(DATA.content||[]).map(x=>`
    <div class="item">
      <b>${esc(x.section)} / ${esc(x.content_key)}</b>
      <div class="small">${esc(x.content_value||"")}</div>
      <button class="danger" onclick="del('deleteContent',${x.id})">DELETE</button>
    </div>`).join("");

  linkList.innerHTML=(DATA.links||[]).map(x=>`
    <div class="item">
      <b>${esc(x.label)}</b> — ${esc(x.location)}
      <div class="small">${esc(x.url)}</div>
      <button class="danger" onclick="del('deleteLink',${x.id})">DELETE</button>
    </div>`).join("");

  mediaList.innerHTML=(DATA.media||[]).map(x=>`
    <div class="item">
      <b>${esc(x.title)}</b> — ${esc(x.media_type)}
      <div class="small">${esc(x.url)}</div>
      <button class="danger" onclick="del('deleteMedia',${x.id})">DELETE</button>
    </div>`).join("");

  episodeList.innerHTML=(DATA.episodes||[]).map(x=>`
    <div class="item">
      <b>S${x.season} E${x.episode_number} — ${esc(x.title)}</b>
      <div class="small">${esc(x.video_url)}</div>
      <button onclick="toggleEpisode(${x.id},${x.published?0:1})">${x.published?'HIDE':'PUBLISH'}</button>
      <button class="danger" onclick="del('deleteEpisode',${x.id})">DELETE</button>
    </div>`).join("");

  castList.innerHTML=(DATA.cast||[]).map(x=>`
    <div class="item">
      <b>${esc(x.name)}</b> — ${esc(x.role)}
      <div class="small">${esc(x.bio||"")}</div>
      <button class="danger" onclick="del('deleteCast',${x.id})">DELETE</button>
    </div>`).join("");

  storyList.innerHTML=(DATA.stories||[]).map(x=>`
    <div class="item">
      <b>${esc(x.author_name)} — ${esc(x.status)}</b>
      <div class="small">${esc(x.story)}</div>
      <button class="danger" onclick="del('deleteStory',${x.id})">DELETE</button>
    </div>`).join("");

  messageList.innerHTML=(DATA.messages||[]).map(x=>`
    <div class="item">
      ${esc(x.message)}
      <button class="danger" onclick="del('deleteMessage',${x.id})">DELETE</button>
    </div>`).join("");

  voteOptionList.innerHTML=(DATA.vote_options||[]).map(x=>`
    <div class="item">
      <b>${esc(x.label)} — ${esc(x.title)}</b>
      <div class="small">${esc(x.description||"")}</div>
      <button class="danger" onclick="del('deleteVoteOption',${x.id})">DELETE</button>
    </div>`).join("");

  applicationList.innerHTML=(DATA.applications||[]).map(x=>`
    <div class="item">
      <b>${esc(x.name)}</b> — ${esc(x.email)} — ${esc(x.status)}
      <div class="small">${esc(x.story)}</div>
      <button onclick="updateApplication(${x.id},'approved')">APPROVE</button>
      <button onclick="updateApplication(${x.id},'rejected')">REJECT</button>
      <button class="danger" onclick="del('deleteApplication',${x.id})">DELETE</button>
    </div>`).join("");

  voteResults.innerHTML=(DATA.vote_counts||[]).map(x=>
    `<div class="item"><b>${esc(x.choice)}</b>: ${x.count} votes</div>`
  ).join("") || "<p class='small'>No votes yet.</p>";
}

async function toggleEpisode(id,published){
  await api({action:"toggleEpisode",id,published:!!published});
  await load();
}

async function updateApplication(id,status){
  await api({action:"updateApplication",id,status});
  await load();
}

function esc(v){
  return String(v??"").replace(/[&<>"']/g,m=>({
    "&":"&amp;","<":"&lt;",">":"&gt;",
    '"':"&quot;","'":"&#039;"
  }[m]));
}
</script>
</body>
</html>
''')

# -----------------------------
# FRONTEND PATCH
# -----------------------------
html = INDEX.read_text()

# Remove Supabase import/client block.
start = html.find('import { createClient } from "https://cdn.jsdelivr.net/npm/@supabase/supabase-js/+esm";')
if start != -1:
    end = html.find('const supabase = createClient(supabaseUrl, supabaseKey);', start)
    if end != -1:
        end += len('const supabase = createClient(supabaseUrl, supabaseKey);')
        html = html[:start] + html[end:]

# Replace application + voting logic.
a = html.find('$("#apply-form")?.addEventListener("submit"')
b = html.find('async function loadStories()', a)

if a != -1 and b != -1:
    replacement = r'''
$("#apply-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();

  const msg = $("#form-message");
  const name = $("#app-name").value.trim();
  const email = $("#app-email").value.trim();
  const story = $("#app-story").value.trim();

  msg.textContent = "SENDING...";

  try {
    const response = await fetch("/api/content", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({
        action: "submitApplication",
        name,
        email,
        story
      })
    });

    const data = await response.json();

    if (!response.ok || !data.success) {
      throw new Error(data.error || "Application failed");
    }

    msg.textContent = "APPLICATION RECEIVED ✓";
    msg.style.cssText = "margin-top:10px;color:#e9b7c8;";
    e.target.reset();

  } catch (error) {
    console.error("Application error:", error);
    msg.textContent = "SOMETHING WENT WRONG. PLEASE TRY AGAIN.";
  }
});


let voteOptions = [];
let selectedVote = localStorage.getItem("back_to_x_selected") || "";
let voteCounts = {};

function renderVotes(){
  $$(".vote-option").forEach(option => {
    const key = option.dataset.vote;
    option.classList.toggle("selected", selectedVote === key);
    option.classList.toggle("dimmed", !!selectedVote && selectedVote !== key);
  });
}

async function loadVotes(){
  try {
    const response = await fetch("/api/content");
    const data = await response.json();

    voteOptions = data.vote_options || [];

    if (voteOptions.length) {
      const container = $("#vote-choices");

      container.innerHTML = voteOptions
        .filter(v => v.active !== 0)
        .map(v => `
          <div class="choice vote-option" data-vote="${escapeHTML(v.choice_key)}">
            <span class="vote-choice-number">${escapeHTML(v.label || "")}</span>
            <h3>${escapeHTML(v.title || "")}</h3>
            <p>${escapeHTML(v.description || "")}</p>
            <button class="vote-btn" data-vote="${escapeHTML(v.choice_key)}" type="button">MAKE YOUR CHOICE</button>
            <div class="vote-choice-message">
              <strong>${escapeHTML(v.message_title || "")}</strong>
              <span>${escapeHTML(v.message_text || "")}</span>
            </div>
          </div>
        `).join("");

      $$(".vote-btn").forEach(btn => {
        btn.addEventListener("click", e => {
          e.stopPropagation();
          submitVote(btn.dataset.vote, btn);
        });
      });

      $$(".vote-option").forEach(option => {
        option.addEventListener("click", () => {
          const btn = option.querySelector(".vote-btn");
          if (btn) btn.click();
        });
      });
    }

    voteCounts = {};
    (data.vote_counts || []).forEach(row => {
      voteCounts[row.choice] = Number(row.count) || 0;
    });

    renderVotes();

    const results = $("#vote-results");
    if(results && Object.keys(voteCounts).length){
      results.innerHTML = Object.entries(voteCounts)
        .map(([key,count]) => `<div class="vote-result">${escapeHTML(key).toUpperCase()} — ${count}</div>`)
        .join("");
    }

  } catch(error) {
    console.error("Vote load error:", error);
  }
}

async function submitVote(choice, btn){
  if(selectedVote) return;

  const buttons = $$(".vote-btn");
  buttons.forEach(b => b.disabled = true);

  const oldText = btn.textContent;
  btn.textContent = "SENDING...";

  try {
    const response = await fetch("/api/content", {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({
        action:"submitVote",
        choice
      })
    });

    const data = await response.json();

    if(!response.ok || !data.success)
      throw new Error(data.error || "Vote failed");

    selectedVote = choice;
    localStorage.setItem("back_to_x_selected", selectedVote);

    btn.textContent = oldText;
    renderVotes();
    await loadVotes();

  } catch(error) {
    console.error("Vote submit error:", error);
    btn.textContent = oldText;
    buttons.forEach(b => b.disabled = false);
  }
}

renderVotes();
loadVotes();


'''
    html = html[:a] + replacement + html[b:]

# Replace D1 settings loader with comprehensive loader.
c = html.find('async function loadD1Content(){')
d = html.find('loadD1Content();', c)

if c != -1 and d != -1:
    d += len('loadD1Content();')

    loader = r'''
async function loadD1Content(){
  try{
    const response = await fetch("/api/content");
    const data = await response.json();

    if(data.settings){
      const s = data.settings;

      const title = document.querySelector(".hero h1");
      const subtitle = document.querySelector(".hero p");

      if(title && s.hero_title) title.textContent = s.hero_title;
      if(subtitle && s.hero_subtitle) subtitle.textContent = s.hero_subtitle;

      if(s.primary_color)
        document.documentElement.style.setProperty("--primary-color", s.primary_color);

      if(s.secondary_color)
        document.documentElement.style.setProperty("--secondary-color", s.secondary_color);

      if(s.font_family)
        document.body.style.fontFamily = s.font_family;
    }

    // Generic CMS values.
    (data.content || [])
      .filter(x => x.active !== 0)
      .forEach(x => {
        const selector = `[data-cms="${CSS.escape(x.section + "." + x.content_key)}"]`;
        document.querySelectorAll(selector).forEach(el => {
          if(x.content_type === "html") el.innerHTML = x.content_value;
          else el.textContent = x.content_value;
        });
      });

    // Social / navigation links.
    const social = (data.links || [])
      .filter(x => x.active !== 0 && x.location === "social");

    const socialCards = document.querySelectorAll(".social-card");

    social.forEach((link, i) => {
      const el = socialCards[i];
      if(!el) return;

      el.href = link.url || "#";

      const strong = el.querySelector("strong");
      if(strong) strong.textContent = link.label || strong.textContent;
    });

    // Active site message.
    const message = (data.messages || [])
      .find(x => x.active !== 0);

    if(message){
      let bar = document.getElementById("d1-site-message");

      if(!bar){
        bar = document.createElement("div");
        bar.id = "d1-site-message";
        bar.style.cssText =
          "position:fixed;top:0;left:0;right:0;z-index:99998;" +
          "padding:10px 16px;text-align:center;" +
          "background:#4A102A;color:#fff;font-size:13px;";
        document.body.prepend(bar);
      }

      bar.textContent = message.message;
    }

  }catch(error){
    console.error("D1 connection error:", error);
  }
}

loadD1Content();
'''

    html = html[:c] + loader + html[d:]

# Add a few CMS hooks to important existing text elements.
replacements = {
    '<section class="section" id="concept">':
        '<section class="section" id="concept">',
    '<h2 class="section-title">THE <span>PAST IS BACK.</span></h2>':
        '<h2 class="section-title" data-cms="concept.title">THE <span>PAST IS BACK.</span></h2>',
    '<p class="intro">Some stories end. Some stories come back.</p>':
        '<p class="intro" data-cms="concept.intro">Some stories end. Some stories come back.</p>',
    '<h2 class="section-title">HOW IT <span>WORKS.</span></h2>':
        '<h2 class="section-title" data-cms="how-it-works.title">HOW IT <span>WORKS.</span></h2>',
    '<h2 class="section-title">FOLLOW <span>THE X.</span></h2>':
        '<h2 class="section-title" data-cms="social.title">FOLLOW <span>THE X.</span></h2>',
    '<p class="intro">Stay close. Follow the story beyond the screen.</p>':
        '<p class="intro" data-cms="social.intro">Stay close. Follow the story beyond the screen.</p>',
    '<h2 class="section-title">MAKE THE <span>CHOICE.</span></h2>':
        '<h2 class="section-title" data-cms="voting.title">MAKE THE <span>CHOICE.</span></h2>',
    '<p class="intro">If you were in their place, what would you choose?</p>':
        '<p class="intro" data-cms="voting.intro">If you were in their place, what would you choose?</p>',
    '<h2 class="section-title join-title">READY TO <span>GO BACK?</span></h2>':
        '<h2 class="section-title join-title" data-cms="apply.title">READY TO <span>GO BACK?</span></h2>',
    '<p class="intro">Think you have an unfinished story? Ready to face your X and make the choice?</p>':
        '<p class="intro" data-cms="apply.intro">Think you have an unfinished story? Ready to face your X and make the choice?</p>'
}

for old, new in replacements.items():
    html = html.replace(old, new)

INDEX.write_text(html)

print("FULL CONTROL BUILDER CREATED")
print("Cloudflare D1 API: READY")
print("Admin dashboard: READY")
print("Frontend Cloudflare loader: READY")
print("Supabase application/voting logic: REPLACED")
