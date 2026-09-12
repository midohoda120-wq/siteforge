export async function onRequest(context) {
  const { request, env } = context;

  if (request.method !== "POST") {
    return Response.json(
      { error: "Method not allowed" },
      { status: 405 }
    );
  }

  const data = await request.json();

  if (data.action === "login") {
    if (!env.ADMIN_PASSWORD) {
      return Response.json(
        { error: "ADMIN_PASSWORD is not configured" },
        { status: 500 }
      );
    }

    if (data.password !== env.ADMIN_PASSWORD) {
      return Response.json(
        { error: "Wrong password" },
        { status: 401 }
      );
    }

    return new Response(
      JSON.stringify({ success: true }),
      {
        headers: {
          "Content-Type": "application/json",
          "Set-Cookie":
            "admin_session=authenticated; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=86400"
        }
      }
    );
  }

  return Response.json({ error: "Unknown action" }, { status: 400 });
}
