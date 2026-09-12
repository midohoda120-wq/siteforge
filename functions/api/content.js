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

  return Response.json({ error: "Method not allowed" }, { status: 405 });
}
