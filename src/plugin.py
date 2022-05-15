from __future__ import print_function
import time
import os
import gettext
from Components.config import config, configfile, ConfigEnableDisable, ConfigSubsection, ConfigYesNo, ConfigClock, getConfigListEntry, ConfigSelection, ConfigOnOff, ConfigSubDict, ConfigNothing, NoSave, ConfigText
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Screens.ChoiceBox import ChoiceBox
from Screens.Console import Console
from Components.ConfigList import ConfigListScreen
from Components.ActionMap import ActionMap
from Components.Button import Button
from Components.FileList import FileList
from Components.Language import language
from Components.Harddisk import harddiskmanager
from Components.Label import Label
from Components.Sources.StaticText import StaticText
from Components.Pixmap import Pixmap
from Plugins.Plugin import PluginDescriptor
from Tools.FuzzyDate import FuzzyTime
from Tools.BoundFunction import boundFunction
from Tools.Notifications import AddPopup
from Components.About import about
from Tools.Directories import resolveFilename, fileExists, SCOPE_LANGUAGE, SCOPE_PLUGINS
from Screens import Standby
try:
	from Tools.StbHardware import getFPWasTimerWakeup
except:
	from Tools.DreamboxHardware import getFPWasTimerWakeup
from enigma import eTimer, eConsoleAppContainer
import NavigationInstance
from Tools import Notifications

from mimetypes import add_type
add_type("application/x-full-backup", ".fbackup")

lang = language.getLanguage()
os.environ["LANGUAGE"] = lang[:2]
gettext.bindtextdomain("enigma2", resolveFilename(SCOPE_LANGUAGE))
gettext.textdomain("enigma2")
gettext.bindtextdomain("FullBackup", "%s%s" % (resolveFilename(SCOPE_PLUGINS), "Extensions/FullBackup/locale/"))


def _(txt):
	t = gettext.dgettext("FullBackup", txt)
	if t == txt:
		t = gettext.gettext(txt)
	return t


PLUGIN_VERSION = _(" ver. ") + "7.0"

BOX_NAME = "none"
MODEL_NAME = "none"
if os.path.exists("/proc/stb/info/vumodel") and not os.path.exists("/proc/stb/info/hwmodel") and not os.path.exists("/proc/stb/info/boxtype") and not os.path.exists("/proc/stb/info/gbmodel"):
	BOX_NAME = "vu"
	try:
		f = open("/proc/stb/info/vumodel")
		MODEL_NAME = f.read().strip()
		f.close()
	except:
		pass
elif os.path.exists("/proc/stb/info/boxtype") and not os.path.exists("/proc/stb/info/hwmodel") and not os.path.exists("/proc/stb/info/gbmodel"):
	BOX_NAME = "all"
	try:
		f = open("/proc/stb/info/boxtype")
		MODEL_NAME = f.read().strip()
		f.close()
	except:
		pass
elif os.path.exists("/proc/stb/info/model") and not os.path.exists("/proc/stb/info/hwmodel") and not os.path.exists("/proc/stb/info/gbmodel"):
	BOX_NAME = "all"
	try:
		f = open("/proc/stb/info/model")
		MODEL_NAME = f.read().strip()
		if MODEL_NAME.startswith('dm') and not os.path.exists("/proc/stb/info/boxtype"):
			BOX_NAME = "dmm"
		f.close()
	except:
		pass
elif os.path.exists("/proc/stb/info/gbmodel") and not os.path.exists("/proc/stb/info/hwmodel"):
	BOX_NAME = "all"
	try:
		f = open("/proc/stb/info/gbmodel")
		MODEL_NAME = f.read().strip()
		f.close()
		if MODEL_NAME in ("gbquad4k", "gbue4k"):
			BOX_NAME = "gigablue"
	except:
		pass
elif os.path.exists("/proc/stb/info/hwmodel") and not os.path.exists("/proc/stb/info/gbmodel"):
	BOX_NAME = "all"
	try:
		f = open("/proc/stb/info/hwmodel")
		MODEL_NAME = f.read().strip()
		f.close()
	except:
		pass

config.plugins.fullbackup = ConfigSubsection()
config.plugins.fullbackup.wakeup = ConfigClock(default=((3 * 60) + 0) * 60) # 3:00
config.plugins.fullbackup.enabled = ConfigEnableDisable(default=False)
config.plugins.fullbackup.day_profile = ConfigSelection(choices=[("1", _("Press OK"))], default="1")
config.plugins.fullbackup.deepstandby = ConfigSelection(default="0", choices=[
		("0", _("disabled")),
		("1", _("wake up for backup")),
		("2", _("wake up and shutdown after backup")),
		])
config.plugins.fullbackup.after_create = ConfigYesNo(default=False)
config.plugins.fullbackup.message = ConfigSelection(default="0", choices=[
		("0", _("no")),
		("1", _("type info")),
		("2", _("type yes/no")),
		])
config.plugins.fullbackup.where = ConfigText(default="none", fixed_size=False)
config.plugins.fullbackup.autoscan = ConfigYesNo(default=True)
config.plugins.fullbackup.autoscan_nelp = ConfigNothing()
config.plugins.fullbackup.autoclean = ConfigSelection(default="0", choices=[
		("0", _("cleanup disabled")),
		("2", _("older than 2 days")),
		("3", _("older than 3 days")),
		("7", _("older than 1 week")),
		("14", _("older than 2 weeks")),
		("21", _("older than 3 weeks")),
		("28", _("older than 4 weeks")),
		("91", _("older than 3 months")),
		])
config.plugins.extra_fullbackup = ConfigSubsection()
config.plugins.extra_fullbackup.day_backup = ConfigSubDict()
for i in range(7):
	config.plugins.extra_fullbackup.day_backup[i] = ConfigEnableDisable(default=True)

weekdays = [
	_("Monday"),
	_("Tuesday"),
	_("Wednesday"),
	_("Thursday"),
	_("Friday"),
	_("Saturday"),
	_("Sunday"),
	]

config.plugins.fullbackup.multiboot_switcher_standbymenu = ConfigYesNo(default=False)
config.plugins.fullbackup.run_multbboot_switcher = ConfigSelection(choices=[("1", _("Press OK"))], default="1")

autoStartTimer = None
_session = None

BACKUP_SCRIPT = "/usr/lib/enigma2/python/Plugins/Extensions/FullBackup/automatic-fullbackup.sh"
DREAM_BACKUP_SCRIPT = "/usr/lib/enigma2/python/Plugins/Extensions/FullBackup/dreambox-fullbackup.sh"
VU4K_BACKUP_SCRIPT = "/usr/lib/enigma2/python/Plugins/Extensions/FullBackup/automatic-fullbackup-vu4k.sh"
HD51_BACKUP_SCRIPT = "/usr/lib/enigma2/python/Plugins/Extensions/FullBackup/automatic-fullbackup-hd51.sh"
zip_bin = "/usr/bin/zip"
ofgwrite_bin = "/usr/bin/ofgwrite"

if not os.path.exists(ofgwrite_bin):
	arch = os.popen("uname -m").read()
	if 'mips' in arch:
		MIPS = "/usr/lib/enigma2/python/Plugins/Extensions/FullBackup/bin/mips/ofgwrite"
		if os.path.exists(MIPS):
			os.chmod(MIPS, 0o755)
			ofgwrite_bin = MIPS
	elif 'armv7l' in arch:
		ARMV71 = "/usr/lib/enigma2/python/Plugins/Extensions/FullBackup/bin/armv7l/ofgwrite"
		if os.path.exists(ARMV71):
			os.chmod(ARMV71, 0o755)
			ofgwrite_bin = ARMV71
	elif 'sh4' in arch:
		SH4 = "/usr/lib/enigma2/python/Plugins/Extensions/FullBackup/bin/sh4/ofgwrite"
		if os.path.exists(SH4):
			os.chmod(SH4, 0o755)
			ofgwrite_bin = SH4


def Freespace(dev):
	try:
		statdev = os.statvfs(dev)
		space = (statdev.f_bavail * statdev.f_frsize) / 1024
		print("[FullBackup] Free space on %s = %i kilobytes" % (dev, space))
		return space
	except:
		return 0


def check_hdd(dir=""):
	if not os.path.exists(dir):
		if Standby.inStandby is None:
			_session and _session.open(MessageBox, _("AFB\nNot found mount device for create full backup!"), type=MessageBox.TYPE_ERROR)
		return False
	if emmc_multiboot:
		if Freespace(dir) < 1500000:
			if Standby.inStandby is None:
				_session and _session.open(MessageBox, _("AFB\nNot enough free space on device!\nYou need at least 1500Mb free space!"), type=MessageBox.TYPE_ERROR)
			return False
	else:
		if Freespace(dir) < 300000:
			if Standby.inStandby is None:
				_session and _session.open(MessageBox, _("AFB\nNot enough free space on device!\nYou need at least 300Mb free space!"), type=MessageBox.TYPE_ERROR)
			return False
	return True


emmc_multiboot = MODEL_NAME in ("hd51", "vs1500", "h7")
emmc_multiboot1 = MODEL_NAME in ("gbquad4k", "gbue4k")


def runBlkid():
	list = []
	if emmc_multiboot or emmc_multiboot1:
		blkid_linux = os.popen("blkid -v").read()
		sfdisk = os.popen("sfdisk -v").read()
		if 'util-linux' in blkid_linux and 'util-linux' in sfdisk:
			ret = os.popen("blkid").readlines()
			for line in ret:
				if emmc_multiboot:
					if '/dev/mmcblk0p3' in line:
						if 'TYPE' not in line:
							os.system('mkfs.ext4 -F /dev/mmcblk0p3')
						list.append(('mmcblk0p3'))
					if '/dev/mmcblk0p5' in line:
						if 'TYPE' not in line:
							os.system('mkfs.ext4 -F /dev/mmcblk0p5')
						list.append(('mmcblk0p5'))
					if '/dev/mmcblk0p7' in line:
						if 'TYPE' not in line:
							os.system('mkfs.ext4 -F /dev/mmcblk0p7')
						list.append(('mmcblk0p7'))
					if '/dev/mmcblk0p9' in line:
						if 'TYPE' not in line:
							os.system('mkfs.ext4 -F /dev/mmcblk0p9')
						list.append(('mmcblk0p9'))
				else:
					if '/dev/mmcblk0p5' in line:
						if 'TYPE' not in line:
							os.system('mkfs.ext4 -F /dev/mmcblk0p5')
						list.append(('mmcblk0p5'))
					if '/dev/mmcblk0p7' in line:
						if 'TYPE' not in line:
							os.system('mkfs.ext4 -F /dev/mmcblk0p7')
						list.append(('mmcblk0p7'))
					if '/dev/mmcblk0p9' in line:
						if 'TYPE' not in line:
							os.system('mkfs.ext4 -F /dev/mmcblk0p9')
						list.append(('mmcblk0p9'))
				if '/dev/mmcblk0p10' in line:
					if 'TYPE' not in line and 'swap' in line:
						os.system('mkswap /dev/mmcblk0p10')
					if not os.path.exists("/etc/init.d/createswap.sh") and 'swap' in line:
						os.system('cp /usr/lib/enigma2/python/Plugins/Extensions/FullBackup/createswap.sh /etc/init.d/createswap.sh && chmod 755 /etc/init.d/createswap.sh')
						os.system("ln -sf /etc/init.d/createswap.sh /etc/rc3.d/S98createswap")
		elif _session:
			_session.openWithCallback(installUtilblkidCallback, MessageBox, _("Install util-linux-blkid?"), MessageBox.TYPE_YESNO)
	return list


