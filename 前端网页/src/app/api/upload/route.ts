import { NextResponse } from "next/server";
import { AGENT_CONFIG } from "@/lib/constants";

export async function POST(request: Request) {
  try {
    const formData = await request.formData();
    const file = formData.get("file") as File | null;
    if (!file) return NextResponse.json({ error: "No file" }, { status: 400 });

    // 转发到 Agent
    const agentForm = new FormData();
    agentForm.append("file", file, file.name);
    const res = await fetch(`${AGENT_CONFIG.BASE_URL}/v1/upload`, {
      method: "POST",
      body: agentForm,
      signal: AbortSignal.timeout(30000),
    });
    const data = await res.json();
    if (!res.ok) return NextResponse.json(data, { status: res.status });
    return NextResponse.json(data);
  } catch (err) {
    return NextResponse.json({ error: "Upload failed" }, { status: 500 });
  }
}
