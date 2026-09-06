#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ELF2OS 商业使用授权协议 v1.0
====================================

版权所有 (C) 2026 anonymous123456988 (https://github.com/anonymous123456988)
保留所有权利 (All Rights Reserved)

本协议是 anonymous123456988（以下简称“授权方”）与您（以下简称“被授权方”）
之间关于 elf2os.py 软件（以下简称“本软件”）的法律协议。

1. 授权范围
   授权方授予被授权方一份非独占、不可转让、不可再许可的永久使用权，
   允许被授权方：
   (1) 在单台计算机上安装并使用本软件；
   (2) 将本软件用于个人或企业内部项目（必须为非商业用途）；
   (3) 使用本软件生成任意数量的 ISO 镜像文件（含 Linux 内核）。
 （4）本程序严禁进行商业用途，诺需要进行商业用途必须经过授权方授权后即可进行商业性用途并保留授权方的商业用途
 （5）以本程序衍生的所有程序与原理必须经过授权方允许后才能进行商业用途

2. 禁止行为
   被授权方不得：
   (1) 对本软件进行反向工程、反编译、反汇编或试图获取源代码；
   (2) 将本软件或其任何修改版本作为独立产品出售、出租、转让或再分发；
   (3) 将本软件嵌入其他商业产品中作为竞品功能；
   (4) 未经授权方书面同意，向任何第三方提供本软件的访问权限。

   本协议不授予被授权方任何所有权，仅授予使用权。

4. 免责声明
   本软件按“现状”提供，不提供任何明示或暗示的保证，
   包括但不限于适销性、特定用途适用性和非侵权性的保证。
   授权方不对因使用本软件造成的任何直接、间接、偶然、特殊或后果性损失承担责任。

5. 协议终止
   如被授权方违反本协议任何条款，本授权自动终止。
   协议终止后，被授权方必须立即停止使用本软件并销毁所有副本。

6. 其他
   本协议受中华人民共和国法律管辖。
   授权方保留随时修改本协议的权利，修改后的协议将发布于官方页面。

   如有任何疑问，请联系：https://github.com/anonymous123456988

"""

import os
import sys
import shutil
import subprocess
import urllib.request
import hashlib
import tarfile
import struct
import time
import stat
import threading
import json
import re
import signal
import ctypes
import traceback
import gzip
import argparse
from pathlib import Path
from typing import Optional, Callable, Tuple, List, Dict, Any

# ============================================================
#  常量配置
# ============================================================

KERNEL_VERSION = "6.6.32"
KERNEL_TARBALL = f"linux-{KERNEL_VERSION}.tar.xz"
KERNEL_URL = f"https://cdn.kernel.org/pub/linux/kernel/v6.x/{KERNEL_TARBALL}"
KERNEL_SHA256 = "b5c34a440dd08e56b3c930dc501500034714b5d0dad350ac82304591a2ea7215"

WORK_DIR = os.path.abspath("os")
# 注意：KERNEL_DIR/KERNEL_SRC_MARKER/KERNEL_CONFIG_MARKER 现改为由
# arch_work_dir(arch) 动态派生（见下方）。以下保留为"默认=x86_64"兼容引用，
# BuildEngine 内部统一使用 self._arch_derived_paths()。
KERNEL_DIR = os.path.join(WORK_DIR, f"linux-{KERNEL_VERSION}")
KERNEL_SRC_MARKER = os.path.join(KERNEL_DIR, "Makefile")
KERNEL_CONFIG_MARKER = os.path.join(KERNEL_DIR, "Kconfig")

ELF_RUNNER_SRC = "elf_runner.c"
INITRAMFS_DIR = os.path.join(WORK_DIR, "initramfs")
ISO_ROOT = os.path.join(WORK_DIR, "iso_root")
BUILD_LOG = os.path.join(WORK_DIR, "build.log")

# 架构工作目录：每个架构独立的子目录，承载该架构的内核源码/镜像/initramfs/ISO/bin。
# 这样不同架构可并行缓存、互不干扰；停止构建时的清理仅删除临时文件，不删这些子目录。
def arch_work_dir(arch: str) -> str:
    """返回某架构的独立工作子目录：os/<arch>/"""
    return os.path.join(WORK_DIR, arch)

def arch_kernel_dir(arch: str) -> str:
    """返回某架构的内核源码目录：os/<arch>/linux-<version>/"""
    return os.path.join(arch_work_dir(arch), f"linux-{KERNEL_VERSION}")

def arch_initramfs_dir(arch: str) -> str:
    return os.path.join(arch_work_dir(arch), "initramfs")

def arch_iso_root(arch: str) -> str:
    return os.path.join(arch_work_dir(arch), "iso_root")

def arch_build_log(arch: str) -> str:
    return os.path.join(arch_work_dir(arch), "build.log")

# 清理机制说明：
# 清理不再只扫描 os/ 顶层"非架构"项，而是深入每个架构工作子目录
# os/<arch>/ 内部，删除该架构的临时构建产物，仅保留：
#   - linux-<version>/        （内核源码/编译产物目录）
#   - linux-<version>.tar.xz  （内核源码压缩包）
#   - <os_name>.iso           （ISO 镜像，若存在）
#   - <os_name>_bin/          （裸 bin 输出目录，若存在）
#   - <os_name>_bin.tar.gz    （裸 bin 打包，若存在）
# 其余（initramfs/、initramfs.cpio.gz、iso_root/、elf_runner.c、build.log
# 等构建期临时文件）一律删除。arch=None 时自动扫描 WORK_DIR 下所有
# 已知架构子目录；也可显式传入 arch 仅清理单个架构。

# 在每个架构子目录内，明确视为"临时"、需要清理的项名（文件或目录）。
# 匹配方式为：项名相等，或项名以这些前缀之一开头（用于 *_bin 变体）。
_ARCH_TEMP_ITEMS = (
    "initramfs",      # initramfs/ 目录
    "initramfs.cpio", # initramfs.cpio / initramfs.cpio.gz
    "iso_root",       # iso_root/ 目录
    "elf_runner.c",   # 临时生成的 runner 源码
    "build.log",      # 该架构构建日志
)

def cleanup_temp_files(work_dir: str = WORK_DIR, preserve_arch_dirs: bool = True,
                       arch: Optional[str] = None) -> int:
    """
    清理各架构工作子目录 os/<arch>/ 内部的临时构建文件，仅保留：
      内核源码目录 linux-<version>/、内核压缩包 linux-<version>.tar.xz，
      以及最终产物（*.iso、*_bin/、*_bin.tar.gz）。
    返回删除的项数。
    arch=None：扫描 work_dir 下所有已知架构子目录并逐一清理；
    arch="x86_64" 等：仅清理指定架构子目录。
    """
    deleted = 0
    if not os.path.isdir(work_dir):
        return 0

    # 收集要清理的架构子目录列表
    if arch is not None:
        if arch not in ARCH_TABLE:
            return 0
        arch_dirs = [arch_work_dir(arch)] if os.path.isdir(arch_work_dir(arch)) else []
    else:
        arch_dirs = []
        for name in os.listdir(work_dir):
            if preserve_arch_dirs and name not in ARCH_TABLE:
                continue
            full = os.path.join(work_dir, name)
            if os.path.isdir(full):
                arch_dirs.append(full)

    kernel_dirname = f"linux-{KERNEL_VERSION}"
    kernel_tarball = KERNEL_TARBALL  # linux-<version>.tar.xz

    for adir in arch_dirs:
        if not os.path.isdir(adir):
            continue
        for item in os.listdir(adir):
            full_item = os.path.join(adir, item)
            # 保留内核源码目录
            if item == kernel_dirname:
                continue
            # 保留内核压缩包
            if item == kernel_tarball:
                continue
            # 保留最终产物：*.iso、*_bin 目录、*_bin.tar.gz
            if item.endswith(".iso") or item.endswith("_bin.tar.gz") or item.endswith("_bin"):
                continue
            # 删除已知临时项（含 initramfs.cpio.gz 这类前缀匹配）
            is_temp = False
            for t in _ARCH_TEMP_ITEMS:
                if item == t or item.startswith(t):
                    is_temp = True
                    break
            if not is_temp:
                # 兜底：除上述保留项外，架构子目录内其余均视为临时
                is_temp = True
            if is_temp:
                try:
                    if os.path.isdir(full_item):
                        shutil.rmtree(full_item, ignore_errors=True)
                    else:
                        os.remove(full_item)
                    deleted += 1
                except OSError:
                    pass
    return deleted

# 构建停止标志（线程安全）：由前端"停止"按钮置 True，引擎各步骤轮询。
_STOP_REQUESTED = {"flag": False}

def request_stop():
    _STOP_REQUESTED["flag"] = True

def clear_stop():
    _STOP_REQUESTED["flag"] = False

def is_stop_requested() -> bool:
    return _STOP_REQUESTED["flag"]

def kill_process_group(proc: Optional[subprocess.Popen]):
    """终止一个 Popen 进程及其进程组（用于停止构建时回收子进程）。"""
    if proc is None:
        return
    try:
        pgid = os.getpgid(proc.pid)
        os.killpg(pgid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.terminate()
        except OSError:
            pass

# ============================================================
#  架构定义表
# ============================================================
# 每个架构字段:
#   arch        : 传给内核 make 的 ARCH= 值（对应 arch/ 目录名）
#   label       : 人类可读标签
#   cross       : 交叉编译前缀（如 aarch64-linux-gnu-），空串表示本机编译
#   toolchain_pkg: Debian/Ubuntu 交叉工具链包名；Arch 用 crossbuild- 或 multilib
#   deb_toolchain / arch_toolchain: 按发行版拆分
#   image       : 内核镜像相对路径（在 KERNEL_DIR 下）
#   image_name  : 复制到输出/ISO 时的文件名
#   defconfig   : 使用的默认配置目标
#   bits        : 64 / 32
#   grub_target : grub-mkstandalone --format= 值（仅用于生成 EFI 引导，BIOS 用 i386-pc）
#   grub_mods   : 额外 GRUB 模块
#   kernel_config_append: 追加到 .config 的架构专属内核选项（覆盖通用部分）
#   host_req    : 本机编译是否要求 HOST 为该架构（True 表示只能在同架构本机编）
#   note        : 说明

ARCH_TABLE: Dict[str, Dict[str, Any]] = {
    "x86_64": {
        "arch": "x86",
        "label": "x86_64 / AMD64 (Intel/AMD 64-bit)",
        "cross": "",
        "defconfig": "x86_64_defconfig",
        "image": "arch/x86/boot/bzImage",
        "image_name": "bzImage",
        "bits": 64,
        "grub_target": "x86_64-efi",
        "grub_mods": "part_gpt part_msdos ext2 iso9660 biosdisk",
        "host_req": True,
        "note": "本机编译（宿主即为 x86_64）",
    },
    "i386": {
        "arch": "x86",
        "label": "i386 / x86 32-bit",
        "cross": "i386-linux-gnu-",
        "defconfig": "i386_defconfig",
        "image": "arch/x86/boot/bzImage",
        "image_name": "bzImage",
        "bits": 32,
        "grub_target": "i386-efi",
        "grub_mods": "part_gpt part_msdos ext2 iso9660 biosdisk",
        "host_req": False,
        "note": "32 位 x86，需 gcc-i686-linux-gnu 交叉工具链",
    },
    "arm64": {
        "arch": "arm64",
        "label": "ARM64 / AArch64 (Raspberry Pi 3+/4/5, 飞腾, 鲲鹏)",
        "cross": "aarch64-linux-gnu-",
        "defconfig": "defconfig",
        "image": "arch/arm64/boot/Image.gz",
        "image_name": "Image.gz",
        "bits": 64,
        "grub_target": "arm64-efi",
        "grub_mods": "part_gpt ext2 iso9660",
        "host_req": False,
        "note": "需 gcc-aarch64-linux-gnu 交叉工具链；镜像为 Image.gz",
    },
    "arm": {
        "arch": "arm",
        "label": "ARM 32-bit (ARMv7, Raspberry Pi 2/Zero)",
        "cross": "arm-linux-gnueabihf-",
        "defconfig": "multi_v7_defconfig",
        "image": "arch/arm/boot/zImage",
        "image_name": "zImage",
        "bits": 32,
        "grub_target": "arm-efi",
        "grub_mods": "part_gpt ext2 iso9660",
        "host_req": False,
        "note": "需 gcc-arm-linux-gnueabihf 交叉工具链；镜像为 zImage",
    },
    "riscv64": {
        "arch": "riscv",
        "label": "RISC-V 64-bit",
        "cross": "riscv64-linux-gnu-",
        "defconfig": "defconfig",
        "image": "arch/riscv/boot/Image",
        "image_name": "Image",
        "bits": 64,
        "grub_target": "riscv64-efi",
        "grub_mods": "part_gpt ext2 iso9660",
        "host_req": False,
        "note": "需 gcc-riscv64-linux-gnu 交叉工具链；镜像为 Image",
    },
    "ppc64le": {
        "arch": "powerpc",
        "label": "PowerPC 64-bit Little-Endian (POWER8/9/10)",
        "cross": "powerpc64le-linux-gnu-",
        "defconfig": "powernv_defconfig",
        "image": "arch/powerpc/boot/zImage.epapr",
        "image_name": "zImage",
        "bits": 64,
        "grub_target": "powerpc-ieee1275",
        "grub_mods": "part_gpt ext2 iso9660",
        "host_req": False,
        "note": "需 gcc-powerpc64le-linux-gnu 交叉工具链；引导用 IEEE1275 (OpenFirmware)",
    },
    "mips64": {
        "arch": "mips",
        "label": "MIPS 64-bit (malta)",
        "cross": "mips64-linux-gnu-",
        "defconfig": "malta_defconfig",
        "image": "arch/mips/boot/vmlinux.gz",
        "image_name": "vmlinux.gz",
        "bits": 64,
        "grub_target": "mips-arc",
        "grub_mods": "part_gpt ext2 iso9660",
        "host_req": False,
        "note": "需 gcc-mips64-linux-gnu 交叉工具链；镜像为 vmlinux.gz",
    },
}

# 输出格式
OUTPUT_ISO = "iso"    # 仅 ISO
OUTPUT_BIN = "bin"    # 仅裸内核+initramfs
OUTPUT_BOTH = "both"  # 两者都生成
VALID_OUTPUTS = (OUTPUT_ISO, OUTPUT_BIN, OUTPUT_BOTH)

# 默认架构（按宿主自动选择，找不到则 x86_64）
DEFAULT_ARCH = "x86_64"
DEFAULT_OUTPUT = OUTPUT_ISO

# ============================================================
#  内核编译所需的额外配置项（通用，追加到 defconfig 之后）
# ============================================================

KERNEL_CONFIG_APPEND = """# elf2os required kernel options
CONFIG_BINFMT_ELF=y
CONFIG_BINFMT_SCRIPT=y
CONFIG_BINFMT_MISC=y
CONFIG_BLK_DEV_INITRD=y
CONFIG_RD_GZIP=y
CONFIG_DEVTMPFS=y
CONFIG_DEVTMPFS_MOUNT=y
CONFIG_TMPFS=y
CONFIG_SHMEM=y
CONFIG_TMPFS_XATTR=y
CONFIG_PROC_FS=y
CONFIG_SYSFS=y
CONFIG_NET=y
CONFIG_INET=y
CONFIG_SERIAL_8250=y
CONFIG_SERIAL_8250_CONSOLE=y
CONFIG_PRINTK=y
CONFIG_BLK_DEV_SD=y
CONFIG_EXT4_FS=y
CONFIG_VFAT_FS=y
CONFIG_NLS_CODEPAGE_437=y
CONFIG_NLS_ISO8859_1=y
# Framebuffer console support
CONFIG_FRAMEBUFFER_CONSOLE=y
CONFIG_FRAMEBUFFER_CONSOLE_DETECT_PRIMARY=y
CONFIG_FRAMEBUFFER_CONSOLE_ROTATION=y
# DRM core and drivers
CONFIG_DRM=y
CONFIG_DRM_BOCHS=y
CONFIG_DRM_VIRTIO_GPU=y
CONFIG_DRM_VMWGFX=y
CONFIG_DRM_VMWGFX_FBCON=y
CONFIG_DRM_FBDEV_EMULATION=y
CONFIG_DRM_FBDEV_OVERALLOC=100
CONFIG_DRM_LOAD_EDID_FIRMWARE=y
# Framebuffer core
CONFIG_FB=y
CONFIG_FB_VESA=y
CONFIG_FB_EFI=y
CONFIG_FB_CFB_FILLRECT=y
CONFIG_FB_CFB_COPYAREA=y
CONFIG_FB_CFB_IMAGEBLIT=y
CONFIG_FB_SYS_FILLRECT=y
CONFIG_FB_SYS_COPYAREA=y
CONFIG_FB_SYS_IMAGEBLIT=y
CONFIG_FB_SYS_OPS=y
# Console display driver support
CONFIG_VT=y
CONFIG_VT_CONSOLE=y
CONFIG_HW_CONSOLE=y
CONFIG_DUMMY_CONSOLE=y
CONFIG_DUMMY_CONSOLE_COLUMNS=80
CONFIG_DUMMY_CONSOLE_ROWS=25
# Boot logo
CONFIG_LOGO=y
CONFIG_LOGO_LINUX_MONO=y
CONFIG_LOGO_LINUX_VGA16=y
CONFIG_LOGO_LINUX_CLUT224=y
# Input device support
CONFIG_INPUT=y
CONFIG_INPUT_KEYBOARD=y
CONFIG_INPUT_MOUSE=y
CONFIG_INPUT_EVDEV=y
CONFIG_INPUT_MOUSEDEV=y
CONFIG_INPUT_MOUSEDEV_PSAUX=y
CONFIG_MOUSE_PS2=y
CONFIG_SERIO=y
CONFIG_SERIO_I8042=y
CONFIG_SERIO_SERPORT=y
# USB support
CONFIG_USB=y
CONFIG_USB_STORAGE=y
CONFIG_USB_XHCI_HCD=y
CONFIG_USB_EHCI_HCD=y
CONFIG_USB_OHCI_HCD=y
CONFIG_USB_UHCI_HCD=y
# HID support
CONFIG_HID=y
CONFIG_HID_GENERIC=y
CONFIG_HID_VMWARE_BALLOON=y
# PCI and SCSI
CONFIG_PCI=y
CONFIG_PCI_MSI=y
CONFIG_SCSI=y
CONFIG_SCSI_MOD=y
CONFIG_SCSI_VIRTIO=y
CONFIG_BLK_DEV=y
CONFIG_BLK_MQ_PCI=y
# ATA and storage
CONFIG_ATA_GENERIC=y
CONFIG_ATA_PIIX=y
# Network
CONFIG_NETDEVICES=y
CONFIG_NET_CORE=y
CONFIG_UNIX=y
CONFIG_E1000=y
CONFIG_E1000E=y
# TTY
CONFIG_TTY=y
CONFIG_BOOT_CONFIG_BOOL=y
# Misc
# Python runtime requirements
CONFIG_SYSVIPC=y
CONFIG_SYSVIPC_SYSCTL=y
CONFIG_POSIX_MQUEUE=y
CONFIG_FUTEX=y
CONFIG_EPOLL=y
CONFIG_SIGNALFD=y
CONFIG_TIMERFD=y
CONFIG_EVENTFD=y
CONFIG_UNIX98_PTYS=y
CONFIG_DEVPTS_MULTIPLE_INSTANCES=y
CONFIG_PROC_VMCORE=y

# ============================================================
#  追加内核配置（用户优化请求：文件系统/网络/驱动/安全/性能/容器，仅追加不删减）
# ============================================================

# ---------- 1. 文件系统支持（高优先级）----------
CONFIG_F2FS_FS=y
CONFIG_BTRFS_FS=y
CONFIG_NTFS_FS=y
CONFIG_XFS_FS=y
CONFIG_CIFS=y
CONFIG_NFS_FS=y
CONFIG_F2FS_FS_XATTR=y
CONFIG_BTRFS_FS_POSIX_ACL=y
CONFIG_XFS_POSIX_ACL=y
CONFIG_NFS_V3=y
CONFIG_NFS_V4=y

# ---------- 2. 网络增强（高优先级）----------
CONFIG_IPV6=y
CONFIG_NETFILTER=y
CONFIG_NF_NAT_IPV4=y
CONFIG_IP_NF_IPTABLES=y
CONFIG_BRIDGE=y
CONFIG_VLAN_8021Q=y
CONFIG_BONDING=y
CONFIG_WIRELESS=y
CONFIG_CFG80211=y
CONFIG_MAC80211=y
CONFIG_NF_CONNTRACK=y
CONFIG_NF_NAT=y
CONFIG_IP_NF_NAT=y
CONFIG_BRIDGE_NF_EBTABLES=y

# ---------- 3. 设备驱动（中优先级：GPU/无线/声卡/触摸/工业）----------
# GPU 驱动
CONFIG_DRM_I915=y
CONFIG_DRM_RADEON=y
CONFIG_DRM_NOUVEAU=y
CONFIG_FB_AMD=y
# 无线网卡
CONFIG_ATH9K=y
CONFIG_RTL8188EU=y
CONFIG_MT76=y
CONFIG_BRCMFMAC=y
CONFIG_CFG80211_WEXT=y
# 声卡
CONFIG_SND=y
CONFIG_SND_HDA_INTEL=y
CONFIG_SND_USB_AUDIO=y
CONFIG_SND_HDA_CODEC_HDMI=y
# 触摸屏
CONFIG_TOUCHSCREEN=y
CONFIG_TOUCHSCREEN_USB_COMPOSITE=y
# 工业接口
CONFIG_CAN=y
CONFIG_CAN_RAW=y
CONFIG_SPI=y
CONFIG_SPI_MASTER=y
CONFIG_CAN_VCAN=y

# ---------- 4. 存储增强（中优先级）----------
CONFIG_BLK_DEV_NVME=y
CONFIG_ATA=y
CONFIG_SATA_AHCI=y
CONFIG_MMC=y
CONFIG_MMC_BLOCK=y
CONFIG_DM_CRYPT=y
CONFIG_DM_VERITY=y
CONFIG_DM_THIN_PROVISIONING=y
CONFIG_DM_CACHE=y

# ---------- 5. 安全加固（高优先级）----------
CONFIG_SECURITY=y
CONFIG_SECURITY_SELINUX=y
CONFIG_SECURITY_APPARMOR=y
CONFIG_RANDOMIZE_BASE=y
CONFIG_STACKPROTECTOR_STRONG=y
CONFIG_STRICT_DEVMEM=y
CONFIG_STRICT_KERNEL_RWX=y
CONFIG_DEBUG_RODATA=y
CONFIG_MODULE_SIG=y
CONFIG_EFI_SECURE_BOOT=y
CONFIG_TPM=y
CONFIG_TPM_TIS=y
CONFIG_SECURITY_SELINUX_BOOTPARAM=y
CONFIG_SECURITY_APPARMOR_BOOTPARAM_VALUE=1

# ---------- 6. 调度器/性能优化（中优先级）----------
CONFIG_PREEMPT=y
CONFIG_SCHED_AUTOGROUP=y
CONFIG_CFQ_GROUP_IOSCHED=y
CONFIG_HUGETLBFS=y
CONFIG_HUGETLB_PAGE=y
CONFIG_TRANSPARENT_HUGEPAGE=y
CONFIG_NUMA=y
CONFIG_PREEMPT_COUNT=y

# ---------- 7. I/O 优化（中优先级）----------
CONFIG_READAHEAD=y
CONFIG_BLK_DEV_IO_TRACE=y
CONFIG_BLK_DEV_THROTTLING=y

# ---------- 8. 容器/虚拟化（低优先级）----------
CONFIG_CGROUPS=y
CONFIG_CGROUP_CPUACCT=y
CONFIG_CGROUP_DEVICE=y
CONFIG_CGROUP_FREEZER=y
CONFIG_CGROUP_SCHED=y
CONFIG_CPUSETS=y
CONFIG_NAMESPACES=y
CONFIG_OVERLAY_FS=y
CONFIG_VETH=y
CONFIG_KVM=y
CONFIG_VHOST_NET=y
CONFIG_VHOST_VSOCK=y
CONFIG_VHOST=y

# ---------- 9. 调试/监控（低优先级）----------
CONFIG_KGDB=y
CONFIG_KGDB_SERIAL_CONSOLE=y
CONFIG_FTRACE=y
CONFIG_FUNCTION_TRACER=y
CONFIG_PERF_EVENTS=y
CONFIG_KPROBES=y
CONFIG_CRASH_DUMP=y
CONFIG_DEBUG_FS=y
CONFIG_LATENCYTOP=y
CONFIG_DEBUG_PREEMPT=y
# ============================================================
#  追加内核配置（第二轮优化：更全的文件系统/网络协议/加密安全/存储/
#   GPU显示/音频/USB/输入/蓝牙无线/工业嵌入式/虚拟化容器/性能监控/
#   电源管理/打印扫描/多媒体/NVDIMM设备树，仅追加不删减，自动去重）
# ============================================================

# ---------- 1. 文件系统（更多）----------
CONFIG_EXFAT_FS=y
CONFIG_ISO9660_FS=y
CONFIG_UDF_FS=y
CONFIG_FUSE_FS=y
CONFIG_SQUASHFS=y
CONFIG_EROFS_FS=y

# ---------- 2. 网络协议栈 ----------
CONFIG_SCTP=y
CONFIG_DCCP=y
CONFIG_TIPC=y
CONFIG_MPTCP=y
CONFIG_IPV6_SIT=y
CONFIG_IPV6_TUNNEL=y
CONFIG_NETFILTER_XTABLES=y

# ---------- 3. 加密与安全（更深入）----------
CONFIG_CRYPTO=y
CONFIG_CRYPTO_AES=y
CONFIG_CRYPTO_SHA256=y
CONFIG_CRYPTO_SHA512=y
CONFIG_CRYPTO_RSA=y
CONFIG_CRYPTO_ECC=y
CONFIG_CRYPTO_CHACHA20=y
CONFIG_CRYPTO_POLY1305=y
CONFIG_CRYPTO_CURVE25519=y
CONFIG_CRYPTO_XXHASH=y
CONFIG_CRYPTO_CRC32C=y
CONFIG_SYSTEM_TRUSTED_KEYRING=y
CONFIG_INTEGRITY=y
CONFIG_IMA=y
CONFIG_EVM=y
CONFIG_ENCRYPTED_KEYS=y
CONFIG_TRUSTED_KEYS=y
CONFIG_KEY_DH_OPERATIONS=y

# ---------- 4. 高级存储 ----------
CONFIG_BCACHE=y
CONFIG_DM_SNAPSHOT=y
CONFIG_DM_MIRROR=y
CONFIG_DM_RAID=y
CONFIG_DM_MULTIPATH=y
CONFIG_DM_LOG_WRITES=y
CONFIG_DM_STRIPED=y
CONFIG_MD=y
CONFIG_MD_RAID0=y
CONFIG_MD_RAID1=y
CONFIG_MD_RAID10=y
CONFIG_MD_RAID456=y
CONFIG_NVME_FC=y
CONFIG_NVME_TCP=y
CONFIG_NVME_RDMA=y

# ---------- 5. GPU/显示（更全面）----------
CONFIG_DRM_AMDGPU=y
CONFIG_DRM_ETNAVIV=y
CONFIG_DRM_EXYNOS=y
CONFIG_DRM_IMX=y
CONFIG_DRM_MESON=y
CONFIG_DRM_MSM=y
CONFIG_DRM_OMAP=y
CONFIG_DRM_RCAR=y
CONFIG_DRM_ROCKCHIP=y
CONFIG_DRM_STM=y
CONFIG_DRM_SUN4I=y
CONFIG_DRM_TEGRA=y
CONFIG_DRM_V3D=y
CONFIG_DRM_VC4=y
CONFIG_DRM_XEN=y
CONFIG_DRM_ZYNQMP=y

# ---------- 6. 音频（更完整）----------
CONFIG_SND_HDA_CODEC_ANALOG=y
CONFIG_SND_HDA_CODEC_REALTEK=y
CONFIG_SND_HDA_CODEC_CA0110=y
CONFIG_SND_HDA_CODEC_CA0132=y
CONFIG_SND_HDA_CODEC_CMEDIA=y
CONFIG_SND_HDA_CODEC_CIRRUS=y
CONFIG_SND_HDA_CODEC_SIGMATEL=y

# ---------- 7. USB（更全面）----------
CONFIG_USB_DWC3=y
CONFIG_USB_DWC2=y
CONFIG_USB_CDNS3=y
CONFIG_USB_MUSB_HDRC=y
CONFIG_USB_RENESAS_USB3=y
CONFIG_USB_XHCI_MTK=y
CONFIG_USB_XHCI_PLATFORM=y
CONFIG_USB_NET_DRIVERS=y
CONFIG_USB_NET_AX8817X=y
CONFIG_USB_NET_AX88179=y
CONFIG_USB_NET_RTL8150=y
CONFIG_USB_NET_RTL8152=y

# ---------- 8. 输入设备（更多）----------
CONFIG_INPUT_JOYSTICK=y
CONFIG_INPUT_TABLET=y
CONFIG_INPUT_TOUCHSCREEN=y
CONFIG_INPUT_APMPOWER=y
CONFIG_INPUT_KEYSPAN=y
CONFIG_INPUT_PCSPKR=y

# ---------- 9. 无线/蓝牙（更完整）----------
CONFIG_BT=y
CONFIG_BT_HCIBTUSB=y
CONFIG_BT_HCIUART=y
CONFIG_BT_HCIUART_H4=y
CONFIG_BT_HCIUART_BCSP=y
CONFIG_BT_HCIUART_LL=y
CONFIG_BT_HCIUART_3WIRE=y
CONFIG_BT_HCIUART_INTEL=y
CONFIG_BT_HCIUART_BCM=y
CONFIG_BT_HCIUART_QCA=y
CONFIG_BT_RFCOMM=y
CONFIG_BT_BNEP=y
CONFIG_BT_CMTP=y
CONFIG_BT_HIDP=y
CONFIG_WLAN_VENDOR_ATH=y
CONFIG_WLAN_VENDOR_BROADCOM=y
CONFIG_WLAN_VENDOR_INTEL=y
CONFIG_WLAN_VENDOR_MEDIATEK=y
CONFIG_WLAN_VENDOR_QUANTENNA=y
CONFIG_WLAN_VENDOR_RALINK=y
CONFIG_WLAN_VENDOR_REALTEK=y
CONFIG_WLAN_VENDOR_RENESAS=y
CONFIG_WLAN_VENDOR_TI=y

# ---------- 10. 工业/嵌入式（更全面）----------
CONFIG_GPIO=y
CONFIG_GPIO_SYSFS=y
CONFIG_GPIO_AGGREGATOR=y
CONFIG_GPIO_PCA953X=y
CONFIG_GPIO_PCF857X=y
CONFIG_GPIO_MAX732X=y
CONFIG_I2C_GPIO=y
CONFIG_SPI_GPIO=y
CONFIG_PWM=y
CONFIG_PWM_SYSFS=y
CONFIG_WATCHDOG=y
CONFIG_WATCHDOG_GPIO=y
CONFIG_HW_RANDOM=y
CONFIG_HW_RANDOM_TPM=y
CONFIG_NVDIMM=y
CONFIG_DAX=y
CONFIG_DEV_DAX=y

# ---------- 11. 虚拟化/容器（更深入）----------
CONFIG_BLK_CGROUP=y
CONFIG_CGROUP_BPF=y
CONFIG_CGROUP_NET_PRIO=y
CONFIG_CGROUP_NET_CLASSID=y
CONFIG_CGROUP_PIDS=y
CONFIG_CGROUP_RDMA=y
CONFIG_CGROUP_PERF=y
CONFIG_CFS_BANDWIDTH=y
CONFIG_RT_GROUP_SCHED=y
CONFIG_USER_NS=y
CONFIG_PID_NS=y
CONFIG_NET_NS=y
CONFIG_IPC_NS=y
CONFIG_UTS_NS=y
CONFIG_TIME_NS=y
CONFIG_CGROUP_NS=y
CONFIG_VIRTIO_BALLOON=y
CONFIG_VIRTIO_MMIO=y
CONFIG_VIRTIO_PCI=y
CONFIG_VIRTIO_PCI_LEGACY=y
CONFIG_VIRTIO_PCI_MODERN=y

# ---------- 12. 性能监控（更完整）----------
CONFIG_PERF_EVENTS_INTEL_UNCORE=y
CONFIG_PERF_EVENTS_INTEL_RAPL=y
CONFIG_PERF_EVENTS_INTEL_CSTATE=y
CONFIG_PERF_EVENTS_AMD_POWER=y
CONFIG_TRACEPOINTS=y
CONFIG_HAVE_SYSTEM_TRACING=y
CONFIG_FUNCTION_GRAPH_TRACER=y
CONFIG_IRQSOFF_TRACER=y
CONFIG_PREEMPT_TRACER=y
CONFIG_SCHED_TRACER=y
CONFIG_MMIOTRACE=y
CONFIG_KPROBE_EVENT=y
CONFIG_UPROBE_EVENT=y
CONFIG_DYNAMIC_FTRACE=y
CONFIG_FUNCTION_PROFILER=y
CONFIG_STACK_TRACER=y
CONFIG_TRACE_BRANCH_PROFILING=y

# ---------- 13. 电源管理 ----------
CONFIG_ACPI=y
CONFIG_ACPI_BATTERY=y
CONFIG_ACPI_AC=y
CONFIG_ACPI_FAN=y
CONFIG_ACPI_THERMAL=y
CONFIG_ACPI_CPUFREQ=y
CONFIG_CPU_FREQ=y
CONFIG_CPU_FREQ_STAT=y
CONFIG_CPU_FREQ_GOV_USERSPACE=y
CONFIG_CPU_FREQ_GOV_ONDEMAND=y
CONFIG_CPU_FREQ_GOV_CONSERVATIVE=y
CONFIG_CPU_IDLE=y
CONFIG_CPU_IDLE_GOV_MENU=y
CONFIG_ENERGY_MODEL=y
CONFIG_ENERGY_AWARE=y
CONFIG_CPU_THERMAL=y
CONFIG_THERMAL=y
CONFIG_THERMAL_WRITABLE_TRIPS=y
CONFIG_PM=y
CONFIG_PM_SLEEP=y
CONFIG_PM_RUNTIME=y
CONFIG_SUSPEND=y
CONFIG_HIBERNATION=y

# ---------- 14. 打印/扫描 ----------
CONFIG_PRINTER=y
CONFIG_USB_PRINTER=y
CONFIG_IPP=y
CONFIG_USB_SERIAL=y
CONFIG_USB_SERIAL_PL2303=y
CONFIG_USB_SERIAL_FTDI_SIO=y
CONFIG_USB_SERIAL_CP210X=y
CONFIG_USB_SERIAL_CH341=y

# ---------- 15. 多媒体（编解码/摄像头）----------
CONFIG_V4L2=y
CONFIG_VIDEO_DEV=y
CONFIG_VIDEO_V4L2=y
CONFIG_V4L2_MEM2MEM=y
CONFIG_V4L2_FWNODE=y
CONFIG_MEDIA_CONTROLLER=y
CONFIG_MEDIA_SUPPORT=y
CONFIG_DRM_DP_AUX_BUS=y
CONFIG_FW_LOADER=y
CONFIG_FW_LOADER_USER_HELPER=y

# ---------- 16. NVDIMM/持久内存 & 设备树（嵌入式必需）----------
CONFIG_OF=y
CONFIG_OF_ADDRESS=y
CONFIG_OF_IRQ=y
CONFIG_OF_GPIO=y
CONFIG_OF_I2C=y
CONFIG_OF_SPI=y
CONFIG_OF_NET=y
CONFIG_OF_MDIO=y
CONFIG_OF_RESERVED_MEM=y

# ===== 本轮追加 (2)：补齐空缺 + 国密/专用加密/更多硬件/调试/电源/RF/多媒体 =====
# 1. 更多文件系统
CONFIG_ECRYPT_FS=y
CONFIG_UBIFS_FS=y
CONFIG_JFFS2_FS=y
CONFIG_ROMFS_FS=y
CONFIG_CRAMFS=y
CONFIG_EFIVAR_FS=y
# 2. 更多网络协议
CONFIG_IP_MROUTE=y
CONFIG_IP_PIMSM_V1=y
CONFIG_IP_PIMSM_V2=y
# 3. 更多存储
CONFIG_ZRAM=y
CONFIG_DM_ZERO=y
CONFIG_DM_FLAKEY=y
CONFIG_MTD=y
CONFIG_MTD_BLOCK=y
CONFIG_MTD_CFI=y
CONFIG_MTD_NAND=y
# 4. 更多 GPU（补齐新硬件）
CONFIG_DRM_PANEL=y
CONFIG_DRM_BRIDGE=y
CONFIG_DRM_LOONGSON=y
CONFIG_DRM_HISI_HIBMC=y
CONFIG_DRM_KMB=y
CONFIG_DRM_GM12U320=y
# 5. 更多 USB（补齐新硬件）
CONFIG_USB_ACM=y
CONFIG_USB_SERIAL_SIMPLE=y
CONFIG_USB_SERIAL_OPTION=y
CONFIG_USB_SERIAL_QC_SERIAL=y
CONFIG_USB_TMC=y
CONFIG_USB_WDM=y
# 6. 更多音频（补齐新硬件）
CONFIG_SND_SOC=y
CONFIG_SND_SOC_AMD=y
CONFIG_SND_SOC_INTEL=y
CONFIG_SND_SOC_ROCKCHIP=y
CONFIG_SND_SOC_TEGRA=y
CONFIG_SND_SOC_BCM=y
CONFIG_SND_PCI=y
CONFIG_SND_PCI_AC97=y
# 7. 更多加密算法（国密/专用）
CONFIG_CRYPTO_CAMELLIA=y
CONFIG_CRYPTO_TWOFISH=y
CONFIG_CRYPTO_SERPENT=y
CONFIG_CRYPTO_CAST5=y
CONFIG_CRYPTO_CAST6=y
CONFIG_CRYPTO_USER_API=y
CONFIG_CRYPTO_USER_API_HASH=y
CONFIG_CRYPTO_USER_API_SKCIPHER=y
# 8. 更多网络硬件驱动
CONFIG_NET_VENDOR_AMAZON=y
CONFIG_NET_VENDOR_GOOGLE=y
CONFIG_NET_VENDOR_MICROSOFT=y
CONFIG_NET_VENDOR_HUAWEI=y
CONFIG_NET_VENDOR_CHELSIO=y
CONFIG_NET_VENDOR_QLOGIC=y
CONFIG_NET_VENDOR_EMULEX=y
CONFIG_NET_VENDOR_CISCO=y
CONFIG_NET_VENDOR_HP=y
CONFIG_NET_VENDOR_IBM=y
# 9. 更多存储硬件（SAS/FC）
CONFIG_SCSI_SAS_ATA=y
CONFIG_SCSI_SAS_LIBSAS=y
CONFIG_SCSI_MPT3SAS=y
CONFIG_SCSI_MPT2SAS=y
CONFIG_FUSION=y
CONFIG_FUSION_SAS=y
# 10. 更多输入设备
CONFIG_INPUT_UINPUT=y
CONFIG_INPUT_JOYDEV=y
CONFIG_INPUT_FF_MEMLESS=y
CONFIG_INPUT_POLLDEV=y
CONFIG_INPUT_SPARSEKMAP=y
# 11. 更多容器/虚拟化
CONFIG_VIRTIO_INPUT=y
CONFIG_VIRTIO_CONSOLE=y
CONFIG_VIRTIO_RNG=y
CONFIG_VIRTIO_FS=y
CONFIG_VSOCKETS=y
CONFIG_VSOCKETS_DIAG=y
# 12. 更多调试
CONFIG_KALLSYMS=y
CONFIG_KALLSYMS_ALL=y
CONFIG_DEBUG_KMEMLEAK=y
CONFIG_DEBUG_OBJECTS=y
CONFIG_DEBUG_LIST=y
CONFIG_DEBUG_SPINLOCK=y
CONFIG_DEBUG_MUTEXES=y
CONFIG_DEBUG_ATOMIC_SLEEP=y
CONFIG_LOCKUP_DETECTOR=y
CONFIG_HARDLOCKUP_DETECTOR=y
# 13. 更多电源管理（ARM/嵌入式）
CONFIG_ARM_CPUIDLE=y
CONFIG_ARM_PSCI=y
CONFIG_ARM_PSCI_CPUIDLE=y
CONFIG_CPU_PM=y
CONFIG_CLOCKSOURCE_WATCHDOG=y
CONFIG_SCHED_MC=y
CONFIG_SCHED_SMT=y
# 14. 更多 RF/无线
CONFIG_NFC=y
CONFIG_NFC_DIGITAL=y
CONFIG_NFC_NCI=y
CONFIG_NFC_HCI=y
CONFIG_IEEE802154=y
CONFIG_IEEE802154_6LOWPAN=y
CONFIG_MAC802154=y
CONFIG_WPAN=y
# 15. 更多多媒体
CONFIG_VIDEOBUF2_V4L2=y
CONFIG_VIDEOBUF2_DMA_CONTIG=y
CONFIG_VIDEOBUF2_VMALLOC=y
CONFIG_MEDIA_USB_SUPPORT=y
CONFIG_USB_VIDEO_CLASS=y
CONFIG_USB_GSPCA=y
CONFIG_RADIO_ADAPTERS=y
CONFIG_DVB_CORE=y
CONFIG_DVB_USB=y
# ===== 第3轮追加(1/17): 更多文件系统（深度嵌入式/特殊场景）=====
CONFIG_AFS_FS=y
CONFIG_9P_FS=y
CONFIG_CEPH_FS=y
CONFIG_ORANGEFS_FS=y
CONFIG_GFS2_FS=y
CONFIG_OCFS2_FS=y
CONFIG_JFS_FS=y
CONFIG_REISERFS_FS=y
CONFIG_HFS_FS=y
CONFIG_HFSPLUS_FS=y
CONFIG_ZONEFS_FS=y
CONFIG_PSTORE=y
CONFIG_PSTORE_RAM=y
CONFIG_PSTORE_BLK=y
# ===== 第3轮追加(2/17): 更多网络协议（5G/边缘计算）=====
CONFIG_6LOWPAN=y
CONFIG_6LOWPAN_NHC=y
CONFIG_NET_9P=y
CONFIG_NET_9P_VIRTIO=y
CONFIG_RDS=y
CONFIG_RDS_TCP=y
CONFIG_RDS_RDMA=y
CONFIG_L2TP=y
CONFIG_L2TP_ETH=y
CONFIG_L2TP_DEBUGFS=y
CONFIG_PPPOE=y
CONFIG_PPP_ASYNC=y
CONFIG_PPP_SYNC_TTY=y
CONFIG_PPP_DEFLATE=y
CONFIG_PPP_BSDCOMP=y
CONFIG_PPP_MPPE=y
CONFIG_NET_PTP=y
CONFIG_PTP_1588_CLOCK=y
# ===== 第3轮追加(3/17): 更多存储（分布式/新型存储）=====
CONFIG_NBD=y
CONFIG_NBD_DEV=y
CONFIG_TARGET_CORE=y
CONFIG_FC=y
CONFIG_FCOE=y
CONFIG_LIBFC=y
CONFIG_NVME_FC_TRANSPORT=y
CONFIG_DEV_DAX_PMEM=y
CONFIG_DEV_DAX_KMEM=y
# ===== 第3轮追加(4/17): 更多加密算法（后量子/哈希/磁盘加密）=====
CONFIG_CRYPTO_KECCAK=y
CONFIG_CRYPTO_SHA3=y
CONFIG_CRYPTO_BLAKE2B=y
CONFIG_CRYPTO_GHASH=y
CONFIG_CRYPTO_GCM=y
CONFIG_CRYPTO_CCM=y
CONFIG_CRYPTO_CTS=y
CONFIG_CRYPTO_LRW=y
CONFIG_CRYPTO_XTS=y
CONFIG_CRYPTO_ESSIV=y
CONFIG_CRYPTO_MD4=y
CONFIG_CRYPTO_MD5=y
CONFIG_CRYPTO_RIPEMD160=y
CONFIG_CRYPTO_RIPEMD256=y
CONFIG_CRYPTO_RIPEMD320=y
CONFIG_CRYPTO_WP512=y
CONFIG_CRYPTO_CRC32=y
CONFIG_CRYPTO_CRC64=y
CONFIG_CRYPTO_TEST=y
# ===== 第3轮追加(5/17): 更多虚拟机/容器（Xen/Hyper-V/VMware 隔离）=====
CONFIG_XEN=y
CONFIG_XEN_PV=y
CONFIG_HYPERV=y
CONFIG_HYPERV_BALLOON=y
CONFIG_HYPERV_NET=y
CONFIG_HYPERV_STORAGE=y
CONFIG_VMWARE_BALLOON=y
CONFIG_VMWARE_PVSCSI=y
CONFIG_VMWARE_VMXNET3=y
CONFIG_PARAVIRT_DEBUG=y
# ===== 第3轮追加(6/17): 更多无线（IoT/LPWAN/BLE/Mesh/ZigBee/Matter）=====
# ===== 第3轮追加(7/17): 更多多媒体（视频编解码/图像解码）=====
CONFIG_SDIO_UART=y
# ===== 第3轮追加(8/17): 更多工业/自动化（现场总线/工业以太网/物联网协议）=====
# ===== 第3轮追加(9/17): 更多电源/能源管理（电池/充电器/传感器/RAPL）=====
CONFIG_POWER_SUPPLY=y
CONFIG_BATTERY=y
CONFIG_CHARGER=y
CONFIG_SENSORS=y
# ===== 第3轮追加(10/17): 更多串行/通信（8250/I2C从/SPI/各SoC串口）=====
CONFIG_SERIAL_8250_DMA=y
CONFIG_SERIAL_8250_MANY_PORT=y
CONFIG_SERIAL_IMX=y
CONFIG_SERIAL_TEGRA=y
CONFIG_SERIAL_MSM=y
CONFIG_I2C_SLAVE=y
CONFIG_SPI_BCM2835=y
# ===== 第3轮追加(11/17): 更多SoC/嵌入式（新兴平台）=====
CONFIG_ARCH_ROCKCHIP=y
CONFIG_ARCH_SUNXI=y
CONFIG_ARCH_TEGRA=y
CONFIG_ARCH_ZYNQ=y
# ===== 第3轮追加(12/17): 更多调试/性能分析（调试信息/VM/PMU）=====
CONFIG_DEBUG_KERNEL=y
CONFIG_DEBUG_INFO=y
CONFIG_DEBUG_INFO_DWARF5=y
CONFIG_DEBUG_VM=y
CONFIG_DEBUG_PAGE_ALLOC=y
CONFIG_DEBUG_BUGVERBOSE=y
CONFIG_DEBUG_WX=y
# ===== 第3轮追加(13/17): 更多固件/微码（CPU微码/EFI胶囊/压缩固件）=====
CONFIG_MICROCODE=y
CONFIG_MICROCODE_INTEL=y
CONFIG_MICROCODE_AMD=y
CONFIG_MICROCODE_OLD_INTERFACE=y
CONFIG_EFI_CAPSULE=y
CONFIG_EFI_CAPSULE_LOADER=y
# ===== 第3轮追加(14/17): 旧硬件兼容（ISA/PnP/AGP/老旧DRM）=====
# ===== 第3轮追加(15/17): 更多输入（ALPS/Apple/Sentelic/PS2/触摸屏IC）=====
# ===== 第3轮追加(16/17): 更多NVM/持久内存（NVDIMM/NFIT/BTT/安全）=====
CONFIG_LIBNVDIMM=y
CONFIG_ACPI_NFIT=y
# ===== 第3轮追加(17/17): 更多集群/分布式（LVS/IPVS/DLM）=====
CONFIG_IP_VS=y
CONFIG_IP_VS_RR=y
CONFIG_IP_VS_WRR=y
CONFIG_IP_VS_LC=y
CONFIG_IP_VS_WLC=y
CONFIG_IP_VS_LBLC=y
CONFIG_IP_VS_LBLCR=y
CONFIG_IP_VS_DH=y
CONFIG_IP_VS_SH=y
CONFIG_IP_VS_SED=y
CONFIG_IP_VS_NQ=y
CONFIG_IP_VS_FTP=y
CONFIG_DLM=y
CONFIG_DLM_DEBUG=y
"""

# 架构专属内核配置追加（仅在对应架构下启用）
ARCH_KERNEL_CONFIG: Dict[str, str] = {
    "x86_64": """
# x86_64 specifics
CONFIG_64BIT=y
CONFIG_X86_64=y
CONFIG_EFI=y
CONFIG_EFI_STUB=y
CONFIG_FB_VESA=y
CONFIG_FB_EFI=y
CONFIG_PARAVIRT=y
CONFIG_KVM_GUEST=y
CONFIG_HYPERVISOR_GUEST=y
""",
    "i386": """
# i386 specifics
CONFIG_32BIT=y
CONFIG_X86_32=y
CONFIG_FB_VESA=y
""",
    "arm64": """
# ARM64 specifics
CONFIG_64BIT=y
CONFIG_ARM64=y
CONFIG_EFI=y
CONFIG_EFI_STUB=y
CONFIG_VIRTIO=y
CONFIG_VIRTIO_BLK=y
CONFIG_VIRTIO_NET=y
CONFIG_VIRTIO_CONSOLE=y
CONFIG_SERIAL_AMBA_PL011=y
CONFIG_SERIAL_AMBA_PL011_CONSOLE=y
CONFIG_FB=y
CONFIG_FB_SIMPLE=y
CONFIG_DRM=y
CONFIG_DRM_VIRTIO_GPU=y
""",
    "arm": """
# ARM 32 specifics
CONFIG_32BIT=y
CONFIG_ARM=y
CONFIG_VIRTIO=y
CONFIG_VIRTIO_BLK=y
CONFIG_VIRTIO_NET=y
CONFIG_SERIAL_AMBA_PL011=y
CONFIG_SERIAL_AMBA_PL011_CONSOLE=y
CONFIG_FB=y
CONFIG_FB_SIMPLE=y
""",
    "riscv64": """
# RISC-V 64 specifics
CONFIG_64BIT=y
CONFIG_RISCV=y
CONFIG_RISCV_ISA_C=y
CONFIG_EFI=y
CONFIG_EFI_STUB=y
CONFIG_SERIAL_8250=y
CONFIG_SERIAL_8250_CONSOLE=y
CONFIG_FB=y
CONFIG_FB_SIMPLE=y
""",
    "ppc64le": """
# PowerPC 64le specifics
CONFIG_64BIT=y
CONFIG_PPC64=y
CONFIG_PPC64LE=y
CONFIG_CPU_LITTLE_ENDIAN=y
CONFIG_EFI=y
CONFIG_EFI_STUB=y
CONFIG_PPC_POWERNV=y
CONFIG_PPC_OF_BOOT_TRAMPOLINE=y
CONFIG_SERIAL_8250=y
CONFIG_SERIAL_8250_CONSOLE=y
CONFIG_FB=y
CONFIG_FB_SIMPLE=y
CONFIG_PPC_VAS=y
""",
    "mips64": """
# MIPS 64 specifics
CONFIG_64BIT=y
CONFIG_MIPS=y
CONFIG_MIPS32_O32=y
CONFIG_MIPS32_N32=y
CONFIG_CPU_MIPS64_R2=y
CONFIG_SERIAL_8250=y
CONFIG_SERIAL_8250_CONSOLE=y
CONFIG_FB=y
CONFIG_FB_SIMPLE=y
""",
}


# ============================================================
#  elf_runner.c 源码（静态编译为 /init，作为 PID 1）
# ============================================================
# 功能：挂载基础文件系统 → 设置完整环境 → 重试机制启动用户 ELF
# 注意：这是 C 代码嵌入 Python 字符串，使用 r''' ... ''' 包裹
# 多架构注意：此 C 源码只用标准 POSIX/linux 头，x86/ARM/RISC-V/PowerPC/MIPS
# 全部可正常编译（无 x86 内联汇编），故单一源码通用于所有架构。

ELF_RUNNER_C = r'''/* elf_runner.c - Minimal init for elf2os (Python ELF optimized, multi-arch) */
#include <unistd.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <dirent.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <fcntl.h>

static void mkdir_p(const char *path) {
    char buf[512];
    snprintf(buf, sizeof(buf), "%s", path);
    for (char *p = buf + 1; *p; p++) {
        if (*p == '/') {
            *p = '\0';
            mkdir(buf, 0755);
            *p = '/';
        }
    }
    mkdir(buf, 0755);
}

static void wait_for_dev(const char *devname, int timeout_sec) {
    char path[256];
    snprintf(path, sizeof(path), "/dev/%s", devname);
    for (int i = 0; i < timeout_sec * 10; i++) {
        if (access(path, F_OK) == 0) return;
        usleep(100000); /* 100ms */
    }
}

static void write_file(const char *path, const char *content) {
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return;
    write(fd, content, strlen(content));
    close(fd);
}

/* 递归删除目录（用于清理 PyInstaller _MEIxxxx 残留） */
static int rm_rf(const char *path) {
    struct stat st;
    if (lstat(path, &st) != 0) return 0;
    if (!S_ISDIR(st.st_mode)) return unlink(path);
    DIR *d = opendir(path);
    if (!d) return -1;
    struct dirent *ent;
    char child[1024];
    while ((ent = readdir(d)) != NULL) {
        if (strcmp(ent->d_name, ".") == 0 || strcmp(ent->d_name, "..") == 0) continue;
        snprintf(child, sizeof(child), "%s/%s", path, ent->d_name);
        rm_rf(child);
    }
    closedir(d);
    return rmdir(path);
}

/* 清理 /tmp 下所有 PyInstaller _MEIxxxx 残留临时目录 */
static void cleanup_mei_dirs(void) {
    DIR *d = opendir("/tmp");
    if (!d) return;
    struct dirent *ent;
    char path[1024];
    while ((ent = readdir(d)) != NULL) {
        if (strncmp(ent->d_name, "_MEI", 4) == 0) {
            snprintf(path, sizeof(path), "/tmp/%s", ent->d_name);
            rm_rf(path);
        }
    }
    closedir(d);
}

int main(void) {
    /* 1. 创建所有必要目录 */
    mkdir_p("/proc");
    mkdir_p("/sys");
    mkdir_p("/dev");
    mkdir_p("/dev/pts");
    mkdir_p("/dev/shm");
    mkdir_p("/tmp");
    mkdir_p("/bin");
    mkdir_p("/lib");
    mkdir_p("/lib64");
    mkdir_p("/usr");
    mkdir_p("/usr/bin");
    mkdir_p("/usr/lib");
    mkdir_p("/usr/lib64");
    mkdir_p("/usr/lib/x86_64-linux-gnu");
    mkdir_p("/usr/lib/aarch64-linux-gnu");
    mkdir_p("/usr/lib/riscv64-linux-gnu");
    mkdir_p("/usr/lib/powerpc64le-linux-gnu");
    mkdir_p("/usr/lib/mips64-linux-gnuabi64");
    mkdir_p("/usr/lib/python3");
    mkdir_p("/usr/lib/python3/lib-dynload");
    mkdir_p("/usr/lib/python3/site-packages");
    mkdir_p("/etc");
    mkdir_p("/root");
    mkdir_p("/mnt");
    mkdir_p("/run");
    mkdir_p("/var");
    mkdir_p("/var/log");

    /* 2. 挂载核心文件系统 */
    mount("proc", "/proc", "proc", 0, NULL);
    mount("sysfs", "/sys", "sysfs", 0, NULL);
    mount("devtmpfs", "/dev", "devtmpfs", 0, "mode=0755");
    mount("devpts", "/dev/pts", "devpts", 0, "mode=0620,gid=5");
    /* tmpfs 512MB - PyInstaller onefile 解压需要大量临时空间 */
    mount("tmpfs", "/tmp", "tmpfs", 0, "size=512M,mode=1777");
    /* /dev/shm for Python multiprocessing shared memory */
    mount("tmpfs", "/dev/shm", "tmpfs", 0, "size=64M,mode=1777");

    /* 3. 等待关键设备就绪 */
    wait_for_dev("tty0", 5);
    wait_for_dev("console", 5);
    wait_for_dev("null", 3);
    wait_for_dev("zero", 3);
    wait_for_dev("random", 3);
    wait_for_dev("urandom", 3);

    /* 4. 设置符号链接 (必要设备) */
    symlink("/proc/self/fd", "/dev/fd");
    symlink("/proc/self/fd/0", "/dev/stdin");
    symlink("/proc/self/fd/1", "/dev/stdout");
    symlink("/proc/self/fd/2", "/dev/stderr");

    /* 5. 设置完整环境变量 (Python ELF 关键) */
    setenv("PATH", "/bin:/usr/bin:/usr/local/bin", 1);
    setenv("HOME", "/tmp", 1);
    setenv("TERM", "linux", 1);
    setenv("TMPDIR", "/tmp", 1);
    setenv("TMP", "/tmp", 1);
    setenv("TEMP", "/tmp", 1);
    /* LD_LIBRARY_PATH 覆盖所有可能路径（含各架构 multiarch 目录） */
    setenv("LD_LIBRARY_PATH",
           "/lib:/lib64:/usr/lib:/usr/lib64:"
           "/usr/lib/x86_64-linux-gnu:/usr/lib/aarch64-linux-gnu:"
           "/usr/lib/riscv64-linux-gnu:/usr/lib/powerpc64le-linux-gnu:"
           "/usr/lib/mips64-linux-gnuabi64:"
           "/usr/lib/python3:/usr/lib/python3/lib-dynload:"
           "/usr/lib/python3/site-packages", 1);
    setenv("LD_PRELOAD", "", 1);
    /* Python 环境：PYTHONHOME 指向 /usr，使 /usr/lib/python3.x 可被自动发现 */
    setenv("PYTHONHOME", "/usr", 1);
    setenv("PYTHONPATH", "/usr/lib/python3:/usr/lib/python3/site-packages", 1);
    setenv("PYTHONDONTWRITEBYTECODE", "1", 1);
    setenv("PYTHONUNBUFFERED", "1", 1);
    setenv("PYTHONIOENCODING", "utf-8", 1);
    setenv("PYTHONNOUSERSITE", "1", 1);
    setenv("OPENSSL_CONF", "/dev/null", 1);
    setenv("LANG", "C.UTF-8", 1);
    setenv("LC_ALL", "C.UTF-8", 1);

    /* 5b. 清理残留 PyInstaller _MEIxxxx 临时目录 + 切换到可写工作目录 */
    cleanup_mei_dirs();
    mkdir_p("/tmp/_MEI");
    chdir("/tmp");

    /* 6. 创建 /etc/ld.so.conf */
    write_file("/etc/ld.so.conf",
        "/lib\n/lib64\n/usr/lib\n/usr/lib64\n"
        "/usr/lib/x86_64-linux-gnu\n"
        "/usr/lib/aarch64-linux-gnu\n"
        "/usr/lib/riscv64-linux-gnu\n"
        "/usr/lib/powerpc64le-linux-gnu\n"
        "/usr/lib/mips64-linux-gnuabi64\n"
        "/usr/lib/python3\n"
        "/usr/lib/python3/lib-dynload\n"
        "/usr/lib/python3/site-packages\n");

    /* 7. 输出启动横幅 */
    const char *banner =
        "\n"
        "╔══════════════════════════════════════════╗\n"
        "║         elf2os - Multi-Arch ELF Boot     ║\n"
        "║     tmpfs=512M  LD_PATH=full  PYTHON=on  ║\n"
        "╚══════════════════════════════════════════╝\n\n";
    write(1, banner, strlen(banner));

    /* 8. 重试机制启动用户 ELF（最多 3 次） */
    char *os_argv[] = { "/bin/os.elf", NULL };
    char *os_envp[] = {
        "PATH=/bin:/usr/bin:/usr/local/bin",
        "HOME=/tmp",
        "TERM=linux",
        "TMPDIR=/tmp",
        "LD_LIBRARY_PATH=/lib:/lib64:/usr/lib:/usr/lib64:"
        "/usr/lib/x86_64-linux-gnu:/usr/lib/aarch64-linux-gnu",
        "PYTHONHOME=/usr",
        "PYTHONPATH=/usr/lib/python3:/usr/lib/python3/site-packages",
        "PYTHONNOUSERSITE=1",
        "LANG=C.UTF-8",
        NULL
    };

    for (int attempt = 1; attempt <= 3; attempt++) {
        char msg[256];
        snprintf(msg, sizeof(msg), "[elf_runner] Attempt %d/3: exec /bin/os.elf\n", attempt);
        write(1, msg, strlen(msg));

        pid_t pid = fork();
        if (pid == 0) {
            execve("/bin/os.elf", os_argv, os_envp);
            const char *err_prefix = "[FATAL] execve failed: ";
            write(2, err_prefix, strlen(err_prefix));
            write(2, strerror(errno), strlen(strerror(errno)));
            write(2, "\n", 1);
            _exit(127);
        } else if (pid > 0) {
            int status = 0;
            waitpid(pid, &status, 0);
            if (WIFEXITED(status) && WEXITSTATUS(status) == 0) {
                const char *msg2 = "[elf_runner] ELF exited cleanly, restarting...\n";
                write(1, msg2, strlen(msg2));
                continue;
            } else if (WIFSIGNALED(status)) {
                int sig = WTERMSIG(status);
                char sigmsg[128];
                snprintf(sigmsg, sizeof(sigmsg),
                         "[elf_runner] ELF killed by signal %d, %s\n",
                         sig, (attempt < 3) ? "retrying..." : "giving up.");
                write(2, sigmsg, strlen(sigmsg));
                if (attempt >= 3) break;
            } else {
                int rc = WIFEXITED(status) ? WEXITSTATUS(status) : -1;
                char rcmsg[128];
                snprintf(rcmsg, sizeof(rcmsg),
                         "[elf_runner] ELF exited with code %d, %s\n",
                         rc, (attempt < 3) ? "retrying..." : "giving up.");
                write(2, rcmsg, strlen(rcmsg));
                if (attempt >= 3) break;
            }
        }
        sleep(1);
    }

    /* 9. 全部失败 → 尝试 busybox shell 作为最后的救命稻草 */
    const char *fallback_msg = "\n[elf_runner] All attempts failed, dropping to shell...\n";
    write(2, fallback_msg, strlen(fallback_msg));

    if (access("/bin/busybox", X_OK) == 0) {
        execl("/bin/busybox", "sh", NULL);
    }

    const char *despair = "\n[elf_runner] No shell available. PID 1 sleeping forever.\n";
    write(2, despair, strlen(despair));
    for (;;) {
        sleep(3600);
    }
    return 0;
}
'''


# ============================================================
#  日志 & 进度回调
# ============================================================

class BuildCallbacks:
    """GUI 回调接口，由前端注入"""
    def log(self, level: str, msg: str):
        print(f"[{level}] {msg}", flush=True)
    def progress(self, pct: int, msg: str = ""):
        pass
    def done(self, success: bool, iso_path: str = "", error: str = ""):
        pass


# ============================================================
#  工具函数
# ============================================================

def detect_distro() -> Tuple[str, str]:
    """检测发行版，返回 (family, name)"""
    try:
        with open("/etc/os-release") as f:
            content = f.read()
        info = {}
        for line in content.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                info[k.strip()] = v.strip().strip('"')
        name = info.get("ID", "unknown").lower()
        family = name
        if name in ("ubuntu", "debian", "kali", "raspbian", "linuxmint",
                    "elementary", "pop", "zorin"):
            family = "debian"
        elif name in ("arch", "manjaro", "endeavouros", "garuda", "artix"):
            family = "arch"
        elif name in ("fedora", "rhel", "centos", "rocky", "almalinux"):
            family = "redhat"
        return family, name
    except Exception:
        pass
    if shutil.which("apt-get"):
        return "debian", "debian"
    if shutil.which("pacman"):
        return "arch", "arch"
    if shutil.which("dnf") or shutil.which("yum"):
        return "redhat", "fedora"
    return "unknown", "unknown"


def sudo_run(cmd: List[str], password: str, timeout: int = 600) -> Tuple[int, str, str]:
    """使用 sudo 运行命令，返回 (rc, stdout, stderr)"""
    full_cmd = ["sudo", "-S", "-p", ""] + cmd
    try:
        proc = subprocess.run(
            full_cmd,
            input=password + "\n",
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except Exception as e:
        return -1, "", str(e)


def run_cmd(cmd: List[str], cwd: Optional[str] = None, env: Optional[Dict] = None,
            timeout: int = 3600) -> Tuple[int, str, str]:
    """运行命令，返回 (rc, stdout, stderr)"""
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except Exception as e:
        return -1, "", str(e)


def download_file(url: str, dest: str, progress_cb: Optional[Callable] = None) -> bool:
    """下载文件，支持进度回调"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "elf2os/2.1"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            total = int(resp.headers.get("Content-Length", "0"))
            downloaded = 0
            chunk_size = 1024 * 256
            with open(dest, "wb") as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb and total > 0:
                        pct = int(downloaded * 100 / total)
                        progress_cb(pct)
        return True
    except Exception as e:
        print(f"Download error: {e}", file=sys.stderr)
        return False


def verify_sha256(filepath: str, expected: str) -> bool:
    """验证 SHA256"""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().lower() == expected.lower()


def is_valid_elf(filepath: str) -> bool:
    """检查文件是否为有效的 ELF"""
    try:
        with open(filepath, "rb") as f:
            header = f.read(16)
        if len(header) < 16:
            return False
        if header[:4] != b"\x7fELF":
            return False
        ei_class = header[4]
        ei_data = header[5]
        if ei_class not in (1, 2) or ei_data not in (1, 2):
            return False
        return True
    except Exception:
        return False


def is_statically_linked(filepath: str) -> bool:
    """检查 ELF 是否为静态链接"""
    try:
        rc, out, _ = run_cmd(["ldd", filepath])
        out_lower = out.lower()
        if rc != 0 and ("not a dynamic" in out_lower or "statically linked" in out_lower):
            return True
        if "statically linked" in out_lower:
            return True
        if rc == 0 and "=>" not in out:
            return True
    except Exception:
        pass
    try:
        with open(filepath, "rb") as f:
            header = f.read(64)
        if len(header) < 52:
            return False
        ei_class = header[4]
        if ei_class == 2:
            e_phoff = struct.unpack_from("<Q", header, 32)[0]
            e_phentsize = struct.unpack_from("<H", header, 54)[0]
            e_phnum = struct.unpack_from("<H", header, 56)[0]
        elif ei_class == 1:
            e_phoff = struct.unpack_from("<I", header, 28)[0]
            e_phentsize = struct.unpack_from("<H", header, 42)[0]
            e_phnum = struct.unpack_from("<H", header, 44)[0]
        else:
            return False
        with open(filepath, "rb") as f:
            f.seek(e_phoff)
            for i in range(min(e_phnum, 32)):
                phdr = f.read(e_phentsize)
                if len(phdr) < 8:
                    break
                p_type = struct.unpack_from("<I", phdr, 0)[0]
                if p_type == 3:  # PT_INTERP
                    return False
        return True
    except Exception:
        pass
    return False


def get_elf_interpreter(filepath: str) -> str:
    """获取 ELF 的 PT_INTERP（动态链接器路径）"""
    try:
        with open(filepath, "rb") as f:
            header = f.read(64)
        ei_class = header[4]
        if ei_class == 2:
            e_phoff = struct.unpack_from("<Q", header, 32)[0]
            e_phentsize = struct.unpack_from("<H", header, 54)[0]
            e_phnum = struct.unpack_from("<H", header, 56)[0]
        else:
            e_phoff = struct.unpack_from("<I", header, 28)[0]
            e_phentsize = struct.unpack_from("<H", header, 42)[0]
            e_phnum = struct.unpack_from("<H", header, 44)[0]

        with open(filepath, "rb") as f:
            f.seek(e_phoff)
            for i in range(e_phnum):
                phdr = f.read(e_phentsize)
                if len(phdr) < 8:
                    break
                p_type = struct.unpack_from("<I", phdr, 0)[0]
                if p_type == 3:
                    if ei_class == 2:
                        p_offset = struct.unpack_from("<Q", phdr, 8)[0]
                        p_filesz = struct.unpack_from("<Q", phdr, 32)[0]
                    else:
                        p_offset = struct.unpack_from("<I", phdr, 4)[0]
                        p_filesz = struct.unpack_from("<I", phdr, 16)[0]
                    f.seek(p_offset)
                    interp = f.read(p_filesz).rstrip(b"\x00").decode("utf-8", errors="replace")
                    return interp
        return ""
    except Exception:
        return ""


def collect_dynamic_deps(filepath: str) -> List[str]:
    """收集 ELF 动态依赖的 .so 列表（一级）"""
    deps = []
    try:
        rc, out, _ = run_cmd(["ldd", filepath])
        if rc != 0:
            return deps
        for line in out.splitlines():
            line = line.strip()
            m = re.search(r"=>\s*(\S+)", line)
            if m:
                path = m.group(1)
                if os.path.exists(path):
                    deps.append(path)
            elif line.startswith("/") and "ld-linux" in line:
                m2 = re.search(r"(\S+ld-linux\S+)\s", line)
                if m2 and os.path.exists(m2.group(1)):
                    deps.append(m2.group(1))
        seen = set()
        unique = []
        for d in deps:
            if d not in seen:
                seen.add(d)
                unique.append(d)
        return unique
    except Exception:
        return []


def collect_deps_recursive(filepath: str, max_depth: int = 6) -> List[str]:
    """递归收集所有 .so 依赖（二级/三级...），BFS 展开"""
    all_deps: Dict[str, str] = {}

    def _resolve_ldd(target: str):
        results = []
        rc, out, _ = run_cmd(["ldd", target])
        if rc != 0:
            return results
        for line in out.splitlines():
            line = line.strip()
            m = re.search(r"=>\s*(\S+)", line)
            if m:
                path = m.group(1)
                if path.startswith("/") and os.path.exists(path):
                    results.append(path)
            elif line.startswith("/") and "ld-linux" in line:
                m2 = re.search(r"(\S+ld-linux\S+)\s", line)
                if m2 and os.path.exists(m2.group(1)):
                    results.append(m2.group(1))
        return results

    queue = [filepath]
    visited = set()
    depth = 0
    while queue and depth < max_depth:
        next_queue = []
        for elf in queue:
            if elf in visited:
                continue
            visited.add(elf)
            deps = _resolve_ldd(elf)
            for d in deps:
                if d not in visited:
                    all_deps[d] = d
                    next_queue.append(d)
        queue = next_queue
        depth += 1
    return list(all_deps.values())


def collect_deps_strace(elf_path: str, timeout: int = 25) -> Tuple[List[str], List[str]]:
    """
    用 strace 真实运行 ELF 一次(构建期自省)，追踪所有被打开的 .so 与 .pyc。
    返回 (so_files, pyc_files)。
    """
    so_files = set()
    pyc_files = set()

    if not shutil.which("strace"):
        print("[collect_deps_strace] strace 未安装，跳过运行时追踪")
        return sorted(so_files), sorted(pyc_files)

    def _is_wanted_dep(path: str) -> bool:
        if not path or not os.path.exists(path):
            return False
        if path.endswith(".so") or ".so." in path:
            so_files.add(path)
            return True
        if path.endswith(".pyc"):
            pyc_files.add(path)
            return True
        return False

    def _parse_strace_output(text: str) -> Tuple[bool, bool]:
        found = False
        saw_ok = False
        for line in text.splitlines():
            if "HELLO_OS_BUILD_OK" in line:
                saw_ok = True
            for pat in (r'openat\([^,]+,\s*"([^"]+)"', r'open\([^,]+,\s*"([^"]+)'):
                m = re.search(pat, line)
                if not m:
                    continue
                if _is_wanted_dep(m.group(1)):
                    found = True
            m2 = re.search(r'trying file=(/[^\s",]+)', line)
            if m2:
                if _is_wanted_dep(m2.group(1).rstrip(",")):
                    found = True
        return found, saw_ok

    def _run_with_env(cmd: List[str], env: Dict[str, str]) -> str:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            env=env, start_new_session=True,
        )
        try:
            out, _ = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                proc.kill()
            out, _ = proc.communicate()
            out = (out or b"") + b"\n[collect_deps_strace] TIMEOUT"
        except Exception:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            out = b""
        return (out or b"").decode("utf-8", errors="replace")

    probe_env = os.environ.copy()
    probe_env["HELLO_OS_BUILD"] = "1"
    probe_env["SDL_VIDEODRIVER"] = "dummy"
    probe_env["SDL_AUDIODRIVER"] = "dummy"
    probe_env["LD_DEBUG"] = "libs"
    cmd_probe = ["strace", "-e", "trace=open,openat,execve", "-f", "-s", "512", elf_path]
    print(f"[collect_deps_strace] 运行构建期探针: HELLO_OS_BUILD=1 strace -f {elf_path}")
    text = _run_with_env(cmd_probe, probe_env)
    found_any, saw_ok = _parse_strace_output(text)
    if saw_ok:
        print("[collect_deps_strace] HELLO_OS_BUILD_OK 已收到 -> 构建期探针成功")
    else:
        print("[collect_deps_strace] 未收到 HELLO_OS_BUILD_OK(ELF 未内置探针或已退出)")
    if found_any:
        print(f"[collect_deps_strace] 探针捕获到 {len(so_files)} 个 .so")
        return sorted(so_files), sorted(pyc_files)

    print("[collect_deps_strace] 回退：尝试 --help/-h/--version/-c 参数...")
    for probe_args in (["--help"], ["-h"], ["--version"], ["-c", "print('probe')"]):
        cmd = ["strace", "-e", "trace=open,openat", "-f", "-s", "512", elf_path] + probe_args
        try:
            text = _run_with_env(cmd, os.environ.copy())
            found_any, _ = _parse_strace_output(text)
            if found_any:
                print(f"[collect_deps_strace] 参数 {probe_args} 捕获到 {len(so_files)} 个 .so")
                break
        except Exception:
            continue

    return sorted(so_files), sorted(pyc_files)


