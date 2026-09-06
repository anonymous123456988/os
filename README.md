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

   如有任何疑问，请联系：3909296166@qq.com
   本工具将开发出手机版和图形化编程形式的elf2os，坚持造福开发者，官网：https://anonymous123456988.github.io/#

elf2os — 将任意 ELF 变成可启动操作系统
一句话介绍：把任意 ELF 可执行文件（包括 Python 应用）打包成一个可以直接启动的 ISO 镜像或裸内核+initramfs，支持 7 种 CPU 架构，自动处理依赖、交叉编译和 Python 运行时注入。

🎯 这个工具能做什么？
elf2os.py 接收一个 ELF 文件作为输入，输出一个可直接启动的操作系统镜像。你不需要写内核代码、不需要配置 GRUB、不需要研究交叉编译——工具全自动完成。

输入：一个 ELF 可执行文件（可以是 C/C++/Go/Rust 编译的，也可以是 PyInstaller/Nuitka 打包的 Python 应用）

输出：

your_os.iso — 可启动的 ISO 镜像（CD-ROM/USB 启动）

your_os_bin/ — 裸内核 + initramfs（用于嵌入式部署、QEMU 直接启动）

启动流程：

text
BIOS/UEFI → GRUB → Linux 内核 → elf_runner (PID 1) → 你的 ELF (/bin/os.elf)
📦 支持的架构
架构	状态	交叉编译工具链	典型用途
x86_64	✅ 生产就绪	本机编译	通用服务器/PC
i386	✅ 生产就绪	gcc-i686-linux-gnu	老旧 32 位设备
ARM64 (AArch64)	✅ 生产就绪	gcc-aarch64-linux-gnu	树莓派 3+/4/5、飞腾、鲲鹏
ARM 32-bit (v7)	✅ 生产就绪	gcc-arm-linux-gnueabihf	树莓派 2/Zero
RISC-V 64-bit	✅ 生产就绪	gcc-riscv64-linux-gnu	开源芯片生态
PowerPC 64le (POWER8+)	✅ 生产就绪	gcc-powerpc64le-linux-gnu	IBM POWER 服务器
MIPS 64-bit	✅ 生产就绪	gcc-mips64-linux-gnu	龙芯等国产芯片
🚀 核心特性
1. 零配置多架构交叉编译
自动检测宿主架构，支持跨架构编译

自动安装所需交叉编译工具链（Debian/Ubuntu/Arch）

每个架构独立缓存，支持并行构建

2. 自动依赖收集
工具会分析你的 ELF 文件，把运行所需的一切都打包进 initramfs：







静态链接的 ELF：无需额外依赖，直接打包

动态链接的 ELF：自动收集所有 .so 依赖（递归 6 层）

Python ELF（PyInstaller/Nuitka）：

自动检测 Python 版本

注入 Python 标准库（排除 test/idlelib/tkinter）

注入 lib-dynload（C 扩展）

注入 site-packages（第三方包）

生成 .pth 路径配置文件

3. 智能的 elf_runner (PID 1)
编译为静态二进制，作为内核启动后的第一个进程（PID 1）：

挂载 /proc、/sys、devtmpfs、/tmp（512MB）

设置完整的 LD_LIBRARY_PATH 和 PYTHONPATH

自动清理 PyInstaller _MEI* 残留目录

重试机制启动 /bin/os.elf（最多 3 次）

失败后 fallback 到 busybox shell

4. 为 Python 应用优化
检测 PyInstaller/Nuitka/Cython 打包特征

通过字节码魔数识别 Python 版本（3.7 ~ 3.13）

注入完整的 Python 运行时（~30MB 标准库精简版）

设置 PYTHONHOME=/usr，PYTHONPATH 自动发现库

/tmp 挂载 512MB（满足 PyInstaller onefile 解压需求）

清理 /tmp/_MEI* 残留（防止磁盘空间耗尽）

5. 内核配置深度优化
基于 Linux 6.6.32 LTS，内核配置包含：

完整的文件系统支持（ext4/xfs/btrfs/f2fs/ntfs/exfat）

网络协议栈（IPv6/Netfilter/桥接/VLAN/MPTCP）

GPU/DRM 驱动（Intel/AMD/NVIDIA/ARM Mali/VirtIO）

安全加固（SELinux/AppArmor/ASLR/堆栈保护）

容器/虚拟化支持（Cgroups/命名空间/KVM）

国密算法支持（SM2/SM3/SM4）

共计 600+ 内核选项，覆盖绝大多数硬件场景

6. 两种输出格式
格式	内容	用途
ISO	kernel.bin + initramfs.cpio.gz + GRUB	CD-ROM/USB 启动，通用
BIN	kernel.bin + initramfs.cpio.gz	QEMU 直接启动，嵌入式部署
7. GUI 界面（可选）
PyQt5 前端：美观的现代化界面

Tkinter 前端：轻量级备选（无需额外依赖）

实时进度条、构建日志、停止构建功能

🔧 系统要求
基础要求
操作系统：Linux (Debian/Ubuntu/Kali/Arch 优先)

Python：3.8+

磁盘空间：至少 10GB（用于内核源码编译）

内存：建议 4GB+

网络：需要下载 Linux 内核 (~150MB)

自动安装的依赖（需要 sudo）
text
build-essential gcc make bc bison flex
libelf-dev libssl-dev libncurses-dev
wget curl cpio gzip xz-utils
grub-pc-bin grub-efi-amd64-bin xorriso
qemu-utils python3-dev strace binutils
kmod libudev-dev autoconf automake pkg-config
mtools gdisk dosfstools
交叉编译额外依赖
bash
# ARM64
sudo apt-get install gcc-aarch64-linux-gnu binutils-aarch64-linux-gnu

# ARM32
sudo apt-get install gcc-arm-linux-gnueabihf binutils-arm-linux-gnueabihf

# RISC-V
sudo apt-get install gcc-riscv64-linux-gnu binutils-riscv64-linux-gnu

# PowerPC
sudo apt-get install gcc-powerpc64le-linux-gnu binutils-powerpc64le-linux-gnu

# MIPS
sudo apt-get install gcc-mips64-linux-gnu binutils-mips64-linux-gnu
📥 安装
方式一：直接下载
bash
git clone https://github.com/anonymous123456988/elf2os
cd elf2os
chmod +x elf2os.py
方式二：一键脚本
bash
curl -o elf2os.py https://raw.githubusercontent.com/.../elf2os.py
python3 elf2os.py --help
💻 使用方法
基础用法
bash
# 交互式模式（GUI）
python3 elf2os.py

# 命令行交互模式
python3 elf2os.py --cli

# 非交互模式（直接指定参数）
sudo python3 elf2os.py --elf /path/to/your/app --name MyOS --arch x86_64 --output both
参数说明
参数	说明	示例
--cli	强制使用命令行模式	--cli
--elf	ELF 文件路径（必须）	--elf ./hello.elf
--name	操作系统名称	--name MyOS
--arch	目标架构	--arch arm64
--output	输出格式	--output both
架构选项
text
x86_64   - 通用 64 位 PC
i386     - 32 位 x86
arm64    - ARM64/AArch64（树莓派 3+/4+/5、飞腾、鲲鹏）
arm      - ARM 32-bit（树莓派 2/Zero）
riscv64  - RISC-V 64-bit
ppc64le  - PowerPC 64-bit Little-Endian（POWER8/9/10）
mips64   - MIPS 64-bit（龙芯等）
输出格式
text
iso    - 仅生成 ISO 镜像（CD-ROM/USB 启动）
bin    - 仅生成裸内核+initramfs（嵌入式部署）
both   - 同时生成 ISO 和裸 bin
📂 工作目录结构
工具会在当前目录创建 os/ 文件夹，按架构隔离：