def installUtilblkidCallback(answer):
		if answer:
			os.system("opkg update && opkg install util-linux-blkid && opkg install util-linux-sfdisk")


def backupCommand():
	try:
		if os.path.exists(BACKUP_SCRIPT):
			os.chmod(BACKUP_SCRIPT, 0o755)
	except:
		pass
	try:
		if os.path.exists(DREAM_BACKUP_SCRIPT):
			os.chmod(DREAM_BACKUP_SCRIPT, 0o755)
	except:
		pass
	try:
		if os.path.exists(VU4K_BACKUP_SCRIPT):
			os.chmod(VU4K_BACKUP_SCRIPT, 0o755)
	except:
		pass
	try:
		if os.path.exists(HD51_BACKUP_SCRIPT):
			os.chmod(HD51_BACKUP_SCRIPT, 0o755)
	except:
		pass
	if BOX_NAME == 'none':
		return ''
	cmd = BACKUP_SCRIPT
	if BOX_NAME == 'dmm':
		cmd = DREAM_BACKUP_SCRIPT
		if MODEL_NAME == "dm900" or MODEL_NAME == "dm920":
			cmd = VU4K_BACKUP_SCRIPT
	if (BOX_NAME == 'vu' and (MODEL_NAME == "solo4k" or MODEL_NAME == "uno4k" or MODEL_NAME == "ultimo4k" or MODEL_NAME == "uno4kse" or MODEL_NAME == "zero4k" or MODEL_NAME == "duo4k" or MODEL_NAME == "duo4kse")) or MODEL_NAME == "lunix4k" or MODEL_NAME == "lunix3-4k" or MODEL_NAME == "gbquad4k" or MODEL_NAME == "gbue4k":
		cmd = VU4K_BACKUP_SCRIPT
	if MODEL_NAME == "hd51" or MODEL_NAME == "sf4008" or MODEL_NAME == "vs1500" or MODEL_NAME == "et11000" or MODEL_NAME == "h7":
		cmd = HD51_BACKUP_SCRIPT
	cmd += " " + config.plugins.fullbackup.where.value
	return cmd


def runBackup():
	destination = config.plugins.fullbackup.where.value
	if destination == 'none':
		return
	if destination:
		try:
			cmd = backupCommand()
			if cmd:
				os.system(cmd)
			else:
				print("[FullBackup] not supported receiver!")
				return
		except Exception as e:
			print("[FullBackup] FAIL:", e)
			return
		if Standby.inStandby and config.plugins.fullbackup.after_create.value and getFPWasTimerWakeup() and config.plugins.fullbackup.deepstandby.value == "2":
			if not os.path.exists("/tmp/.fullbackup"):
				try:
					open('/tmp/.fullbackup', 'wb').close()
				except:
					pass


def runCleanup():
	olderthen = int(config.plugins.fullbackup.autoclean.value)
	destination = config.plugins.fullbackup.where.value
	if destination == 'none':
		return
	if olderthen and destination:
		try:
			backupList = sorted(os.listdir('%s/automatic_fullbackup' % (destination)))
		except:
			backupList = []
		if len(backupList) > 0:
			import re
			pattern = re.compile('^(\d{8}_\d{4})$', re.M)	# '%Y%m%d_%H%M'
			olderthen = int(time.time()) - olderthen * 86400
			for backup in backupList:
				s = pattern.search(backup)
				if not s is None:
					date = time.mktime(time.strptime(s.group(1), '%Y%m%d_%H%M'))
					if int(date) > olderthen:
						continue
					os.system('rm -rf %s/automatic_fullbackup/%s' % (destination, backup))


