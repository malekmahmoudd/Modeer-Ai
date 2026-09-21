# Current agent names — 2026-09-15

CrewAi is the product; Leo is its personal manager and team leader.

The product was renamed from Modeer to CrewAi on September 15. Public branding,
browser metadata/icon, API title, privacy copy and operator alert labels use CrewAi.
Legacy `modeer` database names, session cookies, environment-variable prefixes,
routes and backup filenames remain compatible with existing installations.
The repository directory and old verification artifacts are not renamed.

- `modeer`: Leo — personal manager
- `research`: Clara — research
- `shopping`: Nate — shopping
- `study`: Nova — study
- `career`: Harvey — career
- `travel`: Tessa — travel
- `finance`: Emma — finance
- `writing`: Alex — writing
- `email`: Nora — email
- `fitness`: Maddie — fitness

The backend registry is the source of display names. Frontend panels, chat
authors, memory pickers and briefings read those names. Hero/onboarding/account
copy, portrait descriptions and cross-agent prompt references use the new names.
A prompt directory lists each teammate's name and role so redirects stay clear.

Stable slugs, routes, database ownership keys, asset paths and internal component
identifiers are preserved. No conversation or memory migration is required.
The normal backend startup synchronizes display names into existing agent rows;
restart the backend and serve the rebuilt frontend to apply the change to a
running installation. Do not create replacement agents or rewrite chat history.

All ten prompt versions increased. Historical reviews, screenshots, presentation
exports and quality results remain evidence of their original versions, not
proof of the renamed prompts' live quality. Future presentations should use this
roster. Character artwork, page styling and model settings are unchanged; the product favicon now uses C.

Verification: 351 backend tests passed; Ruff passed; frontend production build
and type checking passed; frontend lint has zero errors and 12 existing warnings.
Provider-input privacy checks were updated for the new names and pass. No live
provider calls or deployment were performed for this rename.