text
os/
├── x86_64/
│   ├── linux-6.6.32/          # 内核源码 + 编译产物
│   ├── linux-6.6.32.tar.xz    # 内核压缩包（缓存）
│   ├── initramfs/             # 构建临时目录
│   ├── initramfs.cpio.gz      # 最终 initramfs
│   ├── MyOS.iso               # ISO 镜像
│   ├── MyOS_bin/              # 裸输出目录
│   │   ├── kernel.bin
│   │   ├── initramfs.cpio.gz
│   │   └── README.txt
│   ├── MyOS_bin.tar.gz        # 裸输出打包
│   └── build.log              # 构建日志
├── arm64/
│   └── ...
└── ...
🧪 测试生成的 ISO
bash
# x86_64
qemu-system-x86_64 -cdrom MyOS.iso -m 512M

# ARM64
qemu-system-aarch64 -machine virt -cpu cortex-a57 -cdrom MyOS.iso -m 512M -nographic

# RISC-V
qemu-system-riscv64 -machine virt -cdrom MyOS.iso -m 512M -nographic
测试裸 bin
bash
# x86_64
qemu-system-x86_64 -kernel kernel.bin -initrd initramfs.cpio.gz -append "console=tty0 init=/init" -m 512M

# ARM64
qemu-system-aarch64 -machine virt -cpu cortex-a57 -kernel kernel.bin -initrd initramfs.cpio.gz -append "console=ttyAMA0 init=/init" -m 512M -nographic
🖼️ GUI 界面预览
PyQt5 前端
text
┌─────────────────────────────────────────────────────────┐
│  🐧 elf2os (多架构)                                    │
│  ELF + Linux 极简内核 → 可启动 ISO / 裸内核+initramfs  │
│  ────────────────────────────────────────────────────   │
│  🔐 sudo 密码（用于安装依赖与交叉工具链）               │
│  [●●●●●●●●●●]                                         │
│  🏷️  操作系统名称                                      │
│  [MyAwesomeOS]                                         │
│  📦 ELF 文件（你的操作系统本体）                       │
│  [/path/to/app.elf] [浏览...]                         │
│  🏗️  目标架构（交叉编译）                              │
│  [x86_64 — x86_64 / AMD64 ▼]                          │
│  📤 输出格式                                           │
│  [ISO 镜像（可启动，默认）▼]                          │
│  ────────────────────────────────────────────────────   │
│  ⏳ 构建进度                                           │
│  [████████░░░░░░░░░░░░] 45% 编译内核...               │
│  ────────────────────────────────────────────────────   │
│  📋 构建日志                                           │
│  ┌─────────────────────────────────────────────────┐   │
│  │ ℹ️ 检测到发行版: Ubuntu (家族: debian)          │   │
│  │ ℹ️ 目标架构: x86_64 / AMD64                    │   │
│  │ ℹ️ 配置内核 (ARCH=x86 CROSS_COMPILE=)...       │   │
│  └─────────────────────────────────────────────────┘   │
│  [🚀 开始构建操作系统]  [🛑 停止构建并清理临时文件]    │
└─────────────────────────────────────────────────────────┘
📜 许可证
本软件采用商业使用授权协议（详见文件头部）：

✅ 个人/企业内部非商业项目：免费使用

❌ 商业用途：需获得授权方书面许可

❌ 禁止行为：反向工程、作为独立产品出售、嵌入竞品

如有商业授权需求，请联系：https://github.com/anonymous123456988

🤝 贡献与反馈
GitHub Issues：https://github.com/anonymous123456988

Bug 报告：请提供完整构建日志（os/<arch>/build.log）


内核配置策略
工具维护了一个 600+ 行的 KERNEL_CONFIG_APPEND 配置块，涵盖：

文件系统（20+ 种）

网络协议（15+ 种）

加密算法（30+ 种）

GPU/DRM 驱动（20+ 种）

安全加固（15+ 项）


# ============================================================
#  elf2os 完整内核配置项
# ============================================================

# ---------- 基础 ELF/可执行文件支持 ----------
CONFIG_BINFMT_ELF=y                 # ELF 可执行文件格式支持
CONFIG_BINFMT_SCRIPT=y              # #! 脚本解释器支持
CONFIG_BINFMT_MISC=y                # 其他二进制格式支持（Java/.NET等）

# ---------- Initramfs 支持 ----------
CONFIG_BLK_DEV_INITRD=y             # initramfs 块设备支持
CONFIG_RD_GZIP=y                    # gzip 压缩 initramfs 支持

# ---------- 虚拟文件系统 ----------
CONFIG_DEVTMPFS=y                   # /dev 设备文件系统
CONFIG_DEVTMPFS_MOUNT=y             # 自动挂载 /dev
CONFIG_TMPFS=y                      # /tmp 内存文件系统
CONFIG_SHMEM=y                      # 共享内存支持
CONFIG_TMPFS_XATTR=y                # tmpfs 扩展属性
CONFIG_PROC_FS=y                    # /proc 进程文件系统
CONFIG_SYSFS=y                      # /sys 系统文件系统

# ---------- 存储/块设备 ----------
CONFIG_BLK_DEV_SD=y                 # SCSI 磁盘驱动
CONFIG_BLK_DEV=y                    # 块设备支持
CONFIG_BLK_MQ_PCI=y                 # 块设备多队列 PCI
CONFIG_BLK_DEV_NVME=y               # NVMe SSD 支持
CONFIG_ATA_GENERIC=y                # 通用 ATA 驱动
CONFIG_ATA_PIIX=y                   # Intel PIIX 芯片组 ATA
CONFIG_SATA_AHCI=y                  # AHCI SATA 控制器

# ---------- SCSI 子系统 ----------
CONFIG_SCSI=y                       # SCSI 子系统
CONFIG_SCSI_MOD=y                   # SCSI 模块支持
CONFIG_SCSI_VIRTIO=y                # VirtIO SCSI
CONFIG_SCSI_SAS_ATA=y               # SAS ATA 桥接
CONFIG_SCSI_SAS_LIBSAS=y            # SAS 库支持
CONFIG_SCSI_MPT3SAS=y               # LSI MPT3 SAS 驱动
CONFIG_SCSI_MPT2SAS=y               # LSI MPT2 SAS 驱动