class FullBackupConfig(ConfigListScreen, Screen):
	skin = """
	<screen position="center,center" size="640,455" title="FullBackup Configuration" >
		<ePixmap name="red"    position="0,0"   zPosition="2" size="140,40" pixmap="skin_default/buttons/red.png" transparent="1" alphatest="on" />
		<ePixmap name="green"  position="160,0" zPosition="2" size="140,40" pixmap="skin_default/buttons/green.png" transparent="1" alphatest="on" />
		<ePixmap name="yellow" position="320,0" zPosition="2" size="140,40" pixmap="skin_default/buttons/yellow.png" transparent="1" alphatest="on" />
		<ePixmap name="blue" position="480,0" zPosition="2" size="140,40" pixmap="skin_default/buttons/blue.png" transparent="1" alphatest="on" />
		<widget name="key_red" position="0,0" size="140,40" valign="center" halign="center" zPosition="4"  foregroundColor="white" font="Regular;18" transparent="1" shadowColor="background" shadowOffset="-2,-2" />
		<widget name="key_green" position="160,0" size="140,40" valign="center" halign="center" zPosition="4"  foregroundColor="white" font="Regular;18" transparent="1" shadowColor="background" shadowOffset="-2,-2" />
		<widget name="key_yellow" position="320,0" size="140,40" valign="center" halign="center" zPosition="4"  foregroundColor="white" font="Regular;18" transparent="1" shadowColor="background" shadowOffset="-2,-2" />
		<widget name="key_blue" position="480,0" size="140,40" valign="center" halign="center" zPosition="4"  foregroundColor="white" font="Regular;18" transparent="1" shadowColor="background" shadowOffset="-2,-2" />
		<widget name="config" position="10,40" size="630,227" scrollbarMode="showOnDemand" />
		<widget name="status" position="10,280" size="630,140" font="Regular;16" />
		<widget name="ButtonMenu" position="10,420" size="35,25" zPosition="3" pixmap="skin_default/buttons/key_menu.png" alphatest="on" />
		<ePixmap alphatest="on" pixmap="skin_default/icons/clock.png" position="560,433" size="14,14" zPosition="3"/>
		<widget font="Regular;18" halign="left" position="585,430" render="Label" size="55,20" source="global.CurrentTime" transparent="1" valign="center" zPosition="3">
			<convert type="ClockToText">Default</convert>
		</widget>
		<widget name="statusbar" position="10,430" size="550,20" font="Regular;18" />
	</screen>"""

	def __init__(self, session, args=0):
		self.session = session
		self.setup_title = _("FullBackup Configuration")
		Screen.__init__(self, session)
		current_path = config.plugins.fullbackup.where.value
		self.isActive = False
		self.statusUploadOMB = False
		self["ButtonMenu"] = Pixmap()
		self["ButtonMenu"].hide()
		hddchoises = [('none', 'None')]
		for p in harddiskmanager.getMountedPartitions():
			if os.path.exists(p.mountpoint) and os.access(p.mountpoint, os.F_OK | os.R_OK):
				if p.mountpoint != '/':
					d = os.path.normpath(p.mountpoint)
					mountpoint = p.mountpoint
					if mountpoint.endswith('/'):
						mountpoint = mountpoint[:-1]
					hddchoises.append((d, mountpoint))
		if (current_path, current_path) in hddchoises:
			default_path = current_path
		else:
			default_path = 'none'
		config.plugins.fullbackup.add_to_where = NoSave(ConfigSelection(default=default_path, choices=hddchoises))
		cfg = config.plugins.fullbackup
		self.appendList = [
			getConfigListEntry(_("Automatic start time"), cfg.wakeup),
			getConfigListEntry(_("Choice days for create backup"), cfg.day_profile),
			getConfigListEntry(_("Behaviour in deep standby"), cfg.deepstandby),
			getConfigListEntry(_("Automatic cleanup backups"), cfg.autoclean),
			getConfigListEntry(_("Show message during the start"), cfg.message),
			]
		self.configList = [
			getConfigListEntry(_("Backup location"), cfg.add_to_where),
			getConfigListEntry(_("Automatic full backup"), cfg.enabled),
			getConfigListEntry(_("Scan at automount for create backup"), cfg.autoscan),
			getConfigListEntry(_("< Needs create file *(any name).fbackup in USB device >"), cfg.autoscan_nelp),
			]
		if cfg.enabled.value:
			list = self.configList + self.appendList
		else:
			list = self.configList
		#if emmc_multiboot:
		#	list.append(getConfigListEntry(_("Show multiBoot switcher in menu shutdown"), cfg.multiboot_switcher_standbymenu))
		#	list.append(getConfigListEntry(_("Open multiBoot switcher"), cfg.run_multbboot_switcher))
		ConfigListScreen.__init__(self, list, session=session, on_change=self.changedEntry)
		self["key_red"] = Button(_("Cancel"))
		self["key_green"] = Button(_("Save"))
		self["key_yellow"] = Button(_("Manual"))
		if BOX_NAME == 'none' or (BOX_NAME == 'dmm' and not (MODEL_NAME == "dm900" or MODEL_NAME == "dm920")):
			self["key_blue"] = Button()
		else:
			self["key_blue"] = Button(_("Restore backup"))
		self["statusbar"] = Label()
		self["status"] = Label()
		self["setupActions"] = ActionMap(["SetupActions", "ColorActions", "InfobarMenuActions"],
		{
			"red": self.cancel,
			"green": self.save,
			"yellow": self.dobackup,
			"blue": self.flashimage,
			"save": self.save,
			"cancel": self.cancel,
			"ok": self.keyOk,
			"mainMenu": self.openMenu,
		}, -2)
		self.onChangedEntry = [self.onEntryChanged]
		self.data = ''
		self.container = eConsoleAppContainer()
		self.container.appClosed.append(self.appClosed)
		self.container.dataAvail.append(self.dataAvail)
		cfg.add_to_where.addNotifier(self.changedWhere)
		self.onClose.append(self.__onClose)
		self.onLayoutFinish.append(self.__layoutFinished)
		self.isStatusUploadOMB()

	def __layoutFinished(self):
		self.setTitle(self.setup_title)

	def onEntryChanged(self):
		cur = self["config"].getCurrent()
		if cur == self.configList[1]:
			list = []
			if cur[1].value and len(self.configList) == len(self["config"].list):
				list = self.configList + self.appendList
			elif not cur[1].value and len(self.configList) < len(self["config"].list):
				list = self.configList
			if len(list):
				self["config"].list = list
				self["config"].l.setList(list)

	def changedEntry(self):
		for x in self.onChangedEntry:
			x()

	def getCurrentEntry(self):
		return self["config"].getCurrent()[0]

	def getCurrentValue(self):
		return str(self["config"].getCurrent()[1].getText())

	def createSummary(self):
		from Screens.Setup import SetupSummary
		return SetupSummary

	def isStatusUploadOMB(self):
		if fileExists("/usr/lib/enigma2/python/Plugins/Extensions/OpenMultiboot/plugin.pyo") and self.isActive:
			self["ButtonMenu"].show()
			self.statusUploadOMB = True
		else:
			self["ButtonMenu"].hide()
			self.statusUploadOMB = False

	def openMenu(self):
		found_dir = ''
		if self.statusUploadOMB:
			OMB_DATA_DIR = 'open-multiboot'
			OMB_UPLOAD_DIR = 'open-multiboot-upload'
			data_dir = '/omb/' + OMB_DATA_DIR
			if os.path.exists(data_dir):
					upload_dir = '/omb/' + OMB_UPLOAD_DIR
					if os.path.exists(upload_dir):
						found_dir = upload_dir
			else:
				for p in harddiskmanager.getMountedPartitions():
					if p.mountpoint != '/':
						data_dir = p.mountpoint + '/' + OMB_DATA_DIR
						if os.path.exists(data_dir) and self.isMounted(p.mountpoint):
							upload_dir = p.mountpoint + '/' + OMB_UPLOAD_DIR
							if os.path.exists(upload_dir):
								found_dir = upload_dir
								break
			if found_dir:
				files = "^.*\.zip"
				if BOX_NAME == 'none':
					self.session.open(MessageBox, _("Your receiver not supported!"), MessageBox.TYPE_ERROR)
					return
				if BOX_NAME == 'all':
					files = "^.*\.(zip|bin)"
					if MODEL_NAME == "fusionhd" or MODEL_NAME == "fusionhdse" or MODEL_NAME == "purehd":
						files = "^.*\.(zip|bin|update)"
					if MODEL_NAME == "hd51" or MODEL_NAME == "sf4008" or MODEL_NAME == "vs1500" or MODEL_NAME == "et11000" or MODEL_NAME == "h7" or MODEL_NAME == "lunix4k" or MODEL_NAME == "lunix3-4k" or MODEL_NAME == "gbquad4k" or MODEL_NAME == "gbue4k":
						files = "^.*\.(zip|bz2|bin)"
				elif BOX_NAME == "vu":
					if MODEL_NAME == "solo4k" or MODEL_NAME == "uno4k" or MODEL_NAME == "ultimo4k" or MODEL_NAME == "uno4kse" or MODEL_NAME == "zero4k" or MODEL_NAME == "duo4k":
						files = "^.*\.(zip|bz2|bin)"
					elif MODEL_NAME == "solo2" or MODEL_NAME == "duo2" or MODEL_NAME == "solose" or MODEL_NAME == "zero":
						files = "^.*\.(zip|bin|update)"
					else:
						files = "^.*\.(zip|bin|jffs2)"
				elif BOX_NAME == "dmm":
					files = "^.*\.(zip|nfi)"
					if MODEL_NAME == "dm900" or MODEL_NAME == "dm920":
						files = "^.*\.(zip|bz2|bin)"
				curdir = config.plugins.fullbackup.where.value
				path = config.plugins.fullbackup.where.value + '/automatic_fullbackup/'
				if os.path.exists(path):
					curdir = path
				self.session.open(SearchOMBfile, curdir, files, found_dir)

	def isMounted(self, device):
		try:
			for line in open("/proc/mounts"):
				if line.find(device[:-1]) > -1:
					return True
		except:
			pass
		return False

	def changedWhere(self, cfg):
		self.isActive = False
		if cfg.value == 'none':
			self["status"].setText(_('Not selected directory backup'))
			self.isStatusUploadOMB()
			return
		path = os.path.join(cfg.value, 'automatic_fullbackup')
		if not os.path.exists(path):
			self["status"].setText(_("No backup present"))
		else:
			try:
				st = os.stat(os.path.join(path, ".timestamp"))
				self.isActive = True
				self["status"].setText(_("Last backup date") + ": " + " ".join(FuzzyTime(st.st_mtime)))
			except Exception as ex:
				print("Failed to stat %s: %s" % (path, ex))
				self.isActive = False
				self["status"].setText(_("Disabled"))
		self.isStatusUploadOMB()

	def __onClose(self):
		config.plugins.fullbackup.add_to_where.notifiers.remove(self.changedWhere)

	def keyOk(self):
		ConfigListScreen.keyOK(self)
		sel = self["config"].getCurrent() and self["config"].getCurrent()[1]
		if sel is None:
			return
		if sel == config.plugins.fullbackup.day_profile:
			self.session.open(DaysProfile)
		elif sel == config.plugins.fullbackup.run_multbboot_switcher:
			self.session.open(MultiBootSwitcher)

	def flashimage(self):
		if BOX_NAME == 'none' or (BOX_NAME == 'dmm' and not (MODEL_NAME == "dm900" or MODEL_NAME == "dm920")):
			self.session.open(MessageBox, _("Your receiver not supported!"), MessageBox.TYPE_ERROR)
			return
		if fileExists("/omb/open-multiboot") and os.path.ismount('/usr/lib/enigma2/python/Plugins/Extensions/OpenMultiboot'):
			self.session.open(MessageBox, _("Sorry!\nThis boot is not flash image!"), MessageBox.TYPE_ERROR)
			return
		if not MODEL_NAME:
			return
		files = "^.*\.(zip|bin)"
		if MODEL_NAME == "hd51" or MODEL_NAME == "solo4k" or MODEL_NAME == "uno4kse" or MODEL_NAME == "uno4k" or MODEL_NAME == "ultimo4k" or MODEL_NAME == "zero4k" or MODEL_NAME == "duo4k" or MODEL_NAME == "duo4kse" or MODEL_NAME == "sf4008" or MODEL_NAME == "vs1500" or MODEL_NAME == "et11000" or MODEL_NAME == "h7" or MODEL_NAME == "lunix4k" or MODEL_NAME == "lunix3-4k" or MODEL_NAME == "dm900" or MODEL_NAME == "dm920" or MODEL_NAME == "gbquad4k" or MODEL_NAME == "gbue4k":
			files = "^.*\.(zip|bz2|bin)"
		elif BOX_NAME == "vu":
			if MODEL_NAME == "solo2" or MODEL_NAME == "duo2" or MODEL_NAME == "solose" or MODEL_NAME == "zero" or MODEL_NAME == "fusionhd" or MODEL_NAME == "fusionhdse" or MODEL_NAME == "purehd":
				files = "^.*\.(zip|bin|update)"
			else:
				files = "^.*\.(zip|bin|jffs2)"
		curdir = '/media/'
		self.session.open(FlashImageConfig, curdir, files)

	def save(self):
		if config.plugins.fullbackup.enabled.value == False:
			config.plugins.fullbackup.autoclean.value = "0"
			config.plugins.fullbackup.message.value = "0"
		config.plugins.fullbackup.where.value = config.plugins.fullbackup.add_to_where.value
		config.plugins.fullbackup.where.save()
		self.saveAll()
		configfile.save()
		self.close(True, self.session)

	def cancel(self):
		for x in self["config"].list:
			x[1].cancel()
		self.close(False, self.session)

	def showOutput(self):
		self["status"].setText(self.data)

	def dobackup(self):
		if config.plugins.fullbackup.where.value == "none":
			self["status"].setText(_('Not selected directory backup'))
			return
		if MODEL_NAME == "none":
			self.session.open(MessageBox, _("Your receiver not supported!"), MessageBox.TYPE_ERROR)
			return
		if not check_hdd(config.plugins.fullbackup.where.value):
			return
		list = [
			(_("Background mode"), "background"),
			(_("Console mode"), "console"),
		]
		if emmc_multiboot:
			list += [
				(_("Background mode") + _(" as recovery"), "background_recovery"),
				(_("Console mode") + _(" as recovery"), "console_recovery"),
			]
		dlg = self.session.openWithCallback(self.CallbackMode, ChoiceBox, title=_("Select the option to create a backup:"), list=list)
		dlg.setTitle(_("Create backup"))

	def CallbackMode(self, ret):
		ret = ret and ret[1]
		if ret:
			if ret == "background":
				self.backgroundMode()
			elif ret == "background_recovery":
				self.backgroundMode(recovery=True)
			elif ret == "console_recovery" or ret == "console":
				text = _('Console log') + _(' - OK show/hide')
				cmd = backupCommand()
				if ret == "console_recovery":
					cmd += " %s" % "recovery"
				self.session.openWithCallback(self.consoleClosed, BackupConsole, text, [cmd])

	def consoleClosed(self, answer=None):
		self.changedWhere(config.plugins.fullbackup.where)

	def backgroundMode(self, recovery=False):
		self.data = ''
		self.showOutput()
		self["statusbar"].setText(_('Running'))
		cmd = backupCommand()
		if recovery:
			cmd += " %s" % "recovery"
		if self.container.execute(cmd):
			print("[FullBackup] failed to execute")
			self.showOutput()

	def appClosed(self, retval):
		print("[FullBackup] done:", retval)
		if retval:
			txt = _("Failed")
		else:
			txt = _("Done")
		self.showOutput()
		self.data = ''
		self["statusbar"].setText(txt)
		self.changedWhere(config.plugins.fullbackup.where)

	def dataAvail(self, str):
		self.data += str
		self.showOutput()


