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

容器/虚拟化（20+ 项）

这些配置在 make defconfig 之后追加到 .config，确保一次编译覆盖绝大多数使用场景。
