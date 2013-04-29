# vim: et:ts=4:sw=4
# Copyright (C) 2013 Pier Luigi Fiorini <pierluigi.fiorini@gmail.com>
# Copyright (C) 2012-2013 Colin Walters <walters@verbum.org>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# Boston, MA 02111-1307, USA.

import os, re, shutil
from gi.repository import GLib
import __builtin__

from .guestfish import GuestFish, GuestMount
from .logger import Logger
from .subprocess_helpers import run_sync, run_async
from .fileutil import find_program_in_path

DEFAULT_GF_PARTITION_OPTS = ['-m', '/dev/sda3', '-m', '/dev/sda1:/boot']
DEFAULT_QEMU_OPTS = ['-vga', 'std', '-m', '768M',
                     '-usb', '-usbdevice', 'tablet',
                     '-smp', '1,sockets=1,cores=1,threads=1']

def new_read_write_mount(diskpath):
    mntdir = "mnt"
    if not os.path.exist(mntdir):
        os.makedirs(mntdir, 0755)
    gfmnt = GuestMount(diskpath, partition_opts=DEFAULT_GF_PARTITION_OPTS,
                                 read_write=True)
    gfmnt.mount(mntdir)
    return (gfmnt, mntdir)

def create_disk(diskpath, osname):
    logger = Logger()

    size_mb = 8 * 1024
    bootsize_mb = 200
    swapsize_mb = 64

    run_sync(["qemu-img", "create", "-f", "qcow2", diskpath, "%iM" % size_mb])

    make_disk_cmd = """launch
part-init /dev/sda mbr
blockdev-getsize64 /dev/sda
blockdev-getss /dev/sda
"""
    gf = GuestFish(diskpath, partition_opts=[], read_write=True)
    lines = gf.run(make_disk_cmd)
    if len(lines) != 2:
        logger.fatal("guestfish returned unexpected output lines (%d, expected 2)" % len(lines))
    disk_bytesize = int(lines[0])
    disk_sectorsize = int(lines[1])
    logger.debug("bytesize: %d sectorsize: %d" % (disk_bytesize, disk_sectorsize))

    bootsize_sectors = bootsize_mb * 1024 / disk_sectorsize * 1024
    swapsize_sectors = swapsize_mb * 1024 / disk_sectorsize * 1024
    rootsize_sectors = disk_bytesize / disk_sectorsize - bootsize_sectors - swapsize_sectors - 64
    boot_offset = 64
    swap_offset = boot_offset + bootsize_sectors
    root_offset = swap_offset + swapsize_sectors
    end_offset = root_offset + rootsize_sectors

    partconfig = """launch
part-add /dev/sda p %d %d
part-add /dev/sda p %d %d
part-add /dev/sda p %d %d
part-set-bootable /dev/sda 1 true
mkfs ext4 /dev/sda1
set-e2label /dev/sda1 %s-boot
mkswap-L %s-swap /dev/sda2
mkfs ext4 /dev/sda3
set-e2label /dev/sda3 %s-root
mount /dev/sda3 /
mkdir /boot
""" % (boot_offset, swap_offset - 1, swap_offset, root_offset - 1, root_offset, end_offset - 1, osname, osname, osname)
    logger.debug("Partition config: %s" % partconfig.rstrip())
    gf.run(partconfig)

def create_disk_snapshot(diskpath, newdiskpath):
    run_sync(["qemu-img", "create", "-f", "qcow2", "-o", "backing_file=" + diskpath, newdiskpath])

def copy_disk(srcpath, destpath):
    run_sync(["qemu-img", "convert", "-O", "qcow2", srcpath, destpath])

def get_qemu_path():
    logger = Logger()
    fallback_paths = ["/usr/libexec/qemu-kvm"]
    qemu_path_string = find_program_in_path("qemu-kvm")
    if not qemu_path_string:
        qemu_path_string = find_program_in_path("kvm")
    if not qemu_path_string:
        for path in fallback_paths:
            if not os.path.exist(path):
                continue
            qemu_path_string = path
    if not qemu_path_string:
        logger.fatal("Unable to find qemu-kvm")
    return qemu_path_string

def get_deploy_dirs(mntdir, osname):
    basedir = os.path.join(mntdir, "ostree", "deploy", osname)
    return [os.path.join(basedir, "current"), os.path.join(basedir, "current-etc")]

def modify_bootloader_append_kernel_args(mntdir, kernel_args):
    conf_path = os.path.join(mntdir, "boot", "syslinux", "syslinux.cfg")
    conf = open(conf_path, "r")
    lines = conf.read().split("\n")
    conf.close()

    modified_lines = []
    kernel_arg = " ".join(kernel_args)
    kernel_line_re = re.compile(r'APPEND \/')
    for line in lines:
        if kernel_line_re.match(line):
            modified_lines.append(line + " " + kernel_arg)
        else:
            modified_lines.append(line)

    modified_conf = modified_lines.join("\n")
    conf = open(conf_path, "w")
    conf.write(modified_conf)
    conf.close()

