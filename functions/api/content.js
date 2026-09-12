export async function onRequest(context) {
  const { request, env } = context;

  if (request.method === "GET") {
    const settings = await env.DB.prepare(
      "SELECT * FROM site_settings LIMIT 1"
    ).first();

    const episodes = await env.DB.prepare(
      "SELECT * FROM episodes ORDER BY season, episode_number"
    ).all();

    const cast = await env.DB.prepare(
      "SELECT * FROM cast WHERE active = 1 ORDER BY id"
    ).all();

    const stories = await env.DB.prepare(
      "SELECT * FROM stories WHERE status = 'approved' ORDER BY created_at DESC"
    ).all();

    const messages = await env.DB.prepare(
      "SELECT * FROM messages WHERE active = 1 ORDER BY created_at DESC"
    ).all();

    return Response.json({
      settings,
      episodes: episodes.results,
      cast: cast.results,
      stories: stories.results,
      messages: messages.results
    });
  }

  if (request.method === "POST") {
    const data = await request.json();

    if (data.action === "saveHero") {
      await env.DB.prepare(`
        INSERT INTO site_settings
        (id, site_name, hero_title, hero_subtitle)
        VALUES (1, 'BACK TO X', ?, ?)
        ON CONFLICT(id) DO UPDATE SET
        hero_title = excluded.hero_title,
        hero_subtitle = excluded.hero_subtitle
      `)
      .bind(data.hero_title || "", data.hero_subtitle || "")
      .run();

      return Response.json({
        success: true,
        message: "Hero saved successfully"
      });
    }

    if (data.action === "addEpisode") {
      await env.DB.prepare(`
        INSERT INTO episodes
        (season, episode_number, title, description, video_url, image_url)
        VALUES (?, ?, ?, ?, ?, ?)
      `)
      .bind(
        data.season || 1,
        data.episode_number || 1,
        data.title || "",
        data.description || "",
        data.video_url || "",
        data.image_url || ""
      )
      .run();

      return Response.json({
        success: true,
        message: "Episode added successfully"
      });
    }

    if (data.action === "addCast") {
      await env.DB.prepare(`
        INSERT INTO cast
        (name, role, bio, image_url, season)
        VALUES (?, ?, ?, ?, ?)
      `)
      .bind(
        data.name || "",
        data.role || "",
        data.bio || "",
        data.image_url || "",
        data.season || 1
      )
      .run();

      return Response.json({
        success: true,
        message: "Cast member added successfully"
      });
    }

    if (data.action === "addStory") {
      await env.DB.prepare(`
        INSERT INTO stories
        (author_name, story, image_url, status)
        VALUES (?, ?, ?, 'approved')
      `)
      .bind(
        data.author_name || "",
        data.story || "",
        data.image_url || ""
      )
      .run();

      return Response.json({
        success: true,
        message: "Story added successfully"
      });
    }

    if (data.action === "addMessage") {
      await env.DB.prepare(`
        INSERT INTO messages
        (message, active)
        VALUES (?, 1)
      `)
      .bind(data.message || "")
      .run();

      return Response.json({
        success: true,
        message: "Message added successfully"
      });
    }

    return Response.json(
      { error: "Unknown action" },
      { status: 400 }
    );
  }

  return Response.json(
    { error: "Method not allowed" },
    { status: 405 }
  );
}
