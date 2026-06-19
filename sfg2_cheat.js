'use strict';

// ═══════════════════════════════════════════════
//  SFG2 MOD MENU v2.0  |  Frida Gadget Script
//  Offline Only: NoRecoil · AntiFlash · NoSpread
//                NoSway · FastReload · UnlimitedAmmo
// ═══════════════════════════════════════════════

var features = {
    noRecoil:      false,
    antiFlash:     false,
    noSpread:      false,
    noSway:        false,
    fastReload:    false,
    unlimitedAmmo: false
};

var menuCreated = false;

// ── Helpers ─────────────────────────────────────

function findExport(name) {
    try {
        var mod = Process.getModuleByName("libUE4.so");
        var list = mod.enumerateExports();
        for (var i = 0; i < list.length; i++) {
            if (list[i].name === name) return list[i].address;
        }
    } catch(e) {}
    return null;
}

function findAny(names) {
    for (var i = 0; i < names.length; i++) {
        var a = findExport(names[i]);
        if (a) return { addr: a, name: names[i] };
    }
    return null;
}

// Hook a float-returning method: return 0.0 when feature ON, call original otherwise
function hookFloat(names, key) {
    var r = findAny(names);
    if (!r) { console.log("[-] " + key + ": not found"); return; }
    var orig = new NativeFunction(r.addr, 'float', ['pointer']);
    Interceptor.replace(r.addr, new NativeCallback(function(self) {
        return features[key] ? 0.0 : orig(self);
    }, 'float', ['pointer']));
    console.log("[+] " + key + ": " + r.name);
}

// ── Native Hooks ────────────────────────────────

// 1. No Recoil — confirmed: _ZN4AMan9GetRecoilEv exists
hookFloat([
    "_ZN4AMan9GetRecoilEv",
    "_ZN7AWeapon9GetRecoilEv"
], "noRecoil");

// 2. Anti-Flashbang — confirmed: _ZN4AMan5FlashEf exists
(function() {
    var names = [
        "_ZN4AMan5FlashEf",
        "_ZN19AMyPlayerController5FlashEf",
        "_ZN19AMyPlayerController20Flash_ImplementationEf"
    ];
    for (var i = 0; i < names.length; i++) {
        (function(n) {
            var addr = findExport(n);
            if (!addr) return;
            try {
                var orig = new NativeFunction(addr, 'void', ['pointer', 'float']);
                Interceptor.replace(addr, new NativeCallback(function(self, t) {
                    if (!features.antiFlash) orig(self, t);
                }, 'void', ['pointer', 'float']));
                console.log("[+] antiFlash: " + n);
            } catch(e) { console.log("[!] antiFlash error " + n + ": " + e.message); }
        })(names[i]);
    }
})();

// 3. No Bullet Spread
// WeaponSpread/ZoomSpread are UProperties (not exported functions).
// Best-effort: try any getter-style exports that may exist in this APK's build.
hookFloat([
    "_ZN7AWeapon9GetSpreadEv",
    "_ZN7AWeapon14GetWeaponSpreadEv",
    "_ZN14AShotgunWeapon9GetSpreadEv",
    "_ZN4AMan9GetSpreadEv",
    "_ZN7AWeapon13GetSpreadAngleEv",
    "_ZN7AWeapon20GetCurrentSpreadAngleEv",
    "_ZN7AWeapon18GetBulletSpreadAngleEv"
], "noSpread");

// 4. No Sway
// ManSpread/PlayerSpread are UProperties — same best-effort approach.
hookFloat([
    "_ZN4AMan7GetSwayEv",
    "_ZN7AWeapon7GetSwayEv",
    "_ZN7AWeapon11GetWeaponSwayEv",
    "_ZN19AMyPlayerController7GetSwayEv",
    "_ZN4AMan12GetWeaponSwayEv"
], "noSway");

