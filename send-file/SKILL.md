---
name: send-file
description: >-
  Get a file from this machine onto the user's other device (phone, laptop) or to another
  person. Use whenever the user says "send me this file", "give me the file", "download this",
  "I want this on my phone", "pass this to <someone>", "share the file", "傳給我",
  "把檔案傳到手機", "我要下載" — or whenever YOU have just produced a file (report, archive,
  image, build) the user needs somewhere other than this shell. Streams it through the ppng.io
  piping-server relay and hands back an ASCII QR + clickable URL + receiving curl. Do NOT spin up
  `python -m http.server`, upload to transfer.sh / a pastebin, or commit the file just to move it —
  this is the house method. Encrypt sensitive content first. Also covers showing a file locally
  on macOS (Quick Look).
user-invocable: true
allowed-tools:
  - Bash(curl *)
  - Bash(openssl rand *)
  - Bash(qrencode *)
  - Bash(command qrencode *)
  - Bash(uvx --from qrcode *)
  - Bash(kill *)
  - Bash(jobs *)
  - Bash(qlmanage *)
  - Bash(ls *)
  - Bash(stat *)
  - Bash(file *)
  - Bash(age *)
  - Bash(gpg *)
  - Bash(7z *)
---

# send-file — get a file to the user's other device, or to another person

The user wants a file that lives on **this** machine to end up **somewhere else** — on their
phone, on a laptop, in a colleague's hands — and this machine is one the recipient can't just
`scp` from (a headless server, a Pi, a remote session behind NAT).

The reflex is to stand up a throwaway web server (`python -m http.server`), push to
`transfer.sh` / a pastebin, or `git add` the file just to shuttle it. Don't. Pipe it through the
hosted **piping-server** relay at **ppng.io**: no account, nothing persisted, the transfer streams
directly sender→receiver with backpressure, and it punches through NAT because both ends make
outbound HTTPS connections to the shared relay.

> **First, is the recipient the user themselves, on a device this runner can already reach?**
> If your runner has a native "put this file in front of the user" channel (a file-to-user tool,
> an attachment mechanism), that is the better path for the user's *own* devices — use it. ppng.io
> is for: another person, a device with no such channel, or when no native channel exists.

## How the relay works

`ppng.io` is a public [piping-server](https://github.com/nwtgck/piping-server) instance. You
`PUT`/`POST` bytes to a path and someone else `GET`s the **same path**; the server holds neither
end's data — it blocks the sender until a receiver connects, then streams through. The **path is
the only secret**. There is no auth, no listing, no storage.

That has three consequences that drive everything below:

1. **Generate a long random path.** A guessable name (`file`, `report`, the filename) can be
   raced by anyone. Use `openssl rand -hex 16`.
2. **Single use, one receiver.** The path is consumed when the receiver connects. A second pull
   gets nothing; to send again, generate a new path.
3. **No confidentiality at the relay.** It's a shared public server — treat the bytes as visible
   in transit. For anything sensitive, **encrypt before sending** (see below), or point the user
   at **piping-ui.org** (same server family, browser E2E encryption).

## Sending

```sh
curl -T <file> "https://ppng.io/$(openssl rand -hex 16)"
```

The command **blocks until the receiver connects** — it is the live pipe, not a queued upload. So:

1. **Run it in the background** and capture the URL first, because the URL is what the user needs
   *before* anyone can pull:

   ```sh
   URL="https://ppng.io/$(openssl rand -hex 16)"
   curl -T <file> "$URL" >/dev/null 2>&1 &      # blocks in the background until pulled
   echo "$URL"
   ```

2. **Hand the user all three outputs** (next section), then wait. Tell them the pipe is live and
   one-shot.

3. **If nobody ever connects, kill it** — don't leave a resident `curl` holding the pipe. Track the
   job (`jobs`, or the `$!` PID) and `kill` it if the user says the handoff is done or abandoned.

## What to hand the user — always three outputs

The recipient may be a phone in the user's hand, a browser on another laptop, or a shell on a
server. Each wants the URL in a different form, so **always emit all three**, in this order:

### 1. An ASCII QR code of the URL

A phone camera scans it straight off the screen — no typing a 32-hex path. Generate it with
`qrencode`, escape-free so it pastes cleanly into a reply:

```sh
command qrencode -t UTF8 -o - "$URL"       # compact half-block UTF-8, NO ANSI colour escapes
```

- Use `command qrencode` to bypass any shell alias (a common one is `qrencode -t ansiutf8`, whose
  colour escapes garble a chat reply). `-t ANSIUTF8` is only right when the output goes straight to
  a terminal the user is watching. `-t ASCII` is the pure-ASCII fallback for fonts without block
  glyphs (bigger, but scans anywhere).
- **Put the QR inside a fenced code block** in your reply. A proportional font breaks the grid
  alignment and the code won't scan; monospace preserves it.
- **No `qrencode`?** Don't hand-roll one. Run the pure-Python CLI via uv, zero setup:
  `uvx --from qrcode qr --ascii "$URL"`. (Package install: `sudo apt install qrencode` /
  `brew install qrencode` — but the `uvx` path needs nothing, so prefer it over installing.)
- The QR *is* the URL, so it carries the same secret: anyone who photographs the screen can pull
  the file. Same single-use/one-receiver rule applies.

### 2. A clickable URL

The bare URL on its own line, as a link so it renders clickable in the reply — for a browser
recipient, opening it is the whole receive step.

### 3. The receiving `curl` command

For a shell recipient, with the real filename already filled in so it's copy-paste-runnable:

```sh
curl -o <file> "<url>"
```

## Sensitive content: encrypt first

The relay sees plaintext. If the file carries anything the user wouldn't post publicly, encrypt it
on this machine before it enters the pipe, and send the key/passphrase over a **different** channel
than the URL:

- **age** (recipient has a key): `age -r <recipient-pubkey> -o <file>.age <file>` → send `<file>.age`.
- **gpg** (symmetric passphrase): `gpg -c <file>` → send `<file>.gpg`, passphrase out-of-band.
- **password-protected 7z** (recipient on any OS, no crypto tooling): `7z a -p -mhe=on <file>.7z <file>`
  (`-mhe=on` encrypts the filenames too), passphrase out-of-band.
- Or hand the user **piping-ui.org** for browser-native E2E encryption over the same relay.

Never put the passphrase in the same message as the URL.

## Local recipient: the person at this machine (macOS)

If the "recipient" is the user sitting at *this* machine and it's a macOS box, they don't need the
network at all — pop the file in Quick Look:

```sh
qlmanage -p <files> >/dev/null 2>&1 &
```

Quick Look floats over the terminal, Esc dismisses, and multiple files give an arrow-key comparison
rail. Use `open <file>` instead only when the user should keep working in the file's app. This path
is **macOS-only** — guard on `qlmanage` being present; on Linux/headless there is no local viewer,
so fall back to the ppng.io network handoff above.

## Guardrails

- Long random path, always. Never a guessable name.
- URL to the user *before* the transfer can complete (sender blocks until pulled).
- All three outputs, every time: ASCII QR (in a fenced code block), clickable URL, receiving `curl`.
- One receiver, one use — regenerate the path to resend.
- Encrypt sensitive bytes before they touch the relay; key travels out-of-band.
- Kill an unpulled sender rather than leaving it resident.