# ---------- 文件系统 ----------
CONFIG_EXT4_FS=y                    # ext4 文件系统
CONFIG_VFAT_FS=y                    # FAT/VFAT 文件系统
CONFIG_EXFAT_FS=y                   # exFAT 文件系统（大容量U盘）
CONFIG_F2FS_FS=y                    # F2FS 闪存友好文件系统
CONFIG_BTRFS_FS=y                   # Btrfs 文件系统（快照/校验）
CONFIG_XFS_FS=y                     # XFS 高性能文件系统
CONFIG_NTFS_FS=y                    # NTFS 文件系统
CONFIG_ISO9660_FS=y                 # ISO9660 CD-ROM 文件系统
CONFIG_UDF_FS=y                     # UDF DVD/蓝光文件系统
CONFIG_FUSE_FS=y                    # FUSE 用户态文件系统
CONFIG_SQUASHFS=y                   # SquashFS 只读压缩文件系统
CONFIG_EROFS_FS=y                   # EROFS 增强只读文件系统
CONFIG_ECRYPT_FS=y                  # eCryptfs 加密文件系统
CONFIG_UBIFS_FS=y                   # UBIFS 闪存文件系统
CONFIG_JFFS2_FS=y                   # JFFS2 闪存文件系统
CONFIG_ROMFS_FS=y                   # ROMFS 只读文件系统
CONFIG_CRAMFS=y                     # CRAMFS 压缩文件系统
CONFIG_AFS_FS=y                     # AFS 分布式文件系统
CONFIG_9P_FS=y                      # 9P 文件系统（virtio-fs）
CONFIG_CEPH_FS=y                    # Ceph 分布式文件系统
CONFIG_ORANGEFS_FS=y                # OrangeFS 并行文件系统
CONFIG_GFS2_FS=y                    # GFS2 集群文件系统
CONFIG_OCFS2_FS=y                   # OCFS2 集群文件系统
CONFIG_JFS_FS=y                     # JFS 文件系统
CONFIG_REISERFS_FS=y                # ReiserFS 文件系统
CONFIG_HFS_FS=y                     # HFS Mac 文件系统
CONFIG_HFSPLUS_FS=y                 # HFS+ Mac 文件系统
CONFIG_ZONEFS_FS=y                  # ZoneFS 分区文件系统
CONFIG_OVERLAY_FS=y                 # OverlayFS 联合文件系统（容器）

# ---------- 网络文件系统 ----------
CONFIG_NFS_FS=y                     # NFS 客户端
CONFIG_NFS_V3=y                     # NFS v3
CONFIG_NFS_V4=y                     # NFS v4
CONFIG_CIFS=y                       # CIFS/SMB 文件系统
CONFIG_EFIVAR_FS=y                  # EFI 变量文件系统

# ---------- 存储持久化 ----------
CONFIG_PSTORE=y                     # pstore 崩溃日志
CONFIG_PSTORE_RAM=y                 # pstore RAM 后端
CONFIG_PSTORE_BLK=y                 # pstore 块设备后端

# ---------- 字符集/本地化 ----------
CONFIG_NLS_CODEPAGE_437=y           # 代码页 437 (US/English)
CONFIG_NLS_ISO8859_1=y              # ISO-8859-1 字符集

# ---------- 显示/Framebuffer ----------
CONFIG_FRAMEBUFFER_CONSOLE=y        # Framebuffer 控制台
CONFIG_FRAMEBUFFER_CONSOLE_DETECT_PRIMARY=y  # 自动检测主显示
CONFIG_FRAMEBUFFER_CONSOLE_ROTATION=y        # 控制台旋转
CONFIG_FB=y                         # Framebuffer 子系统
CONFIG_FB_VESA=y                    # VESA Framebuffer
CONFIG_FB_EFI=y                     # EFI Framebuffer
CONFIG_FB_CFB_FILLRECT=y            # CFB 填充矩形加速
CONFIG_FB_CFB_COPYAREA=y            # CFB 复制区域加速
CONFIG_FB_CFB_IMAGEBLIT=y           # CFB 图像块传输加速
CONFIG_FB_SYS_FILLRECT=y            # 系统填充矩形加速
CONFIG_FB_SYS_COPYAREA=y            # 系统复制区域加速
CONFIG_FB_SYS_IMAGEBLIT=y           # 系统图像块传输加速
CONFIG_FB_SYS_OPS=y                 # 系统操作支持
CONFIG_FB_SIMPLE=y                  # 简单 Framebuffer
CONFIG_FB_AMD=y                     # AMD GPU Framebuffer

# ---------- DRM 图形驱动 ----------
CONFIG_DRM=y                        # DRM 核心
CONFIG_DRM_BOCHS=y                  # Bochs/VirtIO 虚拟显卡
CONFIG_DRM_VIRTIO_GPU=y             # VirtIO GPU
CONFIG_DRM_VMWGFX=y                 # VMWare SVGA
CONFIG_DRM_VMWGFX_FBCON=y           # VMWare FB 控制台
CONFIG_DRM_FBDEV_EMULATION=y        # FBDEV 模拟
CONFIG_DRM_FBDEV_OVERALLOC=100      # FBDEV 过度分配
CONFIG_DRM_LOAD_EDID_FIRMWARE=y     # 加载 EDID 固件
CONFIG_DRM_I915=y                   # Intel i915 GPU
CONFIG_DRM_RADEON=y                 # AMD Radeon GPU
CONFIG_DRM_NOUVEAU=y                # NVIDIA Nouveau GPU
CONFIG_DRM_AMDGPU=y                 # AMD GPU 新驱动
CONFIG_DRM_ETNAVIV=y                # Vivante GPU (i.MX)
CONFIG_DRM_EXYNOS=y                 # Samsung Exynos GPU
CONFIG_DRM_IMX=y                    # i.MX 显示控制器
CONFIG_DRM_MESON=y                  # Amlogic Meson GPU
CONFIG_DRM_MSM=y                    # Qualcomm Adreno GPU
CONFIG_DRM_OMAP=y                   # TI OMAP GPU
CONFIG_DRM_RCAR=y                   # Renesas R-Car GPU
CONFIG_DRM_ROCKCHIP=y               # Rockchip GPU
CONFIG_DRM_STM=y                    # STMicroelectronics GPU
CONFIG_DRM_SUN4I=y                  # Allwinner Sun4i GPU
CONFIG_DRM_TEGRA=y                  # NVIDIA Tegra GPU
CONFIG_DRM_V3D=y                    # Broadcom V3D GPU
CONFIG_DRM_VC4=y                    # Broadcom VC4 GPU
CONFIG_DRM_LOONGSON=y               # Loongson GPU
CONFIG_DRM_HISI_HIBMC=y             # Hisilicon HiBMC GPU
CONFIG_DRM_KMB=y                    # Keem Bay GPU
CONFIG_DRM_GM12U320=y               # GM12U320 GPU
CONFIG_DRM_PANEL=y                  # DRM 面板支持
CONFIG_DRM_BRIDGE=y                 # DRM 桥接支持
CONFIG_DRM_DP_AUX_BUS=y             # DisplayPort AUX 总线

# ---------- 控制台/终端 ----------
CONFIG_VT=y                         # 虚拟终端
CONFIG_VT_CONSOLE=y                 # 终端控制台
CONFIG_HW_CONSOLE=y                 # 硬件控制台
CONFIG_DUMMY_CONSOLE=y              # 虚拟控制台
CONFIG_DUMMY_CONSOLE_COLUMNS=80     # 虚拟控制台列数
CONFIG_DUMMY_CONSOLE_ROWS=25        # 虚拟控制台行数

# ---------- 启动 Logo ----------
CONFIG_LOGO=y                       # 启动 Logo 支持
CONFIG_LOGO_LINUX_MONO=y            # Linux 单色 Logo
CONFIG_LOGO_LINUX_VGA16=y           # Linux VGA16 Logo
CONFIG_LOGO_LINUX_CLUT224=y         # Linux 彩色 Logo