// 5. Fast Reload
// Confirmed: _ZN7AWeapon11StartReloadEv and _ZN7AWeapon9EndReloadEv both exist.
// Strategy: call original StartReload, then immediately call EndReload on the same
// weapon object so the engine sees a completed reload cycle instantly.
(function() {
    var startAddr = findExport("_ZN7AWeapon11StartReloadEv");
    var endAddr   = findExport("_ZN7AWeapon9EndReloadEv");

    if (!startAddr) { console.log("[-] fastReload: StartReload not found"); return; }
    if (!endAddr)   { console.log("[-] fastReload: EndReload not found"); return; }

    var origStart = new NativeFunction(startAddr, 'void', ['pointer']);
    var callEnd   = new NativeFunction(endAddr,   'void', ['pointer']);

    // Guard prevents EndReload from re-entering StartReload via engine callbacks
    var inFastReload = false;

    Interceptor.replace(startAddr, new NativeCallback(function(self) {
        if (!features.fastReload || inFastReload) {
            origStart(self);
            return;
        }
        inFastReload = true;
        origStart(self);
        callEnd(self);
        inFastReload = false;
    }, 'void', ['pointer']));

    console.log("[+] fastReload: StartReload + EndReload hooked");
})();

// 6. Unlimited Ammo
// Confirmed: _ZN7AWeapon4FireEv and _ZN7AWeapon8FullAmmoEv both exist.
// Strategy: wrap Fire() — after each real shot, call FullAmmo() on the same weapon
// object to instantly refill. Falls back to blocking the consume call if FullAmmo
// is missing in a particular APK variant.
(function() {
    var fireAddr     = findExport("_ZN7AWeapon4FireEv");
    var fullAmmoAddr = findExport("_ZN7AWeapon8FullAmmoEv");

    if (!fireAddr) { console.log("[-] unlimitedAmmo: Fire not found"); return; }

    if (fullAmmoAddr) {
        var origFire = new NativeFunction(fireAddr,     'void', ['pointer']);
        var fullAmmo = new NativeFunction(fullAmmoAddr, 'void', ['pointer']);

        Interceptor.replace(fireAddr, new NativeCallback(function(self) {
            origFire(self);
            if (features.unlimitedAmmo) fullAmmo(self);
        }, 'void', ['pointer']));

        console.log("[+] unlimitedAmmo: Fire + FullAmmo hooked");
        return;
    }

    // Fallback: block ammo-consumption call
    console.log("[~] unlimitedAmmo: FullAmmo not found, trying consume-block");
    var consumeR = findAny([
        "_ZN7AWeapon8UseAmmoEi",
        "_ZN7AWeapon11ConsumeAmmoEi",
        "_ZN4AMan8UseAmmoEi",
        "_ZN7AWeapon14DecrementAmmoEv",
        "_ZN7AWeapon13SpendAmmunitionEv"
    ]);
    if (consumeR) {
        var origC = new NativeFunction(consumeR.addr, 'void', ['pointer', 'int']);
        Interceptor.replace(consumeR.addr, new NativeCallback(function(self, n) {
            if (!features.unlimitedAmmo) origC(self, n);
        }, 'void', ['pointer', 'int']));
        console.log("[+] unlimitedAmmo (consume-block): " + consumeR.name);
    } else {
        console.log("[-] unlimitedAmmo: no method found");
    }
})();

// ── Mod Menu UI ─────────────────────────────────

if (Java.available) {
    Java.perform(function() {
        // UE4 on Android uses GameActivity, not the base Activity class.
        // Try the UE4 class first and fall back gracefully.
        var actClass = "com.epicgames.ue4.GameActivity";
        var Activity;
        try {
            Activity = Java.use(actClass);
        } catch(e) {
            actClass  = "android.app.Activity";
            Activity  = Java.use(actClass);
        }
        console.log("[+] UI hook: " + actClass + ".onResume");

        Activity.onResume.implementation = function() {
            this.onResume();
            if (!menuCreated) {
                menuCreated = true;
                var act = this;
                act.runOnUiThread(Java.runnable(function() {
                    try { buildMenu(act); }
                    catch(e) { console.log("[!] buildMenu: " + e); }
                }));
            }
        };
    });
}

