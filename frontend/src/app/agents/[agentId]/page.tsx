"use client";

import { Suspense, use } from "react";

import { ChatWorkspace } from "@/components/chat/ChatWorkspace";
import { Spinner } from "@/components/ui/primitives";

export default function AgentWorkspacePage({
  params,
}: {
  params: Promise<{ agentId: string }>;
}) {
  const { agentId } = use(params);
  return (
    <Suspense
      fallback={
        <div className="grid h-[70vh] place-items-center text-content-faint">
          <Spinner />
        </div>
      }
    >
      <ChatWorkspace agentId={agentId} />
    </Suspense>
  );
}
