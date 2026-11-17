# Hokkaido 0.7.0

The biggest Hokkaido release so far: a second engine. Next to Hokkaido's emulator, the APK now carries [Banana Native](https://git.eden-emu.dev/moceure/BananaNative), which runs a Switch 2 game's code natively on the phone and draws its graphics through Vulkan. You choose the engine per game, and Banana Native runs behind Hokkaido's own screens, with Hokkaido's GPU driver, saves and settings.

Tested on a Samsung Galaxy S26 (Exynos 2600, Xclipse 960, 12 GB), a Galaxy S24 (Exynos 2400, Xclipse 940, 8 GB) and a Galaxy S25 (Snapdragon 8 Elite, Adreno 830, 12 GB), all on Android 17.

**Updating:** install the APK over 0.6.x. Your games, saves and settings stay. Every game keeps running on the Hokkaido engine unless Banana Native has a playable profile for it (see Auto below), and you can switch any game back in Game properties.

## Getting started with Banana Native

1. **GPU driver.** On an Xclipse GPU (Exynos), install a custom RADV driver in Hokkaido's GPU driver manager, globally or for the game. Banana Native uses the same driver as Hokkaido.
2. **Engine.** Open the game's Game properties › **Engine**. Auto already picks Banana Native for its playable games; for the others choose **Banana Native (experimental)**.
3. **First start: Prepare.** Banana Native rewrites the game's code from your dump once. It takes a few minutes, uses the CPU hard and warms the phone, so do it on the charger. You can hide it, pause it, or close Hokkaido; it continues where it stopped.
4. **Play.** Shaders are built while you play and kept, so the first sessions show missing objects and pop-in that go away.
5. **In game,** Back or the controller's menu button opens Hokkaido's menu: pause, controller, Quick settings with all of Banana Native's settings, overlay, exit.

Games added as loose dumps work when Hokkaido has All files access; Banana Native reads the dump folder (the one holding `base/` and `updates/`).

## Moving from the Banana Native app

If you already prepared a game in Banana Native's own app, you don't need to prepare it again:

1. In the Banana Native app, open the game's **Manage** sheet and choose **Export pack…**. It writes `banana-pack-<title ID>-<version>.zip` to a folder you pick.
2. In Hokkaido, open the same game's **Game properties › Import Banana Native pack** and pick that zip.
3. Hokkaido copies the pack and checks it with Banana Native's own checks: it must be this game's, and its code must fit your dump (the same game version). If it doesn't fit, nothing changes and the reason is shown.

Good to know:

- An exported pack has no shaders built while you played (Banana Native leaves them out of exports); the game builds them again while you play.
- Without the import, Hokkaido also finds a pack you unzip yourself into a folder named `<title ID>-work/<any name>/` next to your game, or up to three folders above it.
- Saves don't move automatically yet. Banana Native's save backups and Hokkaido's save import use different zip layouts.

## New: the Banana Native engine

- **One APK, two engines.** Banana Native v0.3.41 is built into Hokkaido. Nothing else to install, and its own launcher never shows.
- **Pick the engine per game:** Game properties › **Engine**: Auto, Hokkaido or Banana Native. The choice appears for every game Banana Native has a profile for.
  - **Auto** picks Banana Native for the games its profiles call playable: Donkey Kong Bananza, Pokémon Pokopia, Mario Kart World, Fire Emblem: Fortune's Weave and Star Fox. Every other game stays on Hokkaido.
  - The games Banana Native is still bringing up are offered as **Banana Native (experimental)**: The Legend of Zelda: Ocarina of Time, Splatoon Raiders, Mario Tennis Fever, and the Switch 2 Editions of Super Mario Bros. Wonder and Kirby and the Forgotten Land.
- **Every way of starting a game honours its engine:** the game list, Start › Global or Custom in Game properties, home-screen shortcuts, and the ExeFS picker.
- **Preparing, in Hokkaido's own screens.** The first start of a game on Banana Native prepares a pack from your dump: it rewrites the game's code, which takes a few minutes. You can hide or pause it, and it continues where it stopped. For the games it covers, Banana Native now builds shaders while you play, so a game starts as soon as its code is ready. Expect missing objects and pop-in for the first sessions while the shaders build; they are kept, so each one is built only once.
- **Shared with Hokkaido:**
  - **GPU driver:** the game's own driver, else the global one, installed into Banana Native for you.
  - **Saves:** both engines use the same save folder. Import, export and delete in Game properties work for both.
  - **Resolution scale:** 1x is 1920x1080, 0.5x is 960x540. A resolution you pick inside the game stays until you change the game's scale in Hokkaido.
- **Hokkaido's in-game menu over Banana Native games.** Back, or the controller's menu button, opens Hokkaido's menu: Pause, Show or hide the controller, Quick settings, Overlay options and Exit, in your Hokkaido theme and colours.
  - **Quick settings** shows all of Banana Native's in-game settings as Hokkaido rows, on four tabs: Performance, Display, Controls and General. Changes apply to the running game at once.
  - The performance overlay sits at the top left in Hokkaido's style, and the paused screen shows Hokkaido's play button.
  - A controller moves through the menu: the D-pad or left stick, A and B, and L / R to switch tabs.
  - **Exit** ends the game and returns to Hokkaido's game list.
- **One game at a time.** Banana Native holds one game. Starting another asks you to close the one still running first.
- **New in Banana Native v0.3.41:** Prepare no longer fails with a missing `pack_dump` module, and button icons in game text (the controller glyphs in prompts) draw with their own font instead of `?`.
## Ocarina of Time on Banana Native