def detect_python_elf(elf_path: str) -> Optional[Dict[str, str]]:
    """检测 ELF 是否由 Python 打包（PyInstaller/Nuitka/Cython/原生 ctypes）"""
    info: Dict[str, str] = {}
    rc, out, _ = run_cmd(["strings", elf_path])
    text = out if rc == 0 else ""
    text_lower = text.lower()

    if "pyinstaller" in text_lower or "pyi_" in text_lower or "pyi-rth" in text_lower:
        info["type"] = "pyinstaller"
    elif "nuitka" in text_lower or "__nuitka_" in text_lower:
        info["type"] = "nuitka"
    elif "__pyx" in text_lower or "cython" in text_lower:
        info["type"] = "cython"

    for line in text.splitlines():
        m = re.search(r"Python\s*(\d+\.\d+)", line)
        if m:
            info["version"] = m.group(1)
            break
    if "version" not in info:
        m2 = re.search(r"(3\.\d+)\.\d+", text[:10000])
        if m2:
            info["version"] = m2.group(1)

    try:
        with open(elf_path, "rb") as f:
            data = f.read(min(os.path.getsize(elf_path), 10 * 1024 * 1024))
        pyc_magics = [
            (b"\x42\x0d\x0d\x0a", "3.7"),
            (b"\x43\x0d\x0d\x0a", "3.8"),
            (b"\x44\x0d\x0d\x0a", "3.8"),
            (b"\x55\x0d\x0d\x0a", "3.9"),
            (b"\x61\x0d\x0d\x0a", "3.10"),
            (b"\x6f\x0d\x0d\x0a", "3.11"),
            (b"\x6d\x0d\x0d\x0a", "3.12"),
            (b"\x74\x0d\x0d\x0a", "3.13"),
        ]
        for magic, ver in pyc_magics:
            if magic in data:
                if "type" not in info:
                    info["type"] = "python-packed"
                if "version" not in info:
                    info["version"] = ver
                break
    except Exception:
        pass

    try:
        with open(elf_path, "rb") as f:
            head = f.read(min(os.path.getsize(elf_path), 2 * 1024 * 1024))
        if b"_MEI" in head or b"pyi_rth_" in head or b"PYI" in head:
            if "type" not in info:
                info["type"] = "pyinstaller"
    except Exception:
        pass

    if "type" in info and "version" not in info:
        try:
            import sys as _sys
            info["version"] = f"{_sys.version_info.major}.{_sys.version_info.minor}"
        except Exception:
            pass

    return info if info else None