# ---------- 输入子系统 ----------
CONFIG_INPUT=y                      # 输入核心
CONFIG_INPUT_KEYBOARD=y             # 键盘支持
CONFIG_INPUT_MOUSE=y                # 鼠标支持
CONFIG_INPUT_EVDEV=y                # 事件设备
CONFIG_INPUT_MOUSEDEV=y             # 鼠标设备
CONFIG_INPUT_MOUSEDEV_PSAUX=y       # PS/2 鼠标设备
CONFIG_INPUT_JOYSTICK=y             # 摇杆支持
CONFIG_INPUT_TABLET=y               # 数位板支持
CONFIG_INPUT_TOUCHSCREEN=y          # 触摸屏支持
CONFIG_INPUT_APMPOWER=y             # APM 电源按钮
CONFIG_INPUT_KEYSPAN=y              # KeySpan 键盘
CONFIG_INPUT_PCSPKR=y               # PC 扬声器
CONFIG_INPUT_UINPUT=y               # uinput 用户态输入
CONFIG_INPUT_JOYDEV=y               # 摇杆设备
CONFIG_INPUT_FF_MEMLESS=y           # 无内存力反馈
CONFIG_INPUT_POLLDEV=y              # 轮询设备
CONFIG_INPUT_SPARSEKMAP=y           # 稀疏键映射

# ---------- 鼠标/串行 ----------
CONFIG_MOUSE_PS2=y                  # PS/2 鼠标
CONFIG_SERIO=y                      # 串行 IO 核心
CONFIG_SERIO_I8042=y                # i8042 键盘控制器
CONFIG_SERIO_SERPORT=y              # 串口设备

# ---------- HID 人机交互 ----------
CONFIG_HID=y                        # HID 核心
CONFIG_HID_GENERIC=y                # 通用 HID
CONFIG_HID_VMWARE_BALLOON=y         # VMWare 气球 HID

# ---------- USB 支持 ----------
CONFIG_USB=y                        # USB 核心
CONFIG_USB_STORAGE=y                # USB 存储
CONFIG_USB_XHCI_HCD=y               # USB 3.0 xHCI
CONFIG_USB_EHCI_HCD=y               # USB 2.0 EHCI
CONFIG_USB_OHCI_HCD=y               # USB 1.1 OHCI
CONFIG_USB_UHCI_HCD=y               # USB 1.1 UHCI
CONFIG_USB_DWC3=y                   # Synopsys DWC3 (USB3)
CONFIG_USB_DWC2=y                   # Synopsys DWC2 (USB2)
CONFIG_USB_CDNS3=y                  # Cadence USB3
CONFIG_USB_MUSB_HDRC=y              # MUSB 控制器
CONFIG_USB_RENESAS_USB3=y           # Renesas USB3
CONFIG_USB_XHCI_MTK=y               # MediaTek xHCI
CONFIG_USB_XHCI_PLATFORM=y          # xHCI 平台驱动
CONFIG_USB_NET_DRIVERS=y            # USB 网卡驱动
CONFIG_USB_NET_AX8817X=y            # ASIX AX8817X
CONFIG_USB_NET_AX88179=y            # ASIX AX88179
CONFIG_USB_NET_RTL8150=y            # Realtek RTL8150
CONFIG_USB_NET_RTL8152=y            # Realtek RTL8152
CONFIG_USB_ACM=y                    # USB ACM (调制解调器)
CONFIG_USB_SERIAL=y                 # USB 串口
CONFIG_USB_SERIAL_PL2303=y          # Prolific PL2303
CONFIG_USB_SERIAL_FTDI_SIO=y        # FTDI FT232
CONFIG_USB_SERIAL_CP210X=y          # Silicon Labs CP210x
CONFIG_USB_SERIAL_CH341=y           # Winchiphead CH341
CONFIG_USB_SERIAL_SIMPLE=y          # 简单 USB 串口
CONFIG_USB_SERIAL_OPTION=y          # Option 无线
CONFIG_USB_SERIAL_QC_SERIAL=y       # Qualcomm 串口
CONFIG_USB_TMC=y                    # USB TMC (测试测量)
CONFIG_USB_WDM=y                    # USB WDM

# ---------- 网络协议栈 ----------
CONFIG_NET=y                        # 网络核心
CONFIG_NET_CORE=y                   # 网络核心
CONFIG_INET=y                       # IPv4
CONFIG_UNIX=y                       # Unix 域套接字
CONFIG_IPV6=y                       # IPv6
CONFIG_SCTP=y                       # SCTP 协议
CONFIG_DCCP=y                       # DCCP 协议
CONFIG_TIPC=y                       # TIPC 集群协议
CONFIG_MPTCP=y                      # 多路径 TCP
CONFIG_IPV6_SIT=y                   # IPv6 over IPv4 隧道
CONFIG_IPV6_TUNNEL=y                # IPv6 隧道
CONFIG_NETFILTER=y                  # Netfilter 防火墙
CONFIG_NETFILTER_XTABLES=y          # Netfilter 扩展表
CONFIG_NF_NAT_IPV4=y                # IPv4 NAT
CONFIG_IP_NF_IPTABLES=y             # IP 表
CONFIG_IP_NF_NAT=y                  # IP NAT
CONFIG_NF_CONNTRACK=y               # 连接跟踪
CONFIG_NF_NAT=y                     # NAT
CONFIG_BRIDGE=y                     # 网桥
CONFIG_BRIDGE_NF_EBTABLES=y         # ebtables
CONFIG_VLAN_8021Q=y                 # VLAN 802.1Q
CONFIG_BONDING=y                    # 网卡绑定
CONFIG_WIRELESS=y                   # 无线核心
CONFIG_CFG80211=y                   # cfg80211 无线配置
CONFIG_CFG80211_WEXT=y              # 无线扩展兼容
CONFIG_MAC80211=y                   # mac80211 无线栈
CONFIG_IP_MROUTE=y                  # IP 多播路由
CONFIG_IP_PIMSM_V1=y                # PIM-SM v1
CONFIG_IP_PIMSM_V2=y                # PIM-SM v2
CONFIG_6LOWPAN=y                    # 6LoWPAN
CONFIG_6LOWPAN_NHC=y                # 6LoWPAN 头部压缩
CONFIG_NET_9P=y                     # 9P 网络协议
CONFIG_NET_9P_VIRTIO=y              # 9P VirtIO
CONFIG_RDS=y                        # RDS 协议
CONFIG_RDS_TCP=y                    # RDS over TCP
CONFIG_RDS_RDMA=y                   # RDS over RDMA
CONFIG_L2TP=y                       # L2TP
CONFIG_L2TP_ETH=y                   # L2TP 以太网
CONFIG_L2TP_DEBUGFS=y               # L2TP 调试
CONFIG_PPPOE=y                      # PPP over Ethernet
CONFIG_PPP_ASYNC=y                  # PPP 异步
CONFIG_PPP_SYNC_TTY=y               # PPP 同步 TTY
CONFIG_PPP_DEFLATE=y                # PPP Deflate
CONFIG_PPP_BSDCOMP=y                # PPP BSD 压缩
CONFIG_PPP_MPPE=y                   # PPP MPPE 加密
CONFIG_NET_PTP=y                    # PTP 网络时钟
CONFIG_PTP_1588_CLOCK=y             # PTP 1588 时钟

