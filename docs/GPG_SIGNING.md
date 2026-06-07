# GPG Commit Signing Setup Guide

## Why Sign Commits?

- **Provenance**: GPG-signed commits prove the code actually came from you, not someone impersonating your identity.
- **Trust**: Teammates and reviewers can verify authorship cryptographically — no "is this really from Aaru?" doubt.
- **Verified Badge**: GitHub displays a **Verified** label next to each signed commit in the history, giving immediate visual confidence.
- **Impersonation Resistance**: Without signing, anyone can set their Git name/email to yours. GPG signing makes that spoofed commit fail verification.

---

## 1. Generate a GPG Key (Windows)

### Option A — Gpg4win (Recommended)

1. Download and install [Gpg4win](https://gnupg.org/download/).
2. During installation, select **GnuPG** and **Kleopatra** (the key manager GUI).
3. Open **Kleopatra** from the Start Menu.
4. Click **File → New Key Pair → Create a personal OpenPGP key pair**.
5. Fill in:
   - **Name**: your GitHub display name.
   - **Email**: `290474269+aaru-sh@users.noreply.github.com`
6. Click **Advanced Settings**:
   - **Key Type**: RSA
   - **Key Size**: 4096 bits
   - **Validity**: 2 years
7. Click **OK**, then **Create**.
8. Set a strong passphrase when prompted (you'll enter this when signing).
9. Optionally **send** the key to a keyserver, or skip — you'll add it to GitHub manually below.

### Option B — Git Bash / WSL

Open **Git Bash** (ships with Git for Windows) and run:

```bash
gpg --full-generate-key
```

Select prompts:

```
Your selection? 1            # RSA and RSA
What keysize do you want? 4096
Key is valid for? 2y         # 2 years
Is this correct? Y

Real name: <your-name>
Email address: 290474269+aaru-sh@users.noreply.github.com
Comment: (optional, e.g. "GitHub Signing Key")
Change (N)ame, (E)mail, or (O)kay/(Q)uit? O

Enter passphrase: **********
```

### Key Renewal Reminder

Keys set to expire after 2 years will stop working on GitHub after expiry. Set a calendar reminder 30 days before expiry to:

```bash
gpg --edit-key <key-id>
expire
# follow prompts to extend
save
```

---

## 2. Add the GPG Key to GitHub

### Find your key ID

```bash
gpg --list-secret-keys --keyid-format=long
```

Output looks like:

```
sec   rsa4096/ABCD1234EFGH5678 2025-01-15 [SC] [expires: 2027-01-15]
      AABBCCDDEEFF0011223344556677889900AABBCC
uid                 [ultimate] Your Name <290474269+aaru-sh@users.noreply.github.com>
ssb   rsa4096/1234ABCD5678EFGH 2025-01-15 [E] [expires: 2027-01-15]
```

The key ID is the 16-character hex string after `rsa4096/` on the `sec` line — in this example `ABCD1234EFGH5678`.

### Export the public key

```bash
gpg --armor --export ABCD1234EFGH5678
```

Copy the entire block including `-----BEGIN PGP PUBLIC KEY BLOCK-----` and `-----END PGP PUBLIC KEY BLOCK-----`.

### Add to GitHub

1. Go to [github.com/settings/keys](https://github.com/settings/keys).
2. Click **New GPG key**.
3. Paste the exported public key block.
4. Click **Add GPG key**.

---

## 3. Configure Git to Use the Key

Set these globally so every commit in every repo is signed by default:

```bash
# Tell Git which key to use
git config --global user.signingkey ABCD1234EFGH5678

# Sign all commits by default
git config --global commit.gpgsign true

# Point to the Gpg4win gpg binary (standard install path)
git config --global gpg.program "C:\Program Files (x86)\GnuPG\bin\gpg.exe"
```

Verify the configuration:

```bash
git config --global user.signingkey
git config --global commit.gpgsign
git config --global gpg.program
```

---

## 4. Verify It Works

Create a test commit and inspect the signature:

```bash
git commit --allow-empty -S -m "test: verify GPG signing"
```

The `-S` flag forces signing. You'll be prompted for your GPG passphrase.

Check the signature:

```bash
git log --show-signature -1
```

Expected output:

```
gpg: Signature made Sat 05 Jul 2025 14:30:00 AM IST
gpg:                using RSA key AABBCCDDEEFF0011223344556677889900AABBCC
gpg: Good signature from "Your Name <290474269+aaru-sh@users.noreply.github.com>" [ultimate]
commit ...
Author: ...
```

The key line is **Good signature** — this confirms everything is working. You can now `git push` and see the **Verified** badge on GitHub.

---

## 5. Troubleshooting Windows Issues

### gpg-agent not running

```bash
gpg-agent --daemon
```

Or restart it:

```bash
gpgconf --kill gpg-agent
gpg-agent --daemon
```

### "gpg: signing failed: Inappropriate ioctl for device"

This means the passphrase prompt can't display. Fix:

```bash
# Use a pinentry program (Gpg4win includes pinentry-mac or pinentry.exe)
git config --global gpg.program "C:\Program Files (x86)\GnuPG\bin\gpg.exe"
# Pinentry should already be configured in gpg-agent.conf — see Section 6
```

### "error: gpg failed to sign the data"

Common causes:
- Wrong key ID — double-check with `gpg --list-secret-keys --keyid-format=long`.
- Key not on GitHub — re-export and re-add.
- gpg.exe not found — verify the path with `where gpg` in PowerShell or `which gpg` in Git Bash.

### Passphrase prompt not appearing

Gpg4win ships with `pinentry.exe` but it may not be configured. Edit (or create) `%APPDATA%\gnupg\gpg-agent.conf`:

```
pinentry-program "C:\Program Files (x86)\GnuPG\bin\pinentry.exe"
```

Then restart the agent:

```bash
gpgconf --kill gpg-agent
gpg-agent --daemon
```

---

## 6. Optional: gpg-agent for Passphrase Caching

Typing your GPG passphrase on every commit is tedious. Configure `gpg-agent` to cache it for a few hours.

Edit or create `%APPDATA%\gnupg\gpg-agent.conf`:

```
# Cache passphrase for 8 hours (28800 seconds)
default-cache-ttl 28800
max-cache-ttl 28800

# Use the Windows pinentry dialog
pinentry-program "C:\Program Files (x86)\GnuPG\bin\pinentry.exe"
```

Restart the agent:

```bash
gpgconf --kill gpg-agent
gpg-agent --daemon
```

The first commit after restarting will prompt for your passphrase. Subsequent commits within the cache window will use the cached passphrase automatically.

### Clear the cache manually

```bash
gpgconf --kill gpg-agent
gpg-agent --daemon
```

---

## Quick Reference

| Task | Command |
|---|---|
| List secret keys | `gpg --list-secret-keys --keyid-format=long` |
| Export public key | `gpg --armor --export <key-id>` |
| Import someone's key | `gpg --import <file>` |
| Verify a signed commit | `git log --show-signature -1` |
| Force-sign a single commit | `git commit -S -m "msg"` |
| Enable global signing | `git config --global commit.gpgsign true` |
| Set signing key | `git config --global user.signingkey <key-id>` |
| Set gpg binary (Windows) | `git config --global gpg.program "C:\Program Files (x86)\GnuPG\bin\gpg.exe"` |
| Restart gpg-agent | `gpgconf --kill gpg-agent && gpg-agent --daemon` |