def get_python_runtime_paths(version: str) -> Dict[str, str]:
    """根据检测到的 Python 版本，定位宿主机上的运行时路径"""
    paths: Dict[str, str] = {}
    import sysconfig

    candidates: List[str] = []
    if version:
        version = version.strip()
        if re.fullmatch(r"3\.\d+", version):
            candidates.append(version)
        parts = version.split(".")
        if len(parts) == 2 and parts[0] == "3":
            candidates.append(parts[0])
    if not candidates:
        candidates.append("3")

    def _find_dir(bases):
        for b in bases:
            if os.path.isdir(b):
                return b
        return None

    for cand in candidates:
        stdlib = _find_dir([
            f"/usr/lib/python{cand}",
            f"/usr/local/lib/python{cand}",
            f"/usr/lib/x86_64-linux-gnu/python{cand}",
            f"/usr/lib64/python{cand}",
        ])
        if stdlib:
            paths["stdlib"] = stdlib
            paths["python_dirname"] = os.path.basename(stdlib)
            break

    if "stdlib" not in paths:
        stdlib = sysconfig.get_path("stdlib")
        if stdlib and os.path.isdir(stdlib):
            paths["stdlib"] = stdlib
            paths["python_dirname"] = os.path.basename(stdlib)

    if "stdlib" in paths:
        for sub in ("lib-dynload", "lib_plat"):
            ld = os.path.join(paths["stdlib"], sub)
            if os.path.isdir(ld):
                paths["lib_dynload"] = ld
                break

    for cand in candidates:
        sp = _find_dir([
            f"/usr/local/lib/python{cand}/site-packages",
            f"/usr/lib/python{cand}/site-packages",
            f"/usr/lib/python{cand}/dist-packages",
            f"/usr/local/lib/python{cand}/dist-packages",
            f"/usr/lib64/python{cand}/site-packages",
        ])
        if sp:
            paths["site_packages"] = sp
            break

    if "site_packages" not in paths:
        sp = sysconfig.get_path("purelib")
        if sp and os.path.isdir(sp):
            paths["site_packages"] = sp

    for exe in ("/usr/bin/python3", "/usr/local/bin/python3"):
        if os.path.exists(exe):
            paths["python_exe"] = exe
            break
    if "python_exe" not in paths:
        which = shutil.which("python3")
        if which:
            paths["python_exe"] = which

    return paths


