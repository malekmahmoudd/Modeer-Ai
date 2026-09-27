# Privacy notice

The canonical text lives at [`backend/app/legal/privacy.md`](../backend/app/legal/privacy.md)
and is served by the app at `GET /api/legal/privacy`.

It sits inside the backend package rather than here because the Docker build
context is `backend/`: a copy in `docs/` would be missing from the image, and
the endpoint would work in development and 404 in production.


## Design tools and reply context

Home and reading preferences are stored separately from your AI profile and are not sent to models. Saved excerpts and team-comparison notes stay with their conversation and are included in account export; they are not injected into AI history. New replies retain a snapshot of the personal context sent at that time. Editing or deleting a memory does not rewrite that old snapshot; delete the chat to remove its snapshots. This records what was sent, not what influenced the answer. Source Peek checks the stored document passage without keeping another copy; deleting the document disables its preview. Explicitly saved excerpts and downloaded Pocket Cards are separate copies. Incognito chats cannot save excerpts or comparison notes.
