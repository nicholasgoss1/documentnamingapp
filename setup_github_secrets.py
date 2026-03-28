#!/usr/bin/env python3
"""
Run once to see what GitHub Secrets to add.
Follow the printed instructions.
"""
from pathlib import Path

groq_path = Path("C:/Projects/Groq API key.txt")
token_path = Path("C:/Projects/GitHub sync token.txt")

print("=" * 60)
print("ADD THESE SECRETS TO GITHUB:")
print()
print("Go to:")
print("github.com/nicholasgoss1/documentnamingapp")
print("/settings/secrets/actions")
print()
print("Click 'New repository secret' for each one below:")
print("=" * 60)

print()
print("SECRET 1:")
print("  Name:  GROQ_API_KEY")
if groq_path.exists():
    key = groq_path.read_text().strip()
    print(f"  Value: (contents of {groq_path})")
    print(f"         starts with: {key[:12]}...")
else:
    print("  Value: your Groq key from console.groq.com/keys")

print()
print("SECRET 2:")
print("  Name:  SYNC_TOKEN")
if token_path.exists():
    tok = token_path.read_text().strip()
    print(f"  Value: (contents of {token_path})")
    print(f"         starts with: {tok[:16]}...")
else:
    print("  Value: your GitHub PAT from")
    print("         github.com/settings/tokens")

print()
print("=" * 60)
print("FIXED DOWNLOAD URL (for new staff / fresh installs):")
print()
print("https://github.com/nicholasgoss1/documentnamingapp"
      "/releases/latest/download/"
      "ClaimsCo_Tools_Setup_latest.exe")
print()
print("Existing staff never need this — they get AI")
print("improvements silently on every app open.")
print("Only needed for: new staff, fresh installs,")
print("or when an App Update release is published.")
print("=" * 60)