def strip_libraries(initramfs_dir: str) -> int:
    """对 initramfs 中所有 .so 和 ELF 执行 strip --strip-unneeded"""
    freed = 0
    if not shutil.which("strip"):
        return 0
    for root, _, files in os.walk(initramfs_dir):
        for f in files:
            fpath = os.path.join(root, f)
            should_strip = False
            if ".so" in f:
                should_strip = True
            elif f == "os.elf" or f == "init":
                should_strip = True
            if should_strip:
                try:
                    size_before = os.path.getsize(fpath)
                    rc, _, _ = run_cmd(["strip", "--strip-unneeded", fpath])
                    if rc == 0:
                        freed += (size_before - os.path.getsize(fpath))
                except Exception:
                    pass
    return freed


def find_gcc_version() -> str:
    """获取 gcc 版本号字符串"""
    rc, out, _ = run_cmd(["gcc", "--version"])
    if rc == 0:
        first_line = out.splitlines()[0] if out else ""
        m = re.search(r"(\d+\.\d+)", first_line)
        if m:
            return m.group(1)
    return "unknown"


def needs_bool_fix(gcc_version: str) -> bool:
    """判断是否需要 CONFIG_BOOT_BOOL_IS_INT 补丁（gcc >= 13）"""
    try:
        return float(gcc_version) >= 13.0
    except ValueError:
        return True


