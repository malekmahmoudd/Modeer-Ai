"use client";

import { use } from "react";

import { ChatWorkspace } from "@/components/chat/ChatWorkspace";

export default function AgentWorkspacePage({
  params,
}: {
  params: Promise<{ agentId: string }>;
}) {
  const { agentId } = use(params);
  return (
    <div className="animate-fade-up">
      <ChatWorkspace agentId={agentId} />
    </div>
  );
}