function buildMenu(activity) {
    Java.perform(function() {

        var LL   = Java.use("android.widget.LinearLayout");
        var FL   = Java.use("android.widget.FrameLayout");
        var TV   = Java.use("android.widget.TextView");
        var BTN  = Java.use("android.widget.Button");
        var VIEW = Java.use("android.view.View");
        var GD   = Java.use("android.graphics.drawable.GradientDrawable");
        var TF   = Java.use("android.graphics.Typeface");
        var FLLP = Java.use("android.widget.FrameLayout$LayoutParams");
        var LLLP = Java.use("android.widget.LinearLayout$LayoutParams");

        var density = activity.getResources().getDisplayMetrics().density.value;
        function dp(v) { return Math.round(v * density); }

        var MATCH = -1, WRAP = -2;
        var decor = Java.cast(activity.getWindow().getDecorView(), FL);

        // ── Panel container ──────────────────────
        var panel = LL.$new(activity);
        panel.setOrientation(1); // VERTICAL

        var pBg = GD.$new();
        pBg.setShape(0);
        pBg.setCornerRadius(dp(16));
        pBg.setColor(0xEE080816);
        pBg.setStroke(dp(2), 0xFFFF2D55);
        panel.setBackground(pBg);
        panel.setPadding(dp(12), dp(10), dp(12), dp(14));
        panel.setMinimumWidth(dp(200));

        // ── Header row (drag handle) ─────────────
        var hRow = LL.$new(activity);
        hRow.setOrientation(0); // HORIZONTAL
        hRow.setGravity(0x10);  // CENTER_VERTICAL

        var accentDot = VIEW.$new(activity);
        var adBg = GD.$new();
        adBg.setShape(1); // OVAL
        adBg.setColor(0xFFFF2D55);
        accentDot.setBackground(adBg);
        var adLP = LLLP.$new(dp(9), dp(9));
        adLP.setMargins(0, 0, dp(8), 0);
        hRow.addView(accentDot, adLP);

        var titleTv = TV.$new(activity);
        titleTv.setText("SFG2 MOD MENU");
        titleTv.setTextColor(0xFFFFFFFF);
        titleTv.setTextSize(14.0);
        titleTv.setTypeface(TF.DEFAULT_BOLD.value);
        hRow.addView(titleTv, LLLP.$new(WRAP, WRAP, 1.0));

        var minBtn = BTN.$new(activity);
        minBtn.setText("−"); // − minus sign
        minBtn.setTextColor(0xFFFFFFFF);
        minBtn.setTextSize(17.0);
        var minBg = GD.$new();
        minBg.setShape(1);
        minBg.setColor(0xFFFF2D55);
        minBtn.setBackground(minBg);
        minBtn.setPadding(0, 0, 0, 0);
        hRow.addView(minBtn, LLLP.$new(dp(30), dp(30)));

        var hRowLP = LLLP.$new(MATCH, WRAP);
        hRowLP.setMargins(0, 0, 0, dp(8));
        panel.addView(hRow, hRowLP);

        // Divider
        var line = VIEW.$new(activity);
        line.setBackgroundColor(0x44FF2D55);
        var lineLP = LLLP.$new(MATCH, dp(1));
        lineLP.setMargins(0, 0, 0, dp(8));
        panel.addView(line, lineLP);

        // ── Feature toggle rows ──────────────────
        var defs = [
            { key: "noRecoil",      label: "No Recoil" },
            { key: "antiFlash",     label: "Anti-Flashbang" },
            { key: "noSpread",      label: "No Bullet Spread" },
            { key: "noSway",        label: "No Sway" },
            { key: "fastReload",    label: "Fast Reload" },
            { key: "unlimitedAmmo", label: "Unlimited Ammo" }
        ];

        for (var i = 0; i < defs.length; i++) {
            (function(d) {
                var row = LL.$new(activity);
                row.setOrientation(0);
                row.setGravity(0x10);
                row.setPadding(dp(8), dp(5), dp(8), dp(5));

                var rBg = GD.$new();
                rBg.setShape(0);
                rBg.setCornerRadius(dp(8));
                rBg.setColor(0x1AFFFFFF);
                row.setBackground(rBg);

                var lbl = TV.$new(activity);
                lbl.setText(d.label);
                lbl.setTextColor(0xFFCCCCCC);
                lbl.setTextSize(12.0);
                row.addView(lbl, LLLP.$new(WRAP, WRAP, 1.0));

                var togBg = GD.$new();
                togBg.setShape(0);
                togBg.setCornerRadius(dp(10));
                togBg.setColor(0xFF3A3A3A);

                var tog = BTN.$new(activity);
                tog.setText("OFF");
                tog.setTextSize(10.0);
                tog.setTextColor(0xFFFFFFFF);
                tog.setTypeface(TF.DEFAULT_BOLD.value);
                tog.setBackground(togBg);
                tog.setPadding(dp(12), dp(2), dp(12), dp(2));

                tog.setOnClickListener({
                    onClick: function(v) {
                        features[d.key] = !features[d.key];
                        var on = features[d.key];
                        tog.setText(on ? "ON" : "OFF");
                        togBg.setColor(on ? 0xFF00C853 : 0xFF3A3A3A);
                        console.log("[MOD] " + d.key + " = " + on);
                    }
                });

                row.addView(tog, LLLP.$new(WRAP, WRAP));

                var rowLP = LLLP.$new(MATCH, WRAP);
                rowLP.setMargins(0, 0, 0, dp(4));
                panel.addView(row, rowLP);
            })(defs[i]);
        }

        // Version footer
        var verTv = TV.$new(activity);
        verTv.setText("v2.0  •  Offline Only");
        verTv.setTextColor(0x55FFFFFF);
        verTv.setTextSize(9.0);
        verTv.setGravity(1); // CENTER_HORIZONTAL
        var verLP = LLLP.$new(MATCH, WRAP);
        verLP.setMargins(0, dp(6), 0, 0);
        panel.addView(verTv, verLP);

        // Add panel to DecorView (top-left, below status bar)
        var panelFLP = FLLP.$new(WRAP, WRAP);
        panelFLP.setMargins(dp(16), dp(90), 0, 0);
        decor.addView(panel, panelFLP);

        // ── Mini "M" restore button ──────────────
        var dot = BTN.$new(activity);
        dot.setText("M");
        dot.setTextColor(0xFFFFFFFF);
        dot.setTextSize(13.0);
        dot.setTypeface(TF.DEFAULT_BOLD.value);
        var dotBg = GD.$new();
        dotBg.setShape(1);
        dotBg.setColor(0xCCFF2D55);
        dot.setBackground(dotBg);

        var dotFLP = FLLP.$new(dp(44), dp(44));
        dotFLP.setMargins(dp(10), dp(90), 0, 0);
        dot.setVisibility(8); // GONE initially
        decor.addView(dot, dotFLP);

        // ── Drag logic ───────────────────────────
        var dragX = [0.0], dragY = [0.0];

        hRow.setOnTouchListener({
            onTouch: function(v, ev) {
                var a = ev.getAction();
                if (a === 0) { // ACTION_DOWN
                    dragX[0] = ev.getRawX();
                    dragY[0] = ev.getRawY();
                    return true;
                }
                if (a === 2) { // ACTION_MOVE
                    var dx = Math.round(ev.getRawX() - dragX[0]);
                    var dy = Math.round(ev.getRawY() - dragY[0]);
                    panelFLP.setMargins(
                        panelFLP.leftMargin.value + dx,
                        panelFLP.topMargin.value  + dy,
                        0, 0
                    );
                    panel.setLayoutParams(panelFLP);
                    dragX[0] = ev.getRawX();
                    dragY[0] = ev.getRawY();
                    return true;
                }
                return false;
            }
        });

        // ── Hide / show ──────────────────────────
        minBtn.setOnClickListener({
            onClick: function(v) {
                panel.setVisibility(8); // GONE
                dot.setVisibility(0);   // VISIBLE
            }
        });

        dot.setOnClickListener({
            onClick: function(v) {
                dot.setVisibility(8);   // GONE
                panel.setVisibility(0); // VISIBLE
            }
        });

        console.log("[+] SFG2 Mod Menu v2.0 ready! Drag header to reposition.");
    });
}