def install_gcc12(password: str, log_fn: Callable) -> None:
    """安装并切换 gcc-12（解决 Kali/gcc 15 与内核 6.6 的兼容问题）"""
    log_fn("info", "🔽 检查 gcc 版本...")
    gcc_ver = find_gcc_version()
    log_fn("info", f"   当前 gcc 版本: {gcc_ver}")
    if gcc_ver.startswith("12"):
        log_fn("info", "   ✅ 已是 gcc-12，无需切换")
        return

    log_fn("info", "🔽 安装 gcc-12（降级，解决 gcc 15 与内核 6.x 不兼容）...")
    rc, out, err = sudo_run(["apt-get", "install", "-y", "gcc-12", "g++-12"], password, timeout=300)
    if rc != 0:
        sudo_run(["apt-get", "update", "-y"], password, timeout=120)
        rc2, out2, err2 = sudo_run(["apt-get", "install", "-y", "gcc-12", "g++-12"], password, timeout=300)
        if rc2 != 0:
            log_fn("warn", f"   gcc-12 安装失败，尝试继续（可能已有其他 gcc）")
            log_fn("warn", f"   stderr: {err2.strip()[:200]}")
            return

    log_fn("info", "🔧 切换默认 gcc/g++ 到 12...")
    sudo_run(["update-alternatives", "--install", "/usr/bin/gcc", "gcc", "/usr/bin/gcc-12", "100"], password)
    sudo_run(["update-alternatives", "--install", "/usr/bin/g++", "g++", "/usr/bin/g++-12", "100"], password)
    sudo_run(["update-alternatives", "--set", "gcc", "/usr/bin/gcc-12"], password)
    sudo_run(["update-alternatives", "--set", "g++", "/usr/bin/g++-12"], password)

    new_ver = find_gcc_version()
    log_fn("info", f"   ✅ gcc 已切换为 {new_ver}")
    if not new_ver.startswith("12"):
        log_fn("warn", f"   ⚠️ gcc 版本仍为 {new_ver}，降级可能不完整")


def detect_host_arch() -> str:
    """检测宿主机器架构，返回 ARCH_TABLE 中的 key"""
    machine = platform_machine()
    mapping = {
        "x86_64": "x86_64",
        "amd64": "x86_64",
        "i386": "i386",
        "i686": "i386",
        "aarch64": "arm64",
        "arm64": "arm64",
        "armv7l": "arm",
        "armv6l": "arm",
        "riscv64": "riscv64",
        "ppc64le": "ppc64le",
        "mips64": "mips64",
    }
    return mapping.get(machine, "x86_64")


def platform_machine() -> str:
    import platform as _platform
    return _platform.machine().lower()


# ============================================================
#  构建引擎
# ============================================================

