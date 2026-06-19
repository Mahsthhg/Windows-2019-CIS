import lief

print("[*] Loading libUE4.so (may take a moment for 121MB file)...")
lib = lief.parse(r"C:\jadx_out\resources\lib\arm64-v8a\libUE4.so")
print(f"[*] Loaded. Scanning {len(lib.exported_symbols)} exports...\n")

keywords = [
    "Spread", "spread",
    "Sway",   "sway",
    "Ammo",   "ammo",
    "Reload", "reload",
    "Recoil", "recoil",
    "Flash",  "flash",
    "Weapon", "weapon",
    "Bullet", "bullet",
    "Fire",   "fire",
    "Shot",   "shot",
    "Clip",   "clip",
    "Mag",    "mag",
    "Aim",    "aim",
    "AMan",   "AWeapon",
    "ABase",  "AGun",
    "GetV",   "SetV",
]

matches = []
for sym in lib.exported_symbols:
    name = sym.name
    for kw in keywords:
        if kw in name:
            matches.append(name)
            break

matches.sort()
print(f"[+] Found {len(matches)} relevant exports:\n")
for m in matches:
    print(m)

print(f"\n[*] Done. Total: {len(matches)} matches.")
