from __future__ import print_function
from Screens.Screen import Screen
from Screens.Standby import TryQuitMainloop
from Screens.MessageBox import MessageBox
from Screens.VirtualKeyBoard import VirtualKeyBoard
from Components.ActionMap import ActionMap
from Components.ConfigList import ConfigListScreen
from Components.Label import Label
from Components.Sources.StaticText import StaticText
import os
from enigma import eTimer
from .plugin import MODEL_NAME, _


def getextdevices(ext):
	cmd = 'blkid -t TYPE=%s -o device' % ext
	try:
		extdevices = os.popen(cmd).read().replace('\n', ',').rstrip(",")
	except:
		extdevices = ""
	if extdevices:
		extdevices = [x.strip() for x in extdevices.split(",")]
	return extdevices


class MultiBootSwitcher(ConfigListScreen, Screen):
	skin = """
		<screen name="MultiBootSwitcher" position="center,center" size="600,280"  flags="wfNoBorder" title="MultiBoot STARTUP switcher" backgroundColor="transparent">
			<eLabel name="b" position="0,0" size="600,280" backgroundColor="#00ffffff" zPosition="-2" />
			<eLabel name="a" position="1,1" size="598,278" backgroundColor="#00000000" zPosition="-1" />
			<eLabel name="line" position="1,69" size="598,1" backgroundColor="#00ffffff" zPosition="1" />
			<widget source="Title" render="Label" position="10,10" foregroundColor="#00ffffff" size="580,35" halign="center" font="Regular; 30" backgroundColor="#00000000" />
			<widget source="config" render="Label" position="10,90" size="580,30" font="Regular; 26" backgroundColor="#00000000" foregroundColor="#00ffffff" zPosition="1" />
			<widget source="options" render="Label" position="10,132" size="580,25" font="Regular; 22" backgroundColor="#00000000" foregroundColor="#00ffffff" />
			<widget name="description" position="10,170" size="580,23" font="Regular; 18" foregroundColor="#00ffffff" backgroundColor="#00000000" valign="center" />
			<widget name="curbootmode" position="10,200" size="580,23" font="Regular; 18" foregroundColor="#00ffffff" backgroundColor="#00000000" valign="center" />
			<ePixmap position="555,47" size="35,25" zPosition="2" pixmap="/usr/share/enigma2/skin_default/buttons/key_info.png" alphatest="blend" />
			<widget source="key_red" render="Label" position="35,242" size="170,30" noWrap="1" zPosition="1" valign="center" font="Regular; 18" halign="left" backgroundColor="#00000000" foregroundColor="#00ffffff" />
			<widget source="key_green" render="Label" position="228,242" size="170,30" noWrap="1" zPosition="1" valign="center" font="Regular; 18" halign="left" backgroundColor="#00000000" foregroundColor="#00ffffff" />
			<widget source="key_yellow" render="Label" position="421,242" size="170,30" noWrap="1" zPosition="1" valign="center" font="Regular; 18" halign="left" backgroundColor="#00000000" foregroundColor="#00ffffff" />
			<eLabel position="25,239" size="6,40" backgroundColor="#00e61700" />
			<eLabel position="216,239" size="6,40" backgroundColor="#0061e500" />
			<eLabel position="407,239" size="6,40" backgroundColor="#00e5b243" />
		</screen>"""

	def __init__(self, session):
		Screen.__init__(self, session)
		self.setup_title = _("MultiBoot STARTUP switcher")
		self.skin = MultiBootSwitcher.skin

		self["key_red"] = StaticText(_("Cancel"))
		self["key_green"] = StaticText(_("Save"))
		self["key_yellow"] = StaticText(_("Rename"))
		self["config"] = StaticText()
		self["options"] = StaticText()
		self["description"] = Label()
		self["curbootmode"] = Label()

		self["actions"] = ActionMap(["InfobarEPGActions", "WizardActions", "SetupActions", "ColorActions"],
		{
			"left": self.left,
			"right": self.right,
			"up": self.up,
			"down": self.down,
			"green": self.save,
			"red": self.cancel,
			"yellow": self.rename,
			"cancel": self.cancel,
			#"ok": self.save,
			"showEventInfo": self.info,
			"showEventInfoSingleEPG": self.info,
		}, -2)
		self.MultiBootSelector = False
		self.waitTimer = eTimer()
		self.waitTimer.callback.append(self.initWaitcheckMount)
		self.waitTimer.start(500, True)
		self.curBootmode()
		self.onLayoutFinish.append(self.layoutFinished)

	def initWaitcheckMount(self):
		self.MultiBootSelector = self.checkMount()
		if self.MultiBootSelector:
			self.getCurrent()

	def curBootmode(self):
		curbootmode = self.readlineFile(('/sys/module/%s/parameters/boxmode') % MODEL_NAME)
		if curbootmode:
			self["curbootmode"].setText(_("Current load boxmode: %s") % str(curbootmode))

	def info(self):
		if not self.MultiBootSelector:
			return
		message = (
			#message 0
			_("*** boxmode=1 (Standard) ***\n\n" +
			"+++ Features +++\n" +
			"3840x2160p60 10-bit HEVC, 3840x2160p60 8-bit VP9, 1920x1080p60 8-bit AVC,\nMAIN only (no PIP), Limited display usages, UHD only (no SD),\nNo multi-PIP, No transcoding\n\n" +
			"--- Restrictions ---\n" +
			"Decoder 0: 3840x2160p60 10-bit HEVC, 3840x2160p60 8-bit VP9, 1920x1080p60 8-bit AVC\n" +
			"OSD Grafic 0: 1080p60 32 bit ARGB\n" +
			"Display 0 Encode Restrictions: 3840x2160p60 12-bit 4:2:0 (HDMI),\n3840x2160p60 12-bit 4:2:2 (HDMI), 3840x2160p60 8-bit 4:4:4 (HDMI),\n1920x1080p60 (component), Only one display format at a time\n\n" +
			"If you want 1080p60 component, HDMI also needs to be 1080p60."),
			#message 1
			_("*** boxmode=12 (Experimental) ***\n\n" +
			"+++ Features +++\n" +
 			"3840x2160p50 10-bit decode for MAIN, 1080p25/50i PIP support, HDMI input (if available),\n UHD display only, No SD display, No transcoding\n\n" +
			"--- Restrictions ---\n" +
			"Decoder 0: 3840x2160p50 10-bit HEVC, 3840x2160p50 8-bit VP9,\n1920x1080p50 8-bit AVC/MPEG\n" +
 			"Decoder 1: 1920x1080p25/50i 10-bit HEVC, 1920x1080p25/50i 8-bit VP9/AVC/MPEG2,\nHDMI In (if available), 3840x2160p50\n" +
			"OSD Graphic 0 (UHD): 1080p50 32-bit ARGB\n" +
			"Window 0 (MAIN/UHD): Limited display capabilities, 1080i50 10-bit de-interlacing\n" +
			"Multi-PIP mode (3x): Enigma2 supported no multi-PIP\n" +
			"Window 1 (PIP/UHD) (Enigma2 PIP Mode): Up to 1/2 x 1/2 screen display, 576i50 de-interlacing\n" +
			"Display 0 (UHD) Encode Restrictions: 3840x2160p50"),
			#message 2
			_("placeholder message 2"),
			)

		if not self.option_enabled:
			idx = 0
			blv = ''
			for x in self.bootloaderList:
				if idx:
					blv += ', '
				blv += x
				idx += 1
			message = (_("Your box needs Bootloaderversion(s)\n\n%s\n\nto make compatible with Bootoptions!") % blv,)
		self.session.open(MessageBox, message[self.option], MessageBox.TYPE_INFO)

	def rename(self):
		if not self.MultiBootSelector:
			return
		if self.list:
			self.oldname = self.list[self.selection]
			if self.oldname:
				self.session.openWithCallback(self.renameCB, VirtualKeyBoard, title=_("Please enter new name:"), text=self.oldname)

	def renameCB(self, newname):
		if newname and newname != 'bootname' and newname != self.oldname:
			if not os.path.exists('/boot/%s' % newname) and os.path.isfile('/boot/%s' % self.oldname):
				ret = os.system("mv -fn '/boot/%s' '/boot/%s'" % (self.oldname, newname))
				if ret:
					self.session.open(MessageBox, _('Rename failed!'), MessageBox.TYPE_ERROR)
				else:
					bootname = self.readlineFile('/boot/bootname').split('=')
					if len(bootname) == 2 and bootname[1] == self.oldname:
						self.writeFile('/boot/bootname', '%s=%s' % (bootname[0], newname))
						self.getCurrent()
						return
					elif self.bootname == self.oldname:
						self.getCurrent()
						return
					self.list[self.selection] = newname
					self["config"].setText(_("Select Image: %s") % (self.list[self.selection] + self.getNumberPartition()))
			else:
				if not os.path.exists('/boot/%s' % self.oldname):
					self.getCurrent()
					txt = _("File not found - rename failed!")
				else:
					txt = _("Name already exists - rename failed!")
				self.session.open(MessageBox, txt, MessageBox.TYPE_ERROR)

	def writeFile(self, FILE, DATA):
		try:
			f = open(FILE, 'w')
			f.write(DATA)
			f.close()
			return True
		except IOError:
			print("[MultiBoot switcher] write error file: %s" % FILE)
			return False

	def readlineFile(self, FILE):
		data = ''
		if os.path.isfile(FILE):
			try:
				f = open(FILE, 'r')
				data = f.readline().replace('\n', '')
				f.close()
			except:
				print("[MultiBoot switcher] error read file: %s" % FILE)
		return data

	def getCurrent(self):
		'''
		#default
		Image 1: boot emmcflash0.kernel1 'root=/dev/mmcblk0p3 rw rootwait'
		Image 2: boot emmcflash0.kernel2 'root=/dev/mmcblk0p5 rw rootwait'
		Image 3: boot emmcflash0.kernel3 'root=/dev/mmcblk0p7 rw rootwait'
		Image 4: boot emmcflash0.kernel4 'root=/dev/mmcblk0p9 rw rootwait'
		#options
		Standard:     hd51_4.boxmode=1 (or no option)
		Experimental: hd51_4.boxmode=12
		#example
		boot emmcflash0.kernel1 'root=/dev/mmcblk0p3 rw rootwait hd51_4.boxmode=1'
		'''

		self.optionsList = (('boxmode=1', _('2160p60 without PiP (default)')), ('boxmode=12', _('2160p50 with PiP')))
		self.bootloaderList = ('v1.07-r19', 'v1.07-r21', 'v1.07-r35')

		#for compatibility to old or other images set 'self.enable_bootnamefile = False'
		#if 'False' and more as on file with same kernel exist is possible no exact matching found (only to display)
		self.enable_bootnamefile = False
		if not self.enable_bootnamefile and os.path.isfile('/boot/bootname'):
			os.system("rm -f /boot/bootname")

		self.list = self.list_files("/boot")
		self.option_enabled = self.readlineFile('/sys/firmware/devicetree/base/bolt/tag').replace('\x00', '') in self.bootloaderList

		boot = self.readlineFile('/boot/STARTUP')
		bootname = self.readlineFile('/boot/bootname').split('=')

		self.selection = None
		self.option = 0

		#read name from bootname file
		if len(bootname) == 2:
			idx = 0
			for x in self.list:
				if x == bootname[1]:
					self.selection = idx
					bootname = x
					break
				idx += 1
			if self.selection is None:
				idx = 0
				for x in self.list:
					if x == bootname[0]:
						self.selection = idx
						bootname = x
						break
					idx += 1
		#verify bootname
		if bootname in self.list:
			line = self.readlineFile('/boot/%s' % bootname)
			if line[22:23] != boot[22:23]:
				self.selection = None
		else:
			self.selection = None
		#bootname searching ...
		if self.selection is None:
			idx = 0
			for x in self.list:
				line = self.readlineFile('/boot/%s' % x)
				if line[22:23] == boot[22:23]:
					bootname = x
					self.selection = idx
					break
				idx += 1
		#bootname not found
		if self.selection is None:
			bootname = _('unknown')
			self.selection = 0
		self.bootname = bootname

		#read current boxmode
		try:
			bootmode = boot.split('rootwait', 1)[1].split('boxmode', 1)[1].split("'", 1)[0].split('=', 1)[1].replace(' ', '')
		except IndexError:
			bootmode = ""
		#find and verify current boxmode
		if self.option_enabled:
			idx = 0
			for x in self.optionsList:
				if bootmode and bootmode == x[0].split('=')[1]:
					self.option = idx
					break
				elif x[0] + "'" in boot or x[0] + " " in boot:
					self.option = idx
					break
				idx += 1

		if bootmode and bootmode != self.optionsList[self.option][0].split('=')[1]:
			bootoption = ', boxmode=' + bootmode + _(" (unknown mode)")
		elif self.option_enabled:
			bootoption = ', ' + self.optionsList[self.option][0]
		else:
			bootoption = ''
		try:
			image = _('Image %s') % (int(boot[22:23]))
		except:
			image = _("Unable to read image number")

		self.startup()
		self.startup_option()
		self["description"].setText(_("Current bootsettings: %s (%s)%s") % (bootname, image, bootoption))

	def layoutFinished(self):
		self.setTitle(self.setup_title)

	def installUtilblkid(self):
		self.session.openWithCallback(self.installUtilblkidCallback, MessageBox, _("Install util-linux-blkid?"), MessageBox.TYPE_YESNO)

	def installUtilblkidCallback(self, answer):
		if answer:
			os.system("opkg update && opkg install util-linux-blkid")
			self.close()

	def checkMount(self):
		if not os.path.exists("/sbin/blkid.util-linux"):
			self.installUtilblkid()
			self["config"].setText(_("Warning!Please install util-linux-blkid."))
			return False
		if not os.path.ismount("/boot") or not os.path.isfile("/boot/STARTUP"):
			try:
				os.mkdir("/boot")
			except OSError:
				pass
			ret = os.system("mount -t vfat /dev/mmcblk0p1 /boot")
			if not os.path.ismount("/boot"):
				return False
		if os.path.ismount("/boot") and not os.path.isfile("/boot/STARTUP"):
			ret = os.system("mount -t vfat /dev/mmcblk0p1 /boot")
			if not os.path.isfile("/boot/STARTUP"):
				return False
		return True

	def startup_option(self):
		if self.option_enabled:
			self["options"].setText(_("Select bootoption: %s") % self.optionsList[self.option][1])
		elif 'up' in self["actions"].actions:
			self["options"].setText(_("Select bootoption: not supported - see info"))
			del self["actions"].actions['up']
			del self["actions"].actions['down']

	def startup(self):
		if not self.MultiBootSelector:
			return
		if len(self.list):
			self["config"].setText(_("Select Image: %s") % (self.list[self.selection] + self.getNumberPartition()))
		elif 'left' in self["actions"].actions:
			self["config"].setText(_("Select Image: %s") % _("no image found"))
			del self["actions"].actions['left']
			del self["actions"].actions['right']
			del self["actions"].actions['green']
			del self["actions"].actions['yellow']
			#del self["actions"].actions['ok']

	def getNumberPartition(self):
		part = ""
		if len(self.list):
			try:
				cur = self.readlineFile('/boot/%s' % self.list[self.selection])
				if cur:
					temp = cur.split(' ')
					device = temp[4].split("=")[1]
					if '/dev/mmcblk0p3' in device:
						part = " (I)"
					elif '/dev/mmcblk0p5' in device:
						part = " (II)"
					elif '/dev/mmcblk0p7' in device:
						part = " (III)"
					elif '/dev/mmcblk0p9' in device:
						part = " (IV)"
			except:
				pass
		return part

	def checkBootEntry(self, ENTRY):
		try:
			ret = False
			temp = ENTRY.split(' ')
			#read kernel, root as number and device name
			kernel = int(temp[1].split("emmcflash0.kernel")[1])
			root = int(temp[4].split("root=/dev/mmcblk0p")[1])
			device = temp[4].split("=")[1]
			#read boxmode and new boxmode settings
			cmdx = 7
			cmd4 = "rootwait'"
			bootmode = '1'
			if 'boxmode' in ENTRY:
				cmdx = 8
				cmd4 = "rootwait"
				bootmode = temp[7].split("%s_4.boxmode=" % MODEL_NAME)[1].replace("'", '')
			setmode = self.optionsList[self.option][0].split('=')[1]
			#verify entries
			if cmdx != len(temp) or 'boot' != temp[0] or 'rw' != temp[5] or cmd4 != temp[6] or kernel != root - kernel - 1 or "'" != ENTRY[-1:]:
				print("[MultiBoot switcher] Command line in '/boot/STARTUP' - problem with not matching entries!")
				ret = True
			#verify length
			elif ('boxmode' not in ENTRY and len(ENTRY) > 96) or ('boxmode' in ENTRY and len(ENTRY) > 115):
				print("[MultiBoot switcher] Command line in '/boot/STARTUP' - problem with line length!")
				ret = True
			#verify boxmode
			elif bootmode != setmode and not self.option_enabled:
				print("[MultiBoot switcher] Command line in '/boot/STARTUP' - problem with unsupported boxmode!")
				ret = True
			#verify device
			elif not device in getextdevices("ext4"):
				print("[MultiBoot switcher] Command line in '/boot/STARTUP' - boot device not exist!")
				ret = True
		except:
			print("[MultiBoot switcher] Command line in '/boot/STARTUP' - unknown problem!")
			ret = True
		return ret

	def save(self):
		if not self.MultiBootSelector:
			return
		error = True
		newboot = self.readlineFile('/boot/%s' % self.list[self.selection])
		if newboot:
			temp = newboot.split(' ')
			device = temp[4].split("=")[1]
			os.system("mkdir /tmp/testimage")
			os.system("mount %s /tmp/testimage" % device)
			if os.path.isfile('/tmp/testimage/usr/bin/enigma2'):
				error = False
				self.saved()
			os.system("umount /tmp/testimage")
		if error:
			self.session.open(MessageBox, _("Error reading image from file '/boot/%s'!\nPlease flashing another image for this partition.") % self.list[self.selection], MessageBox.TYPE_ERROR)

	def saved(self):
		print("[MultiBoot switcher] select new startup: ", self.list[self.selection])
		ret = os.system("cp -f '/boot/%s' /boot/STARTUP" % self.list[self.selection])
		if ret:
			self.session.open(MessageBox, _("File '/boot/%s' copy to '/boot/STARTUP' failed!") % self.list[self.selection], MessageBox.TYPE_ERROR)
			self.getCurrent()
			return

		writeoption = already = failboot = False
		newboot = boot = self.readlineFile('/boot/STARTUP')

		if self.checkBootEntry(boot):
			failboot = True
		elif self.option_enabled:
			for x in self.optionsList:
				if (x[0] + "'" in boot or x[0] + " " in boot) and x[0] != self.optionsList[self.option][0]:
					newboot = boot.replace(x[0], self.optionsList[self.option][0])
					if self.optionsList[self.option][0] == "boxmode=1":
						newboot = newboot.replace("520M@248M", "440M@328M")
						newboot = newboot.replace("200M@768M", "192M@768M")
					elif self.optionsList[self.option][0] == "boxmode=12":
						newboot = newboot.replace("440M@328M", "520M@248M")
						newboot = newboot.replace("192M@768M", "200M@768M")
					writeoption = True
					break
				elif (x[0] + "'" in boot or x[0] + " " in boot) and x[0] == self.optionsList[self.option][0]:
					already = True
					break
			if not (writeoption or already):
				if "boxmode" in boot:
					failboot = True
				elif self.option:
					newboot = boot.replace("rootwait", "rootwait %s_4.%s" % (MODEL_NAME, self.optionsList[self.option][0]))
					if self.optionsList[self.option][0] == "boxmode=1":
						newboot = newboot.replace("520M@248M", "440M@328M")
						newboot = newboot.replace("200M@768M", "192M@768M")
					elif self.optionsList[self.option][0] == "boxmode=12":
						newboot = newboot.replace("440M@328M", "520M@248M")
						newboot = newboot.replace("192M@768M", "200M@768M")
					writeoption = True

		if self.enable_bootnamefile:
			if failboot:
				self.writeFile('/boot/bootname', 'STARTUP_1=STARTUP_1')
			else:
				self.writeFile('/boot/bootname', '%s=%s' % ('STARTUP_%s' % MODEL_NAME, boot[22:23], self.list[self.selection]))

		message = _("Do you want to reboot now with selected image?")
		if failboot:
			print("[MultiBoot switcher] wrong bootsettings: " + boot)
			if '/dev/mmcblk0p3' in getextdevices("ext4"):
				if self.writeFile('/boot/STARTUP', "boot emmcflash0.kernel1 'brcm_cma=440M@328M brcm_cma=192M@768M root=/dev/mmcblk0p3 rw rootwait'"):
					txt = _("Next boot will start from Image 1.")
				else:
					txt = _("Can not repair file %s") % ("'/boot/STARTUP'") + "\n" + _("Caution, next boot is starts with these settings!") + "\n"
			else:
				txt = _("Alternative Image 1 partition for boot repair not found.") + "\n" + _("Caution, next boot is starts with these settings!") + "\n"
			message = _("Wrong Bootsettings detected!") + "\n\n%s\n\n%s\n" % (boot, txt) + _("Do you want to reboot now?")
		elif writeoption:
			if not self.writeFile('/boot/STARTUP', newboot):
				txt = _("Can not write file %s") % ("'/boot/STARTUP'") + "\n" + _("Caution, next boot is starts with these settings!") + "\n"
				message = _("Write error!") + "\n\n%s\n\n%s\n" % (boot, txt) + _("Do you want to reboot now?")

		if failboot or writeoption:
			boot = self.readlineFile('/boot/STARTUP')
			if self.checkBootEntry(boot):
				txt = _("Error in file %s") % ("'/boot/STARTUP'") + "\n" + _("Caution, next boot is starts with these settings!") + "\n"
				message = _("Command line error!") + "\n\n%s\n\n%s\n" % (boot, txt) + _("Do you want to reboot now?")

		self.session.openWithCallback(self.restartBOX, MessageBox, message, MessageBox.TYPE_YESNO, default=False)

	def cancel(self):
		self.close()

	def up(self):
		if not self.MultiBootSelector:
			return
		self.option = self.option - 1
		if self.option == -1:
			self.option = len(self.optionsList) - 1
		self.startup_option()

	def down(self):
		if not self.MultiBootSelector:
			return
		self.option = self.option + 1
		if self.option == len(self.optionsList):
			self.option = 0
		self.startup_option()

	def left(self):
		if not self.MultiBootSelector:
			return
		if self.list:
			self.selection = self.selection - 1
			if self.selection == -1:
				self.selection = len(self.list) - 1
			self.startup()

	def right(self):
		if not self.MultiBootSelector:
			return
		if self.list:
			self.selection = self.selection + 1
			if self.selection == len(self.list):
				self.selection = 0
			self.startup()

	def read_startup(self, FILE):
		if not os.path.isfile(FILE):
			return ""
		with open(FILE, 'r') as myfile:
			data = myfile.read().replace('\n', '')
		myfile.close()
		return data

	def list_files(self, PATH):
		files = []
		for name in os.listdir(PATH):
			if os.path.isfile(os.path.join(PATH, name)):
				try:
					cmdline = self.read_startup("/boot/" + name).split("=", 3)[3].split(" ", 1)[0]
				except IndexError:
					continue
				if cmdline in getextdevices("ext4") and not name == "STARTUP":
					files.append(name)
		return files

	def restartBOX(self, answer):
		if answer is True:
			self.session.open(TryQuitMainloop, 2)
		else:
			self.close()