class BackupConsole(Console):
	def __init__(self, session, title="Console", cmdlist=None, finishedCallback=None, closeOnSuccess=False, dir=None):
		Console.__init__(self, session, title, cmdlist, finishedCallback, closeOnSuccess)
		self.skinName = "Console"
		self["BackupActions"] = ActionMap(["InfobarMenuActions"],
		{
			"mainMenu": self.stopRunBackup,
		}, -2)
		self.stop_run = False
		self.dir = dir
		self.is_hide = False

	def closeConsole(self):
		if (self.run == len(self.cmdlist)) or self.stop_run:
			if self.is_hide:
				self.is_hide = False
				self.show()
				return
			if self.dir is not None:
				self.extendedClosed()
			else:
				self.close()
				self.container.appClosed.remove(self.runFinished)
				self.container.dataAvail.remove(self.dataAvail)
		else:
			if not self.is_hide:
				self.hide()
				self.is_hide = True
			else:
				self.is_hide = False
				self.show()

	def extendedClosed(self):
		text = _("Select action:")
		menu = [(_("Exit"), "exit"), (_("Exit and eject device"), "umount")]

		def extraAction(choice):
			if choice:
				if choice[1] == "exit":
					self.close()
					self.container.appClosed.remove(self.runFinished)
					self.container.dataAvail.remove(self.dataAvail)
				elif choice[1] == "umount":
					result = os.system("umount %s" % self.dir)
					if result == 0:
						txt = _("The device was successfully unmounted!")
					else:
						txt = _("Error unmounting devices!")
					AddPopup(txt, type=MessageBox.TYPE_INFO, timeout=5, id="InfoUmountDevice")
					self.close()
					self.container.appClosed.remove(self.runFinished)
					self.container.dataAvail.remove(self.dataAvail)
		self.session.openWithCallback(extraAction, ChoiceBox, title=text, list=menu)

	def stopRunBackup(self):
		if (self.run != len(self.cmdlist)):
			self.session.openWithCallback(self.stopRunBackupAnswer, MessageBox, _("Do you really want to stop the creation of backup?"), MessageBox.TYPE_YESNO)

	def stopRunBackupAnswer(self, answer):
		if answer:
			self.container.sendCtrlC()
			self.stop_run = True