# ---------- 网络设备驱动 ----------
CONFIG_NETDEVICES=y                 # 网络设备
CONFIG_E1000=y                      # Intel e1000 网卡
CONFIG_E1000E=y                     # Intel e1000e 网卡
CONFIG_ATH9K=y                      # Atheros WiFi
CONFIG_RTL8188EU=y                  # Realtek 8188EU WiFi
CONFIG_MT76=y                       # MediaTek WiFi
CONFIG_BRCMFMAC=y                   # Broadcom WiFi
CONFIG_NET_VENDOR_AMAZON=y          # Amazon 网卡
CONFIG_NET_VENDOR_GOOGLE=y          # Google 网卡
CONFIG_NET_VENDOR_MICROSOFT=y       # Microsoft 网卡
CONFIG_NET_VENDOR_HUAWEI=y          # Huawei 网卡
CONFIG_NET_VENDOR_CHELSIO=y         # Chelsio 网卡
CONFIG_NET_VENDOR_QLOGIC=y          # QLogic 网卡
CONFIG_NET_VENDOR_EMULEX=y          # Emulex 网卡
CONFIG_NET_VENDOR_CISCO=y           # Cisco 网卡
CONFIG_NET_VENDOR_HP=y              # HP 网卡
CONFIG_NET_VENDOR_IBM=y             # IBM 网卡
CONFIG_WLAN_VENDOR_ATH=y            # Atheros WiFi
CONFIG_WLAN_VENDOR_BROADCOM=y       # Broadcom WiFi
CONFIG_WLAN_VENDOR_INTEL=y          # Intel WiFi
CONFIG_WLAN_VENDOR_MEDIATEK=y       # MediaTek WiFi
CONFIG_WLAN_VENDOR_QUANTENNA=y      # Quantenna WiFi
CONFIG_WLAN_VENDOR_RALINK=y         # Ralink WiFi
CONFIG_WLAN_VENDOR_REALTEK=y        # Realtek WiFi
CONFIG_WLAN_VENDOR_RENESAS=y        # Renesas WiFi
CONFIG_WLAN_VENDOR_TI=y             # TI WiFi

# ---------- 蓝牙 ----------
CONFIG_BT=y                         # 蓝牙核心
CONFIG_BT_HCIBTUSB=y                # USB 蓝牙
CONFIG_BT_HCIUART=y                 # UART 蓝牙
CONFIG_BT_HCIUART_H4=y              # H4 UART 蓝牙
CONFIG_BT_HCIUART_BCSP=y            # BCSP UART 蓝牙
CONFIG_BT_HCIUART_LL=y              # LL UART 蓝牙
CONFIG_BT_HCIUART_3WIRE=y           # 3-Wire UART 蓝牙
CONFIG_BT_HCIUART_INTEL=y           # Intel UART 蓝牙
CONFIG_BT_HCIUART_BCM=y             # Broadcom UART 蓝牙
CONFIG_BT_HCIUART_QCA=y             # QCA UART 蓝牙
CONFIG_BT_RFCOMM=y                  # RFCOMM 蓝牙
CONFIG_BT_BNEP=y                    # BNEP 蓝牙
CONFIG_BT_CMTP=y                    # CMTP 蓝牙
CONFIG_BT_HIDP=y                    # HIDP 蓝牙

# ---------- 无线/NFC ----------
CONFIG_NFC=y                        # NFC 核心
CONFIG_NFC_DIGITAL=y                # NFC 数字
CONFIG_NFC_NCI=y                    # NFC NCI
CONFIG_NFC_HCI=y                    # NFC HCI
CONFIG_IEEE802154=y                 # IEEE 802.15.4
CONFIG_IEEE802154_6LOWPAN=y         # 6LoWPAN over 802.15.4
CONFIG_MAC802154=y                  # mac802154
CONFIG_WPAN=y                       # WPAN

# ---------- PCI 总线 ----------
CONFIG_PCI=y                        # PCI 总线
CONFIG_PCI_MSI=y                    # PCI MSI 中断

# ---------- 固件/微码 ----------
CONFIG_MICROCODE=y                  # CPU 微码
CONFIG_MICROCODE_INTEL=y            # Intel 微码
CONFIG_MICROCODE_AMD=y              # AMD 微码
CONFIG_MICROCODE_OLD_INTERFACE=y    # 旧微码接口
CONFIG_FW_LOADER=y                  # 固件加载器
CONFIG_FW_LOADER_USER_HELPER=y      # 用户态固件加载

# ---------- EFI 支持 ----------
CONFIG_EFI_SECURE_BOOT=y            # EFI 安全启动
CONFIG_EFI_CAPSULE=y                # EFI 胶囊
CONFIG_EFI_CAPSULE_LOADER=y         # EFI 胶囊加载器

# ---------- TPM 可信平台 ----------
CONFIG_TPM=y                        # TPM 核心
CONFIG_TPM_TIS=y                    # TPM TIS

# ---------- 安全/加密 ----------
CONFIG_SECURITY=y                   # 安全框架
CONFIG_SECURITY_SELINUX=y           # SELinux
CONFIG_SECURITY_SELINUX_BOOTPARAM=y # SELinux 启动参数
CONFIG_SECURITY_APPARMOR=y          # AppArmor
CONFIG_SECURITY_APPARMOR_BOOTPARAM_VALUE=1  # AppArmor 默认启用
CONFIG_RANDOMIZE_BASE=y             # KASLR 地址随机化
CONFIG_STACKPROTECTOR_STRONG=y      # 强栈保护
CONFIG_STRICT_DEVMEM=y              # 严格 /dev/mem
CONFIG_STRICT_KERNEL_RWX=y          # 内核内存严格 RWX
CONFIG_DEBUG_RODATA=y               # 只读数据段
CONFIG_MODULE_SIG=y                 # 模块签名
CONFIG_INTEGRITY=y                  # 完整性框架
CONFIG_IMA=y                        # IMA 完整性测量
CONFIG_EVM=y                        # EVM 扩展验证
CONFIG_ENCRYPTED_KEYS=y             # 加密密钥
CONFIG_TRUSTED_KEYS=y               # 可信密钥
CONFIG_KEY_DH_OPERATIONS=y          # DH 密钥操作
CONFIG_SYSTEM_TRUSTED_KEYRING=y     # 系统可信密钥环

# ---------- 加密算法 ----------
CONFIG_CRYPTO=y                     # 加密核心
CONFIG_CRYPTO_AES=y                 # AES
CONFIG_CRYPTO_SHA256=y              # SHA256
CONFIG_CRYPTO_SHA512=y              # SHA512
CONFIG_CRYPTO_RSA=y                 # RSA
CONFIG_CRYPTO_ECC=y                 # ECC
CONFIG_CRYPTO_CHACHA20=y            # ChaCha20
CONFIG_CRYPTO_POLY1305=y            # Poly1305
CONFIG_CRYPTO_CURVE25519=y          # Curve25519
CONFIG_CRYPTO_XXHASH=y              # xxHash
CONFIG_CRYPTO_CRC32C=y              # CRC32C
CONFIG_CRYPTO_CAMELLIA=y            # Camellia
CONFIG_CRYPTO_TWOFISH=y             # Twofish
CONFIG_CRYPTO_SERPENT=y             # Serpent
CONFIG_CRYPTO_CAST5=y               # CAST5
CONFIG_CRYPTO_CAST6=y               # CAST6
CONFIG_CRYPTO_KECCAK=y              # Keccak
CONFIG_CRYPTO_SHA3=y                # SHA3
CONFIG_CRYPTO_BLAKE2B=y             # BLAKE2b
CONFIG_CRYPTO_GHASH=y               # GHASH
CONFIG_CRYPTO_GCM=y                 # GCM
CONFIG_CRYPTO_CCM=y                 # CCM
CONFIG_CRYPTO_CTS=y                 # CTS
CONFIG_CRYPTO_LRW=y                 # LRW
CONFIG_CRYPTO_XTS=y                 # XTS
CONFIG_CRYPTO_ESSIV=y               # ESSIV
CONFIG_CRYPTO_MD4=y                 # MD4
CONFIG_CRYPTO_MD5=y                 # MD5
CONFIG_CRYPTO_RIPEMD160=y           # RIPEMD-160
CONFIG_CRYPTO_RIPEMD256=y           # RIPEMD-256
CONFIG_CRYPTO_RIPEMD320=y           # RIPEMD-320
CONFIG_CRYPTO_WP512=y               # Whirlpool
CONFIG_CRYPTO_CRC32=y               # CRC32
CONFIG_CRYPTO_CRC64=y               # CRC64
CONFIG_CRYPTO_TEST=y                # 加密测试
CONFIG_CRYPTO_USER_API=y            # 用户态加密 API
CONFIG_CRYPTO_USER_API_HASH=y       # 用户态哈希 API
CONFIG_CRYPTO_USER_API_SKCIPHER=y   # 用户态对称加密 API

