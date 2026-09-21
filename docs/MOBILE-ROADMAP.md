# CrewAi iOS and Android roadmap

**Agent-name update — 2026-09-15:** Leo is the team leader; Nova (Study), Harvey (Career), Clara (Research), Alex (Writing), Tessa (Travel), Nate (Shopping), Emma (Finance), Maddie (Fitness), and Nora (Email) are the specialists. CrewAi is the product name. See [current naming and compatibility](AGENT-NAMES.md). Historical screenshots, decks and quality artifacts retain the names used when recorded; the earlier live evaluations predate the renamed prompts.

**Dependency update — 2026-09-15:** local production HTTPS journeys, PostgreSQL
recovery races and schema `0004` backup restoration now pass. Real-domain,
off-host, human alert-receipt, physical-device and quality gates remain open.
See [the latest rehearsal](launch-rehearsal-2026-09-14.md). The mobile plan below
remains proposed; no native implementation or store setup was started.

**Planning date:** 2026-09-13. **Repository baseline:** `1ed17eb` plus the documented evidence changes. Read [PROJECT-REPORT.md](PROJECT-REPORT.md) and the [latest independent review](production-readiness-review-2026-09-13.md) first. This is a proposed delivery plan; no mobile application, native authentication endpoint, store account or signing identity was created during this work.

## 1. Recommendation and release dependency

Build a separate **React Native application using Expo and TypeScript**, consuming the existing FastAPI backend. Keep the web application operational and preserve the approved comic design. Start with a small physical-device authentication and streaming prototype, not a full screen-by-screen port.

This recommendation is an engineering inference from the existing React/TypeScript codebase, modest screen count, server-hosted AI, and the value of sharing one mobile implementation. Actual team availability and native experience are unknown. The recommendation should be revisited if the owner already has an experienced Flutter or native team.