class FlashImageConfig(Screen):
	skin = """<screen name="FlashImageConfig" position="center,center" size="560,440" title=" " >
			<ePixmap pixmap="skin_default/buttons/red.png" position="0,0" size="140,40" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/green.png" position="140,0" size="140,40" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/yellow.png" position="280,0" size="140,40" alphatest="on" />
			<widget source="key_red" render="Label" position="0,0" zPosition="1" size="140,40" font="Regular;18" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" />
			<widget source="key_green" render="Label" position="140,0" zPosition="1" size="140,40" font="Regular;18" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" />
			<widget source="key_yellow" render="Label" position="280,0" zPosition="1" size="140,40" font="Regular;18" halign="center" valign="center" backgroundColor="#a08500" transparent="1" />
			<widget source="curdir" render="Label" position="5,50" size="550,20"  font="Regular;17" halign="left" valign="center" backgroundColor="background" transparent="1" noWrap="1" />
			<widget name="filelist" position="5,80" size="550,345" scrollbarMode="showOnDemand" />
		</screen>"""

	def __init__(self, session, curdir, matchingPattern=None):
		Screen.__init__(self, session)

		self["Title"].setText(_("Select the folder with backup"))
		self["key_red"] = StaticText(_("Cancel"))
		self["key_green"] = StaticText("")
		self["key_yellow"] = StaticText("")
		self["curdir"] = StaticText(_("current:  %s") % (curdir or ''))
		self.founds = False
		self.filelist = FileList(curdir, matchingPattern=matchingPattern, enableWrapAround=True)
		self.filelist.onSelectionChanged.append(self.__selChanged)
		self["filelist"] = self.filelist
		self.dualboot = self.dualBoot()
		self.waitTimer = eTimer()
		self.waitTimer.callback.append(self.checkMount)
		self.waitTimer.start(500, True)
		self.stop_enigma = True
		self["FilelistActions"] = ActionMap(["SetupActions", "ColorActions"],
			{
				"green": self.keyGreen,
				"red": self.keyRed,
				"yellow": self.keyYellow,
				"ok": self.keyOk,
				"cancel": self.keyRed
			})
		self.onLayoutFinish.append(self.__layoutFinished)

	def __layoutFinished(self):
		pass

	def checkMount(self):
		self.imbeddedMiltiBoot = runBlkid()

	def dualBoot(self):
		if MODEL_NAME == "et8500":
			try:
				rootfs2 = False
				kernel2 = False
				f = open("/proc/mtd")
				l = f.readlines()
				for x in l:
					if 'rootfs2' in x:
						rootfs2 = True
					if 'kernel2' in x:
						kernel2 = True
				f.close()
				if rootfs2 and kernel2:
					return True
			except:
				pass
		return False

	def imbeddedMiltiBoot(self):
		list = []
		if emmc_multiboot:
			try:
				ret = os.popen("sfdisk -l /dev/mmcblk0").readlines()
				for line in ret:
					if '/dev/mmcblk0p3' in line and 'Linux filesystem' in line:
						list.append(('mmcblk0p3'))
					if '/dev/mmcblk0p5' in line and 'Linux filesystem' in line:
						list.append(('mmcblk0p5'))
					if '/dev/mmcblk0p7' in line and 'Linux filesystem' in line:
						list.append(('mmcblk0p7'))
					if '/dev/mmcblk0p9' in line and 'Linux filesystem' in line:
						list.append(('mmcblk0p9'))
			except:
				pass
		elif emmc_multiboot1:
			try:
				ret = os.popen("sfdisk -l /dev/mmcblk0").readlines()
				for line in ret:
					if '/dev/mmcblk0p5' in line and 'Linux filesystem' in line:
						list.append(('mmcblk0p5'))
					if '/dev/mmcblk0p7' in line and 'Linux filesystem' in line:
						list.append(('mmcblk0p7'))
					if '/dev/mmcblk0p9' in line and 'Linux filesystem' in line:
						list.append(('mmcblk0p9'))
			except:
				pass
		return list

	def getCurrentSelected(self):
		dirname = self.filelist.getCurrentDirectory()
		filename = self.filelist.getFilename()
		if not filename and not dirname:
			cur = ''
		elif not filename:
			cur = dirname
		elif not dirname:
			cur = filename
		else:
			if not self.filelist.canDescent() or len(filename) <= len(dirname):
				cur = dirname
			else:
				cur = filename
		return cur or ''

	def __selChanged(self):
		self["key_yellow"].setText("")
		self["key_green"].setText("")
		self["curdir"].setText(_("current:  %s") % (self.getCurrentSelected()))
		file_name = self.getCurrentSelected()
		try:
			if not self.filelist.canDescent() and file_name != '' and file_name != '/':
				filename = self.filelist.getFilename()
				if filename and filename.endswith(".zip"):
					self["key_yellow"].setText(_("Unzip"))
			elif self.filelist.canDescent() and file_name != '' and file_name != '/':
				self["key_green"].setText(_("Run flash"))
		except:
			pass

	def keyOk(self):
		if self.filelist.canDescent():
			self.filelist.descent()

	def confirmedWarning(self, result):
		if result:
			self.founds = False
			self.pausetimer = eTimer()
			self.pausetimer.callback.append(self.showparameterlist)
			self.pausetimer.start(500, True)

	def keyGreen(self):
		if self["key_green"].getText() == _("Run flash"):
			dirname = self.filelist.getCurrentDirectory()
			if dirname:
				warning_text = "\n"
				if self.dualboot:
					warning_text += _("\nYou are using dual multiboot!")
				if len(self.imbeddedMiltiBoot) > 1:
					warning_text += _("\nYou are using  built-in multiboot from %s sections!") % len(self.imbeddedMiltiBoot)
				self.session.openWithCallback(lambda r: self.confirmedWarning(r), MessageBox, _("Warning!\nUse at your own risk! Make always a backup before use!\nDon't use it if you use multiple ubi volumes in ubi layer!") + warning_text, MessageBox.TYPE_INFO)

	def showparameterlist(self):
		if self["key_green"].getText() == _("Run flash"):
			dirname = self.getCurrentSelected()
			if dirname:
				backup_files = []
				no_backup_files = []
				text = _("Select parameter for start flash!\n")
				text += _('For flashing your receiver files are needed:\n')
				if os.path.exists("/proc/stb/info/hwmodel") and (MODEL_NAME.startswith('fusion') or MODEL_NAME == "lunix4k" or MODEL_NAME == "lunix3-4k"):
					if MODEL_NAME == "lunix3-4k" or MODEL_NAME == "lunix4k":
						backup_files = [("rootfs.tar.bz2"), ("oe_kernel.bin")]
						no_backup_files = ["kernel_cfe_auto.bin", "rootfs.bin", "root_cfe_auto.jffs2", "root_cfe_auto.bin"]
						text += 'oe_kernel.bin, rootfs.tar.bz2'
					else:
						backup_files = [("oe_kernel.bin"), ("oe_rootfs.bin")]
						no_backup_files = ["kernel_cfe_auto.bin", "root_cfe_auto.jffs2", "root_cfe_auto.bin", "rootfs.bin", "kernel.bin"]
						text += 'oe_kernel.bin, oe_rootfs.bin'
				elif os.path.exists("/proc/stb/info/boxtype") and not os.path.exists("/proc/stb/info/hwmodel") and not os.path.exists("/proc/stb/info/gbmodel"):
					if MODEL_NAME in ["hd51", "sf4008", "vs1500", "et11000", "h7"]:
						backup_files = [("kernel1.bin"), ("rootfs.tar.bz2"), ("kernel.bin")]
						no_backup_files = ["kernel_cfe_auto.bin", "rootfs.bin", "root_cfe_auto.jffs2", "root_cfe_auto.bin"]
						text += 'kernel.bin/kernel1.bin, rootfs.tar.bz2'
					else:
						backup_files = [("kernel.bin"), ("rootfs.bin")]
						no_backup_files = ["kernel_cfe_auto.bin", "root_cfe_auto.jffs2", "root_cfe_auto.bin"]
						text += 'kernel.bin, rootfs.bin'
				elif os.path.exists("/proc/stb/info/vumodel") and not os.path.exists("/proc/stb/info/gbmodel") and not os.path.exists("/proc/stb/info/hwmodel"):
					if MODEL_NAME in ["solo4k", "uno4k", "uno4kse", "ultimo4k", "zero4k", "duo4k", "duo4kse"]:
						backup_files = ["kernel_auto.bin", "rootfs.tar.bz2"]
						no_backup_files = ["kernel.bin", "kernel_cfe_auto.bin", "root_cfe_auto.bin" "root_cfe_auto.jffs2", "rootfs.bin"]
						text += 'kernel_auto.bin, rootfs.tar.bz2'
					elif MODEL_NAME in ["solo2", "duo2", "solose", "zero"]:
						backup_files = ["kernel_cfe_auto.bin", "root_cfe_auto.bin"]
						no_backup_files = ["kernel.bin", "root_cfe_auto.jffs2", "rootfs.bin"]
						text += 'kernel_cfe_auto.bin, root_cfe_auto.bin'
					else:
						backup_files = ["kernel_cfe_auto.bin", "root_cfe_auto.jffs2"]
						no_backup_files = ["kernel.bin", "root_cfe_auto.bin", "rootfs.bin"]
						text += 'kernel_cfe_auto.bin, root_cfe_auto.jffs2'
				elif os.path.exists("/proc/stb/info/gbmodel") and not os.path.exists("/proc/stb/info/hwmodel"):
					if MODEL_NAME in ["gbquadplus"]:
						backup_files = ["kernel.bin", "rootfs.bin"]
						text += "kernel.bin, rootfs.bin"
					if MODEL_NAME in ["gbquad4k", "gbue4k"]:
						backup_files = [("kernel1.bin"), ("rootfs.tar.bz2"), ("kernel.bin")]
						no_backup_files = ["kernel_cfe_auto.bin", "rootfs.bin", "root_cfe_auto.jffs2", "root_cfe_auto.bin"]
						text += 'kernel.bin/kernel1.bin, rootfs.tar.bz2'
				elif os.path.exists("/proc/stb/info/model") and MODEL_NAME.startswith('dm') and not os.path.exists("/proc/stb/info/boxtype") and not os.path.exists("/proc/stb/info/gbmodel"):
					if MODEL_NAME in ["dm900", "dm920"]:
						backup_files = [("kernel1.bin"), ("rootfs.tar.bz2"), ("kernel.bin")]
						no_backup_files = ["kernel_cfe_auto.bin", "rootfs.bin", "root_cfe_auto.jffs2", "root_cfe_auto.bin"]
						text += 'kernel.bin/kernel1.bin, rootfs.tar.bz2'
				try:
					self.founds = False
					text += _('\nThe found files:')
					for name in os.listdir(dirname):
						if name in backup_files:
							text += _("  %s (maybe ok)") % name
							self.founds = True
						if name in no_backup_files:
							text += _("  %s (maybe error)") % name
							self.founds = True
					if not self.founds:
						text += _(' nothing!')
				except:
					pass
				if self.founds:
					num_sector = len(self.imbeddedMiltiBoot)
					if num_sector > 1:
						open_list = [
							(_("Simulate (no write)") + _("/First partition"), "simulate"),
							(_("Standard (root and kernel)") + _("/First partition"), "standard"),
							(_("Only root") + _("/First partition"), "root"),
							(_("Only kernel") + _("/First partition"), "kernel"),
						]
					else:
						open_list = [
							(_("Simulate (no write)"), "simulate"),
							(_("Standard (root and kernel)"), "standard"),
							(_("Only root"), "root"),
							(_("Only kernel"), "kernel"),
						]
					open_list2 = [
						(_("Simulate second partition (no write)"), "simulate2"),
						(_("Second partition (root and kernel)"), "standard2"),
						(_("Second partition (only root)"), "root2"),
						(_("Second partition (only kernel)"), "kernel2"),
					]
					if num_sector > 1:
						open_list3 = [
							(_("Simulate second partition (no write)"), "imbedded_simulate2"),
							(_("Second partition"), "imbedded_standard2"),
						]
						if num_sector > 2:
							open_list3 += [
								(_("Simulate third partition (no write)"), "imbedded_simulate3"),
								(_("Third partition"), "imbedded_standard3"),
							]
						if num_sector > 3:
							open_list3 += [
								(_("Simulate fourth partition (no write)"), "imbedded_simulate4"),
								(_("Fourth partition"), "imbedded_standard4"),
							]
					if self.dualboot:
						open_list += open_list2
					if len(self.imbeddedMiltiBoot) > 1:
						open_list += open_list3
				else:
					open_list = [
						(_("Exit"), "exit"),
					]
				self.session.openWithCallback(self.Callbackflashing, ChoiceBox, text, list=open_list)

	def Callbackflashing(self, ret):
		if ret:
			if ret[1] == "exit":
				self.close()
				return
			if self.session.nav.getRecordings():
				self.session.open(MessageBox, _("A recording is currently running. Please stop the recording before trying to start a flashing."), MessageBox.TYPE_ERROR)
				self.founds = False
				return
			dir_flash = self.getCurrentSelected()
			mount_part = ""
			self.stop_enigma = True
			if len(self.imbeddedMiltiBoot) > 1:
				mount_part = os.popen("readlink /dev/root").read()
			text = _("Flashing: ")
			cmd = "echo -e"
			if ret[1] == "simulate":
				text += _("Simulate (no write)")
				cmd = "%s -r -k -n '%s'" % (ofgwrite_bin, dir_flash)
				if len(self.imbeddedMiltiBoot) > 1:
					cmd = "%s -r -k -m1 -n '%s'" % (ofgwrite_bin, dir_flash)
			elif ret[1] == "standard":
				text += _("Standard (root and kernel)")
				cmd = "%s -r -k '%s' > /dev/null 2>&1" % (ofgwrite_bin, dir_flash)
				if len(self.imbeddedMiltiBoot) > 1:
					if emmc_multiboot:
						if 'mmcblk0p3' not in mount_part:
							os.system('umount -fl /dev/mmcblk0p3')
							os.system('mkfs.ext4 -F /dev/mmcblk0p3')
							self.stop_enigma = False
					elif emmc_multiboot1:
						if 'mmcblk0p5' not in mount_part:
							os.system('umount -fl /dev/mmcblk0p5')
							os.system('mkfs.ext4 -F /dev/mmcblk0p5')
							self.stop_enigma = False
					cmd = "%s -r -k -m1 '%s' > /dev/null 2>&1" % (ofgwrite_bin, dir_flash)
			elif ret[1] == "root":
				text += _("Only root")
				cmd = "%s -r '%s' > /dev/null 2>&1" % (ofgwrite_bin, dir_flash)
				if len(self.imbeddedMiltiBoot) > 1:
					if emmc_multiboot:
						if 'mmcblk0p3' not in mount_part:
							os.system('umount -fl /dev/mmcblk0p3')
							os.system('mkfs.ext4 -F /dev/mmcblk0p3')
							self.stop_enigma = False
					elif emmc_multiboot1:
						if 'mmcblk0p5' not in mount_part:
							os.system('umount -fl /dev/mmcblk0p5')
							os.system('mkfs.ext4 -F /dev/mmcblk0p5')
							self.stop_enigma = False
					cmd = "%s -r -m1 '%s'" % (ofgwrite_bin, dir_flash)
			elif ret[1] == "kernel":
				text += _("Only kernel")
				cmd = "%s -k '%s' > /dev/null 2>&1" % (ofgwrite_bin, dir_flash)
				if len(self.imbeddedMiltiBoot) > 1:
					cmd = "%s -k -m1 '%s'" % (ofgwrite_bin, dir_flash)
			elif ret[1] == "simulate2":
				text += _("Simulate second partition (no write)")
				cmd = "%s -kmtd3 -rmtd4 -n '%s'" % (ofgwrite_bin, dir_flash)
			elif ret[1] == "standard2":
				text += _("Second partition (root and kernel)")
				cmd = "%s -kmtd3 -rmtd4 '%s' > /dev/null 2>&1" % (ofgwrite_bin, dir_flash)
			elif ret[1] == "root2":
				text += _("Second partition (only root)")
				cmd = "%s -rmtd4 '%s' > /dev/null 2>&1 &" % (ofgwrite_bin, dir_flash)
			elif ret[1] == "kernel2":
				text += _("Second partition (only kernel)")
				cmd = "%s -kmtd3 '%s' > /dev/null 2>&1" % (ofgwrite_bin, dir_flash)
			elif ret[1] == "imbedded_simulate2":
				text += _("Simulate second partition (no write)")
				cmd = "%s -r -k -m2 -n '%s' > /dev/null 2>&1" % (ofgwrite_bin, dir_flash)
			elif ret[1] == "imbedded_standard2":
				text += _("Second partition")
				if emmc_multiboot:
					if 'mmcblk0p5' not in mount_part:
						os.system('umount -fl /dev/mmcblk0p5')
						os.system('mkfs.ext4 -F /dev/mmcblk0p5')
						self.stop_enigma = False
					cmd = "%s -r -k -m2 '%s' > /dev/null 2>&1" % (ofgwrite_bin, dir_flash)
				elif emmc_multiboot1:
					if 'mmcblk0p7' not in mount_part:
						os.system('umount -fl /dev/mmcblk0p7')
						os.system('mkfs.ext4 -F /dev/mmcblk0p7')
						self.stop_enigma = False
					cmd = "%s -r -k -m2 '%s' > /dev/null 2>&1" % (ofgwrite_bin, dir_flash)
			elif ret[1] == "imbedded_simulate3":
				text += _("Simulate third partition (no write)")
				cmd = "%s -r -k -m3 -n '%s' > /dev/null 2>&1" % (ofgwrite_bin, dir_flash)
			elif ret[1] == "imbedded_standard3":
				text += _("Third partition")
				if emmc_multiboot:
					if 'mmcblk0p7' not in mount_part:
						os.system('umount -fl /dev/mmcblk0p7')
						os.system('mkfs.ext4 -F /dev/mmcblk0p7')
						self.stop_enigma = False
				elif emmc_multiboot1:
					if 'mmcblk0p9' not in mount_part:
						os.system('umount -fl /dev/mmcblk0p9')
						os.system('mkfs.ext4 -F /dev/mmcblk0p9')
						self.stop_enigma = False
					cmd = "%s -r -k -m3 '%s' > /dev/null 2>&1" % (ofgwrite_bin, dir_flash)
			elif ret[1] == "imbedded_simulate4":
				text += _("Simulate fourth partition (no write)")
				cmd = "%s -r -k -m4 -n '%s' > /dev/null 2>&1" % (ofgwrite_bin, dir_flash)
			elif ret[1] == "imbedded_standard4":
				text += _("Fourth partition")
				if emmc_multiboot:
					if 'mmcblk0p9' not in mount_part:
						os.system('umount -fl /dev/mmcblk0p9')
						os.system('mkfs.ext4 -F /dev/mmcblk0p9')
						self.stop_enigma = False
				cmd = "%s -r -k -m4 '%s' > /dev/null 2>&1" % (ofgwrite_bin, dir_flash)
			else:
				return
			message = "echo -e '\n"
			message += _('NOT found files for flashing!\n')
			message += "'"
			if "simulate" in ret[1]:
				if self.founds:
					message = "echo -e '\n"
					message += _('Show only found image and mtd partitions.\n')
					message += "'"
			else:
				if self.founds:
					if len(self.imbeddedMiltiBoot) > 1 and not self.stop_enigma:
						message = "echo -e '\n"
						message += _('ofgwrite flashing ready.\n')
						message += _('please press exit to go back to the menu.\n')
						message += "'"
					else:
						message = "echo -e '\n"
						message += _('ofgwrite will stop enigma2 now to run the flash.\n')
						message += _('Your STB will freeze during the flashing process.\n')
						message += _('Please: DO NOT reboot your STB and turn off the power.\n')
						message += _('The image or kernel will be flashing and auto booted in few minutes.\n')
						message += "'"
			try:
				if os.path.exists(ofgwrite_bin):
					os.chmod(ofgwrite_bin, 0o755)
				else:
					self.session.open(MessageBox, _("'ofgwrite' not installed!"), MessageBox.TYPE_ERROR)
					return
			except:
				pass
			self.session.openWithCallback(self.doClosed, Console, text, cmdlist=[message, cmd])

	def doClosed(self):
		if (len(self.imbeddedMiltiBoot) > 1 and not self.stop_enigma) or self.dualboot:
			os.system('umount -fl /oldroot_bind')
			os.system('umount -fl /newroot')
			self.close()

	def keyRed(self):
		self.close()

	def keyYellow(self):
		if self["key_yellow"].getText() == _("Unzip"):
			filename = self.filelist.getFilename()
			if filename and filename.endswith(".zip"):
				self.session.openWithCallback(self.doUnzip, MessageBox, _("Do you really want to unpack %s ?") % filename, MessageBox.TYPE_YESNO)

	def doUnzip(self, answer):
		if answer is True:
			dirname = self.filelist.getCurrentDirectory()
			filename = self.filelist.getFilename()
			if dirname and filename:
				try:
					os.system('unzip -o %s%s -d %s' % (dirname, filename, dirname))
					self.filelist.refresh()
				except:
					pass


