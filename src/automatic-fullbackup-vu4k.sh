#!/bin/sh
#

VERSION="vu4k/dmm4k/gigablue4k/lunix4k models- 14/04/2019\ncreator of the script Dimitrij (http://forums.openpli.org)\n"
DIRECTORY="$1"
START=$(date +%s)
DATE=`date +%Y%m%d_%H%M`
IMAGEVERSION=`date +%Y%m%d`
MKFS=/bin/tar
BZIP2=/usr/bin/bzip2
ROOTFSTYPE="rootfs.tar.bz2"
WORKDIR="$DIRECTORY/bi"

getaddr() {
	python - $1 $2<<-"EOF"
		from sys import argv
		filename = argv[1]
		address = int(argv[2])
		fh = open(filename,'rb')
		header = fh.read(2048)
		fh.close()
		print "%d" % ( (ord(header[address+2]) <<16 ) | (ord(header[address+1]) << 8) |  ord(header[address]) )
	EOF
}

if [ -f /etc/issue ] ; then
	ISSUE=`cat /etc/issue | grep . | tail -n 1 | sed -e 's/[\t ]//g;/^$/d'`
	IMVER=${ISSUE%?????}
elif [ -f /etc/bhversion ] ; then
	ISSUE=`cat /etc/bhversion | grep . | tail -n 1 | sed -e 's/[\t ]//g;/^$/d'`
	IMVER=${ISSUE%?????}
elif [ -f /etc/vtiversion.info ] ; then
	ISSUE=`cat /etc/vtiversion.info | grep . | tail -n 1 | sed -e 's/[\t ]//g;/^$/d'`
	IMVER=${ISSUE%?????}
elif [ -f /proc/stb/info/vumodel ] && [ -f /etc/version ] ; then
	ISSUE=`cat /etc/version | grep . | tail -n 1 | sed -e 's/[\t ]//g;/^$/d'`
	IMVER=${ISSUE%?????}
else
	IMVER="unknown"
fi

echo "Script date = $VERSION\n"
echo "Back-up media = $DIRECTORY\n"
df -h "$DIRECTORY"
echo "Back-up date_time = $DATE\n"
echo "Working directory = $WORKDIR\n"
echo -n "Drivers = "
opkg list-installed | grep dvb-proxy
opkg list-installed | grep dvb-modules
opkg list-installed | grep gigablue-platform-util
CREATE_ZIP="$2"
IMAGENAME="$3"

if [ -f /proc/stb/info/vumodel ] && [ ! -f /proc/stb/info/hwmodel ] && [ ! -f /proc/stb/info/gbmodel ] ; then
	MODEL=$( cat /proc/stb/info/vumodel )
	if [ $MODEL = "solo4k" ] ; then
		echo "Found VU+ Solo 4K\n"
		MTD_KERNEL="mmcblk0p1"
		KERNELNAME="kernel_auto.bin"
	elif [ $MODEL = "uno4k" ] ; then
		echo "Found VU+ Uno 4K\n"
		MTD_KERNEL="mmcblk0p1"
		KERNELNAME="kernel_auto.bin"
	elif [ $MODEL = "uno4kse" ] ; then
		echo "Found VU+ Uno 4K se\n"
		MTD_KERNEL="mmcblk0p1"
		KERNELNAME="kernel_auto.bin"
	elif [ $MODEL = "ultimo4k" ] ; then
		echo "Found VU+ Ultimo 4K\n"
		MTD_KERNEL="mmcblk0p1"
		KERNELNAME="kernel_auto.bin"
	elif [ $MODEL = "zero4k" ] ; then
		echo "Found VU+ Zero 4K\n"
		MTD_KERNEL="mmcblk0p4"
		KERNELNAME="kernel_auto.bin"
	elif [ $MODEL = "duo4k" ] ; then
		echo "Found VU+ Duo 4K\n"
		MTD_KERNEL="mmcblk0p6"
		KERNELNAME="kernel_auto.bin"
	elif [ $MODEL = "duo4kse" ] ; then
		echo "Found VU+ Duo 4K SE\n"
		MTD_KERNEL="mmcblk0p6"
		KERNELNAME="kernel_auto.bin"
	else
		echo "No supported receiver found!\n"
		exit 0
	fi
	TYPE=VU
	SHOWNAME="Vu+ $MODEL"
	MAINDEST="$DIRECTORY/vuplus/$MODEL"
	EXTRA="$DIRECTORY/automatic_fullbackup/$DATE/vuplus"
	echo "Destination        = $MAINDEST\n"