def get_multiuser_wants_dir(current_etc_dir):
    return os.path.join(current_etc_dir, "systemd", "system", "multi-user.target.wants")

def get_datadir():
    return __builtin__.__dict__["DATADIR"]

def inject_export_journal(current_dir, current_etc_dir):
    bin_dir = os.path.join(current_dir, "usr", "bin")
    multiuser_wants_dir = get_multiuser_wants_dir(current_etc_dir)
    datadir = get_datadir()
    export_script = os.path.join(datadir, "tests", "mauibuild-export-journal-to-serialdev")
    export_script_service = os.path.join(datadir, "tests", "mauibuild-export-journal-to-serialdev.service")
    export_bin = os.path.join(bin_dir, os.path.basename(export_script))
    shutil.copy_file(export_script, export_bin)
    os.chmod(export_bin, 493)
    shutil.copy_file(export_script_service, os.path.join(multiuser_wants_dir, os.path.basename(export_script_service)))

def inject_test_user_creation(current_dir, current_etc_dir, username, password=None):
    if password:
        exec_line = "/bin/sh -c \"/usr/sbin/useradd %s; echo %s | passwd --stdin %s\"" % (username, password, username)
    else:
        exec_line = "/bin/sh -c \"/usr/sbin/useradd %s; passwd -d %s\"" % (username, username)

    add_user_service = """[Unit]
Description=Add user %s
Before=sddm.service

[Service]
ExecStart=%s
Type=oneshot
""" % (username, exec_line)
    add_user_service_path = os.path.join(get_multiuser_wants_dir(current_etc_dir), osname + "-add-user-" + username + ".service")
    add_user_service_file = open(add_user_service_path, "w")
    add_user_service_file.write(add_user_service)
    add_user_service_file.close()

def enable_autologin(current_dir, current_etc_dir, username):
    # FIXME: Login Manager currently doesn't handle autologin settings
    #        so this code might need to be changed
    import ConfigParser
    config_path = os.path.abspath(os.path.join(current_etc_dir, "xdg", "hawaii", "org.hawaii.login-manager"))
    config = ConfigParser.ConfigParser()
    config.readfp(open(config_path, "r"))
    config.add_section("daemon")
    config.set("daemon", "autologin-enable", "true")
    config.set("daemon", "autologin-username", username)
    config_file = open(config_path, "w")
    config.write(config_file)
    config_file.close()

def _find_current_kernel(mntdir, osname):
    logger = Logger()
    deploy_bootdir = os.path.join(mntdir, "ostree", "deploy", osname, "current", "boot")
    for item in os.listdir(deploy_bootdir):
        child = os.path.join(deploy_bootdir, item)
        if os.path.basename(child).startswith("vmlinuz-"):
            return child
    logger.fatal("Couldn't find vmlinuz- in %s" % deploy_bootdir)

def _parse_kernel_release(kernel_path):
    logger = Logger()
    name = os.path.basename(kernel_path)
    index = name.find("-")
    if index == -1:
        logger.fatal("Invalid kernel name %s" % kernel_path)
    return name[index+1:]

def _get_initramfs_path(mntdir, kernel_release):
    logger = Logger()
    bootdir = os.path.join(mntdir, "boot")
    initramfs_name = "initramfs-%s.img" % kernel_release
    path = os.path.join(bootdir, "ostree", initramfs_name)
    if not os.path.exists(path):
        logger.fatal("Couldn't find initramfs %s" % path)
    return path

def pull_deploy(mntdir, srcrepo, osname, target, revision):
    import copy

    logger = Logger()

    bootdir = os.path.join(mntdir, "boot")
    ostreedir = os.path.join(mntdir, "ostree")
    ostree_osdir = os.path.join(ostreedir, "deploy", osname)

    admin_args = ["ostree", "admin", "--ostree-dir=" + ostreedir, "--boot-dir=" + bootdir]

    env_copy = os.environ.copy()
    env_copy["LIBGSYSTEM_ENABLE_GUESTFS_FUSE_WORKAROUND"] = "1"

    procdir = os.path.join(mntdir, "proc")
    if not os.path.exists(procdir):
        args = copy.copy(admin_args)
        args.extend(["init-fs", mntdir])
        run_sync(args, env=env_copy)

    # *** NOTE ***
    # Here we blow away any current deployment.  This is pretty lame, but it
    # avoids us triggering a variety of guestfs/FUSE bugs =(
    # See: https://bugzilla.redhat.com/show_bug.cgi?id=892834
    #
    # But regardless, it's probably useful if every
    # deployment starts clean, and callers can use libguestfs
    # to crack the FS open afterwards and modify config files
    # or the like.
    if os.path.exists(ostree_osdir):
        shutil.rmtree(ostree_osdir)

    if revision:
        rev_or_target = revision
    else:
        rev_or_target = target

    args = copy.copy(admin_args)
    args.extend(["os-init", osname])
    run_sync(args, env=env_copy)

    run_sync(["ostree", "--repo=" + os.path.join(ostreedir, "repo"), "pull-local",
              srcrepo, rev_or_target], env=env_copy)

    args = copy.copy(admin_args)
    args.extend(["deploy", "--no-kernel", osname, target, rev_or_target])
    run_sync(args, env=env_copy)

    args = copy.copy(admin_args)
    args.extend(["update-kernel", "--no-bootloader", osname])
    run_sync(args, env=env_copy)

    args = copy.copy(admin_args)
    args.extend(["prune", osname])
    run_sync(args, env=env_copy)

