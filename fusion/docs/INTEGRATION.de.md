# Integration mit dem Fusion-Launcher

Stand: 31. Oktober 2026. Der Proton-Fork liegt dauerhaft unter
`/home/tobias/Projekte/Proton-Fusion`, der Launcher unter
`/home/tobias/Projekte/fusion-linux-dx11`. Aktive Laufzeiten liegen getrennt von
den Quellen unter `~/.local/share/fusion-linux-dx11/runtimes/Proton-Fusion`.
Build-Dateien bleiben in `.build`, lokale Protokolle und Test-Prefixes in `.local`
des Proton-Projekts. Beide Verzeichnisse sind von Git ausgeschlossen.

## Welche bisherigen Workarounds wohin gehören

| Bisherige Integration | Neue Zuständigkeit | Ergebnis |
|---|---|---|
| Vulkan-Sync-Layer | Wine-X11-Treiber: XDamage-Repaint | Der Launcher lädt den Layer nicht mehr und entfernt einen geerbten Fusion-Layer-Eintrag. Andere Vulkan-Layer bleiben erhalten. |
| `panel-fix.exe`, regelmäßiges Aufzählen der Fenster und `WS_EX_APPWINDOW`-Änderungen | Wine-X11-Fensterklassifikation bei Fensterereignissen | Bekannte persistente Qt-Panels werden direkt verwaltet. Kleine HUDs und fremde Klassen bleiben ausgenommen; die Win32-Stile bleiben unverändert. |
| `bcp47langs=` deaktivieren | Wine `bcp47langs.GetUserLanguages` | Liefert die geordnete bevorzugte UI-Sprachliste als HSTRING mit dem gewünschten Trennzeichen; der leere Erfolgs-Stub entfällt. |
| ICU-/Compiler-DLL-Präferenzen, Xalia-/AT-Bridge-Abschaltung, DXVK-Standardwerte | `fusion/profile.py` und `fusion/dxvk.conf` im Proton-Paket | Ein Profil wird vor der Wine-Initialisierung angewendet. Benutzerdefinierte Einstellungen werden berücksichtigt. |
| Große nicht fokussierbare Phantom-Dialoge ausblenden (`window-fix.py`) | Weiterhin Launcher, vorerst | Der bisherige Filter beruht auf X11-Titel, Dialogtyp, Fokus-Hinweisen und Größenverhältnis. Ohne eindeutige Win32-Identität oder eigenen Reproducer würde eine pauschale Übernahme in Wine auch echte Dialoge riskieren. |
| Browser-/OAuth-Brücke und Protokollhandler | Launcher/Desktop-Integration | Verknüpft die proprietäre Anmeldung mit dem Linux-Browser; keine allgemeine Wine-API-Korrektur. |
| SpaceMouse-SDK, HID, Tastenkonfiguration und Kamerageschwindigkeit | Optionale Fusion-Integration | Verwendet Fusion-spezifische APIs und Gerätekonfiguration. Ein Proton-Fork ersetzt diese Anbindung nicht. |
| Fusion-Sprache, DPI, DragWidth/DragHeight, passende Autodesk-Compiler-DLL | Anwendungs-/Prefix-Konfiguration | Benutzerpräferenzen und Autodesk-Dateien bleiben im passenden Anwendungs-/Prefix-Kontext. |

Die Panel-Auswahl behält die gezielten Qt-Klassen- und Geometrie-Kriterien des
bisherigen Helpers bei. Der Wechsel beseitigt die Polling-Verzögerung und das
Umschreiben der Fensterstile; er behauptet keine allgemeine Lösung für sämtliche
Qt-Popups. Die Kommentierungsleiste wird nur zusammen mit einem passenden
sichtbaren vertikalen Panel erkannt.

## Laufzeit-Vertrag

Ein ausführbares `proton` allein gilt nicht mehr als passende Laufzeit.
`fusion-runtime.json` benennt Build-ID, Quell-Commit, Proton-Basis und die
erforderlichen Features. Es enthält SHA-256-Hashes für Launcher, Python-Profil,
DXVK-Vorgaben und die geänderten Wine-Module einschließlich der Windows-DLL.