elif [ -f /proc/stb/info/hwmodel ] && [ ! -f /proc/stb/info/gbmodel ]; then
	MODEL=$( cat /proc/stb/info/hwmodel )
	if [ $MODEL = "lunix3-4k" ] ; then
		echo "Found Qviart lunix3 4K\n"
		MTD_KERNEL="mmcblk0p1"
		KERNELNAME="oe_kernel.bin"
		TYPE=QVIART
		SHOWNAME="Qviart $MODEL"
		MAINDEST="$DIRECTORY/update/$MODEL"
		EXTRA="$DIRECTORY/automatic_fullbackup/$DATE/update"
		echo "Destination        = $MAINDEST\n"
	elif [ $MODEL = "lunix4k" ] ; then
		echo "Found Qviart lunix4K\n"
		MTD_KERNEL="mmcblk0p1"
		KERNELNAME="oe_kernel.bin"
		TYPE=QVIART
		SHOWNAME="Qviart $MODEL"
		MAINDEST="$DIRECTORY/update/$MODEL"
		EXTRA="$DIRECTORY/automatic_fullbackup/$DATE/update"
		echo "Destination        = $MAINDEST\n"
	else
		echo "No supported receiver found!\n"
		exit 0
	fi
elif [ -f /proc/stb/info/model ] && [ ! -f /proc/stb/info/hwmodel ] && [ ! -f /proc/stb/info/gbmodel ]; then
	MODEL=$( cat /proc/stb/info/model )
	if [ $MODEL = "dm900" ] || [ $MODEL = "dm920" ] ; then
		echo "Found Dreambox dm900/dm920\n"
		MTD_KERNEL="mmcblk0p1"
		KERNELNAME="kernel.bin"
		TYPE=DREAMBOX
		SHOWNAME="Dreambox $MODEL"
		MAINDEST="$DIRECTORY/$MODEL"
		EXTRA="$DIRECTORY/automatic_fullbackup/$DATE"
		echo "Destination        = $MAINDEST\n"
	else
		echo "No supported receiver found!\n"
		exit 0
	fi
elif [ -f /proc/stb/info/gbmodel ] && [ ! -f /proc/stb/info/hwmodel ]; then
	MODEL=$( cat /proc/stb/info/gbmodel )
	if [ $MODEL = "gbquad4k" ] ; then
		echo "Found GigaBlue UHD Quad 4K\n"
		MODEL="quad4k"
		MTDROOTFS=$(readlink /dev/root)
		if [ $MTDROOTFS = "mmcblk0p3" ]; then
			MTD_KERNEL="mmcblk0p2"
		fi
		if [ $MTDROOTFS = "mmcblk0p5" ]; then
			MTD_KERNEL="mmcblk0p4"
		fi
		if [ $MTDROOTFS = "mmcblk0p7" ]; then
			MTD_KERNEL="mmcblk0p6"
		fi
		if [ $MTDROOTFS = "mmcblk0p9" ]; then
			MTD_KERNEL="mmcblk0p8"
		fi
		KERNELNAME="kernel.bin"
		TYPE=GIGABLUE
		SHOWNAME="Gigablue $MODEL"
		MAINDEST="$DIRECTORY/gigablue/$MODEL"
		EXTRA="$DIRECTORY/automatic_fullbackup/$DATE/gigablue"
		echo "Destination        = $MAINDEST\n"
	elif [ $MODEL = "gbue4k" ] ; then
		echo "Found GigaBlue UHD UE 4K\n"
		MODEL="ue4k"
		MTDROOTFS=$(readlink /dev/root)
		if [ $MTDROOTFS = "mmcblk0p5" ]; then
			MTD_KERNEL="mmcblk0p4"
		fi
		if [ $MTDROOTFS = "mmcblk0p7" ]; then
			MTD_KERNEL="mmcblk0p6"
		fi
		if [ $MTDROOTFS = "mmcblk0p9" ]; then
			MTD_KERNEL="mmcblk0p8"
		fi
		KERNELNAME="kernel.bin"
		TYPE=GIGABLUE
		SHOWNAME="Gigablue $MODEL"
		MAINDEST="$DIRECTORY/gigablue/$MODEL"
		EXTRA="$DIRECTORY/automatic_fullbackup/$DATE/gigablue"
		echo "Destination        = $MAINDEST\n"
	else
		echo "No supported receiver found!\n"
		exit 0
	fi
else
	echo "No supported receiver found!\n"
	exit 0
fi

if [ ! -f $MKFS ] ; then
	echo "NO TAR FOUND, ABORTING\n"
	exit 0
fi
if [ ! -f "$BZIP2" ] ; then 
	echo "$BZIP2 not installed yet, now installing\n"
	opkg update > /dev/null 2>&1
	opkg install bzip2 > /dev/null 2>&1
	echo "Exit, try again\n"
	sleep 10
	exit 0
fi

echo "Starting Full Backup!\nOptions control panel will not be available 2-15 minutes.\nPlease wait ..."
echo "--------------------------"

control_c(){
   echo "Control C was pressed, quiting..."
   umount /tmp/bi/root 2>/dev/null
   rmdir /tmp/bi/root 2>/dev/null
   rmdir /tmp/bi 2>/dev/null
   rm -rf "$WORKDIR" 2>/dev/null
   exit 255
}
trap control_c SIGINT

