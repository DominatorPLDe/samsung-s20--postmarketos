# Samsung Galaxy S20+ (SM-G985F / y2slte) - Standalone Linux Server

## 1. System Overview

This repository provides all source code, driver patches, kernel configuration, initramfs components, and pre-built bootable images required to turn the Samsung Galaxy S20+ (Exynos 990, model SM-G985F / codename `y2slte`) into an autonomous, power-efficient, headless 64-bit Linux server.

The system supports two execution modes:
- **Volatile RAM Boot**: Boots purely into RAM (`fastboot boot boot_community.img`) without making any modifications to the internal UFS flash storage.
- **Permanent Flash Installation**: Flashes directly to the internal boot partition (`/dev/sda33`). Once installed, the smartphone boots automatically upon power-on or reboot without requiring a connected PC, button combinations, or serial intervention.

### Hardware Specifications & Driver Support Matrix

| Subsystem | Specification | Implementation & Operational Status |
| :--- | :--- | :--- |
| SoC | Samsung Exynos 990 (7nm EUV) | Fully initialized |
| CPU | 8 Cores (Tri-Cluster):<br>- 4x Cortex-A55 @ 2.00 GHz<br>- 2x Cortex-A76 @ 2.60 GHz<br>- 2x Mongoose M5 @ 2.73 GHz | EAS (Energy Aware Scheduling) & Schedutil.<br>Hardware DVFS via native ACPM driver (`exynos990-acpm`). |
| GPU | ARM Mali-G77 MP11 (Valhall) | Open-source DRM/KMS Panfrost driver (`panfrost.ko`). |
| System Memory | 7.84 GB LPDDR5 RAM | 100% available, ~1.8 GB utilized under server workloads, ~5.5 GB free. |
| Storage | UFS 3.0 (128 GB Flash) | `/dev/sda32` (`userdata`, ~108 GB) mounted persistently as `/data` (ext4). All firmware partitions write-protected. |
| Wireless Networking | Broadcom BCM4375 (Wi-Fi 6 / 802.11ax) | PCIe driver `brcmfmac` & `brcmfmac-wcc` stabilized with PCIe S2MPU fixes. WPA2/WPA3 support. |
| Wired USB Network | USB-C OTG ConfigFS Gadget | Dual RNDIS (Windows) & CDC-NCM (Linux/macOS) + ACM Serial with built-in DHCP server. |
| Display & Power | 6.7" Dynamic AMOLED 2X | Initialized via DECON; automated panel blanking after 12s (0-Watt AMOLED idle power saving). |
| Thermal Management | Exynos TMU (Thermal Management Unit) | 4 physical on-die sensors (Battery, Cluster 0, Cluster 1, Cluster 2) with 2-point factory calibration. |

---

## 2. Project Lineage & Credits

To ensure proper attribution under open-source standards, this section outlines the baseline work provided by upstream projects and the specific technical additions developed in this repository.

### Upstream & Prior Community Foundations
- **Base Kernel**: Port of `linux-next` (`next-20241018-990`) maintained by the Exynos 990 mainline Linux community (notably Ivan Meler, Igor Pecovnik, and collaborating developers).
- **Secondary Bootloader (`lk3rd`)**: The Little Kernel 3rd-stage bootloader deployed to partition `/dev/sda13`, which initializes the USB PHY and provides standard Android Fastboot protocol support.
- **Reference Device Trees**: Initial DTS skeletons and pin definitions based on Samsung Exynos 990 reference trees.

### Additions & Improvements Developed in this Repository
- **Native Hardware DVFS via ACPM Mailbox Protocol**:
  Implemented and integrated `exynos-acpm.c`, `exynos990-cpufreq.c`, and `exynos-mailbox.c`. In previous mainline builds, CPU frequency scaling was either unavailable or resulted in kernel panics due to unhandled AP-to-ACPM mailbox communication. This implementation delivers stable dynamic frequency scaling across all three CPU clusters (A55, A76, M5) under the `schedutil` governor.
- **Tri-Cluster Energy-Aware Scheduling (EAS)**:
  Tuned capacity-aware task placement and energy cost tables specifically for the 4+2+2 heterogeneous Exynos 990 core topology.
- **Exynos TMU Calibration & Driver Integration**:
  Configured `exynos990_tmu.c` to accurately read all 4 hardware thermal sensors utilizing chip-specific 2-point calibration registers.
- **Broadcom BCM4375 Wi-Fi 6 PCIe Fix**:
  Implemented the PCIe S2MPU subsystem (`s2mpu.c`), eliminating PCIe bus translation faults and preventing `brcmfmac` kernel panics under sustained network I/O.
- **AMOLED Zero-Watt Power Saving (Display Blanking)**:
  Added an automated DECON display shutdown routine in `/init` that blanks the AMOLED panel 12 seconds after boot, reducing idle device draw to ~0.7W and preventing screen burn-in.