class SearchOMBfile(Screen):
	skin = """<screen name="SearchOMBfile" position="center,center" size="560,440" title=" " >
			<ePixmap pixmap="skin_default/buttons/red.png" position="0,0" size="140,40" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/green.png" position="140,0" size="140,40" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/yellow.png" position="280,0" size="140,40" alphatest="on" />
			<widget source="key_red" render="Label" position="0,0" zPosition="1" size="140,40" font="Regular;17" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" />
			<widget source="key_green" render="Label" position="140,0" zPosition="1" size="140,40" font="Regular;17" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" />
			<widget source="key_yellow" render="Label" position="280,0" zPosition="1" size="140,40" font="Regular;17" halign="center" valign="center" backgroundColor="#a08500" transparent="1" />
			<widget source="curdir" render="Label" position="5,50" size="550,20"  font="Regular;17" halign="left" valign="center" backgroundColor="background" transparent="1" noWrap="1" />
			<widget name="filelist" position="5,80" size="550,345" scrollbarMode="showOnDemand" />
		</screen>"""

	def __init__(self, session, curdir, matchingPattern=None, found_dir=''):
		Screen.__init__(self, session)

		self["Title"].setText(_("Select backup for add to OpenMultiboot"))
		self["key_red"] = StaticText(_("Cancel"))
		self["key_green"] = StaticText("")
		self["key_yellow"] = StaticText("")
		self["curdir"] = StaticText(_("current:  %s") % (curdir or ''))
		self.found_dir = found_dir
		self.model = ''
		self.txt = ''
		self.msg = None
		self.filelist = FileList(curdir, matchingPattern=matchingPattern, enableWrapAround=True)
		self.filelist.onSelectionChanged.append(self.__selChanged)
		self["filelist"] = self.filelist

		self["FilelistActions"] = ActionMap(["SetupActions", "ColorActions"],
			{
				"green": self.keyGreen,
				"red": self.keyRed,
				"yellow": self.keyYellow,
				"ok": self.keyOk,
				"cancel": self.keyRed
			})
		self.onLayoutFinish.append(self.__layoutFinished)

	def __layoutFinished(self):
		pass

	def getCurrentSelected(self):
		dirname = self.filelist.getCurrentDirectory()
		filename = self.filelist.getFilename()
		if not filename and not dirname:
			cur = ''
		elif not filename:
			cur = dirname
		elif not dirname:
			cur = filename
		else:
			if not self.filelist.canDescent() or len(filename) <= len(dirname):
				cur = dirname
			else:
				cur = filename
		return cur or ''

	def __selChanged(self):
		self["key_yellow"].setText("")
		self["key_green"].setText("")
		self["curdir"].setText(_("current:  %s") % (self.getCurrentSelected()))
		file_name = self.getCurrentSelected()
		try:
			if not self.filelist.canDescent() and file_name != '' and file_name != '/':
				filename = self.filelist.getFilename()
				if filename and filename.endswith(".zip"):
					self["key_yellow"].setText(_("Unzip"))
			elif self.filelist.canDescent() and file_name != '' and file_name != '/':
				self["key_green"].setText(_("Add to OMB"))
		except:
			pass

	def keyOk(self):
		if self.filelist.canDescent():
			self.filelist.descent()

	def keyGreen(self):
		if self["key_green"].getText() == _("Add to OMB"):
			dirname = self.filelist.getCurrentDirectory()
			if dirname:
				self.showparameterlist()

	def showparameterlist(self):
		if self["key_green"].getText() == _("Add to OMB"):
			dirname = self.getCurrentSelected()
			if dirname:
				founds = False
				backup_files = []
				no_backup_files = []
				text = _('For backup your receiver files are needed:\n')
				self.model = MODEL_NAME
				if BOX_NAME == 'all':
					if MODEL_NAME.startswith('fusion'):
						backup_files = [("oe_kernel.bin"), ("oe_rootfs.bin")]
						no_backup_files = ["kernel_cfe_auto.bin", "root_cfe_auto.jffs2", "root_cfe_auto.bin", "rootfs.bin", "kernel.bin", "rootfs.tar.bz2"]
					elif MODEL_NAME == "lunix3-4k" or MODEL_NAME == "lunix4k":
						backup_files = [("rootfs.tar.bz2"), ("oe_kernel.bin")]
						no_backup_files = ["kernel_cfe_auto.bin", "rootfs.bin", "root_cfe_auto.jffs2", "root_cfe_auto.bin"]
						text += 'oe_kernel.bin, rootfs.tar.bz2'
					elif (MODEL_NAME == "hd51" or MODEL_NAME == "sf4008" or MODEL_NAME == "vs1500" or MODEL_NAME == "et11000" or MODEL_NAME == "h7"):
						backup_files = [("kernel1.bin"), ("rootfs.tar.bz2"), ("kernel.bin")]
						no_backup_files = ["kernel_cfe_auto.bin", "rootfs.bin", "root_cfe_auto.jffs2", "root_cfe_auto.bin"]
						text += 'kernel.bin/kernel1.bin, rootfs.tar.bz2'
					else:
						backup_files = [("kernel.bin"), ("rootfs.bin")]
						no_backup_files = ["kernel_cfe_auto.bin", "root_cfe_auto.jffs2", "root_cfe_auto.bin", "rootfs.tar.bz2"]
						text += 'kernel.bin, rootfs.bin'
				elif BOX_NAME == "vu":
					if MODEL_NAME == "solo4k" or MODEL_NAME == "uno4k" or MODEL_NAME == "ultimo4k" or MODEL_NAME == "uno4kse" or MODEL_NAME == "zero4k" or MODEL_NAME == "duo4k":
						backup_files = ["kernel_auto.bin", "rootfs.tar.bz2"]
						no_backup_files = ["kernel.bin", "kernel_cfe_auto.bin", "root_cfe_auto.bin" "root_cfe_auto.jffs2", "rootfs.bin"]
						text += 'kernel_auto.bin, rootfs.tar.bz2'
					elif MODEL_NAME in ["duo2", "solose", "solo2", "zero"]:
						backup_files = ["kernel_cfe_auto.bin", "root_cfe_auto.bin"]
						no_backup_files = ["kernel.bin", "kernel_auto.bin", "root_cfe_auto.jffs2", "rootfs.bin", "rootfs.tar.bz2"]
						text += 'kernel_cfe_auto.bin, root_cfe_auto.bin'
					else:
						backup_files = ["kernel_cfe_auto.bin", "root_cfe_auto.jffs2"]
						no_backup_files = ["kernel.bin", "kernel_auto.bin", "root_cfe_auto.bin", "rootfs.bin", "rootfs.tar.bz2"]
						text += 'kernel_cfe_auto.bin, root_cfe_auto.jffs2'
				elif BOX_NAME == "dmm":
					backup_files = ["*.nfi"]
					text += '*.nfi'
					if MODEL_NAME == "dm900" or MODEL_NAME == "dm920":
						backup_files = [("kernel1.bin"), ("rootfs.tar.bz2"), ("kernel.bin")]
						no_backup_files = ["kernel_cfe_auto.bin", "rootfs.bin", "root_cfe_auto.jffs2", "root_cfe_auto.bin"]
						text += 'kernel.bin/kernel1.bin, rootfs.tar.bz2'
				elif BOX_NAME == "gigablue":
					if MODEL_NAME in ("gbquad4k", "gbue4k"):
						backup_files = [("kernel1.bin"), ("rootfs.tar.bz2"), ("kernel.bin")]
						no_backup_files = ["kernel_cfe_auto.bin", "rootfs.bin", "root_cfe_auto.jffs2", "root_cfe_auto.bin"]
						text += 'kernel.bin/kernel1.bin, rootfs.tar.bz2'
						self.model = MODEL_NAME == "gbquad4k" and "quad4k" or "ue4k"
				try:
					text += _('\nThe found files:')
					for name in os.listdir(dirname):
						if BOX_NAME == "dmm" and not (MODEL_NAME == "dm900" or MODEL_NAME == "dm920"):
							if filename.endswith(".nfi"):
								text += _("  %s (maybe ok)") % name
								founds = True
						elif name in backup_files:
							text += _("  %s (maybe ok)") % name
							founds = True
						if name in no_backup_files:
							text += _("  %s (maybe error)") % name
							founds = True
					if not founds:
						text += _(' nothing!')
				except:
					pass
				if founds and self.model:
					need_dir = "/%s/" % self.model
					if not dirname.endswith(need_dir):
						return
				if founds:
					if os.path.exists(zip_bin):
						self.session.openWithCallback(self.CallbackAddOMB, MessageBox, text + _("\nPack in zip archive current folder and add to '%s' OMB?") % (self.found_dir), MessageBox.TYPE_YESNO)
					else:
						self.session.open(MessageBox, _("'zip' not installed!"), MessageBox.TYPE_ERROR)

	def CallbackAddOMB(self, ret):
		if ret:
			self.msg = self.session.open(MessageBox, _("Please wait!\nGreating zip archive..."), MessageBox.TYPE_INFO, enable_input=False)
			self.pauseTimer = eTimer()
			self.pauseTimer.callback.append(self.runzipOMB)
			self.pauseTimer.start(500, True)

	def runzipOMB(self):
		dirname = self.filelist.getCurrentDirectory()
		txt = _("Error creating zip archive!")
		try:
			tstamp = time.strftime('%Y-%m-%d-%H:%M')
			try:
				name = about.getImageTypeString()
				image_name = name.replace(' ', '').replace('\n', '').replace('\l', '').replace('\t', '')
			except:
				image_name = ''
			zip_name = "backup_%s-%s-%s_usb.zip" % (image_name, self.model, tstamp)
			os.system("cd %s && %s -r %s/%s . -i /%s/* && cd" % (dirname, zip_bin, dirname, zip_name, self.model))
			current_file_zip = "%s%s" % (dirname, zip_name)
			if os.path.exists(current_file_zip):
				omb_file_zip = "%s/%s" % (self.found_dir, zip_name)
				os.system("mv %s %s" % (current_file_zip, omb_file_zip))
				if os.path.exists(omb_file_zip):
					txt = _("'%s' archive was successfully added to '%s' OMB!") % (zip_name, self.found_dir)
		except:
			pass
		if self.msg:
			self.msg.close()
		self.txt = txt
		self.pause_Timer = eTimer()
		self.pause_Timer.callback.append(self.postzipOMB)
		self.pause_Timer.start(200, True)

	def postzipOMB(self):
		self.session.open(MessageBox, self.txt, MessageBox.TYPE_INFO, timeout=15)

	def keyRed(self):
		self.close()

	def keyYellow(self):
		if self["key_yellow"].getText() == _("Unzip"):
			filename = self.filelist.getFilename()
			if filename and filename.endswith(".zip"):
				self.session.openWithCallback(self.doUnzip, MessageBox, _("Do you really want to unpack %s ?") % filename, MessageBox.TYPE_YESNO)

	def doUnzip(self, answer):
		if answer is True:
			dirname = self.filelist.getCurrentDirectory()
			filename = self.filelist.getFilename()
			if dirname and filename:
				try:
					os.system('unzip -o %s%s -d %s' % (dirname, filename, dirname))
					self.filelist.refresh()
				except:
					pass