def configure_bootloader(mntdir, osname):
    logger = Logger()

    boot_dir = os.path.join(mntdir, "boot")
    ostree_dir = os.path.join(mntdir, "ostree")

    default_fstab = """LABEL=%s-root / ext4 defaults 1 1
LABEL=%s-boot /boot ext4 defaults 1 2
LABEL=%s-swap swap swap defaults 0 0
""" % (osname, osname, osname)
    fstab_path = os.path.join(ostree_dir, "deploy", osname, "current-etc", "fstab")
    f = open(fstab_path, "w")
    f.write("")
    f.close()

    deploy_kernel_path = _find_current_kernel(mntdir, osname)
    boot_kernel_path = os.path.join(boot_dir, "ostree", os.path.basename(deploy_kernel_path))
    if not os.path.exists(boot_kernel_path):
        logger.fatal("%s doesn't exist" % boot_kernel_path)
    kernel_release = _parse_kernel_release(deploy_kernel_path)
    initramfs_path = _get_initramfs_path(mntdir, kernel_release)

    boot_relative_kernel_path = os.path.relpath(boot_kernel_path, bootdir)
    boot_relative_initramfs_path = os.path.relpath(initramfs_path, bootdir)

    syslinux_dir = os.path.join(mntdir, "boot", "syslinux")
    fileutil.ensure_dir(syslinux_dir)
    conf_path = os.path.join(syslinux_dir, "syslinux.cfg")
    conf = """PROMPT 1
TIMEOUT 50
DEFAULT %s

LABEL %s
    LINUX /%s
    APPEND root=LABEL=%s-root rw quiet splash ostree=%s/current
    INITRD /%s
""" % (osname, osname, boot_relative_kernel_path, osname, osname, boot_relative_initramfs_path)
    conf_file = open(conf_path, "w")
    conf_file.write(conf)
    conf_file.close()

def bootload_install(diskpath, workdir, osname):
    logger = Logger()

    qemu_args = [get_qemu_path(),] + DEFAULT_QEMU_OPTS

    tmp_kernel_path = os.path.join(workdir, "kernel.img")
    tmp_initrd_path = os.path.join(workdir, "initrd.img")

    (gfmnt, mntdir) = new_read_write_mount(diskpath)
    try:
        (current_dir, current_etc_dir) = get_deploy_dirs(mntdir, osname)

        inject_export_journal(current_dir, current_etc_dir)

        kernel_path = _find_current_kernel(mntdir, osname)
        kernel_release = _parse_kernel_release(kernel_path)
        initrd_path = _get_initramfs_path(mntdir)

        shutil.copy2(kernel_path, tmp_kernel_path)
        shutil.copy2(initrd_path, tmp_initrd_path)
    finally:
        gfmnt.umount()

    console_output = os.path.join(workdir, "bootloader-console.out")
    journal_output = os.path.join(workdir, "bootloader-journal-json.txt")

    qemu_args += ["-drive", "file=" + diskpath + ",if=virtio",
        "-vnc", "none",
        "-serial", "file:" + console_output,
        "-chardev", "socket,id=charmonitor,path=qemu.monitor,server,nowait",
        "-mon", "chardev=charmonitor,id=monitor,mode=control",
        "-device", "virtio-serial",
        "-chardev", "file,id=journaljson,path=" + journal_output,
        "-device", "virtserialport,chardev=journaljson,name=org.maui.journaljson",
        "-kernel", tmp_kernel_path,
        "-initrd", tmp_initrd_path,
        "-append", "console=ttyS0 root=LABEL=" + osname + "-root rw ostree=" + osname + "/current systemd.unit=" + osname + "-install-bootloader.target"
    ]
    proc = run_async(qemu_args, cwd=workdir)
    logger.debug("waiting for pid %d" % proc.pid)
    def on_child_exited(pid, exitcode):
        os.unlink(tmp_kernel_path)
        os.unlink(tmp_initrd_path)
        if exitcode != 0:
            logger.error("Couldn't install bootloader through qemu, error code: %d" % exitcode)
    GLib.child_watch_add(proc.pid, on_child_exited)