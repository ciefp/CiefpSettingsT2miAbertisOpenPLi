import subprocess
import os
import platform
import shutil
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Button import Button
from Components.Pixmap import Pixmap
from Tools.Directories import resolveFilename, SCOPE_PLUGINS
from Plugins.Plugin import PluginDescriptor

PLUGIN_VERSION = "1.1"
PLUGIN_NAME = "CiefpSettingsT2miAbertisOpenPLi"
PLUGIN_PATH = "/usr/lib/enigma2/python/Plugins/Extensions/CiefpSettingsT2miAbertisOpenPLi"
DATA_PATH = os.path.join(PLUGIN_PATH, "data")
SCRIPTS_PATH = os.path.join(DATA_PATH, "scripts")
ICON_PATH = os.path.join(PLUGIN_PATH, "icon.png")

class CiefpSettingsT2miAbertisOpenPLi(Screen):
    skin = """
    <screen name="CiefpSettingsT2miAbertisOpenPLi" position="center,center" size="1600,800" title="..:: CiefpSettings T2mi Abertis OpenPLi Installer ::..(v{version})">
        <!-- Menu section -->
        <widget name="info" position="10,10" size="780,650" font="Regular;24" valign="center" halign="left" />

        <!-- Background section -->
        <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/CiefpSettingsT2miAbertisOpenPLi/background.png" position="790,10" size="800,650" alphatest="on" />

        <!-- Status section -->
        <widget name="status" position="10,670" size="1580,50" font="Bold;24" valign="center" halign="center" backgroundColor="#cccccc" foregroundColor="#000000" />
        <widget name="key_red" position="10,730" size="500,60" font="Bold;26" halign="center" backgroundColor="#9F1313" foregroundColor="#000000" />
        <widget name="key_green" position="550,730" size="500,60" font="Bold;26" halign="center" backgroundColor="#1F771F" foregroundColor="#000000" />
        <widget name="key_yellow" position="1090,730" size="500,60" font="Bold;26" halign="center" backgroundColor="#D6A200" foregroundColor="#000000" />
    </screen>
    """.format(version=PLUGIN_VERSION)

    def __init__(self, session):
        self.session = session
        Screen.__init__(self, session)
        self.setupUI()
        self.showPrompt()

    def setupUI(self):
        self["info"] = Label("Initializing plugin...")
        self["status"] = Label("")
        self["key_red"] = Button("Exit")
        self["key_green"] = Button("Install")
        self["key_yellow"] = Button("Update")
        self["actions"] = ActionMap(["ColorActions", "SetupActions"], {
            "red": self.exitPlugin,
            "green": self.startInstallation,
            "yellow": self.runUpdate,
            "cancel": self.close
        }, -1)

    def showPrompt(self):
        self["info"].setText(
            "This plugin will install the following components:\n"
            "- Astra-SM\n"
            "- Configuration files (sysctl.conf, astra-sm.conf, astra-sm.lua)\n"
            "- SoftCam.Key\n"
            "- Abertis script\n\n"
            "Do you want to proceed with the installation?"
        )
        self["status"].setText("Awaiting your choice.")

    def runUpdate(self):
        try:
            self["status"].setText("Updating plugin...")
            self.runCommand('wget -q "--no-check-certificate" https://raw.githubusercontent.com/ciefp/CiefpSettingsT2miAbertisOpenPLi/main/installer.sh -O - | /bin/sh')
            self["status"].setText("Update complete.")
        except Exception as e:
            self["status"].setText(f"Update failed: {str(e)}")

    def startInstallation(self):
        installed_files = []
        try:
            self["info"].setText("Checking system compatibility...")
            system_info = platform.machine()
            is_py3 = (platform.python_version_tuple()[0] == '3')

            if not is_py3:
                self["status"].setText("Python3 is required for this plugin.")
                return

            if system_info in ["arm", "armv7", "armv7l"]:
                system_info = "arm"
            elif system_info not in ["mips"]:
                self["status"].setText("Unsupported architecture: " + system_info)
                return

            self["info"].setText("Installing Astra-SM...")
            self.runCommand("opkg update && opkg install astra-sm")
            self["status"].setText("Astra-SM installed successfully.")
            installed_files.append("astra-sm")

            self["info"].setText("Copying configuration files...")

            # Kopiranje lokalnih fajlova
            os.makedirs("/etc/astra", exist_ok=True)
            os.makedirs("/etc/astra/scripts", exist_ok=True)
            os.makedirs("/etc/tuxbox/config/oscam-emu", exist_ok=True)

            shutil.copy(os.path.join(DATA_PATH, "sysctl.conf"), "/etc/sysctl.conf")
            installed_files.append("sysctl.conf")
            shutil.copy(os.path.join(DATA_PATH, "astra-sm.conf"), "/etc/astra/astra-sm.conf")
            installed_files.append("astra-sm.conf")
            shutil.copy(os.path.join(DATA_PATH, "astra-sm.lua"), "/etc/astra/astra-sm.lua")
            installed_files.append("astra-sm.lua")
            shutil.copy(os.path.join(SCRIPTS_PATH, "abertis"), "/etc/astra/scripts/abertis")
            os.chmod("/etc/astra/scripts/abertis", 0o755)
            installed_files.append("abertis")

            # Provera za softcam.key ili SoftCam.key
            softcam_path = None
            if os.path.exists(os.path.join(DATA_PATH, "softcam.key")):
                softcam_path = os.path.join(DATA_PATH, "softcam.key")
            elif os.path.exists(os.path.join(DATA_PATH, "SoftCam.Key")):
                softcam_path = os.path.join(DATA_PATH, "SoftCam.Key")

            if softcam_path:
                shutil.copy(softcam_path, "/etc/tuxbox/config/softcam.key")
                installed_files.append("softcam.key (/etc/tuxbox/config/)")
                shutil.copy(softcam_path, "/etc/tuxbox/config/oscam-emu/softcam.key")
                installed_files.append("softcam.key (/etc/tuxbox/config/oscam-emu/)")
            else:
                raise Exception("SoftCam.Key file not found in data directory")

            self["info"].setText("\n".join([
                "Installation successful! Installed files:",
                *[f"- {file}" for file in installed_files],
                "\nInstallation complete. Please reboot your system."
            ]))
            self["status"].setText("Installation completed successfully.")

            self.session.openWithCallback(self.rebootPrompt, MessageBox, "Installation complete! Do you want to reboot now?", MessageBox.TYPE_YESNO)
        except Exception as e:
            self["status"].setText(f"Error: {str(e)}")

    def runCommand(self, command):
        try:
            process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()
            if process.returncode != 0:
                raise Exception(stderr.decode("utf-8"))
        except Exception as e:
            self["status"].setText(f"Error: {str(e)}")

    def rebootPrompt(self, confirmed):
        if confirmed:
            self.close()
            self.runCommand("reboot")

    def exitPlugin(self):
        self.close()

def Plugins(**kwargs):
    return [
        PluginDescriptor(
            name=PLUGIN_NAME,
            description=f"Installer for T2MI Abertis configuration (Version {PLUGIN_VERSION})",
            where=[PluginDescriptor.WHERE_PLUGINMENU, PluginDescriptor.WHERE_EXTENSIONSMENU],
            icon=ICON_PATH,
            fnc=lambda session, **kwargs: session.open(CiefpSettingsT2miAbertisOpenPLi)
        )
    ]