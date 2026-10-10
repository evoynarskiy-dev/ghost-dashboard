# 👾 Ghost Dashboard

A minimalist, high-performance Wayland control center tailored for **Arch Linux & Hyprland**, styled in clean **VS Code Dark+ / Catppuccin** aesthetics.

Designed specifically for secondary vertical monitors (e.g., 1080x1920) and multi-display power-user workstations.

---

## ⚡ Key Features

- **👾 60 FPS Canvas Pacman:** Smooth graphical 2D canvas animation featuring Pacman chasing a ghost across the top header with zero CPU overhead.
- **📅 Interactive Calendar & Notes:** Monthly grid with Sunday-first layout, clean date rendering, and persistent date-linked notes stored in `~/.config/ghost_notes.json`.
- **📊 Multi-Threaded Hardware Telemetry (Zero-Lag):**
  - **AMD Ryzen 7 (Zen 4 / AM5):** Live CPU load and core thermals directly via the Linux `k10temp` kernel driver.
  - **NVIDIA GeForce RTX (50xx / 40xx):** Real-time GPU load, core temperature, and VRAM allocation via asynchronous `nvidia-smi` queries.
  - **Network I/O & Interfaces:** Real-time network bandwidth monitor (Download/Upload speeds) tracking active network adapters (Ethernet, Wi-Fi, Tailscale).
  - *All heavy metrics run in an isolated daemon thread, ensuring buttery-smooth 60 FPS UI responsiveness.*
- **🔊 Native PipeWire Application Audio Mixer:**
  - Independent per-app volume sliders and mute toggles (Google Chrome, Discord, Steam games, media players) directly mirroring Pavucontrol.
  - Asynchronous, non-blocking execution via `wpctl` and `pactl`.
  - Smart polling: automatically detects active audio streams without UI flickering or stutter.
- **🎯 War Thunder Controller:** One-click launch shortcut alongside an instant emergency process killer (`killall -9 aces`).
- **🚀 Dynamic App Launcher & Task Killer:** Automatic indexing of system `.desktop` entries with instant fuzzy search and an integrated running process manager.

---

## 🛠 Installation & Quickstart

### 1. Prerequisites (Arch Linux)

```bash
sudo pacman -S --needed python tk python-psutil

2. Python Dependencies

pip install customtkinter --break-system-packages

3. Running the Dashboard

python main.py

🖥 Hyprland Integration (Lua Config)

Add the window rule and keybind to your ~/.config/hypr/hyprland.lua:

-- Window rule for tiling on vertical monitor
hl.window_rule({
    name  = "ghost-dashboard",
    match = { title = "Ghost Dashboard" },
    float = false,
})

-- Keybind (SUPER + D to launch)
hl.bind(mainMod .. " + D", hl.dsp.exec_cmd("python ~/ghost-dashboard/main.py"))

🗺 Roadmap

- [x] v1.0 (Current Release):
    - Multi-threaded hardware monitoring (CPU thermals, GPU VRAM, Network I/O).
    - PipeWire application audio mixer with real-time stream detection.
    - 60 FPS Canvas Pacman animation.
    - Hyprland tiling integration.
- [ ] v1.1 (Upcoming):
    - One-click audio output device switcher (Headphones / Speakers).
    - Pinned favorite apps in the launcher bar.
- [ ] v1.2 (Planned):
    - Live weather widget integration.
    - Real-time crypto arbitrage spread ticker for multi-exchange monitoring.

📜 License

MIT License. Open for personal ricing and community customization.


4. Нажми вверху справа зеленую кнопку **«Commit changes...»** ➔ и подтверди **«Commit changes»**.

Все иероглифы пропадут, и страница станет идеально чистой. 

*(А в терминале потом просто сделаешь `git pull`, чтобы локальный файл подтянулся).*
