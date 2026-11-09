#!/bin/bash
# build_boot_image.sh - Erstellt das fertige boot.img aus Kernel und Initramfs
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

KERNEL_IMG="${1:-$REPO_ROOT/kernel/Image}"
DTB_FILE="${2:-$REPO_ROOT/kernel/exynos990-y2slte.dtb}"
OUT_FILE="${3:-$REPO_ROOT/images/boot_custom.img}"

if [ ! -f "$KERNEL_IMG" ]; then
    echo "[-] Kernel-Image nicht gefunden: $KERNEL_IMG"
    echo "Verwendung: ./build_boot_image.sh [KERNEL_IMAGE] [DTB_FILE] [OUTPUT_BOOT_IMG]"
    exit 1
fi

echo "[*] Erstelle temporaeres Initramfs..."
TMP_RD=$(mktemp -d)
cd "$REPO_ROOT/initramfs"
find . | cpio -o -H newc | gzip -9 > "$TMP_RD/initramfs.img"

echo "[*] Assembliere boot.img..."
python3 "$REPO_ROOT/tools/mkbootimg.py" \
    --kernel "$KERNEL_IMG" \
    --ramdisk "$TMP_RD/initramfs.img" \
    --dtb "$DTB_FILE" \
    --header_version 2 \
    --pagesize 2048 \
    --base 0x10000000 \
    --kernel_offset 0x00008000 \
    --ramdisk_offset 0x02800000 \
    --tags_offset 0x00000100 \
    --dtb_offset 0x03800000 \
    --cmdline 'console=tty0 console=ttyGS0,115200 clk_ignore_unused pd_ignore_unused iomem=relaxed swiotlb=65536 root=/dev/ram0 rw init=/init' \
    -o "$OUT_FILE"

rm -rf "$TMP_RD"
echo "[+] Boot-Image erfolgreich erstellt: $OUT_FILE"