class BuildEngine:
    """核心构建逻辑，不依赖 GUI"""

    def __init__(self, callbacks: BuildCallbacks, password: str,
                 os_name: str, elf_path: str,
                 target_arch: str = DEFAULT_ARCH,
                 output_format: str = DEFAULT_OUTPUT):
        self.cb = callbacks
        self.password = password
        self.os_name = re.sub(r"[^a-zA-Z0-9_-]", "_", os_name.strip()) or "helloos"
        self.elf_path = os.path.abspath(elf_path)

        # 架构与输出
        if target_arch not in ARCH_TABLE:
            raise ValueError(f"不支持的架构: {target_arch}，可选: {', '.join(ARCH_TABLE.keys())}")
        self.target_arch = target_arch
        self.arch_cfg = ARCH_TABLE[target_arch]
        if output_format not in VALID_OUTPUTS:
            raise ValueError(f"不支持的输出格式: {output_format}，可选: {', '.join(VALID_OUTPUTS)}")
        self.output_format = output_format

        # 所有路径按架构隔离到 os/<arch>/ 子目录
        self.arch_work = arch_work_dir(target_arch)
        self.kernel_dir = arch_kernel_dir(target_arch)
        self.work_dir = self.arch_work
        self.initramfs_dir = arch_initramfs_dir(target_arch)
        self.iso_root = arch_iso_root(target_arch)
        self.iso_path = os.path.join(self.arch_work, f"{self.os_name}.iso")
        self.bin_dir = os.path.join(self.arch_work, f"{self.os_name}_bin")
        self.log_file = None

        self._python_info: Optional[Dict[str, str]] = None
        self._all_deps: List[str] = []
        self._kernel_image: Optional[str] = None  # 架构内核镜像绝对路径（缓存复用/编译后填充）

    # ---- 架构缓存：检查 os/<arch>/ 是否已含有效内核镜像+initramfs ----
    def _arch_cache_valid(self) -> bool:
        """若架构子目录存在且含可用内核镜像+initramfs，返回 True（可复用，跳过编译）。"""
        if not os.path.isdir(self.arch_work):
            return False
        # 内核镜像：编译产物在 arch/<...>/ 下；若已编译，_kernel_image 未持久化时按 arch_cfg 推导
        expected_image = os.path.join(self.kernel_dir, self.arch_cfg["image"])
        if not os.path.exists(expected_image) or os.path.getsize(expected_image) < 100_000:
            return False
        # initramfs：step4 产物 initramfs.cpio.gz 位于架构工作目录
        initramfs = os.path.join(self.arch_work, "initramfs.cpio.gz")
        if not os.path.exists(initramfs) or os.path.getsize(initramfs) < 1000:
            return False
        return True

    def _use_arch_cache(self) -> bool:
        """标记当前构建是否走缓存复用路径（供 step3/step4 判断跳过）。"""
        return getattr(self, "_from_cache", False)

    # ---- 日志 ----
    def _log(self, level: str, msg: str):
        timestamp = time.strftime("%H:%M:%S")
        line = f"[{timestamp}] {level} {msg}"
        if self.log_file:
            self.log_file.write(line + "\n")
            self.log_file.flush()
        self.cb.log(level, msg)

    def _progress(self, pct: int, msg: str = ""):
        pct = max(0, min(100, int(pct)))
        self.cb.progress(pct, msg)

    # ---- 步骤 1: 依赖安装 ----
    def step1_install_deps(self):
        self._log("info", "🔍 检测发行版...")
        family, name = detect_distro()
        self._log("info", f"   发行版: {name} (家族: {family})")
        self._log("info", f"   目标架构: {self.arch_cfg['label']}")
        self._log("info", f"   输出格式: {self.output_format}")

        # gcc-12 降级（仅 Debian 家族 + 本机 x86 编译时必要；交叉编译宿主工具链也建议）
        if family == "debian":
            install_gcc12(self.password, self._log)
        elif family == "arch":
            self._log("info", "   Arch 系统：跳过 gcc 降级（如编译失败请手动安装 gcc12）")

        # 基础依赖包
        packages = [
            "build-essential", "gcc", "make", "bc", "bison", "flex",
            "libelf-dev", "libssl-dev", "libncurses-dev", "wget", "curl",
            "cpio", "gzip", "xz-utils", "grub-pc-bin", "grub-efi-amd64-bin",
            "xorriso", "qemu-utils", "python3", "python3-dev", "python3-venv",
            "file", "diffutils", "strace", "binutils",
            "kmod", "libudev-dev", "autoconf", "automake", "pkg-config",
            "mtools", "gdisk", "dosfstools",
        ]

        # 按目标架构追加交叉工具链
        cross_pkgs = self._cross_toolchain_packages(family)
        packages.extend(cross_pkgs)

        if family == "debian":
            self._log("info", "📦 更新 apt 包索引...")
            sudo_run(["apt-get", "update", "-y"], self.password, timeout=120)

            self._log("info", "📦 安装/检查依赖包...")
            rc, out, err = sudo_run(["apt-get", "install", "-y"] + packages, self.password, timeout=900)
            if rc != 0:
                self._log("warn", "批量安装部分失败，尝试逐个安装...")
                for pkg in packages:
                    rc2, _, err2 = sudo_run(["apt-get", "install", "-y", pkg], self.password, timeout=180)
                    if rc2 != 0:
                        self._log("warn", f"   ⚠️ 跳过: {pkg}")
                    else:
                        self._log("info", f"   ✅ {pkg}")
        elif family == "arch":
            self._log("info", "📦 安装 Arch 依赖...")
            arch_pkgs = ["base-devel", "wget", "cpio", "xz", "grub", "xorriso",
                         "qemu", "python3", "strace", "file", "diffutils",
                         "kmod", "binutils", "mtools", "dosfstools", "gdisk"]
            arch_pkgs.extend(cross_pkgs)
            sudo_run(["pacman", "-S", "--noconfirm"] + arch_pkgs, self.password, timeout=900)
        else:
            self._log("warn", f"⚠️ 未识别发行版 {name}，尝试通用安装...")
            if shutil.which("apt-get"):
                sudo_run(["apt-get", "update", "-y"], self.password, timeout=120)
                sudo_run(["apt-get", "install", "-y"] + packages, self.password, timeout=900)
            elif shutil.which("pacman"):
                sudo_run(["pacman", "-S", "--noconfirm", "base-devel", "wget", "cpio", "xz", "grub", "xorriso"],
                         self.password, timeout=900)

        # 验证关键工具
        required_tools = ["gcc", "make", "wget", "cpio", "xorriso", "strip"]
        grub_tool = shutil.which("grub-mkrescue") or shutil.which("grub2-mkrescue")
        if not grub_tool and self.output_format in (OUTPUT_ISO, OUTPUT_BOTH):
            required_tools.append("grub-mkrescue")

        missing = [t for t in required_tools if not shutil.which(t)]
        if missing:
            self._log("error", f"❌ 缺少工具: {', '.join(missing)}")
            raise RuntimeError(f"缺少必要工具: {missing}")

        # 验证交叉工具链（若非本机架构）
        if self.arch_cfg["cross"]:
            cross_prefix = self.arch_cfg["cross"]
            cross_gcc = cross_prefix + "gcc"
            if not shutil.which(cross_gcc):
                self._log("warn", f"⚠️ 交叉编译器 {cross_gcc} 未找到，内核交叉编译可能失败")
            else:
                self._log("info", f"   ✅ 交叉编译器: {cross_gcc}")

        self._log("info", f"✅ 所有依赖已就绪 (gcc {find_gcc_version()})")

    def _cross_toolchain_packages(self, family: str) -> List[str]:
        """返回目标架构所需的交叉工具链包列表"""
        cross = self.arch_cfg["cross"]
        if not cross:
            return []
        # 去掉末尾 '-'
        tc_name = cross.rstrip("-")
        if family == "debian":
            # Debian/Ubuntu/Kali: gcc-<triplet>
            return [f"gcc-{tc_name}", f"binutils-{tc_name}"]
        elif family == "arch":
            # Arch: 通过 AUR/交叉编译，或 multilib；这里给出提示性包名
            return [f"{tc_name}-gcc", f"{tc_name}-binutils"]
        return []

    # ---- 步骤 2: 内核源码 ----
    def step2_prepare_kernel(self):
        os.makedirs(self.work_dir, exist_ok=True)

        kdir = self.kernel_dir
        makefile_path = os.path.join(kdir, "Makefile")
        kconfig_path = os.path.join(kdir, "Kconfig")

        if os.path.exists(makefile_path) and os.path.exists(kconfig_path):
            
            try:
                size = os.path.getsize(makefile_path)
                with open(makefile_path) as f:
                    content = f.read(5000)
                if size > 5000 and "VERSION" in content and "PATCHLEVEL" in content:
                    self._log("info", f"♻️  复用已有内核源码: {self.kernel_dir}")
                    return
            except Exception:
                pass
            self._log("info", "⚠️  已有内核源码不完整，重新下载...")
            shutil.rmtree(self.kernel_dir, ignore_errors=True)

        tarball_path = os.path.join(self.work_dir, KERNEL_TARBALL)
        if not os.path.exists(tarball_path) or os.path.getsize(tarball_path) < 100_000_000:
            self._log("info", f"🌐 下载 Linux 内核 {KERNEL_VERSION}...")
            self._log("info", f"   URL: {KERNEL_URL}")
            if os.path.exists(tarball_path):
                os.remove(tarball_path)

            def dl_progress(pct):
                self._progress(15 + int(pct * 0.15), f"下载内核... {pct}%")

            if not download_file(KERNEL_URL, tarball_path, dl_progress):
                raise RuntimeError("内核下载失败")
            if os.path.getsize(tarball_path) < 100_000_000:
                raise RuntimeError("内核下载文件过小")

            self._log("info", "🔐 验证 SHA256...")
            if not verify_sha256(tarball_path, KERNEL_SHA256):
                self._log("warn", "   SHA256 不匹配，继续尝试（可能是镜像延迟）")
            else:
                self._log("info", "   ✅ SHA256 验证通过")

        self._log("info", "📂 解压内核源码...")
        if os.path.exists(self.kernel_dir):
            shutil.rmtree(self.kernel_dir, ignore_errors=True)

        with tarfile.open(tarball_path, "r:xz") as tar:
            members = tar.getmembers()
            total = len(members)
            for i, m in enumerate(members):
                tar.extract(m, self.work_dir)
                if i % 500 == 0:
                    self._progress(30 + int(i * 5 / total), f"解压内核... {int(i*100/total)}%")
        self._progress(35, "解压内核完成")

        if not os.path.exists(makefile_path):
            raise RuntimeError("内核解压后未找到 Makefile")
        self._log("info", f"✅ 内核源码就绪: {kdir}")

    # ---- 步骤 3: 编译内核（含交叉编译）----
    def step3_build_kernel(self):
        kdir = self.kernel_dir
        arch = self.arch_cfg["arch"]
        cross = self.arch_cfg["cross"]
        defconfig = self.arch_cfg["defconfig"]

        # 架构缓存复用：若 os/<arch>/ 已有有效内核镜像+initramfs，跳过编译直接复用
        if self._arch_cache_valid():
            cached_image = os.path.join(kdir, self.arch_cfg["image"])
            self._kernel_image = cached_image
            self._from_cache = True
            size_mb = os.path.getsize(cached_image) / 1024 / 1024
            self._log("info", f"♻️  复用架构缓存: {cached_image} ({size_mb:.1f} MB)，跳过内核编译")
            self._progress(70, "复用已编译内核")
            return

        self._log("info", f"⚙️  配置内核 (ARCH={arch} CROSS_COMPILE={cross or '(native)'})...")
        self._log("info", f"   配置目标: {defconfig}")

        # 清理旧配置
        run_cmd(["make", f"ARCH={arch}", f"CROSS_COMPILE={cross}", "mrproper"], cwd=kdir, timeout=300)

        rc, out, err = run_cmd(
            ["make", f"ARCH={arch}", f"CROSS_COMPILE={cross}", defconfig],
            cwd=kdir, timeout=600)
        if rc != 0:
            self._log("warn", f"   {defconfig} 失败，尝试 tinyconfig/defconfig...")
            run_cmd(["make", f"ARCH={arch}", f"CROSS_COMPILE={cross}", "tinyconfig"],
                    cwd=kdir, timeout=300)

        # 追加通用配置项
        config_path = os.path.join(kdir, ".config")
        with open(config_path, "a") as f:
            f.write("\n")
            f.write(KERNEL_CONFIG_APPEND)
            # 追加架构专属配置
            arch_extra = ARCH_KERNEL_CONFIG.get(self.target_arch, "")
            if arch_extra:
                f.write("\n")
                f.write(arch_extra)

        # gcc 13+ bool 修复（仅 x86 本机编译路径需要，交叉编译器版本可能不同）
        if self.target_arch == "x86_64" and needs_bool_fix(find_gcc_version()):
            self._log("info", "   🔧 应用 CONFIG_BOOT_BOOL_IS_INT=y (修复 gcc 13+)")
            with open(config_path, "a") as f:
                f.write("CONFIG_BOOT_BOOL_IS_INT=y\n")

        rc, out, err = run_cmd(
            ["make", f"ARCH={arch}", f"CROSS_COMPILE={cross}", "olddefconfig"],
            cwd=kdir, timeout=300)
        if rc != 0:
            self._log("warn", f"olddefconfig 警告: {err.strip()[:200]}")

        # 编译
        np = os.cpu_count() or 1
        self._log("info", f"🔨 编译内核 (ARCH={arch}, -j{np})...")
        cmd = ["make", "-j", str(np), f"ARCH={arch}", f"CROSS_COMPILE={cross}"]
        # 镜像目标：x86 用 bzImage，其余用对应 image 名（make 默认 all 即可）
        if self.target_arch in ("x86_64", "i386"):
            cmd.append("bzImage")
        else:
            cmd.append("all")

        env = os.environ.copy()
        if self.target_arch == "x86_64":
            env["KCFLAGS"] = "-std=gnu11"

        proc = subprocess.Popen(cmd, cwd=kdir, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        line_count = 0
        error_lines = []
        while True:
            if is_stop_requested():
                kill_process_group(proc)
                raise InterruptedError("用户请求停止构建（内核编译中）")
            line = proc.stdout.readline()
            if not line:
                break
            line = line.strip()
            line_count += 1
            if line:
                line_lower = line.lower()
                if "error:" in line_lower or "Error" in line:
                    error_lines.append(line)
                    self._log("error", f"   {line}")
                elif any(k in line_lower for k in ["image:", "kernel:", arch]):
                    if line_count % 50 == 0:
                        self._log("info", f"   {line}")
            if line_count < 5000:
                self._progress(35 + min(int(line_count * 30 / 5000), 30), "编译内核...")
        proc.wait(timeout=7200)
        if proc.returncode != 0:
            err_msg = "\n".join(error_lines[-10:]) if error_lines else "未知编译错误"
            raise RuntimeError(f"内核编译失败 (rc={proc.returncode}): {err_msg}")

        # 定位内核镜像
        image_rel = self.arch_cfg["image"]
        bzimage = os.path.join(kdir, image_rel)
        if not os.path.exists(bzimage):
            # 兜底：尝试常见位置
            fallbacks = [
                os.path.join(kdir, "arch/arm64/boot/Image"),
                os.path.join(kdir, "arch/riscv/boot/Image"),
                os.path.join(kdir, "arch/powerpc/boot/zImage"),
                os.path.join(kdir, "arch/mips/boot/vmlinux"),
                os.path.join(kdir, "arch/arm/boot/zImage"),
                os.path.join(kdir, "vmlinux"),
            ]
            for fb in fallbacks:
                if os.path.exists(fb):
                    bzimage = fb
                    break
        if not os.path.exists(bzimage):
            raise RuntimeError(f"内核镜像未生成: {bzimage}")

        # 若镜像是压缩格式但目标是裸 Image，按需 gzip
        self._kernel_image = bzimage
        size_mb = os.path.getsize(bzimage) / 1024 / 1024
        self._log("info", f"✅ 内核编译完成: {bzimage} ({size_mb:.1f} MB)")
        self._progress(70, "内核编译完成")

    # ---- 步骤 4: 构建 initramfs ----
    def step4_build_initramfs(self):
        self._log("info", "📦 构建 initramfs...")

        # 缓存复用：step3 已标记 _from_cache=True 时，initramfs.cpio.gz 已存在且通过校验，直接复用
        cached_initramfs = os.path.join(self.arch_work, "initramfs.cpio.gz")
        if getattr(self, "_from_cache", False) and os.path.exists(cached_initramfs):
            size_mb = os.path.getsize(cached_initramfs) / 1024 / 1024
            self._log("info", f"♻️  复用架构缓存 initramfs: {cached_initramfs} ({size_mb:.2f} MB)")
            self._progress(85, "initramfs 完成(缓存)")
            return

        if os.path.exists(self.initramfs_dir):
            shutil.rmtree(self.initramfs_dir, ignore_errors=True)
        os.makedirs(self.initramfs_dir, exist_ok=True)

        # 目录布局（含各架构 multiarch 路径，便于跨架构 .so 注入）
        dirs = ["bin", "lib", "lib64", "usr/lib", "usr/lib64",
                "usr/lib/x86_64-linux-gnu",
                "usr/lib/aarch64-linux-gnu",
                "usr/lib/riscv64-linux-gnu",
                "usr/lib/powerpc64le-linux-gnu",
                "usr/lib/mips64-linux-gnuabi64",
                "usr/lib/python3", "usr/lib/python3/lib-dynload",
                "usr/lib/python3/site-packages",
                "usr/bin",
                "proc", "sys", "dev", "dev/shm", "tmp", "etc", "root", "mnt", "run",
                "var", "var/log"]
        for d in dirs:
            os.makedirs(os.path.join(self.initramfs_dir, d), exist_ok=True)

        # 1. 编译 elf_runner → /init（静态，使用本机 gcc 即可，runner 是宿主工具）
        runner_c = os.path.join(self.work_dir, ELF_RUNNER_SRC)
        with open(runner_c, "w") as f:
            f.write(ELF_RUNNER_C)
        runner_bin = os.path.join(self.initramfs_dir, "init")
        rc, out, err = run_cmd(["gcc", "-static", "-Os", "-s", "-o", runner_bin, runner_c])
        if rc != 0:
            raise RuntimeError(f"elf_runner 编译失败 (rc={rc}): {err.strip()[:300]}")
        os.chmod(runner_bin, 0o755)
        self._log("info", f"   ✅ elf_runner 编译完成 (静态, {os.path.getsize(runner_bin)//1024}KB)")

        # 2. 复制用户 ELF → /bin/os.elf
        if not os.path.exists(self.elf_path):
            raise RuntimeError(f"ELF 文件不存在: {self.elf_path}")
        if not is_valid_elf(self.elf_path):
            raise RuntimeError(f"文件不是有效的 ELF: {self.elf_path}")

        os_elf_dest = os.path.join(self.initramfs_dir, "bin", "os.elf")
        shutil.copy2(self.elf_path, os_elf_dest)
        os.chmod(os_elf_dest, 0o755)
        static_check = is_statically_linked(self.elf_path)
        self._log("info", f"   ✅ ELF 已安装: /bin/os.elf ({os.path.getsize(os_elf_dest)/1024:.1f}KB, "
                  f"{'静态' if static_check else '动态'})")

        # 3. 检测 Python ELF
        self._python_info = detect_python_elf(self.elf_path)
        if self._python_info:
            self._log("info", f"   🐍 检测到 Python ELF: type={self._python_info.get('type','?')}, "
                      f"version={self._python_info.get('version','?')}")
        else:
            self._log("info", "   ℹ️  非 Python ELF，按通用动态 ELF 处理")

        # 4. 收集依赖
        is_python = bool(self._python_info)
        collect_dyn = (not static_check) or is_python
        if collect_dyn:
            self._log("info", "   📋 [Phase 1] ldd 递归收集依赖...")
            deps_recursive = collect_deps_recursive(self.elf_path, max_depth=6)
            self._log("info", f"      ldd 递归发现 {len(deps_recursive)} 个 .so")

            self._log("info", "   📋 [Phase 2] strace 构建期运行 ELF 追踪依赖...")
            strace_sos, strace_pycs = collect_deps_strace(self.elf_path)
            self._log("info", f"      strace 发现 {len(strace_sos)} 个 .so, {len(strace_pycs)} 个 .pyc")

            extra_deps: List[str] = []
            if is_python:
                py_paths = get_python_runtime_paths(self._python_info.get("version", ""))
                py_exe = py_paths.get("python_exe") if py_paths else None
                if py_exe:
                    self._log("info", "   📋 [Phase 2b] 收集 python3 解释器依赖...")
                    extra_deps = collect_deps_recursive(py_exe, max_depth=4)
                    self._log("info", f"      python3 依赖: {len(extra_deps)} 个 .so")

            all_deps_set: Dict[str, str] = {}
            for d in deps_recursive: all_deps_set[d] = d
            for d in strace_sos: all_deps_set[d] = d
            for d in extra_deps: all_deps_set[d] = d
            self._all_deps = sorted(all_deps_set.values())
            self._log("info", f"   📋 合并后共 {len(self._all_deps)} 个唯一依赖库")

            # 分类复制 .so
            so_count = 0
            for dep in self._all_deps:
                basename = os.path.basename(dep)
                if "lib64" in dep:
                    dest_dir = os.path.join(self.initramfs_dir, "lib64")
                elif "aarch64-linux-gnu" in dep:
                    dest_dir = os.path.join(self.initramfs_dir, "usr", "lib", "aarch64-linux-gnu")
                elif "riscv64-linux-gnu" in dep:
                    dest_dir = os.path.join(self.initramfs_dir, "usr", "lib", "riscv64-linux-gnu")
                elif "powerpc64le-linux-gnu" in dep:
                    dest_dir = os.path.join(self.initramfs_dir, "usr", "lib", "powerpc64le-linux-gnu")
                elif "mips64-linux-gnuabi64" in dep:
                    dest_dir = os.path.join(self.initramfs_dir, "usr", "lib", "mips64-linux-gnuabi64")
                elif "x86_64-linux-gnu" in dep:
                    dest_dir = os.path.join(self.initramfs_dir, "usr", "lib", "x86_64-linux-gnu")
                elif dep.startswith("/usr/local/"):
                    dest_dir = os.path.join(self.initramfs_dir, "usr", "lib")
                else:
                    dest_dir = os.path.join(self.initramfs_dir, "lib")
                os.makedirs(dest_dir, exist_ok=True)
                shutil.copy2(dep, os.path.join(dest_dir, basename))
                so_count += 1
            self._log("info", f"      ✅ 已复制 {so_count} 个 .so 文件")

            # 动态链接器
            interp = get_elf_interpreter(self.elf_path)
            if not interp and is_python:
                py_paths = get_python_runtime_paths(self._python_info.get("version", ""))
                py_exe = py_paths.get("python_exe") if py_paths else None
                if py_exe:
                    interp = get_elf_interpreter(py_exe)
            if interp:
                if os.path.exists(interp):
                    interp_dest_dir = os.path.join(self.initramfs_dir, os.path.dirname(interp).lstrip("/"))
                    os.makedirs(interp_dest_dir, exist_ok=True)
                    shutil.copy2(interp, os.path.join(self.initramfs_dir, interp.lstrip("/")))
                    self._log("info", f"      🔗 动态链接器: {interp}")
                else:
                    self._log("warn", f"      ⚠️ 动态链接器不存在: {interp}")
                    interp_basename = os.path.basename(interp)
                    for search_dir in ["/lib", "/lib64", "/usr/lib", "/usr/lib64"]:
                        candidate = os.path.join(search_dir, interp_basename)
                        if os.path.exists(candidate):
                            dest_dir = os.path.join(self.initramfs_dir, search_dir.strip("/"))
                            os.makedirs(dest_dir, exist_ok=True)
                            shutil.copy2(candidate, os.path.join(self.initramfs_dir, search_dir.strip("/"), interp_basename))
                            self._log("info", f"      🔗 找到替代链接器: {candidate}")
                            break

            # ld.so.conf
            py_dir_for_ld = "python3"
            if is_python and self._python_info.get("version"):
                cand = self._python_info.get("version", "")
                if re.fullmatch(r"3\.\d+", cand):
                    py_dir_for_ld = f"python{cand}"
            with open(os.path.join(self.initramfs_dir, "etc", "ld.so.conf"), "w") as f:
                f.write("/lib\n/lib64\n/usr/lib\n/usr/lib64\n")
                f.write("/usr/lib/x86_64-linux-gnu\n")
                f.write("/usr/lib/aarch64-linux-gnu\n")
                f.write("/usr/lib/riscv64-linux-gnu\n")
                f.write("/usr/lib/powerpc64le-linux-gnu\n")
                f.write("/usr/lib/mips64-linux-gnuabi64\n")
                f.write(f"/usr/lib/{py_dir_for_ld}\n")
                f.write(f"/usr/lib/{py_dir_for_ld}/lib-dynload\n")
                f.write("/usr/lib/python3/site-packages\n")
        else:
            self._log("info", "   ℹ️ ELF 为静态链接，跳过动态依赖收集")

        # 5. 注入 Python 运行时
        if self._python_info:
            py_version = self._python_info.get("version", "")
            if py_version:
                self._inject_python_runtime(py_version)
            else:
                self._log("warn", "   ⚠️ 无法确定 Python 版本，跳过运行时注入")

        # 6. os-release
        with open(os.path.join(self.initramfs_dir, "etc", "os-release"), "w") as f:
            f.write(f'NAME="{self.os_name}"\nID={self.os_name.lower()}\n')
            f.write('VERSION="1.0"\nPRETTY_NAME="elf2os - Multi-Arch ELF Runtime"\n')

        # 7. strip
        self._log("info", "   ✂️  Strip 优化体积...")
        freed = strip_libraries(self.initramfs_dir)
        if freed > 0:
            self._log("info", f"      💾 释放 {freed/1024:.1f} KB")

        # 8. 打包 initramfs
        self._progress(78, "打包 initramfs...")
        initramfs_cpio = os.path.join(self.work_dir, "initramfs.cpio.gz")

        if shutil.which("cpio"):
            find_proc = subprocess.Popen(["find", ".", "-print"], cwd=self.initramfs_dir, stdout=subprocess.PIPE)
            cpio_proc = subprocess.Popen(["cpio", "-H", "newc", "-o"], cwd=self.initramfs_dir,
                                         stdin=find_proc.stdout, stdout=subprocess.PIPE)
            find_proc.stdout.close()
            cpio_data = cpio_proc.stdout.read()
            find_proc.wait()
            cpio_rc = cpio_proc.wait()
            if cpio_rc != 0:
                self._log("warn", f"   cpio 返回非零: {cpio_rc}，使用 Python 纯实现")
                self._create_initramfs_python(initramfs_cpio)
            else:
                with open(initramfs_cpio, "wb") as f:
                    f.write(gzip.compress(cpio_data, 9))
        else:
            self._create_initramfs_python(initramfs_cpio)

        if not os.path.exists(initramfs_cpio) or os.path.getsize(initramfs_cpio) < 1000:
            raise RuntimeError("initramfs 打包失败")

        size_mb = os.path.getsize(initramfs_cpio) / 1024 / 1024
        self._log("info", f"✅ initramfs 构建完成: {size_mb:.2f} MB")
        self._progress(85, "initramfs 完成")

    def _inject_python_runtime(self, version: str):
        """将宿主机 Python 运行时注入 initramfs（版本化目录布局）"""
        self._log("info", f"   🐍 [Phase 3] 注入 Python {version} 运行时...")

        paths = get_python_runtime_paths(version)
        if not paths:
            self._log("warn", f"      ⚠️ 无法定位 Python {version} 运行时路径")
            return

        py_dir = paths.get("python_dirname", f"python{version}")
        self._log("info", f"      stdlib: {paths.get('stdlib', 'NOT FOUND')}")
        self._log("info", f"      lib_dynload: {paths.get('lib_dynload', 'NOT FOUND')}")
        self._log("info", f"      site_packages: {paths.get('site_packages', 'NOT FOUND')}")
        self._log("info", f"      python_exe: {paths.get('python_exe', 'NOT FOUND')}")
        self._log("info", f"      python_dirname: {py_dir}")

        if "stdlib" in paths:
            stdlib_src = paths["stdlib"]
            stdlib_dst = os.path.join(self.initramfs_dir, "usr", "lib", py_dir)
            os.makedirs(os.path.dirname(stdlib_dst), exist_ok=True)
            ignore_patterns = shutil.ignore_patterns(
                "test", "tests", "__pycache__", "*.pyc", "*.pyo",
                "idlelib", "tkinter", "turtledemo", "ctypes/test",
                "distutils", "ensurepip", "venv", "pydoc_data")
            try:
                shutil.copytree(stdlib_src, stdlib_dst, ignore=ignore_patterns, dirs_exist_ok=True)
                self._log("info", f"      ✅ 标准库已复制 (→ /usr/lib/{py_dir})")
            except Exception as e:
                self._log("warn", f"      ⚠️ 标准库复制失败: {e}")

        py3_link = os.path.join(self.initramfs_dir, "usr", "lib", "python3")
        if os.path.exists(py3_link) or os.path.islink(py3_link):
            try: os.remove(py3_link)
            except OSError: pass
        try:
            os.symlink(py_dir, py3_link)
            self._log("info", f"      ✅ /usr/lib/python3 -> {py_dir} (软链)")
        except OSError as e:
            self._log("warn", f"      ⚠️ 软链创建失败: {e}")

        if "lib_dynload" in paths:
            ld_src = paths["lib_dynload"]
            ld_dst = os.path.join(stdlib_dst, "lib-dynload")
            os.makedirs(ld_dst, exist_ok=True)
            so_count = sum(1 for f in os.listdir(ld_src) if f.endswith(".so")
                           and shutil.copy2(os.path.join(ld_src, f), os.path.join(ld_dst, f)))
            self._log("info", f"      ✅ lib-dynload: {so_count} 个 C 扩展")

        if "site_packages" in paths:
            sp_src = paths["site_packages"]
            sp_dst = os.path.join(self.initramfs_dir, "usr", "lib", "python3", "site-packages")
            os.makedirs(sp_dst, exist_ok=True)
            so_count = 0
            for root, dirs, files in os.walk(sp_src):
                has_so = any(f.endswith((".so", ".pyd")) for f in files)
                if not has_so:
                    continue
                rel = os.path.relpath(root, sp_src)
                dest_dir = os.path.join(sp_dst, rel) if rel != "." else sp_dst
                os.makedirs(dest_dir, exist_ok=True)
                for f in files:
                    if f.endswith((".so", ".pyd", ".py")):
                        shutil.copy2(os.path.join(root, f), os.path.join(dest_dir, f))
                        if f.endswith(".so"):
                            so_count += 1
            if so_count > 0:
                self._log("info", f"      ✅ site-packages: {so_count} 个 C 扩展 (.so)")

        if "python_exe" in paths:
            pyexe_src = paths["python_exe"]
            pyexe_dst_dir = os.path.join(self.initramfs_dir, "usr", "bin")
            os.makedirs(pyexe_dst_dir, exist_ok=True)
            pyexe_dst = os.path.join(pyexe_dst_dir, "python3")
            try:
                shutil.copy2(pyexe_src, pyexe_dst)
                os.chmod(pyexe_dst, 0o755)
                self._log("info", f"      ✅ python3 解释器已复制 (→ /usr/bin/python3)")
            except Exception as e:
                self._log("warn", f"      ⚠️ python3 解释器复制失败: {e}")

        sp_pth_dir = os.path.join(self.initramfs_dir, "usr", "lib", "python3", "site-packages")
        os.makedirs(sp_pth_dir, exist_ok=True)
        with open(os.path.join(sp_pth_dir, "elf2os.pth"), "w") as f:
            f.write(f"/usr/lib/{py_dir}\n")
            f.write(f"/usr/lib/{py_dir}/lib-dynload\n")
            f.write("/usr/lib/python3/site-packages\n")

    def _create_initramfs_python(self, output_path: str):
        """纯 Python 实现 initramfs (cpio newc + gzip) 打包"""
        cpio_data = b""
        initramfs_dir = self.initramfs_dir

        def cpio_pad(size: int) -> int:
            return (size + 3) & ~3

        def write_header(name: str, mode: int, filesize: int):
            nonlocal cpio_data
            name_bytes = name.encode("utf-8")
            header = struct.pack(
                "6s8s8s8s8s8s8s8s8s8s8s8s8s8s",
                b"070701", b"00000000", f"{mode:04o}".encode().zfill(8),
                b"00000000", b"00000000", b"00000001", b"00000000",
                f"{filesize:08x}".encode().zfill(8), b"00000000", b"00000000",
                b"00000000", b"00000000", f"{len(name_bytes)+1:08x}".encode().zfill(8), b"00000000")
            cpio_data += header
            cpio_data += name_bytes + b"\x00"
            pad = cpio_pad(110 + len(name_bytes) + 1) - (110 + len(name_bytes) + 1)
            cpio_data += b"\x00" * pad

        def write_file(name: str, mode: int, data: bytes):
            write_header(name, mode, len(data))
            nonlocal cpio_data
            cpio_data += data
            pad = cpio_pad(len(data)) - len(data)
            cpio_data += b"\x00" * pad

        all_items = []
        for root, dirs, files in os.walk(initramfs_dir):
            for d in sorted(dirs):
                all_items.append(("dir", os.path.relpath(os.path.join(root, d), initramfs_dir), os.path.join(root, d)))
            for f in sorted(files):
                all_items.append(("file", os.path.relpath(os.path.join(root, f), initramfs_dir), os.path.join(root, f)))

        for item_type, rel, full in all_items:
            if item_type == "dir":
                st_info = os.lstat(full)
                write_header(rel, st_info.st_mode & 0o777 | 0o040000, 0)
            else:
                st_info = os.lstat(full)
                if os.path.islink(full):
                    write_file(rel, st_info.st_mode & 0o777 | 0o120000, os.readlink(full).encode())
                else:
                    with open(full, "rb") as fh:
                        write_file(rel, st_info.st_mode & 0o777 | 0o100000, fh.read())

        write_header("TRAILER!!!", 0, 0)
        with open(output_path, "wb") as f:
            f.write(gzip.compress(cpio_data, 9))

    # ---- 步骤 5a: 输出裸 bin（内核镜像 + initramfs）----
    def step5a_build_bin(self):
        """生成裸输出目录：内核镜像 + initramfs.cpio.gz（+ 启动说明）"""
        self._log("info", "📦 [Step 5a] 生成裸内核+initramfs (bin)...")
        if os.path.exists(self.bin_dir):
            shutil.rmtree(self.bin_dir, ignore_errors=True)
        os.makedirs(self.bin_dir, exist_ok=True)

        # 复制内核镜像（重命名为统一名 kernel.bin，保留原始扩展信息）
        src_image = getattr(self, "_kernel_image", os.path.join(self.kernel_dir, self.arch_cfg["image"]))
        if not os.path.exists(src_image):
            raise RuntimeError(f"内核镜像不存在: {src_image}")
        kernel_out = os.path.join(self.bin_dir, "kernel.bin")
        shutil.copy2(src_image, kernel_out)
        self._log("info", f"   ✅ 内核: kernel.bin ({os.path.getsize(kernel_out)//1024}KB, 原: {self.arch_cfg['image_name']})")

        # 复制 initramfs
        initramfs_src = os.path.join(self.work_dir, "initramfs.cpio.gz")
        initramfs_out = os.path.join(self.bin_dir, "initramfs.cpio.gz")
        shutil.copy2(initramfs_src, initramfs_out)
        self._log("info", f"   ✅ initramfs: initramfs.cpio.gz ({os.path.getsize(initramfs_out)//1024}KB)")

        # 写入启动说明（按架构给出加载命令）
        readme = os.path.join(self.bin_dir, "README.txt")
        arch = self.arch_cfg["arch"]
        image_name = self.arch_cfg["image_name"]
        readme_text = f"""elf2os 裸输出 - {self.os_name}
==========================================
架构: {self.arch_cfg['label']}
内核镜像: kernel.bin (源自 {image_name})
initramfs: initramfs.cpio.gz

[直接启动 - QEMU]
  # {arch} 示例（按实际架构替换 -machine/-cpu）：
"""
        if self.target_arch == "x86_64":
            readme_text += f'  qemu-system-x86_64 -kernel kernel.bin -initrd initramfs.cpio.gz -append "console=tty0 init=/init" -m 512M\n'
        elif self.target_arch == "i386":
            readme_text += f'  qemu-system-i386 -kernel kernel.bin -initrd initramfs.cpio.gz -append "console=tty0 init=/init" -m 512M\n'
        elif self.target_arch == "arm64":
            readme_text += f'  qemu-system-aarch64 -machine virt -cpu cortex-a57 -kernel kernel.bin -initrd initramfs.cpio.gz -append "console=ttyAMA0 init=/init" -m 512M -nographic\n'
        elif self.target_arch == "arm":
            readme_text += f'  qemu-system-arm -machine virt -cpu cortex-a15 -kernel kernel.bin -initrd initramfs.cpio.gz -append "console=ttyAMA0 init=/init" -m 512M -nographic\n'
        elif self.target_arch == "riscv64":
            readme_text += f'  qemu-system-riscv64 -machine virt -kernel kernel.bin -initrd initramfs.cpio.gz -append "console=ttyS0 init=/init" -m 512M -nographic\n'
        elif self.target_arch == "ppc64le":
            readme_text += f'  qemu-system-ppc64 -machine powernv -kernel kernel.bin -initrd initramfs.cpio.gz -append "console=tty0 init=/init" -m 1G\n'
        elif self.target_arch == "mips64":
            readme_text += f'  qemu-system-mips64 -machine malta -kernel kernel.bin -initrd initramfs.cpio.gz -append "console=tty0 init=/init" -m 512M\n'
        readme_text += f"""
[手动打包 ISO]
  使用 grub-mkrescue 将 kernel.bin + initramfs.cpio.gz 按标准 ISO 布局打包即可。
  目录布局:
    iso/boot/kernel.bin
    iso/boot/initramfs.cpio.gz
    iso/boot/grub/grub.cfg
"""
        with open(readme, "w") as f:
            f.write(readme_text)
        self._log("info", f"   ✅ 启动说明: README.txt")

        # 打包为 tar.gz 便于分发
        tar_path = os.path.join(self.work_dir, f"{self.os_name}_bin.tar.gz")
        with tarfile.open(tar_path, "w:gz") as tar:
            tar.add(self.bin_dir, arcname=os.path.basename(self.bin_dir))
        self._log("info", f"✅ 裸 bin 包完成: {tar_path} ({os.path.getsize(tar_path)//1024}KB)")

    # ---- 步骤 5b: 打包 ISO ----
    def step5b_build_iso(self):
        self._log("info", "💿 [Step 5b] 生成 ISO 镜像...")

        if os.path.exists(self.iso_root):
            shutil.rmtree(self.iso_root, ignore_errors=True)
        os.makedirs(os.path.join(self.iso_root, "boot"), exist_ok=True)
        os.makedirs(os.path.join(self.iso_root, "boot", "grub"), exist_ok=True)

        # 复制内核（使用统一名 kernel.bin，grub 配置引用它）
        src_image = getattr(self, "_kernel_image", os.path.join(self.kernel_dir, self.arch_cfg["image"]))
        if not os.path.exists(src_image):
            raise RuntimeError(f"内核镜像不存在: {src_image}")
        kernel_dest = os.path.join(self.iso_root, "boot", "kernel.bin")
        shutil.copy2(src_image, kernel_dest)
        self._log("info", f"   ✅ 内核: /boot/kernel.bin ({os.path.getsize(kernel_dest)//1024}KB)")

        # 复制 initramfs
        initramfs_src = os.path.join(self.arch_work, "initramfs.cpio.gz")
        initramfs_dest = os.path.join(self.iso_root, "boot", "initramfs.cpio.gz")
        shutil.copy2(initramfs_src, initramfs_dest)
        self._log("info", f"   ✅ initramfs: /boot/initramfs.cpio.gz ({os.path.getsize(initramfs_dest)//1024}KB)")

        # grub.cfg（统一用 kernel.bin + initrd，跨架构通用）
        grub_dir = os.path.join(self.iso_root, "boot", "grub")
        grub_cfg_path = os.path.join(grub_dir, "grub.cfg")
        safe_name = self.os_name.replace('"', '\\"')
        console = "console=tty0" if self.target_arch in ("x86_64", "i386", "ppc64le", "mips64") else "console=ttyAMA0"
        grub_cfg = (
            'set timeout=0\n'
            'set default=0\n'
            '\n'
            f'menuentry "{safe_name} ({self.target_arch})" {{\n'
            # 添加 vt.global_cursor_default=0 和 nomodeset
            f'    linux /boot/kernel.bin {console} init=/init quiet loglevel=0 vt.global_cursor_default=0 nomodeset\n'
            '    initrd /boot/initramfs.cpio.gz\n'
            '}\n'
        )
        with open(grub_cfg_path, "w") as f:
            f.write(grub_cfg)
        self._log("info", f"   ✅ GRUB 配置: {grub_cfg_path}")

        # 生成 ISO
        self._progress(90, "生成 ISO...")
        self._log("info", "🔨 运行 grub-mkrescue...")

        grub_cmd = shutil.which("grub-mkrescue") or shutil.which("grub2-mkrescue")
        if not grub_cmd:
            raise RuntimeError("找不到 grub-mkrescue 或 grub2-mkrescue")

        cmd = [grub_cmd, "-o", self.iso_path, self.iso_root]
        # 非 x86 架构：指示 grub 使用对应 EFI 目标（通过环境变量）
        env = os.environ.copy()
        if self.target_arch != "x86_64":
            env["GRUB_TARGET"] = self.arch_cfg["grub_target"]

        rc, out, err = run_cmd(cmd, timeout=300, env=env)

        if rc != 0:
            self._log("warn", f"   grub-mkrescue 失败，尝试 xorriso 直接构建...")
            self._log("warn", f"   stderr: {err.strip()[:200]}")
            # xorriso 兜底（EFI + BIOS 混合，主要面向 x86；其他架构尽力而为）
            xorriso_cmd = [
                "xorriso", "-as", "mkisofs", "-iso-level", "3",
                "-full-iso9660-filenames", "-volid", self.os_name[:32],
                "-eltorito-boot", "boot/grub/i386-pc/eltorito.img",
                "-eltorito-catalog", "boot/grub/boot.cat",
                "-no-emul-boot", "-boot-load-size", "4", "-boot-info-table",
                "-eltorito-alt-boot", "-e", "boot/grub/efi.img", "-no-emul-boot",
                "-append_partition", "2", "0xef", "boot/grub/efi.img",
                "-output", self.iso_path, self.iso_root]
            rc2, out2, err2 = run_cmd(xorriso_cmd, timeout=300)
            if rc2 != 0:
                raise RuntimeError(
                    f"ISO 生成失败。grub-mkrescue: {err.strip()[:200]} | xorriso: {err2.strip()[:200]}")

        if not os.path.exists(self.iso_path):
            raise RuntimeError("ISO 文件未生成")

        size_mb = os.path.getsize(self.iso_path) / 1024 / 1024
        self._log("info", f"✅ ISO 生成完成: {self.iso_path} ({size_mb:.1f} MB)")
        self._progress(100, "构建完成!")
        return self.iso_path

    # ---- 主流程 ----
    def run_all(self):
        clear_stop()  # 本次构建开始，清除历史停止请求
        try:
            os.makedirs(self.work_dir, exist_ok=True)
            self.log_file = open(arch_build_log(self.target_arch), "a", buffering=1)
            self._log("info", f"🏷️  操作系统名称: {self.os_name}")
            self._log("info", f"📦 ELF 文件: {self.elf_path}")
            self._log("info", f"🎯 目标架构: {self.arch_cfg['label']}")
            self._log("info", f"📤 输出格式: {self.output_format}")
            self._log("info", f"📁 架构工作目录: {self.arch_work}")
            self._log("info", f"📋 构建日志: {arch_build_log(self.target_arch)}")

            # 架构缓存提示
            if self._arch_cache_valid():
                self._log("info", f"♻️  检测到架构 '{self.target_arch}' 的现有编译产物，将跳过内核编译与 initramfs 重建")
            self._log("info", "─" * 50)

            self._progress(1, "开始构建...")

            # 停止检查辅助
            def _check_stop():
                if is_stop_requested():
                    raise InterruptedError("用户请求停止构建")

            self._log("info", "📦 [Step 1/5] 检查并安装依赖...")
            _check_stop(); self.step1_install_deps()
            self._progress(15, "依赖就绪")

            self._log("info", "🌐 [Step 2/5] 准备内核源码...")
            _check_stop(); self.step2_prepare_kernel()
            self._progress(35, "内核源码就绪")

            self._log("info", "🔨 [Step 3/5] 编译内核...")
            _check_stop(); self.step3_build_kernel()

            self._log("info", "📦 [Step 4/5] 构建 initramfs...")
            _check_stop(); self.step4_build_initramfs()

            # Step 5: 按输出格式分发
            if self.output_format in (OUTPUT_ISO, OUTPUT_BOTH):
                self._log("info", "💿 [Step 5/5] 打包 ISO...")
                _check_stop(); self.step5b_build_iso()
            if self.output_format in (OUTPUT_BIN, OUTPUT_BOTH):
                self._log("info", "📦 [Step 5/5] 生成裸 bin...")
                _check_stop(); self.step5a_build_bin()

            # 构建成功后清理临时文件
            self._log("info", "🧹 清理临时构建文件...")
            cleanup_temp_files(WORK_DIR, preserve_arch_dirs=True, arch=self.target_arch)


            self._log("info", "─" * 50)
            summary = [f"🎉 构建成功! 架构={self.target_arch}, 输出={self.output_format}"]
            if self.output_format in (OUTPUT_ISO, OUTPUT_BOTH):
                summary.append(f"   ISO : {self.iso_path}")
            if self.output_format in (OUTPUT_BIN, OUTPUT_BOTH):
                summary.append(f"   BIN : {self.bin_dir}/  (tar: {self.arch_work}/{self.os_name}_bin.tar.gz)")
            for s in summary:
                self._log("info", s)
            self.cb.done(True, self.iso_path if self.output_format in (OUTPUT_ISO, OUTPUT_BOTH) else self.bin_dir, "")

        except InterruptedError:
            self._log("warn", "🛑 构建已被用户停止，清理临时文件...")
            cleanup_temp_files(WORK_DIR, preserve_arch_dirs=True, arch=self.target_arch)
            self.cb.done(False, "", "构建已停止（用户请求）")
        except Exception as e:
            err_msg = str(e)
            self._log("error", f"💥 构建失败: {err_msg}")
            self._log("error", traceback.format_exc())
            # 失败后同样清理临时文件，但保留架构子目录与最终产物
            try: cleanup_temp_files(WORK_DIR, preserve_arch_dirs=True, arch=self.target_arch)
            except Exception: pass
            self.cb.done(False, "", err_msg)
        finally:
            if self.log_file:
                self.log_file.close()
                self.log_file = None
            clear_stop()


# ============================================================
#  命令行模式
# ============================================================

def cli_mode(cli_args: Optional[argparse.Namespace] = None):
    """命令行交互/非交互模式"""
    print("=" * 60)
    print("  elf2os — 将 ELF 文件打包为可启动操作系统 (多架构)")
    print("=" * 60)
    print()

    import getpass
    password = getpass.getpass("🔐 请输入 sudo 密码: ")
    if not password:
        print("❌ 密码不能为空", file=sys.stderr)
        sys.exit(1)
    rc, _, err = sudo_run(["true"], password, timeout=10)
    if rc != 0:
        print(f"❌ sudo 验证失败: {err.strip()[:200]}", file=sys.stderr)
        sys.exit(1)

    # 非交互模式（--elf 等参数已传）
    if cli_args and cli_args.elf:
        os_name = cli_args.name or "helloos"
        elf_path = os.path.abspath(cli_args.elf)
        target_arch = cli_args.arch or detect_host_arch()
        output_format = cli_args.output or DEFAULT_OUTPUT
    else:
        # 交互询问
        os_name = input("🏷️  操作系统名称 (默认: helloos): ").strip() or "helloos"

        print("\n🎯 可选架构:")
        for key, cfg in ARCH_TABLE.items():
            print(f"   {key:8s} - {cfg['label']}")
        default_arch = detect_host_arch()
        target_arch = input(f"🏗️  目标架构 (默认: {default_arch}): ").strip() or default_arch

        print("\n📤 输出格式: iso / bin / both (默认: iso)")
        output_format = input("   选择: ").strip() or DEFAULT_OUTPUT

        elf_path = input("📦 ELF 文件路径: ").strip()
        elf_path = os.path.abspath(elf_path)

    if target_arch not in ARCH_TABLE:
        print(f"❌ 不支持的架构: {target_arch}", file=sys.stderr)
        print(f"   可选: {', '.join(ARCH_TABLE.keys())}", file=sys.stderr)
        sys.exit(1)
    if output_format not in VALID_OUTPUTS:
        print(f"❌ 不支持的输出格式: {output_format}", file=sys.stderr)
        print(f"   可选: {', '.join(VALID_OUTPUTS)}", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(elf_path):
        print(f"❌ ELF 文件不存在: {elf_path}", file=sys.stderr)
        sys.exit(1)
    if not is_valid_elf(elf_path):
        print(f"❌ 文件不是有效的 ELF: {elf_path}", file=sys.stderr)
        sys.exit(1)

    print(f"\n   架构: {ARCH_TABLE[target_arch]['label']}")
    print(f"   输出: {output_format}")
    py_info = detect_python_elf(elf_path)
    if py_info:
        print(f"   🐍 Python ELF: {py_info.get('type','?')} {py_info.get('version','')}")
    else:
        print("   ℹ️  非 Python ELF")
    print()

    class CLICallbacks(BuildCallbacks):
        def progress(self, pct, msg=""):
            bar_len = 30
            filled = int(bar_len * pct / 100)
            bar = "█" * filled + "░" * (bar_len - filled)
            print(f"\r   [{bar}] {pct:3d}% {msg}", end="", flush=True)
            if pct >= 100:
                print()

    cb = CLICallbacks()
    engine = BuildEngine(cb, password, os_name, elf_path, target_arch, output_format)
    engine.run_all()


# ============================================================
#  GUI 前端
# ============================================================

def detect_gui_backend() -> str:
    try:
        import PyQt5  # noqa
        return "pyqt5"
    except ImportError:
        pass
    try:
        import tkinter  # noqa
        return "tkinter"
    except ImportError:
        pass
    return "none"


class PyQt5Frontend:
    def run(self):
        from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                                     QHBoxLayout, QLabel, QLineEdit, QPushButton,
                                     QFileDialog, QProgressBar, QPlainTextEdit,
                                     QMessageBox, QFrame, QComboBox)
        from PyQt5.QtCore import Qt, QThread, pyqtSignal
        from PyQt5.QtGui import QFont, QColor, QPalette  # noqa: F401  (QFont/QColor/QPalette 在 Window 中使用)

        app = QApplication(sys.argv)

        class Worker(QThread):
            log_signal = pyqtSignal(str, str)
            progress_signal = pyqtSignal(int, str)
            done_signal = pyqtSignal(bool, str, str)

            def __init__(self, password, os_name, elf_path, arch, output):
                super().__init__()
                self.password, self.os_name, self.elf_path = password, os_name, elf_path
                self.arch, self.output = arch, output

            def run(self):
                class GuiCB(BuildCallbacks):
                    def __init__(self, ls, ps, ds):
                        self._ls, self._ps, self._ds = ls, ps, ds
                    def log(self, level, msg): self._ls(level, msg)
                    def progress(self, pct, msg): self._ps(pct, msg)
                    def done(self, success, iso_path, error): self._ds(success, iso_path, error)

                cb = GuiCB(self.log_signal.emit, self.progress_signal.emit, self.done_signal.emit)
                engine = BuildEngine(cb, self.password, self.os_name, self.elf_path, self.arch, self.output)
                engine.run_all()

        class Window(QMainWindow):
            def __init__(self):
                super().__init__()
                self.setWindowTitle("elf2os — 将 ELF 变成操作系统 (多架构)")
                self.setMinimumSize(760, 600)

                central = QWidget()
                self.setCentralWidget(central)
                layout = QVBoxLayout(central)
                layout.setContentsMargins(24, 20, 24, 20)
                layout.setSpacing(10)

                title = QLabel("🐧 elf2os (多架构)")
                title.setFont(QFont("Sans", 18, 75))
                title.setStyleSheet("color: #89b4fa; padding-bottom: 4px;")
                layout.addWidget(title)
                subtitle = QLabel("ELF + Linux 极简内核 → 可启动 ISO / 裸内核+initramfs · 支持 x86/ARM64/ARM/RISC-V/PowerPC/MIPS")
                subtitle.setFont(QFont("Sans", 8))
                subtitle.setStyleSheet("color: #a6adc8; padding-bottom: 8px;")
                layout.addWidget(subtitle)

                sep = QFrame(); sep.setFrameShape(QFrame.HLine); sep.setStyleSheet("color: #313244; max-height: 1px;")
                layout.addWidget(sep)

                layout.addWidget(QLabel("🔐 sudo 密码（用于安装依赖与交叉工具链）"))
                self.pwd_input = QLineEdit(); self.pwd_input.setEchoMode(QLineEdit.Password)
                self.pwd_input.setPlaceholderText("输入 sudo 密码...")
                layout.addWidget(self.pwd_input)

                layout.addWidget(QLabel("🏷️  操作系统名称"))
                self.name_input = QLineEdit(); self.name_input.setPlaceholderText("例如: MyAwesomeOS")
                layout.addWidget(self.name_input)

                layout.addWidget(QLabel("📦 ELF 文件（你的操作系统本体）"))
                elf_row = QHBoxLayout()
                self.elf_input = QLineEdit(); self.elf_input.setPlaceholderText("选择 ELF 文件路径...")
                elf_row.addWidget(self.elf_input, 1)
                browse_btn = QPushButton("浏览..."); browse_btn.setMaximumWidth(100)
                browse_btn.clicked.connect(self._browse); elf_row.addWidget(browse_btn)
                layout.addLayout(elf_row)

                # 架构选择
                layout.addWidget(QLabel("🏗️  目标架构（交叉编译）"))
                self.arch_combo = QComboBox()
                host = detect_host_arch()
                for key, cfg in ARCH_TABLE.items():
                    self.arch_combo.addItem(f"{key} — {cfg['label']}", key)
                    if key == host:
                        self.arch_combo.setCurrentText(f"{key} — {cfg['label']}")
                layout.addWidget(self.arch_combo)

                # 输出格式
                layout.addWidget(QLabel("📤 输出格式"))
                self.output_combo = QComboBox()
                self.output_combo.addItem("ISO 镜像（可启动，默认）", OUTPUT_ISO)
                self.output_combo.addItem("裸 bin（内核+initramfs，便于手动部署/嵌入式）", OUTPUT_BIN)
                self.output_combo.addItem("两者都生成 (ISO + bin)", OUTPUT_BOTH)
                layout.addWidget(self.output_combo)

                sep2 = QFrame(); sep2.setFrameShape(QFrame.HLine); sep2.setStyleSheet("color: #313244; max-height: 1px;")
                layout.addWidget(sep2)

                layout.addWidget(QLabel("⏳ 构建进度"))
                self.progress = QProgressBar(); self.progress.setValue(0)
                layout.addWidget(self.progress)
                self.status_label = QLabel("就绪 | 请输入信息后点击构建")
                self.status_label.setStyleSheet("color: #a6adc8; font-size: 9px;")
                layout.addWidget(self.status_label)

                sep3 = QFrame(); sep3.setFrameShape(QFrame.HLine); sep3.setStyleSheet("color: #313244; max-height: 1px;")
                layout.addWidget(sep3)

                layout.addWidget(QLabel("📋 构建日志"))
                self.log_view = QPlainTextEdit(); self.log_view.setReadOnly(True)
                self.log_view.setMaximumBlockCount(2000)
                layout.addWidget(self.log_view, 1)

                self.build_btn = QPushButton("🚀 开始构建操作系统")
                self.build_btn.clicked.connect(self._start_build)
                layout.addWidget(self.build_btn)

                # 停止构建按钮（默认禁用，构建中启用）
                self.stop_btn = QPushButton("🛑 停止构建并清理临时文件")
                self.stop_btn.setEnabled(False)
                self.stop_btn.clicked.connect(self._stop_build)
                layout.addWidget(self.stop_btn)

                self.statusBar().showMessage("就绪")
                self.worker = None

            # 窗口关闭(X)：触发停止+清理后退出
            def closeEvent(self, event):
                if self.worker is not None and self.worker.isRunning():
                    self._stop_build(wait=False)
                # 清理工作目录临时文件（保留架构子目录与最终产物）
                try:
                    n = cleanup_temp_files(WORK_DIR, preserve_arch_dirs=True, arch=self.target_arch)
                    if n: self.statusBar().showMessage(f"已清理 {n} 项临时文件")
                except Exception:
                    pass
                event.accept()

            def _browse(self):
                path, _ = QFileDialog.getOpenFileName(self, "选择 ELF 文件", "", "ELF Files (*);;All Files (*)")
                if path: self.elf_input.setText(path)

            def _append_log(self, level, msg):
                color_map = {"info": "#a6e3a1", "warn": "#f9e2af", "error": "#f38ba8"}
                icon_map = {"info": "ℹ️", "warn": "⚠️", "error": "❌"}
                color = color_map.get(level, "#cdd6f4")
                self.log_view.appendHtml(f'<span style="color:{color}">{icon_map.get(level,"•")} {msg}</span>')

            def _set_progress(self, pct, msg):
                self.progress.setValue(pct)
                if msg: self.status_label.setText(msg)

            def _build_done(self, success, path, error):
                self.build_btn.setEnabled(True)
                self.stop_btn.setEnabled(False)
                for w in (self.pwd_input, self.name_input, self.elf_input):
                    w.setEnabled(True)
                if success:
                    QMessageBox.information(self, "构建成功",
                        f"✅ 操作系统已生成!\n\n路径: {path}\n\n测试: qemu-system-x86_64 -cdrom <iso> -m 512M")
                    self.statusBar().showMessage(f"✅ 构建成功: {path}")
                else:
                    QMessageBox.critical(self, "构建失败/停止", f"❌ {error}")
                    self.statusBar().showMessage("❌ 构建失败/已停止")

            def _start_build(self):
                password = self.pwd_input.text().strip()
                os_name = self.name_input.text().strip()
                elf_path = self.elf_input.text().strip()
                target_arch = self.arch_combo.currentData()
                output_format = self.output_combo.currentData()

                if not password: return QMessageBox.warning(self, "输入错误", "请输入 sudo 密码")
                if not os_name: return QMessageBox.warning(self, "输入错误", "请输入操作系统名称")
                if not elf_path or not os.path.exists(elf_path):
                    return QMessageBox.warning(self, "输入错误", "请选择有效的 ELF 文件")
                if not is_valid_elf(elf_path):
                    return QMessageBox.warning(self, "文件错误", "所选文件不是有效的 ELF 文件")

                rc, _, err = sudo_run(["true"], password, timeout=10)
                if rc != 0:
                    return QMessageBox.critical(self, "密码错误", f"sudo 验证失败:\n{err.strip()[:200]}")

                self.build_btn.setEnabled(False)
                self.stop_btn.setEnabled(True)
                for w in (self.pwd_input, self.name_input, self.elf_input):
                    w.setEnabled(False)
                self.log_view.clear(); self.progress.setValue(0)
                self.statusBar().showMessage("构建中...")

                self.worker = Worker(password, os_name, elf_path, target_arch, output_format)
                self.worker.log_signal.connect(self._append_log)
                self.worker.progress_signal.connect(self._set_progress)
                self.worker.done_signal.connect(self._build_done)
                self.worker.start()

            def _stop_build(self, wait=True):
                """请求停止当前构建：置停止标志、终止 worker 线程、清理临时文件。"""
                self.statusBar().showMessage("正在停止构建...")
                request_stop()
                if self.worker is not None:
                    # 等待一小段让引擎自然退出（清理路径会触发）
                    if wait:
                        self.worker.wait(3000)
                    if self.worker.isRunning():
                        self.worker.terminate()
                        self.worker.wait(2000)
                        if self.worker.isRunning():
                            self.worker.kill()
                # 清理临时文件，但保留架构子目录(os/<arch>/)与最终产物(ISO/_bin)
                try:
                    n = cleanup_temp_files(WORK_DIR, preserve_arch_dirs=True, arch=self.target_arch)
                    self._append_log("warn", f"🛑 已停止构建并清理 {n} 项临时文件（架构编译产物与最终产物已保留）")
                except Exception as e:
                    self._append_log("error", f"清理临时文件时出错: {e}")
                self.statusBar().showMessage("已停止并清理临时文件")

        win = Window(); win.show()
        sys.exit(app.exec_())


class TkinterFrontend:
    def run(self):
        import tkinter as tk
        from tkinter import ttk, filedialog, messagebox, scrolledtext

        root = tk.Tk()
        root.title("elf2os — 将 ELF 变成操作系统 (多架构)")
        root.geometry("780x660")
        root.configure(bg="#1e1e2e")

        style = ttk.Style()
        try: style.theme_use("clam")
        except tk.TclError: pass
        style.configure("TLabel", background="#1e1e2e", foreground="#cdd6f4", font=("Sans", 10))
        style.configure("TEntry", fieldbackground="#313244", foreground="#cdd6f4")
        style.configure("TButton", background="#89b4fa", foreground="#1e1e2e", font=("Sans", 11, "bold"))
        style.map("TButton", background=[("active", "#b4befe"), ("disabled", "#585b70")])
        style.configure("TProgressbar", background="#a6e3a1", troughcolor="#313244")
        style.configure("TCombobox", fieldbackground="#313244", foreground="#cdd6f4")

        main = ttk.Frame(root, padding=20); main.pack(fill="both", expand=True)

        tk.Label(main, text="🐧 elf2os (多架构)", font=("Sans", 20, "bold"),
                 bg="#1e1e2e", fg="#89b4fa").pack(anchor="w", pady=(0, 4))
        tk.Label(main, text="ELF + Linux 极简内核 → ISO / 裸 bin · x86/ARM64/ARM/RISC-V/PowerPC/MIPS",
                 font=("Sans", 8), bg="#1e1e2e", fg="#a6adc8").pack(anchor="w", pady=(0, 12))

        ttk.Separator(main, orient="horizontal").pack(fill="x", pady=4)

        ttk.Label(main, text="🔐 sudo 密码").pack(anchor="w", pady=(8, 2))
        pwd_var = tk.StringVar(); pwd_entry = ttk.Entry(main, textvariable=pwd_var, show="●"); pwd_entry.pack(fill="x", pady=(0, 8))

        ttk.Label(main, text="🏷️  操作系统名称").pack(anchor="w", pady=(4, 2))
        name_var = tk.StringVar(); name_entry = ttk.Entry(main, textvariable=name_var); name_entry.pack(fill="x", pady=(0, 8))

        ttk.Label(main, text="📦 ELF 文件").pack(anchor="w", pady=(4, 2))
        elf_frame = ttk.Frame(main); elf_frame.pack(fill="x", pady=(0, 8))
        elf_var = tk.StringVar(); elf_entry = ttk.Entry(elf_frame, textvariable=elf_var)
        elf_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        def browse():
            p = filedialog.askopenfilename(title="选择 ELF 文件", filetypes=[("ELF files", "*"), ("All files", "*.*")])
            if p: elf_var.set(p)
        ttk.Button(elf_frame, text="浏览...", command=browse).pack(side="right")

        ttk.Label(main, text="🏗️  目标架构（交叉编译）").pack(anchor="w", pady=(4, 2))
        arch_var = tk.StringVar(value=detect_host_arch())
        arch_combo = ttk.Combobox(main, textvariable=arch_var, state="readonly")
        arch_combo['values'] = [f"{k} — {v['label']}" for k, v in ARCH_TABLE.items()]
        arch_combo.set(f"{detect_host_arch()} — {ARCH_TABLE[detect_host_arch()]['label']}")
        arch_combo.pack(fill="x", pady=(0, 8))

        ttk.Label(main, text="📤 输出格式").pack(anchor="w", pady=(4, 2))
        output_var = tk.StringVar(value="iso")
        output_combo = ttk.Combobox(main, textvariable=output_var, state="readonly")
        output_combo['values'] = ["iso — ISO 镜像（可启动）", "bin — 裸内核+initramfs", "both — 两者都生成"]
        output_combo.set("iso — ISO 镜像（可启动）")
        output_combo.pack(fill="x", pady=(0, 8))

        ttk.Separator(main, orient="horizontal").pack(fill="x", pady=4)
        ttk.Label(main, text="⏳ 构建进度").pack(anchor="w", pady=(8, 2))
        progress = ttk.Progressbar(main, length=100, mode="determinate"); progress.pack(fill="x", pady=(0, 4))
        status_var = tk.StringVar(value="就绪 | 请输入信息后点击构建")
        ttk.Label(main, textvariable=status_var).pack(anchor="w")
        ttk.Separator(main, orient="horizontal").pack(fill="x", pady=4)
        ttk.Label(main, text="📋 构建日志").pack(anchor="w", pady=(8, 2))
        log_view = scrolledtext.ScrolledText(main, height=13, font=("Monospace", 9),
                                              bg="#11111b", fg="#a6e3a1", insertbackground="#cdd6f4")
        log_view.pack(fill="both", expand=True, pady=(0, 8))

        build_btn = ttk.Button(main, text="🚀 开始构建操作系统"); build_btn.pack(pady=4)
        stop_btn = ttk.Button(main, text="🛑 停止构建并清理临时文件", state="disabled")
        stop_btn.pack(pady=(0, 8))
        bottom = tk.Label(root, text="就绪", bg="#11111b", fg="#a6adc8", font=("Sans", 9), anchor="w", padx=10)
        bottom.pack(fill="x", side="bottom")

        build_thread = {"ref": None}  # 持有构建线程引用，便于停止时 join

        class GuiCB(BuildCallbacks):
            def __init__(self):
                self.log_view, self.progress_bar, self.status, self.bottom = log_view, progress, status_var, bottom
            def log(self, level, msg):
                color = {"info": "#a6e3a1", "warn": "#f9e2af", "error": "#f38ba8"}.get(level, "#cdd6f4")
                self.log_view.insert("end", f"{'ℹ️' if level=='info' else '⚠️' if level=='warn' else '❌'} {msg}\n", (level,))
                self.log_view.tag_config(level, foreground=color); self.log_view.see("end")
                self.bottom.config(text=msg[:80]); root.update_idletasks()
            def progress(self, pct, msg):
                self.progress_bar["value"] = pct
                if msg: self.status.set(msg)
                root.update_idletasks()
            def done(self, success, path, error):
                build_btn.config(state="normal"); stop_btn.config(state="disabled")
                pwd_entry.config(state="normal")
                name_entry.config(state="normal"); elf_entry.config(state="normal")
                if success:
                    messagebox.showinfo("构建成功", f"✅ 已生成!\n\n路径: {path}")
                    bottom.config(text=f"✅ 构建成功: {path}")
                else:
                    messagebox.showerror("构建失败/停止", f"❌ {error}")
                    bottom.config(text="❌ 构建失败/已停止")

        def start_build():
            password, os_name, elf_path = pwd_var.get().strip(), name_var.get().strip(), elf_var.get().strip()
            if not password: return messagebox.showwarning("输入错误", "请输入 sudo 密码")
            if not os_name: return messagebox.showwarning("输入错误", "请输入操作系统名称")
            if not elf_path or not os.path.exists(elf_path):
                return messagebox.showwarning("输入错误", "请选择有效的 ELF 文件")
            if not is_valid_elf(elf_path):
                return messagebox.showwarning("文件错误", "不是有效的 ELF 文件")
            # 解析 arch/output
            arch_val = arch_var.get().split(" — ")[0]
            out_val = output_var.get().split(" — ")[0]
            if arch_val not in ARCH_TABLE: return messagebox.showerror("架构错误", f"不支持: {arch_val}")
            if out_val not in VALID_OUTPUTS: return messagebox.showerror("格式错误", f"不支持: {out_val}")

            rc, _, err = sudo_run(["true"], password, timeout=10)
            if rc != 0: return messagebox.showerror("密码错误", f"sudo 验证失败:\n{err.strip()[:200]}")

            build_btn.config(state="disabled"); stop_btn.config(state="normal")
            pwd_entry.config(state="disabled")
            name_entry.config(state="disabled"); elf_entry.config(state="disabled")
            log_view.delete("1.0", "end"); progress["value"] = 0; bottom.config(text="构建中...")
            cb = GuiCB()
            engine = BuildEngine(cb, password, os_name, elf_path, arch_val, out_val)
            t = threading.Thread(target=engine.run_all, daemon=True)
            build_thread["ref"] = t
            t.start()

        def stop_build():
            if build_thread["ref"] is None or not build_thread["ref"].is_alive():
                return
            if not messagebox.askyesno("停止构建", "确定要停止当前构建并清理临时文件吗？\n（架构编译产物与最终产物将被保留）"):
                return
            bottom.config(text="正在停止构建...")
            request_stop()
            t = build_thread["ref"]
            t.join(timeout=4)
            if t.is_alive():
                # daemon 线程无法强制杀死，但停止标志已置位，引擎会在下一检查点退出
                bottom.config(text="停止信号已发送，等待构建自然退出...")
            try:
                n = cleanup_temp_files(WORK_DIR, preserve_arch_dirs=True, arch=self.target_arch)
                log_view.insert("end", f"🛑 已停止构建并清理 {n} 项临时文件（架构编译产物与最终产物已保留）\n")
                log_view.see("end")
            except Exception as e:
                log_view.insert("end", f"清理临时文件时出错: {e}\n")
            bottom.config(text="已停止并清理临时文件")

        def on_close():
            # 窗口关闭：若正在构建则先停止
            if build_thread["ref"] is not None and build_thread["ref"].is_alive():
                request_stop()
                try: build_thread["ref"].join(timeout=3)
                except Exception: pass
            # 清理临时文件，保留架构子目录与最终产物
            try: cleanup_temp_files(WORK_DIR, preserve_arch_dirs=True, arch=self.target_arch)
            except Exception: pass
            root.destroy()

        build_btn.config(command=start_build)
        stop_btn.config(command=stop_build)
        root.protocol("WM_DELETE_WINDOW", on_close)
        if "XDG_RUNTIME_DIR" not in os.environ:
            os.environ["XDG_RUNTIME_DIR"] = "/tmp/runtime-root"; os.makedirs("/tmp/runtime-root", exist_ok=True)
            try: os.chmod("/tmp/runtime-root", 0o700)
            except OSError: pass
        root.mainloop()


# ============================================================
#  主入口
# ============================================================

def main():
    if "XDG_RUNTIME_DIR" not in os.environ:
        os.environ["XDG_RUNTIME_DIR"] = "/tmp/runtime-root"; os.makedirs("/tmp/runtime-root", exist_ok=True)
        try: os.chmod("/tmp/runtime-root", 0o700)
        except OSError: pass

    parser = argparse.ArgumentParser(
        description="elf2os — 将 ELF 文件 + Linux 极简内核打包为可启动操作系统 (多架构)")
    parser.add_argument("--cli", action="store_true", help="强制使用命令行模式")
    parser.add_argument("--elf", type=str, help="ELF 文件路径（非交互模式）")
    parser.add_argument("--name", type=str, default="helloos", help="操作系统名称")
    parser.add_argument("--arch", type=str, choices=list(ARCH_TABLE.keys()),
                        help="目标架构 (默认: 自动检测宿主架构)")
    parser.add_argument("--output", type=str, choices=list(VALID_OUTPUTS),
                        help="输出格式: iso / bin / both (默认: iso)")
    args = parser.parse_args()

    use_cli = args.cli or not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY")

    if use_cli or args.elf:
        cli_mode(args if args.elf else None)
        return

    backend = detect_gui_backend()
    print(f"[elf2os] 检测到 GUI 后端: {backend}")
    if backend == "pyqt5":
        PyQt5Frontend().run()
    elif backend == "tkinter":
        print("[elf2os] 使用 tkinter 前端")
        TkinterFrontend().run()
    else:
        print("❌ 未找到可用的 GUI 框架!", file=sys.stderr)
        print("请安装: sudo apt-get install -y python3-pyqt5 python3-tk", file=sys.stderr)
        print("或运行: sudo python3 elf2os.py --cli", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
