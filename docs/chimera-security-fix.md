# Chimera Security Fix: API Key Management

## Problem
app/build.gradle.kts embeds API keys as buildConfigField strings. These compile into the APK and are trivially extractable via:
- jadx (decompiler)
- strings command (raw string extraction)
- apktool + smali inspection

## Solution: Runtime Injection + EncryptedSharedPreferences

### Step 1: Remove buildConfigField keys from app/build.gradle.kts

Delete these lines:


Keep only non-secret flags like DEMO_MODE.

### Step 2: Create SecureKeyStore wrapper



### Step 3: Add dependency



### Step 4: CI injection via local.properties



### Step 5: Runtime loader in Application class



## Verification Checklist
- [ ] APK strings analysis shows no API keys
- [ ] CI build still injects keys for functional tests
- [ ] EncryptedSharedPreferences master key auto-backup disabled
- [ ] local.properties added to .gitignore
