# What CrewAi stores about you

CrewAi is a personal assistant with a team of specialists that share what they
know about you. That only works because it remembers things — so this page says
exactly what it keeps, where that lives, and who can reach it.

Written for the person using it, not for a lawyer. If anything here is unclear,
assume the more cautious reading and ask.

## What it keeps

- **Your messages and the replies**, in full, for every specialist you talk to.
- **Facts it learns about you.** As you chat, CrewAi extracts durable personal
  facts — what you study, where you work, what you are training for, what you
  can afford, what you are avoiding. Some are shared across the whole team; some
  stay with one specialist.
- **Goals** you set, and **daily briefings** it generates.
- **Your account**: display name, email address, when you joined, and whether
  automatic learning is on.
- **Your password and recovery codes — never in readable form.** The password
  is stored as a scrypt hash and each recovery code as a SHA-256 hash; neither
  can be read back, by you or by the operator. A code is marked used once used.
- **Usage counters**: how many requests and roughly how many tokens your account
  has used, per minute and per day. These exist to stop one account exhausting
  the shared allowance. They record volume, never content. If a request fails
  before the model sends any text, it is not counted against you.
- **Sign-in attempt counters**: how many times someone tried to sign in or reset
  a password for an email address, and how many accounts were created from one
  network address, for up to an hour. They are stored as one-way hashes of the
  address, not the address itself, and exist to stop guessing.

Some of what it remembers is sensitive by nature — health, money, work. When
CrewAi recognises a fact as sensitive it does not store it automatically unless
the deployment has opted in (`MEMORY_STORE_SENSITIVE`). **Recognising it is best
effort**, not a guarantee: a health or money detail phrased in an ordinary way
can be saved as an ordinary fact. Everything stored is visible to you in Memory,
where you can edit or delete it — so it is worth a look now and then. Anything
you save yourself is stored exactly as you wrote it, sensitive or not.

## Where it lives

In one PostgreSQL database on the server running your deployment. Nothing is
sent to an analytics service, an advertiser, or a third party beyond the model
provider below.

**Backups** are encrypted with AES-256 and may be copied off the server. They
contain everything above. Restoring a backup restores your data as it was when
that backup was taken.

## Who can see it

- **You.**
- **Whoever runs the server.** They hold the database and the backup passphrase,
  so they can read anything in it. CrewAi is self-hosted: trust
  in the operator is part of the arrangement, and no software here changes that.
- **Your model provider.** To answer you, CrewAi sends the specialist's
  instructions, the relevant facts it remembers about you, the recent messages
  of that conversation (up to the last 40) and your new message to the
  configured provider — by default Groq. While automatic learning is on, a
  second, separate request sends your message again so the model can pick out
  any durable facts worth remembering; switch it off on your Account page and
  that second request is not made. Your message text and your personal context
  leave the server on every turn.
  What the provider does with it is governed by their terms, not this document.
- **Nobody else.** Other accounts on the same deployment cannot read your
  conversations, memories or goals; that isolation is enforced and tested.

## What CrewAi does not do

- No advertising, profiling for advertising, or selling data.
- No training of any model on your conversations by CrewAi itself.
- No sharing between accounts.
- No logging of your message content in server logs — logs record timings,
  status codes and error types only.

## Your control

| You want to | How |
|---|---|
| See what it remembers | Memory, in the app — every stored fact, editable |
| Stop it learning from your messages | Account → What Leo learns → switch off "Learn from my messages automatically". Nothing already saved is removed, and you can still save facts yourself |
| Correct or delete a single fact | Memory — edit or delete it. An edit is yours: CrewAi will not overwrite it automatically later |
| Delete one conversation | Open conversation history, then choose its delete button |
| Take everything with you | Account → Download my data — a JSON file, messages included |
| Delete everything | Account → Delete my account → type DELETE |
| Sign out every device | Account → Sign out every device |

**Deletion is immediate and irreversible.** It removes your account,
conversations, messages, memories, goals, briefings and usage counters from the
live database. It cannot reach backups already taken — those age out on the
backup retention schedule, 30 days by default.

## Sessions and access

You sign in with your email and password, or with an invitation key if the
operator gave you one. CrewAi stores only hashes of passwords, keys and recovery
codes, never the secrets themselves. A session is a signed, HttpOnly,
SameSite=Strict cookie that expires after seven days.

If you lose a device, sign out everywhere. If you forget your password, use one
of your recovery codes; that also signs out every other device. Changing your
password does the same. No email is ever sent, so there is no reset link: if you
lose your password and every recovery code, only the operator can let you back
in, after checking it is really you. If you think an invitation key has leaked,
tell the operator — it needs rotating, which signing out cannot do.

## Advice, and its limits

The specialists give guidance on finance, fitness, career and study. It is
generated by a language model. It can be wrong, out of date, or confidently
mistaken about your situation. **It is not medical, legal or financial advice**,
and no specialist is a substitute for a doctor, lawyer, accountant or
qualified professional. For anything with real consequences, check it.

## Changes

This deployment is self-hosted; whether anyone can sign up or only invited people
is the operator's setting. If what is stored or who can see it changes, the
operator should tell you before it takes effect.