# ---------- 内存管理 ----------
CONFIG_HUGETLBFS=y                  # 大页文件系统
CONFIG_HUGETLB_PAGE=y               # 大页支持
CONFIG_TRANSPARENT_HUGEPAGE=y       # 透明大页
CONFIG_NUMA=y                       # NUMA 支持

# ---------- 调度器 ----------
CONFIG_PREEMPT=y                    # 抢占式内核
CONFIG_SCHED_AUTOGROUP=y            # 自动任务组
CONFIG_CFQ_GROUP_IOSCHED=y          # CFQ 组 IO 调度
CONFIG_SCHED_MC=y                   # 多核调度
CONFIG_SCHED_SMT=y                  # 超线程调度

# ---------- I/O 调度 ----------
CONFIG_READAHEAD=y                  # 预读
CONFIG_BLK_DEV_IO_TRACE=y           # IO 追踪
CONFIG_BLK_DEV_THROTTLING=y         # IO 节流

# ---------- CGROUPS 容器 ----------
CONFIG_CGROUPS=y                    # Cgroups 核心
CONFIG_CGROUP_CPUACCT=y             # CPU 记账
CONFIG_CGROUP_DEVICE=y              # 设备控制
CONFIG_CGROUP_FREEZER=y             # 冻结控制
CONFIG_CGROUP_SCHED=y               # 调度控制
CONFIG_CGROUP_BPF=y                 # BPF 控制
CONFIG_CGROUP_NET_PRIO=y            # 网络优先级
CONFIG_CGROUP_NET_CLASSID=y         # 网络类 ID
CONFIG_CGROUP_PIDS=y                # PID 限制
CONFIG_CGROUP_RDMA=y                # RDMA 控制
CONFIG_CGROUP_PERF=y                # 性能控制
CONFIG_CPUSETS=y                    # CPU 集合
CONFIG_CFS_BANDWIDTH=y              # CFS 带宽
CONFIG_RT_GROUP_SCHED=y             # RT 组调度
CONFIG_BLK_CGROUP=y                 # IO Cgroup
CONFIG_NAMESPACES=y                 # 命名空间
CONFIG_USER_NS=y                    # 用户命名空间
CONFIG_PID_NS=y                     # PID 命名空间
CONFIG_NET_NS=y                     # 网络命名空间
CONFIG_IPC_NS=y                     # IPC 命名空间
CONFIG_UTS_NS=y                     # UTS 命名空间
CONFIG_TIME_NS=y                    # 时间命名空间
CONFIG_CGROUP_NS=y                  # Cgroup 命名空间

# ---------- 虚拟化/容器 ----------
CONFIG_VIRTIO=y                     # VirtIO 核心
CONFIG_VIRTIO_BLK=y                 # VirtIO 块设备
CONFIG_VIRTIO_CONSOLE=y             # VirtIO 控制台
CONFIG_VIRTIO_NET=y                 # VirtIO 网络
CONFIG_VIRTIO_BALLOON=y             # VirtIO 气球
CONFIG_VIRTIO_MMIO=y                # VirtIO MMIO
CONFIG_VIRTIO_PCI=y                 # VirtIO PCI
CONFIG_VIRTIO_PCI_LEGACY=y          # VirtIO PCI 旧版
CONFIG_VIRTIO_PCI_MODERN=y          # VirtIO PCI 新版
CONFIG_VIRTIO_INPUT=y               # VirtIO 输入
CONFIG_VIRTIO_RNG=y                 # VirtIO 随机数
CONFIG_VIRTIO_FS=y                  # VirtIO 文件系统
CONFIG_VHOST=y                      # VHost 核心
CONFIG_VHOST_NET=y                  # VHost 网络
CONFIG_VHOST_VSOCK=y                # VHost VSOCK
CONFIG_VSOCKETS=y                   # VSOCK
CONFIG_VSOCKETS_DIAG=y              # VSOCK 诊断
CONFIG_VETH=y                       # 虚拟以太网
CONFIG_KVM=y                        # KVM 虚拟化
CONFIG_PARAVIRT_DEBUG=y             # 半虚拟化调试
CONFIG_XEN=y                        # Xen 虚拟化
CONFIG_XEN_PV=y                     # Xen PV
CONFIG_HYPERV=y                     # Hyper-V
CONFIG_HYPERV_BALLOON=y             # Hyper-V 气球
CONFIG_HYPERV_NET=y                 # Hyper-V 网络
CONFIG_HYPERV_STORAGE=y             # Hyper-V 存储
CONFIG_VMWARE_BALLOON=y             # VMWare 气球
CONFIG_VMWARE_PVSCSI=y              # VMWare PVSCSI
CONFIG_VMWARE_VMXNET3=y             # VMWare VMXNET3

# ---------- 块设备/存储 ----------
CONFIG_NBD=y                        # NBD 网络块设备
CONFIG_NBD_DEV=y                    # NBD 设备
CONFIG_TARGET_CORE=y                # LIO 目标核心
CONFIG_FC=y                         # Fibre Channel
CONFIG_FCOE=y                       # FCoE
CONFIG_LIBFC=y                      # FC 库
CONFIG_NVME_FC_TRANSPORT=y          # NVMe FC 传输
CONFIG_DEV_DAX_PMEM=y               # DAX PMEM
CONFIG_DEV_DAX_KMEM=y               # DAX 内核内存
CONFIG_LIBNVDIMM=y                  # NVDIMM 库
CONFIG_ACPI_NFIT=y                  # ACPI NFIT
CONFIG_BCACHE=y                     # BCache
CONFIG_ZRAM=y                       # ZRAM 压缩内存
CONFIG_DM_CRYPT=y                   # DM-Crypt
CONFIG_DM_VERITY=y                  # DM-Verity
CONFIG_DM_THIN_PROVISIONING=y       # 精简配置
CONFIG_DM_CACHE=y                   # DM-Cache
CONFIG_DM_SNAPSHOT=y                # DM-Snapshot
CONFIG_DM_MIRROR=y                  # DM-Mirror
CONFIG_DM_RAID=y                    # DM-Raid
CONFIG_DM_MULTIPATH=y               # DM-Multipath
CONFIG_DM_LOG_WRITES=y              # DM-Log-Writes
CONFIG_DM_STRIPED=y                 # DM-Striped
CONFIG_DM_ZERO=y                    # DM-Zero
CONFIG_DM_FLAKEY=y                  # DM-Flakey
CONFIG_MD=y                         # RAID 核心
CONFIG_MD_RAID0=y                   # RAID0
CONFIG_MD_RAID1=y                   # RAID1
CONFIG_MD_RAID10=y                  # RAID10
CONFIG_MD_RAID456=y                 # RAID4/5/6
CONFIG_MTD=y                        # 内存技术设备
CONFIG_MTD_BLOCK=y                  # MTD 块设备
CONFIG_MTD_CFI=y                    # CFI flash
CONFIG_MTD_NAND=y                   # NAND flash