Ocarina of Time is playable through Banana Native on the Galaxy S26 with a custom RADV driver. Hokkaido sets it up for that phone:

- **Mesh draws through compute on Xclipse GPUs with RADV.** There, the GPU's task shaders made Ocarina of Time's world freeze and then hang the GPU. This applies to every game on a RADV driver on an Exynos phone.
- **Hold 60 fps on.** The frame rate no longer jumps up and down, which made the phone lower its GPU clock even further.
- **On 12 GB phones:** softer large textures, and game memory handed to the GPU in parts, so the game fits better.
- **Banana Native's RAM saver stays off.** Its file-backed texture pools left holes in the terrain.
- **New live sliders** under Quick settings › Performance: Draw distance, Model detail, Shadow range, Foliage distance and Fog at the cut. Shorter distances make busy places lighter on the GPU.
- **Lower vegetation detail** by default, as Banana Native recommends. Full vegetation is a choice in Quick settings.

## Hokkaido engine

The fixes marked as from upstream are ported from [Eglantine](https://github.com/Djihads80/Eglantine) and were tested there; on our phones they were checked for regressions in the games we have.

- **New: Frame skip,** under Settings › Graphics and in the in-game Quick settings, for every game or per game. From 0 to 3 frames left undrawn after each drawn one: a game that slows down when the phone can't keep up runs at its own speed again, but shows fewer frames. 0, the default, draws every frame. Thanks to Diriande (#19).
- **Stopping a game frees its memory.** A Switch 2 game's RAM used to stay held until Hokkaido was closed; now it is released when the game stops, so the next game, or a Banana Native game, has it back (upstream #634).
- **CPU (NCE) fixes from upstream:**
  - Instructions that write the zero register no longer change the stack pointer, which caused random hangs and crashes minutes into play (#740).
  - An illegal instruction in a game stops only that game thread, with a log of where it happened, instead of closing the app (#741).
- **Yoshi and the Mysterious Book:** its movie player no longer stops with error 2162-0001 after a few minutes of movies.
- **Graphics fixes from upstream:**
  - Mario Tennis Fever no longer closes at the start of a match on AMD-based GPUs such as Xclipse: geometry shaders now stay within the GPU's output limit.
  - Donkey Kong Bananza's tutorial video panel no longer turns into tile noise on RADV: a draw that samples its own render target now reads a copy.
  - Mario Kart World: roads that used half-precision compares from constant buffers draw again, and its dynamic resolution no longer flips every few frames.
  - Float-to-integer conversions that read constant buffers keep their sign and absolute-value bits (used by Pokémon Pokopia).
  - Less CPU work on the GPU thread: pages the game rewrites every frame are no longer write-protected and trapped.
  - Vulkan validity fixes for query copies, vertex-binding strides and sparse textures.

## Saves

- **Save export and import** take only the games' save folders. Banana Native's working files beside them no longer break the save manager.
- **Deleting a game's save** also removes Banana Native's pending save transaction, so a deleted save no longer comes back.

## For contributors

- `tools/android/sync_bananative.sh` updates the embedded Banana Native to a release: its Android sources, our patches (`src/android/banana/patches/`) and the release's build values.
- `tools/android/build_bananative_native.sh` builds Banana Native's game hosts from source. Then `-PbananaNativeLibs=<folder>` puts them into Hokkaido's APK in place of the release's, for debugging and fixes.
- Banana Native's diagnostic switches go in `Android/data/<app id>/files/env-<title ID>.txt`, one `KEY=VALUE` per line, read at the game's next start.

## Known issues

- **Banana Native needs a custom RADV driver on Xclipse phones.** Samsung's own driver has no placed memory maps, so a Banana Native game shows a black screen with sound there.
- **Ocarina of Time on Banana Native:**
  - On 12 GB phones it uses most of the memory. Some textures in the distance can show pink.
  - The lighting can turn dark for a moment when you turn the camera.
  - The first sessions show missing objects and pop-in while shaders build.
- **On the Hokkaido engine:**
  - Fast Fusion runs at low frame rates, loads slowly and its image shimmers.
  - Ocarina of Time can stay on a black screen after its intro movie on some Snapdragon phones (issue #12).
  - Pokopia runs slower than in earlier versions on the Galaxy S26, and its frames come out unevenly, so walking and turning the camera look jittery. It runs better on the Galaxy S24. Banana Native is the faster engine for it.
- **The APK is larger,** about 100 MB, since it carries Banana Native.
- Microphone input is not supported on Android.
- The phone heats up during long sessions and slows down until it cools.

## For testers

- Install the APK, add your games folder, and set up keys and firmware as usual. None are included.
- **Hokkaido engine:** Handheld mode, NCE CPU backend, 0.5x resolution, and a custom RADV driver on Xclipse GPUs.
- **Banana Native engine:** a custom RADV driver on Xclipse GPUs, and Prepare on the charger.
- Diagnostic switches can be set in `Android/data/dev.lichii.android/files/env.txt` (see the README).
- Report problems at https://github.com/pavelgajdo/Hokkaido/issues with your phone, driver, the engine and the log: `eden_log.txt` for Hokkaido, or the game's log from `Android/data/dev.lichii.android/files/logs/` for Banana Native.

## Thanks

Diriande for the frame skip (#19). The Eglantine and Lichii contributors whose fixes are ported here: linyesh, SmileyTatsu, rdenno, Rhys Denno, MythosOfs, kraibse, Duck912, Dominic and Zortos.

Banana Native is by moceure and its contributors (MIT licence), based on [nxnative](https://github.com/seedds/nxnative) by seedds. Its frame generation uses Lossless Scaling's LSFG through Eden's port (GPL-3.0).