def main(session, **kwargs):
	session.openWithCallback(doneConfiguring, FullBackupConfig)


def doneConfiguring(session, retval):
	"user has closed configuration, check new values...."
	global autoStartTimer
	if autoStartTimer is not None:
		autoStartTimer.update()

##################################
# Autostart section


class AutoStartTimer:
	def __init__(self, session):
		self.session = session
		self.timer = eTimer()
		self.timer.callback.append(self.onTimer)
		self.pause_timer = eTimer()
		self.pause_timer.callback.append(self.setPauseStart)
		self.pause_timer.startLongTimer(60)
		self.waitGreatetimer = eTimer()
		self.waitGreatetimer.timeout.get().append(self.checkStatusAfterBackup)

	def setPauseStart(self):
		try:
			config.plugins.fullbackup.after_create.value = False
			config.plugins.fullbackup.after_create.save()
			if os.path.exists("/tmp/.fullbackup"):
				try:
					os.remove("/tmp/.fullbackup")
				except:
					pass
			if getFPWasTimerWakeup() and config.plugins.fullbackup.enabled.value and config.plugins.fullbackup.deepstandby.value == "2":
				start_time = self.getWakeTime()
				now = int(time.time())
				now_day = time.localtime(now)
				cur_day = int(now_day.tm_wday)
				if start_time > 0 and 0 < start_time - now <= 300 and config.plugins.extra_fullbackup.day_backup[cur_day].value:
					recordings = self.session.nav.getRecordings()
					next_timer = False
					if not recordings:
						for timer in NavigationInstance.instance.RecordTimer.timer_list:
							if 0 < timer.begin - time.time() <= 60 * 5:
								next_timer = True
								continue
					if not recordings and not next_timer:
						if Standby.inStandby is None:
							Notifications.AddNotification(Standby.Standby)
						if not config.plugins.fullbackup.after_create.value:
							self.waitStandby_timer = eTimer()
							self.waitStandby_timer.timeout.get().append(self.checkStartStandbyStatus)
							self.waitStandby_timer.start(5000, True)
		except:
			pass
		self.update()

	def checkStartStandbyStatus(self):
		if Standby.inStandby:
			try:
				config.plugins.fullbackup.after_create.value = True
				config.plugins.fullbackup.after_create.save()
				Standby.inStandby.onClose.append(self.onLeaveStandbyForFullBackup)
			except:
				pass

	def onLeaveStandbyForFullBackup(self):
		try:
			if config.plugins.fullbackup.after_create.value:
				config.plugins.fullbackup.after_create.value = False
				config.plugins.fullbackup.after_create.save()
				self.waitGreatetimer.stop()
		except:
			pass

	def checkStatusAfterBackup(self):
		if config.plugins.fullbackup.after_create.value and Standby.inStandby and getFPWasTimerWakeup() and config.plugins.fullbackup.enabled.value and config.plugins.fullbackup.deepstandby.value == "2":
			if os.path.exists("/tmp/.fullbackup"):
				try:
					os.remove("/tmp/.fullbackup")
				except:
					pass
				start_deepstandy = True
				try:
					recordings = self.session.nav.getRecordings()
					next_rec_time = -1
					if not recordings:
						next_rec_time = self.session.nav.RecordTimer.getNextRecordingTime()
					if recordings or (next_rec_time > 0 and (next_rec_time - time.time()) < 300):
						return
				except:
					pass
				if fileExists("/usr/lib/enigma2/python/Plugins/Extensions/EPGRefresh/EPGRefresh.py") and fileExists("/usr/lib/enigma2/python/Plugins/Extensions/EPGRefresh/plugin.py"):
					try:
						deepstandy_options = config.plugins.epgrefresh.enabled.value and config.plugins.epgrefresh.wakeup.value and config.plugins.epgrefresh.afterevent.value
					except:
						deepstandy_options = False
					if deepstandy_options:
						try:
							now = time.localtime(time.time())
							begin = int(time.mktime(
								(now.tm_year, now.tm_mon, now.tm_mday,
								config.plugins.epgrefresh.begin.value[0],
								config.plugins.epgrefresh.begin.value[1],
								0, now.tm_wday, now.tm_yday, now.tm_isdst)
							))
							end = int(time.mktime(
								(now.tm_year, now.tm_mon, now.tm_mday,
								config.plugins.epgrefresh.end.value[0],
								config.plugins.epgrefresh.end.value[1],
								0, now.tm_wday, now.tm_yday, now.tm_isdst)
							))
							if begin >= end:
								end += 86400
							if 0 < begin - time.time() <= 60 * 5 or abs(time.time() - begin) < 900 and end > time.time():
								start_deepstandy = False
								if fileExists("/usr/lib/enigma2/python/Plugins/Extensions/EPGRefresh/EPGSaveLoadConfiguration.py"):
									try:
										cur_day = int(now.tm_wday)
										wakeup_day = config.plugins.epgrefresh_extra.day_refresh[cur_day].value
									except:
										wakeup_day = False
									if not wakeup_day:
										start_deepstandy = True
						except:
							pass
				if fileExists("/usr/lib/enigma2/python/Plugins/Extensions/EPGImport/EPGImport.py") and fileExists("/usr/lib/enigma2/python/Plugins/Extensions/EPGImport/plugin.py"):
					now = time.localtime(time.time())
					cur_day = int(now.tm_wday)
					try:
						if config.plugins.epgimport.deepstandby.value == 'wakeup':
							start = True
						else:
							start = False
						deepstandby_options = start and config.plugins.epgimport.enabled.value and config.plugins.epgimport.shutdown.value and config.plugins.extra_epgimport.day_import[cur_day].value
					except:
						deepstandby_options = False
					if deepstandby_options:
						try:
							begin = int(time.mktime(
								(now.tm_year, now.tm_mon, now.tm_mday,
								config.plugins.epgimport.wakeup.value[0],
								config.plugins.epgimport.wakeup.value[1],
								0, now.tm_wday, now.tm_yday, now.tm_isdst)
							))
							start_epgimport = False
							if begin > int(time.time()) and begin - int(time.time()) < 300:
								start_epgimport = True
								start_deepstandy = False
							if not start_epgimport:
								try:
									from Plugins.Extensions.EPGImport.plugin import autoStartTimer as EPGimport_autoStartTimer, epgimport
								except:
									pass
								else:
									try:
										if EPGimport_autoStartTimer is not None and epgimport.isImportRunning() and config.plugins.epgimport.deepstandby_afterimport.value:
											start_deepstandy = False
									except:
										pass
						except:
							pass
				if start_deepstandy and Standby.inTryQuitMainloop == False:
					self.session.open(Standby.TryQuitMainloop, 1)

	def getWakeTime(self):
		if config.plugins.fullbackup.enabled.value:
			clock = config.plugins.fullbackup.wakeup.value
			nowt = time.time()
			now = time.localtime(nowt)
			return int(time.mktime((now.tm_year, now.tm_mon, now.tm_mday,
					clock[0], clock[1], 0, now.tm_wday, now.tm_yday, now.tm_isdst)))
		else:
			return -1

	def getStatus(self):
		wake_up = self.getWakeTime()
		now_t = time.time()
		now = int(now_t)
		now_day = time.localtime(now_t)
		if wake_up > 0:
			cur_day = int(now_day.tm_wday)
			wakeup_day = WakeupDayOfWeek()
			if wakeup_day == -1:
				return -1
			if wake_up < now:
				wake_up += 86400 * wakeup_day
			else:
				if not config.plugins.extra_fullbackup.day_backup[cur_day].value:
					wake_up += 86400 * wakeup_day
		else:
			wake_up = -1
		return wake_up

	def update(self, atLeast=0):
		self.timer.stop()
		wake = self.getWakeTime()
		now_t = time.time()
		now = int(now_t)
		now_day = time.localtime(now_t)
		if wake > 0:
			cur_day = int(now_day.tm_wday)
			wakeup_day = WakeupDayOfWeek()
			if wakeup_day == -1:
				return -1
			if wake < now + atLeast:
				wake += 86400 * wakeup_day
			else:
				if not config.plugins.extra_fullbackup.day_backup[cur_day].value:
					wake += 86400 * wakeup_day
			next = wake - now
			self.timer.startLongTimer(next)
		else:
			wake = -1
		return wake

	def onTimer(self):
		self.timer.stop()
		now = int(time.time())
		wake = self.getWakeTime()
		atLeast = 0
		if abs(wake - now) < 60:
			runCleanup()
			if config.plugins.fullbackup.message.value == "1":
				if Standby.inStandby is None:
					self.session.open(MessageBox, _("Starting Automatic Full Backup!\nOptions control panel will not be available 5-7 minutes.\nPlease wait ..."), MessageBox.TYPE_INFO, timeout=15)
				self.runTimer = eTimer()
				self.runTimer.callback.append(self.startBackup)
				self.runTimer.start(18000, True)
			elif config.plugins.fullbackup.message.value == "2":
				if Standby.inStandby is None:
					self.session.openWithCallback(self.confirmStartBackup, MessageBox, _("In the next few seconds to start Automatic Full Backup!\nOptions control panel will not be available 5-7 minutes.\nRun backup now?"), MessageBox.TYPE_YESNO, timeout=15)
				else:
					self.runTimer = eTimer()
					self.runTimer.callback.append(self.startBackup)
					self.runTimer.start(18000, True)
			else:
				self.runTimer = eTimer()
				self.runTimer.callback.append(self.startBackup)
				self.runTimer.start(18000, True)
			atLeast = 60
		self.update(atLeast)

	def startBackup(self):
		try:
			if config.plugins.fullbackup.after_create.value and getFPWasTimerWakeup() and config.plugins.fullbackup.enabled.value and config.plugins.fullbackup.deepstandby.value == "2" and Standby.inStandby:
				if not self.waitGreatetimer.isActive():
					self.waitGreatetimer.startLongTimer(900)
		except:
			pass
		runBackup()

	def confirmStartBackup(self, answer):
		if answer:
			self.runTimer = eTimer()
			self.runTimer.callback.append(self.startBackup)
			self.runTimer.start(3000, True)