- **Autonomous Headless Initramfs & Persistence**:
  Engineered a custom `/init` userland that automatically configures dual USB-Ethernet gadgets, mounts the 108 GB UFS `userdata` partition to `/data`, verifies file systems, and sets critical bootloader partitions to read-only (`blockdev --setro`).
- **Autostart Service Infrastructure**:
  Created a non-blocking boot execution hook for `/data/scripts/autostart.sh`, enabling headless startup of services (e.g., servers, databases, containers) without PC intervention.
- **Dynamic Thermal Guard**:
  Designed a production background daemon (`thermal_guard.sh`) implementing hysteresis-based thermal throttling without CPU hotplugging (which triggers EL3 firmware `-EIO` faults on M5 cores).
- **Headless Network Setup & Web Tools**:
  Created `wifi-connect` for interactive terminal Wi-Fi management with `/data` persistence, plus an embedded HTTP dashboard (`s20_dashboard.py`) and remote web console.
- **Safe Flashing Tools**:
  Developed verified Windows batch scripts (`BOOT_RAM_TEST.bat` and `FLASH_PERMANENT.bat`) enforcing whole-image flashing to prevent partition corruption caused by unsupported fastboot sparse chunking (`-S`) in `lk3rd`.

---

## 3. Repository Structure

```text
s20plus-linux-server/
├── README.md                             # Project documentation and setup guide
├── LICENSE                               # GNU General Public License v2 (GPL-2.0)
├── .gitignore                            # Git ignore configuration
│
├── images/
│   ├── boot_community.img                # Pre-built, verified standalone boot image (35.45 MB)
│   └── SHA256SUMS                        # Cryptographic checksums
│
├── flash-tools/
│   ├── BOOT_RAM_TEST.bat                 # 1-Click RAM boot script (volatile, zero flash write)
│   ├── FLASH_PERMANENT.bat               # 1-Click permanent flash script (/dev/sda33)
│   ├── fastboot.exe                      # Standalone fastboot binary for Windows
│   ├── AdbWinApi.dll                     # Required Windows USB communication library
│   └── AdbWinUsbApi.dll                  # Required Windows USB communication library
│
├── kernel/
│   ├── patches/
│   │   └── exynos990_full_hardware.patch # Cumulative unified patch for linux-next
│   ├── config/
│   │   └── exynos990_y2slte_defconfig    # Tested kernel defconfig (.config)
│   ├── dts/
│   │   ├── exynos990-y2slte.dts          # Device tree for Samsung Galaxy S20+
│   │   ├── exynos990.h                   # Hardware constants and register offsets
│   │   ├── exynos990.dtsi                # Exynos 990 SoC base device tree
│   │   └── exynos990-pinctrl.dtsi        # Pin controller definitions
│   └── drivers/                          # Exynos drivers (ACPM, Mailbox, TMU, S2MPU)
│
├── initramfs/
│   ├── init                              # Root init script (Mounts, USB gadget, Display blanking)
│   ├── usr/bin/s20_dashboard.py          # Built-in lightweight web dashboard (Port 80)
│   ├── usr/local/bin/wifi-connect        # Wi-Fi setup utility with /data persistence
│   └── etc/wpa_supplicant/               # Neutral Wi-Fi configuration template
│
└── scripts/
    ├── build_boot_image.sh               # Shell script to build boot.img from kernel and initramfs
    ├── autostart.sh.example              # Template for /data/scripts/autostart.sh
    ├── thermal_guard.sh.example          # Template for thermal hysteresis frequency limiter
    └── modus.sh.example                  # Template for CPU governor profiles (auto / sparsam / boost)
```

---

## 4. Hardware Requirements & Prerequisites

1. **Target Device**: Samsung Galaxy S20+ LTE (Model SM-G985F, Exynos 990 / `y2slte`).
2. **Unlocked Bootloader**: OEM unlocking enabled in Android Developer Options, bootloader unlocked via Samsung Download Mode.
3. **Installed Secondary Bootloader (lk3rd)**: `lk3rd` must be flashed to partition `/dev/sda13`. `lk3rd` provides the standard Fastboot USB interface.

---

## 5. Quick Start (Pre-built Image)

### Method A: Volatile RAM Boot (Zero-Risk Evaluation)

Test the system completely from RAM without modifying internal storage:

1. Power off the phone.
2. Hold **VOLUME DOWN** and connect the phone to your PC using a USB-C cable. The phone will enter the `lk3rd` Fastboot mode.
3. Open the `flash-tools/` directory on your PC and run:
   ```cmd
   BOOT_RAM_TEST.bat
   ```
4. The script uploads the image directly to RAM (`fastboot boot boot_community.img`). The system boots within 9 to 15 seconds.

### Method B: Permanent Flash Installation