# ---------- SCSI 目标 ----------
CONFIG_FUSION=y                     # Fusion MPT
CONFIG_FUSION_SAS=y                 # Fusion SAS

# ---------- 音频 ----------
CONFIG_SND=y                        # 音频核心
CONFIG_SND_HDA_INTEL=y              # Intel HD Audio
CONFIG_SND_HDA_CODEC_HDMI=y         # HDMI 音频
CONFIG_SND_HDA_CODEC_ANALOG=y       # 模拟音频
CONFIG_SND_HDA_CODEC_REALTEK=y      # Realtek 音频
CONFIG_SND_HDA_CODEC_CA0110=y       # CA0110 音频
CONFIG_SND_HDA_CODEC_CA0132=y       # CA0132 音频
CONFIG_SND_HDA_CODEC_CMEDIA=y       # C-Media 音频
CONFIG_SND_HDA_CODEC_CIRRUS=y       # Cirrus 音频
CONFIG_SND_HDA_CODEC_SIGMATEL=y     # SigmaTel 音频
CONFIG_SND_USB_AUDIO=y              # USB 音频
CONFIG_SND_SOC=y                    # ALSA SoC
CONFIG_SND_SOC_AMD=y                # AMD SoC 音频
CONFIG_SND_SOC_INTEL=y              # Intel SoC 音频
CONFIG_SND_SOC_ROCKCHIP=y           # Rockchip SoC 音频
CONFIG_SND_SOC_TEGRA=y              # Tegra SoC 音频
CONFIG_SND_SOC_BCM=y                # Broadcom SoC 音频
CONFIG_SND_PCI=y                    # PCI 音频
CONFIG_SND_PCI_AC97=y               # AC97 音频

# ---------- GPIO ----------
CONFIG_GPIO=y                       # GPIO 核心
CONFIG_GPIO_SYSFS=y                 # GPIO sysfs
CONFIG_GPIO_AGGREGATOR=y            # GPIO 聚合器
CONFIG_GPIO_PCA953X=y               # PCA953X GPIO
CONFIG_GPIO_PCF857X=y               # PCF857X GPIO
CONFIG_GPIO_MAX732X=y               # MAX732X GPIO

# ---------- I2C/SPI ----------
CONFIG_I2C_GPIO=y                   # GPIO I2C
CONFIG_I2C_SLAVE=y                  # I2C 从设备
CONFIG_SPI=y                        # SPI 核心
CONFIG_SPI_MASTER=y                 # SPI 主控制器
CONFIG_SPI_GPIO=y                   # GPIO SPI
CONFIG_SPI_BCM2835=y                # BCM2835 SPI

# ---------- PWM ----------
CONFIG_PWM=y                        # PWM 核心
CONFIG_PWM_SYSFS=y                  # PWM sysfs

# ---------- 看门狗 ----------
CONFIG_WATCHDOG=y                   # 看门狗核心
CONFIG_WATCHDOG_GPIO=y              # GPIO 看门狗

# ---------- 随机数 ----------
CONFIG_HW_RANDOM=y                  # 硬件随机数
CONFIG_HW_RANDOM_TPM=y              # TPM 随机数

# ---------- 电源管理 ----------
CONFIG_ACPI=y                       # ACPI
CONFIG_ACPI_BATTERY=y               # ACPI 电池
CONFIG_ACPI_AC=y                    # ACPI 电源适配器
CONFIG_ACPI_FAN=y                   # ACPI 风扇
CONFIG_ACPI_THERMAL=y               # ACPI 热管理
CONFIG_ACPI_CPUFREQ=y               # ACPI CPU 频率
CONFIG_CPU_FREQ=y                   # CPU 频率
CONFIG_CPU_FREQ_STAT=y              # CPU 频率统计
CONFIG_CPU_FREQ_GOV_USERSPACE=y     # 用户态调控器
CONFIG_CPU_FREQ_GOV_ONDEMAND=y      # OnDemand 调控器
CONFIG_CPU_FREQ_GOV_CONSERVATIVE=y  # Conservative 调控器
CONFIG_CPU_IDLE=y                   # CPU 空闲
CONFIG_CPU_IDLE_GOV_MENU=y          # Menu 空闲调控器
CONFIG_ENERGY_MODEL=y               # 能源模型
CONFIG_ENERGY_AWARE=y               # 能源感知
CONFIG_CPU_THERMAL=y                # CPU 热管理
CONFIG_THERMAL=y                    # 热管理核心
CONFIG_THERMAL_WRITABLE_TRIPS=y     # 可写热阈
CONFIG_PM=y                         # 电源管理
CONFIG_PM_SLEEP=y                   # PM 睡眠
CONFIG_PM_RUNTIME=y                 # PM 运行时
CONFIG_SUSPEND=y                    # 挂起
CONFIG_HIBERNATION=y                # 休眠
CONFIG_CPU_PM=y                     # CPU 电源管理
CONFIG_CLOCKSOURCE_WATCHDOG=y       # 时钟源看门狗
CONFIG_POWER_SUPPLY=y               # 电源供应
CONFIG_BATTERY=y                    # 电池
CONFIG_CHARGER=y                    # 充电器
CONFIG_SENSORS=y                    # 传感器

# ---------- ARM 特有 ----------
CONFIG_ARM_CPUIDLE=y                # ARM CPU 空闲
CONFIG_ARM_PSCI=y                   # ARM PSCI
CONFIG_ARM_PSCI_CPUIDLE=y           # ARM PSCI 空闲
CONFIG_ARCH_ROCKCHIP=y              # Rockchip SoC
CONFIG_ARCH_SUNXI=y                 # Allwinner SoC
CONFIG_ARCH_TEGRA=y                 # NVIDIA Tegra
CONFIG_ARCH_ZYNQ=y                  # Xilinx Zynq
CONFIG_OF=y                         # 设备树
CONFIG_OF_ADDRESS=y                 # 设备树地址
CONFIG_OF_IRQ=y                     # 设备树 IRQ
CONFIG_OF_GPIO=y                    # 设备树 GPIO
CONFIG_OF_I2C=y                     # 设备树 I2C
CONFIG_OF_SPI=y                     # 设备树 SPI
CONFIG_OF_NET=y                     # 设备树网络
CONFIG_OF_MDIO=y                    # 设备树 MDIO
CONFIG_OF_RESERVED_MEM=y            # 设备树保留内存

# ---------- 串口/控制台 ----------
CONFIG_TTY=y                        # TTY 核心
CONFIG_SERIAL_8250_DMA=y            # 8250 DMA
CONFIG_SERIAL_8250_MANY_PORT=y      # 多 8250 端口
CONFIG_SERIAL_IMX=y                 # i.MX 串口
CONFIG_SERIAL_TEGRA=y               # Tegra 串口
CONFIG_SERIAL_MSM=y                 # MSM 串口
CONFIG_SERIAL_AMBA_PL011=y          # AMBA PL011
CONFIG_SERIAL_AMBA_PL011_CONSOLE=y  # PL011 控制台
CONFIG_BOOT_CONFIG_BOOL=y           # 启动配置