class DaysProfile(ConfigListScreen, Screen):
	skin = """
			<screen position="center,center" size="400,230" title="Days Profile" >
			<widget name="config" position="0,0" size="400,180" scrollbarMode="showOnDemand" />
			<widget name="key_red" position="0,190" size="140,40" valign="center" halign="center" zPosition="4"  foregroundColor="white" font="Regular;18" transparent="1"/>
			<widget name="key_green" position="140,190" size="140,40" valign="center" halign="center" zPosition="4"  foregroundColor="white" font="Regular;18" transparent="1"/>
			<ePixmap name="red"    position="0,190"   zPosition="2" size="140,40" pixmap="skin_default/buttons/red.png" transparent="1" alphatest="on" />
			<ePixmap name="green"  position="140,190" zPosition="2" size="140,40" pixmap="skin_default/buttons/green.png" transparent="1" alphatest="on" />
		</screen>"""

	def __init__(self, session, args=0):
		self.session = session
		Screen.__init__(self, session)

		self.list = []

		for i in range(7):
			self.list.append(getConfigListEntry(weekdays[i], config.plugins.extra_fullbackup.day_backup[i]))

		ConfigListScreen.__init__(self, self.list)

		self["key_red"] = Button(_("Cancel"))
		self["key_green"] = Button(_("Save"))
		self["setupActions"] = ActionMap(["SetupActions", "ColorActions"],
		{
			"red": self.cancel,
			"green": self.save,
			"save": self.save,
			"cancel": self.cancel,
			"ok": self.save,
		}, -2)
		self.onLayoutFinish.append(self.setCustomTitle)

	def setCustomTitle(self):
		self.setTitle(_("Days Profile"))

	def save(self):
		if not config.plugins.extra_fullbackup.day_backup[0].value:
			if not config.plugins.extra_fullbackup.day_backup[1].value:
				if not config.plugins.extra_fullbackup.day_backup[2].value:
					if not config.plugins.extra_fullbackup.day_backup[3].value:
						if not config.plugins.extra_fullbackup.day_backup[4].value:
							if not config.plugins.extra_fullbackup.day_backup[5].value:
								if not config.plugins.extra_fullbackup.day_backup[6].value:
									self.session.open(MessageBox, _("You may not use this settings!\nAt least one day a week should be included!"), MessageBox.TYPE_INFO, timeout=6)
									return
		for x in self["config"].list:
			x[1].save()
		self.close()

	def cancel(self):
		for x in self["config"].list:
			x[1].cancel()
		self.close()


def WakeupDayOfWeek():
	start_day = -1
	try:
		now = time.time()
		now_day = time.localtime(now)
		cur_day = int(now_day.tm_wday)
	except:
		cur_day = -1

	if cur_day >= 0:
		for i in range(1, 8):
			if config.plugins.extra_fullbackup.day_backup[(cur_day + i) % 7].value:
				return i
	return start_day


class GreatingManualBackup(MessageBox):
	def __init__(self, session, dir):
		try:
			#if MODEL_NAME == "hd51" or MODEL_NAME == "vs1500" or MODEL_NAME == "h7":
			#	list = [(_("Yes"), True), (_("Yes") + _(" as recovery"), "recovery"), (_("No"), False)]
			#	MessageBox.__init__(self, session, text=_("Do you really want to create a full backup in directory %s ?") % dir, list=list)
			#else:
			MessageBox.__init__(self, session, _("Do you really want to create a full backup in directory %s ?") % dir, MessageBox.TYPE_YESNO)
		except:
			MessageBox.__init__(self, session, _("Do you really want to create a full backup in directory %s ?") % dir, MessageBox.TYPE_YESNO)
		self.skinName = "MessageBox"


def msgManualBackupClosed(ret, curdir=None):
	if ret and curdir is not None:
		try:
			cmd = ''
			if BOX_NAME == 'none':
				cmd = "echo 'Your box not supported!'\n"
			else:
				if not check_hdd(curdir):
					return
				cmd = BACKUP_SCRIPT
				if BOX_NAME == 'dmm':
					cmd = DREAM_BACKUP_SCRIPT
					if MODEL_NAME == "dm900" or MODEL_NAME == "dm920":
						cmd = VU4K_BACKUP_SCRIPT
				elif (BOX_NAME == 'vu' and (MODEL_NAME == "solo4k" or MODEL_NAME == "uno4k" or MODEL_NAME == "ultimo4k" or MODEL_NAME == "uno4kse" or MODEL_NAME == "zero4k" or MODEL_NAME == "duo4k" or MODEL_NAME == "duo4kse")) or MODEL_NAME == "lunix4k" or MODEL_NAME == "lunix3-4k" or MODEL_NAME == "gbquad4k" or MODEL_NAME == "gbue4k":
					cmd = VU4K_BACKUP_SCRIPT
				elif MODEL_NAME == "hd51" or MODEL_NAME == "sf4008" or MODEL_NAME == "vs1500" or MODEL_NAME == "et11000" or MODEL_NAME == "h7":
					cmd = HD51_BACKUP_SCRIPT
				cmd += " %s" % curdir
				if os.path.exists(zip_bin):
					cmd += " %s" % zip_bin
				else:
					cmd += "none"
				try:
					name = about.getImageTypeString()
					image_name = name.replace(' ', '').replace('\n', '').replace('\l', '').replace('\t', '')
				except:
					image_name = 'unknown'
				cmd += " %s" % image_name
				if ret == "recovery":
					cmd += " %s" % ret
			text = _('Console log') + _(' - OK show/nide')
			global _session
			if _session is not None:
				_session.open(BackupConsole, text, [cmd], dir=curdir)
		except:
			pass


def menu(menuid, **kwargs):
	if menuid == "shutdown" and config.plugins.fullbackup.multiboot_switcher_standbymenu.value:
		return [(_("MultiBoot switcher"), openMultiBootSwitcher, "multiboot_switcher", 4)]
	return []


from .MultiBootSwitcher import MultiBootSwitcher


def openMultiBootSwitcher(session, **kwargs):
	session.open(MultiBootSwitcher)


def getNextWakeup():
	if autoStartTimer:
		if config.plugins.fullbackup.enabled.value and config.plugins.fullbackup.deepstandby.value != "0" and config.plugins.fullbackup.where.value != 'none':
			return autoStartTimer.getStatus()
	return -1


def autostart(reason, session=None, **kwargs):
	global autoStartTimer
	global _session
	if reason == 0:
		if session is not None:
			_session = session
			if autoStartTimer is None:
				autoStartTimer = AutoStartTimer(session)


def filescan_open(list, session, **kwargs):
	try:
		file = list[0].path
		dir = os.path.split(file)[0]
		print('[FullBackup] current dir is %s' % dir)
		if dir != "" and dir != "/" and "/media/" in dir:
			session.openWithCallback(boundFunction(msgManualBackupClosed, curdir=dir), GreatingManualBackup, dir)
		else:
			session.open(MessageBox, _("Read error current dir, sorry."), MessageBox.TYPE_ERROR)
	except:
		print("[FullBackup] read error current dir, sorry")


def start_filescan(**kwargs):
	if os.path.exists("/proc/hisi"):
		return []
	from Components.Scanner import Scanner, ScanPath
	if not config.plugins.fullbackup.autoscan.value:
		return []
	return \
		Scanner(mimetypes=["application/x-full-backup"],
			paths_to_scan=[
					ScanPath(path="", with_subdirs=False),
				],
			name="Full Backup",
			description=_("Create a full backup image"),
			openfnc=filescan_open,
		)


description = _("Full backup for all receivers") + PLUGIN_VERSION


def Plugins(**kwargs):
	if os.path.exists("/proc/hisi"):
		return []
	return [
		PluginDescriptor(
			name="Automatic Full Backup",
			description=description,
			where=[PluginDescriptor.WHERE_AUTOSTART, PluginDescriptor.WHERE_SESSIONSTART],
			fnc=autostart,
			wakeupfnc=getNextWakeup
		),
		PluginDescriptor(
			name=_("Automatic Full Backup"),
			description=description,
			where=PluginDescriptor.WHERE_PLUGINMENU,
			icon='plugin.png',
			fnc=main
		),
		PluginDescriptor(
			name="Automatic Full Backup",
			where=PluginDescriptor.WHERE_FILESCAN,
			fnc=start_filescan
		),
		#PluginDescriptor(
		#	name="MultiBoot switcher",
		#	where=PluginDescriptor.WHERE_MENU,
		#	fnc=menu
		#),
	]