echo "\nWARNING!\n"
echo "To stop creating a backup, press the Menu button.\n"
sleep 2

## PREPARING THE BUILDING ENVIRONMENT
rm -rf "$WORKDIR"
echo "Remove directory   = $WORKDIR\n"
mkdir -p "$WORKDIR"
echo "Recreate directory = $WORKDIR\n"
mkdir -p /tmp/bi/root
echo "Create directory   = /tmp/bi/root\n"
sync
mount --bind / /tmp/bi/root

#dd if=/dev/$MTD_KERNEL of=$WORKDIR/kernel.dump
#ADDR=$(getaddr $WORKDIR/kernel.dump 44)
#dd if=$WORKDIR/kernel.dump of=$WORKDIR/$KERNELNAME bs=$ADDR count=1 && rm $WORKDIR/kernel.dump
echo "Kernel resides on /dev/$MTD_KERNEL\n"
dd if=/dev/$MTD_KERNEL of=$WORKDIR/$KERNELNAME > /dev/null 2>&1

echo "Start creating rootfs.tar\n"
#$MKFS -jcf $WORKDIR/$ROOTFSTYPE -C /tmp/bi/root .
$MKFS -cf $WORKDIR/rootfs.tar -C /tmp/bi/root --exclude=/var/nmbd/* . > /dev/null 2>&1
$BZIP2 $WORKDIR/rootfs.tar > /dev/null 2>&1

TSTAMP="$(date "+%Y-%m-%d-%Hh%Mm")"

if [ $TYPE = "VU" ] || [ $TYPE = "QVIART" ] || [ $TYPE = "DREAMBOX" ] || [ $TYPE = "GIGABLUE" ] ; then
	rm -rf "$MAINDEST"
	echo "Removed directory  = $MAINDEST\n"
	mkdir -p "$MAINDEST" 
	echo "Created directory  = $MAINDEST\n"
	mv "$WORKDIR/$KERNELNAME" "$MAINDEST/$KERNELNAME"
	mv "$WORKDIR/$ROOTFSTYPE" "$MAINDEST/$ROOTFSTYPE"
	echo "$MODEL-$IMAGEVERSION" > "$MAINDEST/imageversion"
	if [ $TYPE = "QVIART" ] ; then
		if [ -f /boot/initrd_run.bin ] ; then
			cp /boot/initrd_run.bin "$MAINDEST/initrd_run.bin
		fi
	fi
	if [ $MODEL = "lunix3-4k" ] || [ $MODEL = "lunix4k" ] || [ $MODEL = "dm900" ] || [ $MODEL = "dm920" ] ; then
		echo ""
	elif [ $MODEL = "uno4k" ] || [ $MODEL = "zero4k" ] ; then
		echo "rename this file to 'force.update' when need confirmation" > "$MAINDEST/noforce.update"
	else
		if [ $TYPE != "GIGABLUE" ] ; then
			echo "This file forces a reboot after the update" > "$MAINDEST/reboot.update"
		fi
	fi
	if [ $MODEL = "zero4k" ] || [ $MODEL = "uno4k" ] || [ $MODEL = "uno4kse" ] || [ $MODEL = "ultimo4k" ] || [ $MODEL = "solo4k" ] || [ $MODEL = "duo4k" ] || [ $MODEL = "duo4kse" ] ; then
		echo "rename this file to 'mkpart.update' for forces create partition and kernel update." > "$MAINDEST/nomkpart.update"
	fi
	if [ -z "$CREATE_ZIP" ] ; then
		mkdir -p "$EXTRA/$MODEL"
		echo "Created directory  = $EXTRA/$MODEL\n"
		touch "$MAINDEST/$IMVER"
		cp -r "$MAINDEST" "$EXTRA" 
		touch "$DIRECTORY/automatic_fullbackup/.timestamp"
	else
		if [ $CREATE_ZIP != "none" ] ; then
			echo "Create zip archive..."
			cd $DIRECTORY && $CREATE_ZIP -r $DIRECTORY/backup-$IMAGENAME-$MODEL-$TSTAMP.zip . -i /$MODEL/*
			cd
		fi
	fi
	if [ -f "$MAINDEST/rootfs.tar.bz2" -a -f "$MAINDEST/$KERNELNAME" ] ; then
		echo " "
		echo "BACK-UP MADE SUCCESSFULLY IN: $MAINDEST\n"
	else
		echo " "
		echo "Image creation FAILED!\n"
	fi
fi
umount /tmp/bi/root
rmdir /tmp/bi/root
rmdir /tmp/bi
rm -rf "$WORKDIR"
sleep 5
END=$(date +%s)
DIFF=$(( $END - $START ))
MINUTES=$(( $DIFF/60 ))
SECONDS=$(( $DIFF-(( 60*$MINUTES ))))
if [ $SECONDS -le  9 ] ; then 
	SECONDS="0$SECONDS"
fi
echo "BACKUP FINISHED IN $MINUTES.$SECONDS MINUTES\n"
exit
