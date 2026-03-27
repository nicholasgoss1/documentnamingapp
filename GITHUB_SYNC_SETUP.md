# GitHub Corrections Sync Setup

## What this does

Every correction staff make is silently pushed to the
corrections-sync branch on GitHub. Nick's machine pulls
all corrections once per day and improves the AI automatically.
Staff see nothing at any point.

## One-time setup (Nick only)

1. Generate a GitHub Personal Access Token:
   - Go to github.com/settings/tokens
   - Click "Generate new token" (fine-grained)
   - Repository access: Only select repositories
     → select documentnamingapp
   - Permissions: Contents → Read and write
   - Generate token, copy it immediately
   - Save to C:/Projects/GitHub sync token.txt

2. Copy the token file to each staff machine at:
   C:/Projects/GitHub sync token.txt
   OR %LOCALAPPDATA%\ClaimFileRenamer\github_token.txt

   The easiest way is to include the token file in the
   app installer so it is placed automatically on install.
   See "Bundling the token in the installer" below.

3. That is it. On first run the app creates the
   corrections-sync branch automatically.

## Bundling the token in the installer (recommended)

Add the token file to build.spec datas:
```
('C:/Projects/GitHub sync token.txt', '.')
```

The app copies it to %LOCALAPPDATA%\ClaimFileRenamer\ on
first run if not already present at C:/Projects/.

This way staff machines get the token automatically when
they install the app — no manual setup per machine.

## Checking it works

Make a test correction in the app.
Wait 30 seconds.
Go to github.com/nicholasgoss1/documentnamingapp/tree/corrections-sync
You should see a corrections/ folder containing:
  corrections_[COMPUTERNAME].json

## What staff see: Nothing.

## Token security note

The token only has write access to this one repository.
It cannot access any other GitHub resources.
If the token is ever compromised, go to
github.com/settings/tokens and revoke it, generate a new one,
and update C:/Projects/GitHub sync token.txt then rebuild
the installer.
