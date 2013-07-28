mauibuild
=========

This is the Maui build system.

It takes care of building the Yocto base system and build all the
components specified by a manifest JSON file into their own tree.

The Maui Wiki has a much more detailed documentation about the [build procedure](http://wiki.maui-project.org/System/Build).

## Prerequisites

Maui base system is based on [Poky 8.0 (danny)](https://www.yoctoproject.org/download/yocto-project-13-poky-80),
install the **Essential** packages as explained in the [Required Packages for the Host Development System](http://www.yoctoproject.org/docs/1.3/poky-ref-manual/poky-ref-manual.html#required-packages-for-the-host-development-system) section of the reference manual before preceding.

You can also read the [quick start](https://www.yoctoproject.org/docs/current/yocto-project-qs/yocto-project-qs.html) guide to learn more about Yocto.

Also install the following packages:

 * autoconf
 * automake
 * python
 * python-gi
 * fontconfig
 * elfutils

If you build disk images you will also need:

 * guestfish
 * guestfsd
 * guestmount
 * libguestfs-tools

To make live images install:

 * squashfs-tools
 * xorriso

To build the man pages on Debian and Ubuntu:

 * xlstproc
 * docbook
 * docbook-xml
 * docbook-xsl

To build the man pages on Fedora:

 * xsltproc
 * docbook-utils
 * docbook-style-xsl

A 64-bit host operating system is required.

You also need:

 * Linux 2.6.28 or newer
 * *linux-user-chroot* and *ostree*, follow the next sections for more information
 * *gummiboot* to make `x86_64` live images, follow the next sections for more information

### Disable colored output

Output is colored by default.

To turn colors type this command before running *mauibuild*:

```sh
export ANSI_COLORS_DISABLED=1
```

### Setup guestfs on Ubuntu

To build disk images on Ubuntu you will need to make a symbolic link to the right libguestfs path:

```sh
sudo ln -s /usr/lib/guestfs /usr/lib/x86_64-linux-gnu/guestfs
```

This was tested on Ubuntu 12.10 only, it might be different in another release.

### Configure FUSE

If you run `mauibuld` with an unprivileged user (i.e. not root) and you want to build disk images,
your user must be in the *fuse* group and FUSE must be configured to allow non-root users to
specify the *allow_other* or *allow_root* mount options.

To add the currently logged-in user to the *fuse* group on Debian and Ubuntu systems:

```sh
sudo adduser $USER fuse
```

Now edit */etc/fuse.conf* and uncomment `user_allow_other`.

### Download and install linux-user-chroot

Install the following additional packages:

 * libtool

Here's how you download and install *linux-user-chroot*:

```sh
mkdir -p ~/git
cd ~/git
git clone git://git.gnome.org/linux-user-chroot
cd linux-user-chroot
./autogen.sh --prefix=/usr --enable-newnet-helper
make
sudo make install
sudo chmod +s /usr/bin/linux-user-chroot{,-newnet}
```

### Download and install ostree

Install the following additional packages, on Debian and Ubuntu:

 * zlib1g-dev
 * libarchive-dev
 * libattr1-dev
 * libglib2.0-dev
 * libsoup2.4-dev
 * xsltproc
 * gtk-doc-tools

Or if you are on Fedora:

 * zlib-devel
 * libarchive-devel
 * libattr-devel
 * glib2-devel
 * libsoup-devel
 * xsltproc
 * gtk-doc-tools

Here's how you download and install *ostree*:

```sh
mkdir -p ~/git
cd ~/git
git clone git://git.gnome.org/ostree
cd ostree
git submodule init
git submodule update
./autogen.sh --prefix=/usr --with-libarchive --enable-documentation --enable-kernel-updates --enable-grub2-hook
make
sudo make install
sudo mkdir /ostree
```

### Download and install gummiboot

If you distro has gummiboot packaged, install the package.

Otherwise, if you distro doesn't package gummiboot, here's how to build it.

gummiboot requires GNU Efi, unless you can install a package here's how to build it from sources:

```sh
mkdir -p ~/git
cd ~/git
git clone git://git.code.sf.net/p/gnu-efi/code gnu-efi-code
cd gnu-efi-code
cd gnu-efi-3.0
make
sudo make install PREFIX=/usr
```

gummiboot also requires the following packages on Debian and Ubuntu:

 * libblkid-dev

Or if you are on Fedora:

 * libblkid-devel

Build gummiboot:

```sh
mkdir -p ~/git
cd ~/git
git clone git://anongit.freedesktop.org/gummiboot
cd gummiboot
./autogen.sh c
make
sudo make install
```

## Download the manifest

Create a directory and checkout the *maui* repository.
Here's an example:

```sh
mkdir ~/git
cd ~/git
git clone git://github.com/mauios/maui.git
```

## Install mauibuild

From the *mauibuild* checkout directory type:

```sh
./autogen.sh --enable-maintainer-mode
make
sudo make install
```

## Configure mauibuild

```sh
mkdir -p ~/mauibuildwork
cd ~/mauibuildwork
ln -s ~/git/maui/manifest.json
```

Now resolve the components and build:

```sh
mauibuild make -n resolve
```

Tasks are chained, so after a resolve a build will automatically be executed
if at least one component changed since the previous resolve.

Every time the manifest file changes you have to type the above command.