# ---------- 性能监控 ----------
CONFIG_PERF_EVENTS=y                # 性能事件
CONFIG_PERF_EVENTS_INTEL_UNCORE=y   # Intel Uncore
CONFIG_PERF_EVENTS_INTEL_RAPL=y     # Intel RAPL
CONFIG_PERF_EVENTS_INTEL_CSTATE=y   # Intel C-state
CONFIG_PERF_EVENTS_AMD_POWER=y      # AMD 电源

# ---------- 跟踪/调试 ----------
CONFIG_TRACEPOINTS=y                # 跟踪点
CONFIG_HAVE_SYSTEM_TRACING=y        # 系统跟踪
CONFIG_FUNCTION_GRAPH_TRACER=y      # 函数图跟踪
CONFIG_IRQSOFF_TRACER=y             # IRQ 关闭跟踪
CONFIG_PREEMPT_TRACER=y             # 抢占跟踪
CONFIG_SCHED_TRACER=y               # 调度跟踪
CONFIG_MMIOTRACE=y                  # MMIO 跟踪
CONFIG_KPROBE_EVENT=y               # Kprobe 事件
CONFIG_UPROBE_EVENT=y               # Uprobe 事件
CONFIG_DYNAMIC_FTRACE=y             # 动态 ftrace
CONFIG_FUNCTION_PROFILER=y          # 函数分析
CONFIG_STACK_TRACER=y               # 栈跟踪
CONFIG_TRACE_BRANCH_PROFILING=y     # 分支分析
CONFIG_FTRACE=y                     # ftrace
CONFIG_FUNCTION_TRACER=y            # 函数跟踪
CONFIG_KGDB=y                       # KGDB 调试
CONFIG_KGDB_SERIAL_CONSOLE=y        # KGDB 串口控制台
CONFIG_KPROBES=y                    # Kprobes
CONFIG_CRASH_DUMP=y                 # Crash Dump
CONFIG_DEBUG_FS=y                   # debugfs
CONFIG_LATENCYTOP=y                 # 延迟分析
CONFIG_DEBUG_PREEMPT=y              # 抢占调试
CONFIG_DEBUG_KERNEL=y               # 内核调试
CONFIG_DEBUG_INFO=y                 # 调试信息
CONFIG_DEBUG_INFO_DWARF5=y          # DWARF5 调试信息
CONFIG_DEBUG_VM=y                   # VM 调试
CONFIG_DEBUG_PAGE_ALLOC=y           # 页面分配调试
CONFIG_DEBUG_BUGVERBOSE=y           # BUG 详细
CONFIG_DEBUG_WX=y                   # W+X 内存调试
CONFIG_DEBUG_KMEMLEAK=y             # 内存泄漏检测
CONFIG_DEBUG_OBJECTS=y              # 对象调试
CONFIG_DEBUG_LIST=y                 # 链表调试
CONFIG_DEBUG_SPINLOCK=y             # 自旋锁调试
CONFIG_DEBUG_MUTEXES=y              # 互斥锁调试
CONFIG_DEBUG_ATOMIC_SLEEP=y         # 原子睡眠调试
CONFIG_LOCKUP_DETECTOR=y            # 锁检测
CONFIG_HARDLOCKUP_DETECTOR=y        # 硬锁检测
CONFIG_KALLSYMS=y                   # 符号表
CONFIG_KALLSYMS_ALL=y               # 所有符号
CONFIG_PROC_VMCORE=y                # /proc/vmcore
CONFIG_HAVE_SYSTEM_TRACING=y        # 系统跟踪

# ---------- 打印/扫描 ----------
CONFIG_PRINTER=y                    # 打印机
CONFIG_USB_PRINTER=y                # USB 打印机
CONFIG_IPP=y                        # IPP 协议
CONFIG_RADIO_ADAPTERS=y             # 无线电适配器

# ---------- 多媒体 ----------
CONFIG_V4L2=y                       # V4L2 核心
CONFIG_VIDEO_DEV=y                  # 视频设备
CONFIG_VIDEO_V4L2=y                 # V4L2
CONFIG_V4L2_MEM2MEM=y               # V4L2 内存到内存
CONFIG_V4L2_FWNODE=y                # V4L2 固件节点
CONFIG_MEDIA_CONTROLLER=y           # 媒体控制器
CONFIG_MEDIA_SUPPORT=y              # 媒体支持
CONFIG_MEDIA_USB_SUPPORT=y          # USB 媒体
CONFIG_USB_VIDEO_CLASS=y            # USB 视频类
CONFIG_USB_GSPCA=y                  # GSPCA 摄像头
CONFIG_DVB_CORE=y                   # DVB 核心
CONFIG_DVB_USB=y                    # DVB USB
CONFIG_VIDEOBUF2_V4L2=y             # videobuf2 V4L2
CONFIG_VIDEOBUF2_DMA_CONTIG=y       # DMA 连续
CONFIG_VIDEOBUF2_VMALLOC=y          # vmalloc

# ---------- CPU/SoC 架构 ----------
CONFIG_64BIT=y                      # 64 位 (x86_64/arm64/riscv64/ppc64/mips64)
CONFIG_X86_64=y                     # x86_64
CONFIG_X86_32=y                     # x86_32
CONFIG_ARM64=y                      # ARM64
CONFIG_ARM=y                        # ARM32
CONFIG_RISCV=y                      # RISC-V
CONFIG_RISCV_ISA_C=y                # RISC-V C 扩展
CONFIG_PPC64=y                      # PowerPC 64
CONFIG_PPC64LE=y                    # PowerPC 64le
CONFIG_CPU_LITTLE_ENDIAN=y          # 小端
CONFIG_PPC_POWERNV=y                # PowerNV
CONFIG_PPC_OF_BOOT_TRAMPOLINE=y     # PPC OF 引导
CONFIG_PPC_VAS=y                    # PPC VAS
CONFIG_MIPS=y                       # MIPS
CONFIG_MIPS32_O32=y                 # MIPS O32 ABI
CONFIG_MIPS32_N32=y                 # MIPS N32 ABI
CONFIG_CPU_MIPS64_R2=y              # MIPS64 R2

# ---------- EFI ----------
CONFIG_EFI=y                        # EFI 支持
CONFIG_EFI_STUB=y                   # EFI Stub

# ---------- 半虚拟化 ----------
CONFIG_PARAVIRT=y                   # 半虚拟化 (x86)
CONFIG_KVM_GUEST=y                  # KVM Guest (x86)
CONFIG_HYPERVISOR_GUEST=y           # Hypervisor Guest

# ---------- 杂项 ----------
CONFIG_SYSVIPC=y                    # System V IPC
CONFIG_SYSVIPC_SYSCTL=y             # System V IPC sysctl
CONFIG_POSIX_MQUEUE=y               # POSIX 消息队列
CONFIG_FUTEX=y                      # Futex
CONFIG_EPOLL=y                      # Epoll
CONFIG_SIGNALFD=y                   # Signalfd
CONFIG_TIMERFD=y                    # Timerfd
CONFIG_EVENTFD=y                    # Eventfd
CONFIG_UNIX98_PTYS=y                # Unix98 PTY
CONFIG_DEVPTS_MULTIPLE_INSTANCES=y  # 多 devpts 实例