Install the system permanently to the internal UFS storage:

1. Put the phone into Fastboot mode (Power off -> Hold Volume Down -> Connect USB-C).
2. Open the `flash-tools/` directory and run:
   ```cmd
   FLASH_PERMANENT.bat
   ```
3. The script flashes `boot_community.img` directly to partition `boot` (`/dev/sda33`) and reboots the phone.

> **Critical Fastboot Notice**: Never flash raw partitions with the `-S` parameter (sparse chunking) on `lk3rd`. `lk3rd` does not support sparse chunking on raw partitions and will overwrite offset 0. The provided `FLASH_PERMANENT.bat` script is pre-configured with the correct parameters.

---

## 6. Network Access & Configuration

### Direct Access via USB-C Cable (Available Immediately)

Upon boot, the system initializes an automated USB-Ethernet network interface over the USB-C cable:

- **Phone IP Address**: `10.42.0.2` (or Link-Local `169.254.239.1`)
- **Host PC IP**: The phone assigns an IP between `10.42.0.10` and `10.42.0.50` via built-in DHCP.
- **Web Dashboard**: `http://10.42.0.2` (Port 80)
- **Web Terminal**: `http://10.42.0.2:7681` (In-browser shell)
- **SSH Access**: `ssh root@10.42.0.2` (Port 22, passwordless root login)

### Setting Up Wi-Fi (Persistent)

To connect the server to your wireless network:

1. Connect via Web Terminal (`http://10.42.0.2:7681`) or SSH (`ssh root@10.42.0.2`).
2. Run the connection tool:
   ```sh
   wifi-connect "YOUR_WIFI_SSID" "YOUR_WIFI_PASSWORD"
   ```
3. The script configures `wlan0`, obtains an IP address via DHCP, and writes the credentials to `/data/wpa_supplicant.conf`.
4. On all subsequent boots, the system connects automatically to this Wi-Fi network.

---

## 7. Persistent Storage & Autostart Services

### Partition Layout

- **Root Filesystem (`/`)**: Operates as a fast `tmpfs` RAM disk (~3.7 GB available). Changes to root system files are volatile unless reloaded from `/data`.
- **Persistent Storage (`/data`)**: The internal UFS partition `/dev/sda32` (`userdata`, ~108 GB) is mounted automatically at `/data` (ext4). All user files, databases, scripts, and server binaries must be stored in `/data`.

### Starting Custom Services on Boot

Once `/data` is mounted, `/init` automatically checks for and executes `/data/scripts/autostart.sh` in the background:

```sh
mkdir -p /data/scripts /data/logs
cp scripts/autostart.sh.example /data/scripts/autostart.sh
chmod +x /data/scripts/autostart.sh
```

---

## 8. Building from Source (Kernel & Initramfs)

### 1. Patch and Compile the Kernel

Clone the mainline Linux Next tree for Exynos 990:

```bash
git clone https://github.com/exynos990-mainline/linux.git -b next-20241018-990
cd linux

# Apply the cumulative hardware enablement patch:
git apply /path/to/kernel/patches/exynos990_full_hardware.patch

# Copy kernel configuration and build:
cp /path/to/kernel/config/exynos990_y2slte_defconfig .config
make ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- -j$(nproc) Image dtbs
```

### 2. Package the Boot Image

Use the packaging script `scripts/build_boot_image.sh`:

```bash
./scripts/build_boot_image.sh \
    /path/to/linux/arch/arm64/boot/Image \
    /path/to/linux/arch/arm64/boot/dts/exynos/exynos990-y2slte.dtb \
    images/boot_custom.img
```

---

## 9. Operating Rules & Safety Guidelines

### Rule 1: Do Not CPU-Hotplug Mongoose M5 Cores

On the Exynos 990, attempting to take CPU cores 6 and 7 (Mongoose M5) offline via `/sys/devices/system/cpu/cpuX/online` causes an unrecoverable `-EIO` error inside the EL3 secure firmware. Once disabled, cores cannot be re-enabled without a hardware reset.
- **Recommended Procedure**: Regulate power and clock limits using sysfs (`scaling_max_freq`) and pin specific tasks to Cortex-A55 (cores 0-3) or Cortex-A76 (cores 4-5) using `taskset`. Never take cores offline.

### Rule 2: Protect the lk3rd Bootloader Partition

Partitions `/dev/sda1` through `/dev/sda31` and `/dev/sdb`, `/dev/sdc`, `/dev/sdd`, `/dev/sde` are write-protected at boot (`blockdev --setro`).
- Flash exclusively to the `boot` partition (`/dev/sda33`).
- Partition `/dev/sda13` contains `lk3rd` and must not be overwritten under any circumstances.

---

## 10. License

This repository is licensed under the **GNU General Public License Version 2 (GPL-2.0)**. Refer to the `LICENSE` file for full terms and conditions.
