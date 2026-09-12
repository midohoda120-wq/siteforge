export async function onRequest(context) {
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