React Native's official guidance recommends a framework such as Expo for new applications. Expo provides native modules/build tooling, and its current `expo/fetch` documentation includes streamed response reading. These capabilities make it a suitable starting point, but do not prove that CrewAi's POST/SSE, authentication and background behavior work on a device. Pin a compatible Expo/React Native/React set at implementation time rather than copying the web package versions. [React Native setup](https://reactnative.dev/docs/environment-setup), [Expo streaming fetch](https://docs.expo.dev/versions/latest/sdk/expo/#expofetch-api).

**Prerequisite:** local PostgreSQL recovery races, production HTTPS browser journeys and schema `0004` restoration now pass. Carry these checks into the real hosted environment before exposing native password accounts. Real-domain, genuinely remote backup, operator-receipt and quality gates remain open. The latest live answer evaluation has 27 automated passes, 11 failures and one unavailable grade; the separate live application journey passed 13 checks. See [rehearsal evidence](launch-rehearsal-2026-09-14.md) and [current quality evidence](quality-evidence-2026-09-15.md). Platform references below retain the September 13 planning baseline; reverify them at mobile implementation and submission time.

## 2. Technology alternatives

| Option | Reuse and fit | Cost/maintenance implications | Decision |
|---|---|---|---|
| React Native + Expo | Reuses TypeScript knowledge, domain types, pure utilities, artwork and design tokens. Native views/navigation replace DOM/CSS. Existing backend remains. | One shared mobile codebase, with platform-specific testing and occasional native configuration. Expo services are optional infrastructure choices, not required ownership of the product. | Recommended, subject to physical-device feasibility spike. |
| Flutter | Reuses APIs, assets and design intent; client logic/UI moves to Dart and Flutter widgets. Strong control over rendering for custom comic panels. | One mobile codebase, but new language/UI implementation and less direct reuse of the React work. Attractive with an experienced Flutter team. | Viable alternative; no demonstrated need to switch the current team. |
| Separate native iOS/Android | Reuses backend/contracts/artwork; SwiftUI and Kotlin/Compose implement two clients. | Maximum direct platform control, two UI/state/transport implementations, more parity and release coordination work. | Prefer only with dedicated platform engineers or substantial native requirements. |

Flutter's architecture supports cross-platform reuse with platform embedding and a Dart framework; that supports its viability, not a claim that it is inherently faster for this team. [Flutter architecture](https://docs.flutter.dev/resources/architectural-overview). Native alternatives are planning options, not implemented modules.

Do not wrap the web page in a WebView and call mobile complete. Keyboard behavior, native navigation, accessibility, secure credential storage, interrupted networks and store requirements need explicit work. A WebView prototype could test demand, but is not the recommended production architecture.

## 3. MVP scope mapped to the existing product

The mobile MVP is a private personal AI workspace, with no public content feed and no external actions.

| Journey | Existing foundation | Mobile deliverable |
|---|---|---|
| Sign in / optional signup / recovery | Password/key routes, recovery codes, account epoch | Native forms, secure sessions, deliberate recovery-code handling and accessible validation |
| First use | Leo onboarding, shared facts and profile | Concise privacy/AI-sharing explanation, explicit required consent, first chat and inspectable memory |
| Home / team | Hero, featured specialists, Today, all ten identities | Native navigation and portrait panels, quick entry to Leo and specialists |
| Chat / history | POST SSE, conversation API, four reply states | Streaming native transcript, keyboard-safe composer, history, continuation/retry and reconnect reconciliation |
| Memory | Shared/private CRUD, pinning, automatic-memory switch | Read/save/edit/delete facts with clear scope and learning controls |
| Goals / Today | Goal CRUD and deterministic briefing | Manage priorities and use the daily view without claiming calendar integration |
| Account rights | Export, deletion, sign-out-everywhere | Secure export/share flow, deletion inside the app, local-cache purge and revocation handling |
| AI output concerns | No reporting workflow established | In-app report action, server intake and an operator handling process before Google Play release |

MVP excludes Ask My Team UI, voice, push reminders, widgets, HealthKit/Health Connect, calendar/email connections, camera/document uploads, autonomous actions, payments, social login and offline AI generation. Each is optional future scope, not an implied commitment. Keep the email agent as a drafting assistant. Do not request contacts, microphone, health or location permissions without a implemented feature that needs them.

## 4. Reuse boundary and proposed code organization

Keep `backend/` and `frontend/` intact. Proposed additions are a `mobile/` app and, only when useful, a small shared TypeScript package for domain types, URL validation and presentation-independent utilities. Avoid reorganizing the entire repository as a prerequisite.

Reuse the ten portrait assets after rights/provenance review, the palette and typography hierarchy, wording for agent identities, and API domain concepts. Reuse tests as behavior specifications. Generate or validate mobile API types against a versioned development schema artifact; do not reopen production Swagger merely to obtain types.

Do not directly reuse browser components, Tailwind classes, `next/navigation`, Next image/font loaders, browser `window.location`, DOM Markdown rendering or the chat hook unchanged. The current hook combines network parsing with React/browser state and drops memory error fields. Extract a tested transport/event parser behind an adapter only after fixing its contract. Native Markdown must enforce the same URL policy and avoid unsafe embedded HTML. [Current hook](../frontend/src/features/chat/useChatStream.ts), [types](../frontend/src/types/index.ts), [links](../frontend/src/lib/links.ts).

Separate native modules conceptually into API/auth, chat transport, server-state cache, local storage, design primitives, and feature screens. Keep provider keys, prompts, model selection, extraction rules and quota enforcement on the server.

## 5. Backend changes and native authentication

Current authentication is browser-oriented: an HttpOnly SameSite cookie scoped to `/api`, mutation checks against one Origin, and a signed epoch-based session. The mobile app has no trusted browser Origin, and copying a web Origin header is not a new authentication design. [Auth](../backend/app/core/auth.py), [auth routes](../backend/app/api/routes/auth.py).

**Proposed native contract:** short-lived bearer access tokens plus rotating refresh credentials backed by per-device server records. Prefer a carefully reviewed established authentication implementation; do not invent a cryptographic protocol. Define expiry, hashed refresh-token storage, token-family reuse detection, atomic rotation, device logout, sign-out-everywhere, and password/recovery revocation. Validate account/epoch or an equivalent revocation control on every authenticated request. Never weaken browser cookie/Origin protections to accommodate native clients.

Document separate native login/refresh/logout endpoints or an explicit negotiated response mode. Password and invitation-key entry may reuse verification logic, but native issuance must be an intentional server behavior. Preserve the implemented atomic recovery-code use and credential locks, verify them on PostgreSQL, and apply the same concurrency discipline to proposed refresh rotation. Require no client-held provider secret, shared signing secret or privileged API key.

Use Expo SecureStore for small credentials, not transcripts. Its documented platform behavior differs: Android data is removed on uninstall; iOS Keychain values can survive reinstall, and biometric changes can invalidate protected entries. Clear credentials on logout/deletion, verify session validity at launch, handle unreadable entries as reauthentication, and test backup/restore exclusions. Do not treat uninstall as a reliable server logout. [SecureStore documentation](https://docs.expo.dev/versions/latest/sdk/securestore/).

Treat biometrics as optional local access protection, not a replacement for server authorization or recovery. Recovery codes should be shown only on deliberate issuance and never included in analytics, logs or routine local caches. Provide copy/save choices with an explanation; do not silently save codes into photos or documents.

Use verified HTTPS universal/app links for supported entry points. Define allowed routes and parameters, verify ownership after login, and reject arbitrary redirect destinations. Never place passwords, access keys, refresh tokens, chat text or recovery codes in links. Social login is out of MVP; if added, use a system browser and authorization-code/PKCE flow, then reassess platform login requirements. Expo notes that OAuth testing needs a development build with its own scheme rather than relying on Expo Go. [Expo authentication](https://docs.expo.dev/guides/authentication/).

## 6. Request identity, streaming and lifecycle

The current API streams `start`, `delta`, `end`, `memory` and `error` frames. It has persisted completion metadata but no durable generation ID, idempotency key or event replay. In-process conversation locks only serialize one worker. These gaps matter more when a phone loses connectivity or the OS suspends it.

Before building the full chat UI, add:

1. A client-generated request ID/idempotency key scoped to account and operation, plus a payload fingerprint. Repeated identical sends return the same operation; a changed payload under the same key is rejected.
2. A durable operation/turn record and atomic server claim. Expose accepted/running/completed/truncated/interrupted/failed state and its conversation/message IDs. Define a lease/expiry for crashed workers.
3. A way to reconcile status after reconnecting. Full replayable SSE is optional for MVP if the client can fetch the operation and stored transcript safely. Do not advertise seamless resume without replay semantics.
4. Stable error codes for authentication, allowance, provider limits, transport interruption and memory failure. Preserve `retry_after` where appropriate.
5. Cursor pagination for growing conversation/message collections before a mobile client downloads an entire account history on each visit.

Use the existing POST/SSE approach unless the prototype demonstrates a concrete reason to switch transports. Implement chunk-boundary-safe UTF-8 and frame parsing, terminal-event handling, explicit abort and cleanup. Test a final delta combined with a finish reason, partial network frames, missing terminal events, post-answer memory errors and the difference between server and client timeouts. Expo's documented streaming API is a candidate transport, not a substitute for those tests.

On backgrounding, assume execution and network access can be suspended. MVP policy: reconcile the server operation when foregrounded; never automatically resend the prompt. If a disconnect cancels generation, display its persisted partial state. If future product requirements demand guaranteed completion while the app is closed, add a durable server job rather than relying on a phone background task.

On apparent cancellation, do not claim the provider stopped spending until the backend confirms the state. “Try again” is an explicit regeneration, while “Continue” adds a new user turn. Display whether additional allowance may be used. Deduplicate using server IDs rather than matching message text. Two devices sending/retrying simultaneously must not create two charges for the same operation.

## 7. Local storage, offline use and synchronization

Recommended MVP: server-authoritative records, a bounded account-partitioned cache, and a local unsent draft. Permit reading previously cached conversations offline; clearly indicate when they were last synchronized. There is no offline model. Disable AI sends while offline rather than silently queueing them for later expenditure.

For transcript caches, use an encrypted database or another vetted encrypted store with keys protected by the platform, explicit size/age bounds, backup policy and logout cleanup. SecureStore itself is not a database for large content. Do not cache sensitive memories by default without an explicit product decision. Keep analytics and crash reports free of prompts, facts, tokens and recovery material.

Purge all account-specific cache and drafts on account switching, logout/deletion as defined by the product, and confirmed revocation. Ensure export temporary files are removed according to a documented policy. A locked screen should not expose chat text in app-switcher previews if the privacy design calls for hiding it; test both platforms.

For MVP, memory/goal writes require a connection and server confirmation. Optimistic UI must revert on failure. Add versions/ETags or equivalent conflict detection before supporting offline edits; a mobile edit must not silently overwrite a newer web correction. Future sync needs deletion tombstones, cursor expiry and reconciliation rules. Test restored device backups so deleted accounts/facts do not reappear in local state.

## 8. Native design and accessibility

Adapt the Sunshine & Ink identity: warm paper, yellow/pink fields, dark text, subtle borders, large human artwork on discovery screens, and a quiet reading surface in chat. Keep ink on pink and deep pink text from the contrast fix. Do not bring back low-contrast white-on-pink controls. [Web tokens](../frontend/src/app/globals.css), [artwork provenance](CHARACTER-ART.md).

Use native bottom navigation for Home, Team, Memory and Goals, with Account clearly reachable. Chat should be a navigation-stack screen with history accessible and standard back behavior. Fit the composer above the keyboard, respect safe areas, preserve scroll position, and follow new text only when the reader is already near the bottom. Do not drag a user away from an older message while streaming.

Support platform text scaling and meaningful accessibility names/roles. Announce reply outcomes and memory errors, not every streamed token. Ensure recovery actions work with VoiceOver and TalkBack. Decorative art should not dominate accessibility traversal; agent images need concise identity descriptions only when informative. Make panels usable with large fonts, reduced motion, landscape and small screens. Define tablet scope separately rather than silently assuming phone layouts are tablet-ready.

Bundle approved/licensed font files and appropriately sized artwork. Keep body text native/selectable, avoid rasterizing text into hero images, virtualize long transcripts, and profile image decode/memory use. Test older representative devices; impressive desktop screenshots are not a frame-rate or battery measurement.

## 9. Push, safety and operational readiness

Push is optional after MVP. The existing daily briefing is generated from stored context; it is not already a scheduled notification product. Only add push for a chosen use case such as opt-in reminders or a completed background job. That requires a server scheduler/job system, device-token registration and revocation, timezone preferences, deduplication, quiet hours and provider delivery monitoring.

Request notification permission at the point of value. Default payloads should be generic and contain no health/finance details or reply text. A deep link opens the app and rechecks authorization. Logout/account deletion must unregister device tokens. Do not ask for notification permission merely because the framework supports it.

Public mobile availability needs an abuse/safety workflow beyond existing prompts: in-app AI-output reporting, rate-limited report intake, an authorized review queue, a response policy, retention limits and content-minimizing logs. Google Play specifically requires in-app reporting/flagging for AI-generated offensive content and prevention of restricted content. Build this into the store-release scope, not a later optional enhancement. [Google AI-generated content policy](https://support.google.com/googleplay/android-developer/answer/13985936?hl=en-GB).

Model capacity remains server-wide. Estimate demand from measured active users × turns/day × observed input/output/extraction usage, plus peak simultaneous streams. Existing allowance units are deliberately conservative and are not provider billing tokens. Load-test admission, first-token latency, stream completion, SQL pool pressure, password hashing and memory extraction on the chosen host. Measure limits before promising user counts. Keep a single worker until durable claims and distributed monitoring are ready.

Proposed launch targets should be agreed before testing: response/first-token latency percentiles, successful completed-turn rate, allowance-rejection behavior, crash-free sessions, backup age, restore time and operator response time. No current artifact establishes a production SLA. Record app version, API version and operation IDs without logging personal text.

## 10. Test strategy and acceptance matrix

Automate domain/transport/state tests plus device end-to-end tests. Keep real-provider sampling small and budgeted; scripted upstreams should deterministically exercise failures.

- **Devices:** at least one physical iPhone and Android phone, current and oldest supported OS in simulators/emulators, a small display, an older/memory-constrained Android device, and large text. Choose exact minimum OS support after framework/device research.
- **Account isolation:** A→B switching, stale caches, expired sessions, deleted account, sign-out-everywhere, password recovery, refresh-token replay and simultaneous recovery. A valid session must never reveal another account's state.
- **Streaming:** Wi-Fi→cellular, airplane mode, background/foreground, OS termination, slow response, idle stream, total cap, cancellation, failed extraction, duplicate taps and two-device overlap.
- **Data:** memory on/off, sensitive-candidate handling, manual correction protection, pinning, private specialist isolation at actual provider input, goal conflicts, export and deletion cleanup.
- **UI/accessibility:** VoiceOver/TalkBack, keyboard/safe-area behavior, text scaling, reduced motion, focus after errors, portrait loading and long Markdown/code/table content.
- **Security:** no credentials in logs/deep links/backups; native token lifecycle; TLS; root/backend ownership checks; account deletion; signed release configuration and dependency checks.
- **Quality:** complete release-agent evaluation plus short real end-to-end personalized journeys. Store a source/config fingerprint and human adjudication of contested judge outcomes.

Acceptance requires recorded results against a named build/backend revision. A responsive web check at 390px does not count as a native-device pass, and an automated accessibility scanner does not replace screen-reader testing.

## 11. Builds, distribution and current store requirements

The owner must retain Apple/Google developer accounts, bundle/application IDs, signing authority and recovery access. No accounts are created by this plan. Separate development, staging and production API endpoints and signing profiles; never ship development bypasses or provider keys. Use development builds for native-module/auth tests and signed release candidates for final verification. Local iOS builds require the Apple toolchain; Expo offers local/cloud build paths, so Windows development alone is not the whole iOS release environment. [Expo local builds](https://docs.expo.dev/guides/local-app-overview/).

**Apple, verified 2026-09-13:** current submission requirements call for Xcode 26 or later and the iOS 26 SDK or later. This is a build requirement, not a requirement to make iOS 26 the app's minimum supported OS. Recheck when submitting. [Apple requirements](https://developer.apple.com/news/upcoming-requirements/).

Use TestFlight for internal/external beta distribution; external builds can require beta review. Supply working reviewer credentials, instructions, a reachable backend and an explanation of AI behavior and feature flags. [TestFlight external review](https://developer.apple.com/help/app-store-connect/test-a-beta-version/invite-external-testers).

Apple requires in-app account deletion where the app supports account creation. Implement the native deletion flow rather than only linking to a support email. [Apple deletion requirements](https://developer.apple.com/support/offering-account-deletion-in-your-app/). Complete App Privacy disclosures for the actual app, backend and third-party SDK data handling. [App Privacy details](https://developer.apple.com/app-store/app-privacy-details/).

Apple's review guidelines require disclosure and explicit permission before sharing personal data with third parties, including third-party AI. Proposed implementation: before the first AI request, explain which provider receives message/history/selected context and obtain recorded permission. This is separate from the automatic-memory switch, which controls storage/extraction and does not prevent existing context being sent for replies. Also review age-rating, health/finance positioning, and any future payment or social-login requirements against the actual product. [Apple review guidelines](https://developer.apple.com/app-store/review/guidelines/).

**Google Play, verified 2026-09-13:** current phone-app submission guidance requires Android 16/API 36 or higher, following the August 31, 2026 requirement. This target API is distinct from the minimum supported Android version. Recheck the requirements at submission and confirm the selected Expo/native build supports them. [Android target requirements](https://developer.android.com/google/play/requirements/target-sdk).

Google requires an in-app deletion path and a functional external web resource for requesting account/data deletion where account creation is offered. Build and test that external resource; the existing authenticated JSON endpoint alone is not the complete store deliverable. Document retention exceptions truthfully. [Google deletion requirements](https://support.google.com/googleplay/android-developer/answer/13327111?hl=en).

Complete Google Data safety declarations from actual flows and included SDKs. [Data safety guidance](https://support.google.com/googleplay/android-developer/answer/10787469?hl=en). The AI reporting feature in section 9 is a release requirement. For personal developer accounts created after November 13, 2023, the documented production-access process requires a closed test with at least 12 testers continuously opted in for 14 days. Applicability depends on the owner's account; do not assume it applies to every organization account. [Google testing requirements](https://support.google.com/googleplay/android-developer/answer/14151465?hl=en).

Budget store preparation for screenshots, descriptions, privacy/support URLs, age/content declarations, signing, reviewer access and correction cycles. Store approval time is external and not guaranteed by an engineering estimate. Payments are outside MVP; if introduced, perform a separate country/store-specific billing-policy review before implementation. Over-the-air updates must respect native compatibility and store policy; they are not a way to bypass review of material product changes.

## 12. Phases, dependencies and estimates

Estimates are planning ranges, not commitments. Assumptions: one experienced full-time React Native/TypeScript engineer, backend support around half-time, part-time design/QA, reuse of existing artwork, English phone UI, no billing/push/voice/integrations, and prompt/provider behavior largely retained. Owner decisions, hardware, credentials and a usable staging host are available when needed. Ranges overlap; they are not a priced quote.

| Phase | Indicative duration | Deliverables | Exit criteria / dependency |
|---|---|---|---|
| 0. Backend release closure | 1–3 engineering weeks, operational waiting separate | Staging verification of implemented recovery/context/error fixes, quality acceptance, real-domain staging, backup/alert proof | Critical findings closed; staging accounts and reliable rollback/restore available |
| 1. Native feasibility | 1–2 weeks | Small Expo development builds on both physical platforms; native auth design and streamed chat prototype | Sign in, stream, interrupt, reconcile and revoke on both devices without duplicates or secret leakage |
| 2. API/auth foundation | 2–4 weeks | Native session issuance/rotation, operation identity, conflict/error contract, pagination, shared types | Security/concurrency tests pass; web authentication remains protected |
| 3. Product MVP | 3–5 weeks | Home/team/chat/history/memory/goals/account screens, export/deletion, bounded cache, design/accessibility implementation | All mapped journeys work against staging with large text and scripted failure cases |
| 4. Release hardening | 2–3 weeks | Device matrix, VoiceOver/TalkBack, load/quality verification, privacy permission and AI reporting/support workflow | No unresolved high-severity defects; evidence tied to signed candidate build |
| 5. Beta and stores | 2–4+ calendar weeks | TestFlight/Play testing, store declarations/assets, monitored rollout | Account-specific testing requirements met; owner release decision and store approval |

With overlap, plan roughly **12–18 calendar weeks** under these assumptions, plus unresolved hosting/account approvals and unexpected store cycles. A single engineer also owning backend, design and QA should plan roughly **16–24+ weeks**. Reduce uncertainty after Phase 1. Do not compress the schedule by substituting emulator screenshots for lifecycle/security validation.

Largest risks: recovery/auth concurrency, streaming behavior during OS suspension, maintaining strict memory boundaries across devices, shared provider quota, platform accessibility, store AI/privacy requirements, and limited verified asset provenance. Mitigate each with an early prototype/test or named owner; adding voice, offline writes or payments requires a revised estimate.

## 13. Prioritized implementation backlog

**P0 — Before native account access**

1. Verify the implemented R13-01 recovery and credential/session fixes with PostgreSQL race tests.
2. Verify the implemented R13-02/R13-03 memory-error propagation and aggregate context bounds in staging; reuse their regression cases for the future native client.
3. Establish staged API version/schema and native token threat model; retain browser protections.
4. Add operation IDs, idempotency and durable turn ownership; specify reconciliation after uncertainty.
5. Prove physical-device streaming/auth/revocation on the chosen framework/toolchain.

**P1 — Required MVP / store delivery**

6. Implement native shell, approved artwork/tokens, accessible keyboard-safe chat and history.
7. Implement memory/goals/Today/account parity and bounded account-isolated storage.
8. Add AI-sharing consent distinct from automatic learning; export/deletion and local purge.
9. Implement AI response reporting and an owned support/triage workflow; external deletion resource.
10. Add full device lifecycle/security tests, source-linked quality artifacts, signed builds and monitoring.
11. Complete store metadata, SDK/privacy declarations, beta requirements and controlled rollout.

**P2 — After observed demand**

Push reminders/background completion, biometric app lock, tablet optimization, localization/RTL, widgets, attachments, voice and selected integrations. Ask My Team should remain off until its own interaction/cost/failure design is approved. Payments require a separate product and policy phase.

## 14. Owner decisions and first milestone

Owner decisions: account mode and email-identity/support policy; automatic-memory default and AI-sharing consent wording; target countries/ages/languages; minimum OS/device coverage; hosting/provider budget and expected beta cohort; retention/offline-cache policy; asset rights; signing-account ownership; analytics/crash-reporting vendor or no vendor; and whether paid features are in a later release. Record decisions rather than assuming them from the web implementation.

**Recommended first milestone:** after critical backend fixes, deliver a two-platform prototype that signs into a synthetic staging account, streams one Leo reply, loses connectivity mid-reply, reloads the authoritative partial result, retries without duplicate expenditure, and rejects the session after sign-out-everywhere. Include one private-memory isolation check at the actual provider input. This is the smallest useful test of the architectural risks before investing in the complete native UI.

At its review, choose the final framework/toolchain, approve the native auth/operation contracts, revise estimates using measured work, and only then begin the full mobile MVP. No part of this roadmap is evidence that native features are already implemented.
