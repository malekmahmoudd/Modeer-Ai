# Design add-ons — September 2026

These additions retain Sunshine & Ink and support English and Arabic.

- **My Front Desk:** Home's specialist row can be pinned, unpinned and ordered with keyboard-accessible buttons. The default four remain the initial choice. Account preferences persist across devices.
- **Continue This Item:** Today items carry their text and detail to a new, editable specialist draft. Nothing sends automatically; content travels in tab session storage, never a URL.
- **Reading Desk:** Chat controls for text size, line spacing, reading width and temporary reading focus. Preferences are independent of Data Saver. Escape exits focus.
- **Source Peek:** Citation chips open a desktop drawer or mobile sheet containing the exact retrieved passage. Chunk ID, sent length and hash verify it. Old replies without a reference, deleted documents and changed passages report unavailable instead of substituting different text.
- **Context Drawer:** A snapshot of personal context sent with that reply, plus the number of history messages. This does not prove influence. Internal instructions and transcript content are not duplicated in the drawer. Old replies have no retrospective snapshot.
- **Team Comparison:** Existing Ask My Team consultations can be reopened side by side, with editable trade-offs and a choice saved on the synthesis. No new model call. The existing deployment switch for creating team consultations is unchanged.
- **Selected-text actions:** Select text and choose “Work with an excerpt,” or edit the excerpt in the drawer. Explain, translate and teammate handoff prepare drafts. Saved excerpts appear in Plans. Incognito saving is disabled.
- **Pocket Cards:** Editable study sheets, numbered interview cues and packing checklists, built from existing content without a model call. Downloads are self-contained printable HTML; browser print can save PDF. Exports escape content and include no scripts or remote resources.

## Storage and rollout

Run `cd backend && .venv/bin/alembic upgrade head` before starting this version against an existing database. Migration **0011** adds `users.ui_preferences`; fresh SQLite databases create it automatically. Back up existing production data using the established deployment process. This implementation does not deploy or migrate a live database.

Preferences are separate from the profile sent to models. Saved excerpts and comparison notes are message metadata, excluded from model history. Account export includes these and context snapshots; deleting their conversation/account removes them. Regenerating a reply with saved content is blocked until the saved content is removed.

Context snapshots are retained with their original chat: deleting or editing a memory does not rewrite an old receipt. Document passage bodies are not copied into receipts; deleting the document makes Source Peek unavailable. A saved excerpt or downloaded card is an explicit copy and is not removed by deleting the source document.