Der Installer und die Laufzeitauswahl im Manager akzeptieren nur diesen Vertrag.
`runtime-lock.json` in der Fusion-Installation hält den exakten Build und den
Manifest-Hash fest. `proton-path` zeigt auf das unveränderliche Versionsverzeichnis,
nicht auf den beweglichen `current`-Link. Eine neue globale Laufzeit verändert
damit nicht unbemerkt die bereits ausgewählte Installation. Der Launcher prüft
die Bindung und Payload vor Sprache, DPI, Hintergrunddiensten oder Fusion-Start.
Fehlt die Laufzeit oder stimmt ein Hash nicht, bricht er mit einer Fehlermeldung
ab. Er fällt nicht auf Steam Experimental, GE-Proton oder einen beliebigen
anderen Ordner zurück.

## Bauen und aktivieren

Für einen lokalen x86_64-Testbuild mit der exakt passenden offiziellen Basis:

```bash
cd /home/tobias/Projekte/Proton-Fusion
bash fusion/scripts/build-native-modules.sh "$PWD/.build/native"
bash fusion/scripts/build-pe-modules.sh "$PWD/.build/pe"
python3 fusion/scripts/install-local.py \
  --base "$HOME/.local/share/Steam/steamapps/common/Proton - Experimental" \
  --unix-build "$PWD/.build/native" --pe-build "$PWD/.build/pe"
```

Der Installer legt einen neuen Build unter `versions/<Build-ID>` an und setzt
erst nach vollständiger Bereitstellung `current` um. Vorherige Builds bleiben
erhalten. Der Referenzstand wird mit `fusion/upstream.json` abgeglichen; eine
zwischenzeitlich andere Steam-Basis wird nicht mit alten Wine-Modulen vermischt.

Fusion anschließend schließen und die Integration anwenden:

```bash
cd /home/tobias/Projekte/fusion-linux-dx11
./install.sh --apply-update
```

Bei der ersten Einrichtung findet oder erstellt der Fusion-Installer das
Proton-Fusion-Quellprojekt als dauerhaften Geschwisterordner seines eigenen
Checkouts und baut die lokale Laufzeit. Bereits vorhandene gültige Builds werden
verwendet. Es werden dabei keine Systempakete oder Container-Engines installiert.
Der lokale Build setzt Compiler, Clang/LLD, Autoconf, Bison/Flex und die benötigten
Wine-/X11-Entwicklungsbibliotheken voraus.

Für eine verteilbare Laufzeit ist weiterhin der vollständige SDK-Build vorgesehen.
Dessen Paket enthält ebenfalls Profil und Manifest. Der hier lokal verifizierte
Overlay-Build ist an den Host und x86_64 gebunden; die Existenz des Build-Skripts
ist kein Nachweis einer vollständigen SDK-/32-Bit-Validierung.

## Validierung

* Der Frame-Reproducer bestand nach den zusätzlichen Änderungen 40 Serien mit
  Resize und Minimieren ohne veraltetes letztes Bild bei 30/200 ms.
* Der Panel-Reproducer prüft Panel, Kommentarleiste, kleines HUD und fremde Klasse
  sowie den abgeschalteten Fix. Die positiven Fenster sind verwaltet, die
  negativen bleiben unmanaged. Das Probeprogramm prüft zusätzlich, dass kein
  `WS_EX_APPWINDOW` eingefügt wurde.
* Der Sprach-Reproducer vergleicht `GetUserLanguages` für `;` und `|` mit der
  tatsächlichen bevorzugten Windows-UI-Sprachliste und gibt den HSTRING frei.
* Der Launcher hat Tests für fehlende/fremde Laufzeiten, geänderte Module,
  geänderte Metadaten, stabile Versionsbindungen und das Entfernen ausschließlich
  des alten Fusion-Layers.

Die nativen Probes laufen in eigenen Prefixes. Ein erfolgreicher Start von
Fusion ist zusätzlich zu prüfen; er ersetzt keine vollständige CAD-, Anmelde-
oder Mehrmonitor-Abnahme.
