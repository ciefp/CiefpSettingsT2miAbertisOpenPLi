import os
import platform
import shutil
import json
from urllib.request import urlopen

from enigma import eConsoleAppContainer, eDVBDB

from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Button import Button
from Plugins.Plugin import PluginDescriptor

PLUGIN_VERSION = "1.5"  # Verzija povećana zbog promjene izvora
PLUGIN_NAME = "CiefpSettingsT2miAbertisOpenPLi"
PLUGIN_PATH = "/usr/lib/enigma2/python/Plugins/Extensions/CiefpSettingsT2miAbertisOpenPLi"
DATA_PATH = os.path.join(PLUGIN_PATH, "data")
SCRIPTS_PATH = os.path.join(DATA_PATH, "scripts")
ICON_PATH = os.path.join(PLUGIN_PATH, "icon.png")

# NOVA GitHub API adresa za settings
GITHUB_SETTINGS_FOLDER_API = "https://api.github.com/repos/ciefp/ciefpsettings-enigma2-zipped/contents/"
# Prefiks za filtriranje - samo 75E-34W settings
ZIP_PREFIX = "ciefp-E2-75E-34W-"
ZIP_SUFFIX = ".zip"


class CiefpSettingsT2miAbertisOpenPLi(Screen):
    skin = """
    <screen name="CiefpSettingsT2miAbertisOpenPLi" position="center,center" size="1600,800" title="..:: CiefpSettings T2mi Abertis OpenPLi Installer ::..(v{version})">
        <widget name="info" position="10,10" size="780,650" font="Regular;24" valign="center" halign="left" />

        <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/CiefpSettingsT2miAbertisOpenPLi/background.png" position="790,10" size="800,650" alphatest="on" />

        <widget name="status" position="10,670" size="1580,50" font="Bold;24" valign="center" halign="center" backgroundColor="#cccccc" foregroundColor="#000000" />

        <widget name="key_red" position="10,730" size="370,60" font="Bold;26" halign="center" backgroundColor="#9F1313" foregroundColor="#000000" />
        <widget name="key_green" position="410,730" size="370,60" font="Bold;26" halign="center" backgroundColor="#1F771F" foregroundColor="#000000" />
        <widget name="key_yellow" position="810,730" size="370,60" font="Bold;26" halign="center" backgroundColor="#D6A200" foregroundColor="#000000" />
        <widget name="key_blue" position="1210,730" size="380,60" font="Bold;26" halign="center" backgroundColor="#1E5AA8" foregroundColor="#000000" />
    </screen>
    """.format(version=PLUGIN_VERSION)

    def __init__(self, session):
        self.session = session
        Screen.__init__(self, session)

        self._container = None
        self._on_cmd_done = None

        self.setupUI()
        self.showPrompt()

    def setupUI(self):
        self["info"] = Label("Initializing plugin...")
        self["status"] = Label("")
        self["key_red"] = Button("Exit")
        self["key_green"] = Button("Install")
        self["key_yellow"] = Button("Update")
        self["key_blue"] = Button("OpenPLi Settings")

        self["actions"] = ActionMap(["ColorActions", "SetupActions"], {
            "red": self.exitPlugin,
            "green": self.startInstallation,
            "yellow": self.runUpdate,
            "blue": self.installOpenPliSettings,
            "cancel": self.close
        }, -1)

    def showPrompt(self):
        self["info"].setText(
            "This plugin can do:\n\n"
            "GREEN (Install):\n"
            "- Install Astra-SM\n"
            "- Stop Astra-SM, copy files, start Astra-SM again\n"
            "- Copy config files (sysctl.conf, astra-sm.conf, astra-sm.lua)\n"
            "- SoftCam.Key\n"
            "- Abertis script\n\n"
            "BLUE (OpenPLi Settings):\n"
            "- Download latest OpenPLi channel list from GitHub (ZIP)\n"
            "- Install settings + satellites.xml\n"
            "- Reload settings (no reboot needed)\n\n"
            "YELLOW (Update):\n"
            "- Update installer script\n\n"
            "Choose an option."
        )
        self["status"].setText("Awaiting your choice.")

    # -------------------------
    # Non-blocking shell runner
    # -------------------------
    def runCommandAsync(self, command, done_cb=None, status_text=None):
        """Run a shell command without freezing Enigma2 GUI."""
        if status_text:
            self["status"].setText(status_text)

        if self._container is not None:
            self["status"].setText("Busy, please wait...")
            return

        self._on_cmd_done = done_cb
        self._container = eConsoleAppContainer()
        self._container.appClosed.append(self._commandFinished)
        try:
            self._container.execute(command)
        except Exception as e:
            self._container = None
            self._on_cmd_done = None
            self["status"].setText("Command start failed: %s" % str(e))

    def _commandFinished(self, retval):
        cb = self._on_cmd_done
        self._container = None
        self._on_cmd_done = None
        if cb:
            try:
                cb(retval)
            except Exception as e:
                self["status"].setText("Callback error: %s" % str(e))

    # -------------------------
    # Safe copy for executables
    # -------------------------
    def safe_copy_executable(self, src, dest, mode=0o755):
        """Copy to dest.new then atomic rename to avoid ETXTBSY."""
        tmp = dest + ".new"
        shutil.copy2(src, tmp)
        os.chmod(tmp, mode)
        os.rename(tmp, dest)

    # -------------
    # UPDATE (yellow)
    # -------------
    def runUpdate(self):
        cmd = 'wget -q "--no-check-certificate" https://raw.githubusercontent.com/ciefp/CiefpSettingsT2miAbertisOpenPLi/main/installer.sh -O - | /bin/sh'
        self.runCommandAsync(cmd, done_cb=self._updateDone, status_text="Updating plugin...")

    def _updateDone(self, retval):
        if retval == 0:
            self["status"].setText("Update complete.")
        else:
            self["status"].setText("Update failed (code %d)." % retval)

    # -----------------
    # INSTALL (green)
    # -----------------
    def startInstallation(self):
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

        self["info"].setText("Installing Astra-SM (opkg)...")
        self.runCommandAsync(
            "opkg update && opkg install astra-sm",
            done_cb=self._astraInstallDone,
            status_text="Installing Astra-SM..."
        )

    def _astraInstallDone(self, retval):
        if retval != 0:
            self["status"].setText("Astra-SM install failed (code %d)." % retval)
            return

        # Astra-SM is often running all the time -> stop it before copying scripts/configs
        self["info"].setText("Stopping Astra-SM to copy files safely...")
        stop_cmd = (
            "if [ -x /etc/init.d/astra-sm ]; then /etc/init.d/astra-sm stop >/dev/null 2>&1; fi; "
            "killall -9 astra-sm >/dev/null 2>&1; "
        )
        self.runCommandAsync(stop_cmd, done_cb=self._astraStoppedCopyFiles, status_text="Stopping Astra-SM...")

    def _astraStoppedCopyFiles(self, retval):
        # Even if stop returns non-zero, we still try to proceed (killall may have succeeded)
        try:
            self["status"].setText("Copying configuration files...")
            self["info"].setText("Copying configuration files...")

            os.makedirs("/etc/astra", exist_ok=True)
            os.makedirs("/etc/astra/scripts", exist_ok=True)
            os.makedirs("/etc/tuxbox/config/oscam-emu", exist_ok=True)

            shutil.copy(os.path.join(DATA_PATH, "sysctl.conf"), "/etc/sysctl.conf")
            shutil.copy(os.path.join(DATA_PATH, "astra-sm.conf"), "/etc/astra/astra-sm.conf")
            shutil.copy(os.path.join(DATA_PATH, "astra-sm.lua"), "/etc/astra/astra-sm.lua")

            # Script abertis (safe replace)
            self.safe_copy_executable(os.path.join(SCRIPTS_PATH, "abertis"), "/etc/astra/scripts/abertis")

            # SoftCam.Key (case-insensitive fallback)
            softcam_path = None
            if os.path.exists(os.path.join(DATA_PATH, "softcam.key")):
                softcam_path = os.path.join(DATA_PATH, "softcam.key")
            elif os.path.exists(os.path.join(DATA_PATH, "SoftCam.Key")):
                softcam_path = os.path.join(DATA_PATH, "SoftCam.Key")

            if not softcam_path:
                raise Exception("SoftCam.Key file not found in data directory")

            shutil.copy(softcam_path, "/etc/tuxbox/config/softcam.key")
            shutil.copy(softcam_path, "/etc/tuxbox/config/oscam-emu/softcam.key")

            # Start Astra-SM again
            self["info"].setText("Starting Astra-SM...")
            start_cmd = "if [ -x /etc/init.d/astra-sm ]; then /etc/init.d/astra-sm start >/dev/null 2>&1; fi;"
            self.runCommandAsync(start_cmd, done_cb=self._astraRestartedFinish, status_text="Starting Astra-SM...")

        except Exception as e:
            self["status"].setText("Error: %s" % str(e))
            # Try to start Astra-SM anyway
            start_cmd = "if [ -x /etc/init.d/astra-sm ]; then /etc/init.d/astra-sm start >/dev/null 2>&1; fi;"
            self.runCommandAsync(start_cmd, status_text="Starting Astra-SM...")

    def _astraRestartedFinish(self, retval):
        # Installation done; suggest BLUE for settings list
        self["status"].setText("Install done. You can now press BLUE for latest channel list.")
        self["info"].setText(
            "Installation successful!\n\n"
            "Installed:\n"
            "- astra-sm\n"
            "- /etc/sysctl.conf\n"
            "- /etc/astra/astra-sm.conf\n"
            "- /etc/astra/astra-sm.lua\n"
            "- /etc/astra/scripts/abertis\n"
            "- /etc/tuxbox/config/softcam.key\n"
            "- /etc/tuxbox/config/oscam-emu/softcam.key\n\n"
            "Next step:\n"
            "- Press BLUE (OpenPLi Settings) to install the latest channel list and reload settings.\n\n"
            "Note: Reboot is not required for the channel list (BLUE does reload),\n"
            "but you may reboot later if you want."
        )
        self.session.open(
            MessageBox,
            "Files copied and Astra-SM restarted.\n\nNow press BLUE to install the latest OpenPLi channel list (and reload).",
            MessageBox.TYPE_INFO
        )

    # --------------------------
    # OPENPLI SETTINGS (blue)
    # --------------------------
    def getLatestSettingsZipUrl(self):
        """Find the ZIP in the GitHub folder with prefix ciefp-E2-75E-34W-."""
        try:
            resp = urlopen(GITHUB_SETTINGS_FOLDER_API, timeout=20)
            data = json.loads(resp.read().decode("utf-8"))

            for item in data:
                name = item.get("name", "")
                # Filtriraj samo fajlove koji počinju sa ZIP_PREFIX i završavaju sa .zip
                if name.startswith(ZIP_PREFIX) and name.endswith(ZIP_SUFFIX):
                    return item.get("download_url")
            return None
        except Exception as e:
            self["status"].setText("GitHub fetch error: %s" % str(e))
            return None

    def installOpenPliSettings(self):
        self["status"].setText("Checking latest OpenPLi settings...")

        zip_url = self.getLatestSettingsZipUrl()
        if not zip_url:
            self["status"].setText("No settings ZIP found in GitHub folder.")
            return

        cmd = (
            "opkg install unzip >/dev/null 2>&1; "
            "rm -rf /tmp/ciefp_settings /tmp/ciefp_settings.zip; "
            "mkdir -p /tmp/ciefp_settings; "
            "wget -O /tmp/ciefp_settings.zip \"%s\" >/dev/null 2>&1; "
            "unzip -o /tmp/ciefp_settings.zip -d /tmp/ciefp_settings >/dev/null 2>&1; "
            "cp -rf /tmp/ciefp_settings/*/* /etc/enigma2/ >/dev/null 2>&1; "
            "if [ -f /tmp/ciefp_settings/*/satellites.xml ]; then "
            "  mkdir -p /etc/tuxbox/; "
            "  cp -f /tmp/ciefp_settings/*/satellites.xml /etc/tuxbox/ >/dev/null 2>&1; "
            "fi; "
            "sync; "
            "rm -rf /tmp/ciefp_settings /tmp/ciefp_settings.zip; "
        ) % zip_url

        self["info"].setText("Installing OpenPLi settings...\n\nSource:\n%s" % zip_url)
        self.runCommandAsync(cmd, done_cb=self._settingsInstallDone, status_text="Installing OpenPLi settings...")

    def _settingsInstallDone(self, retval):
        if retval != 0:
            self["status"].setText("Settings install failed (code %d)." % retval)
            return

        try:
            db = eDVBDB.getInstance()
            db.reloadServicelist()
            db.reloadBouquets()
            self["status"].setText("Settings installed & reloaded successfully.")
            self["info"].setText(
                "OpenPLi settings installed successfully!\n\n"
                "Done:\n"
                "- Download ZIP from GitHub\n"
                "- Install to /etc/enigma2\n"
                "- Copy satellites.xml (if present)\n"
                "- Reload servicelist & bouquets\n"
            )
        except Exception as e:
            self["status"].setText("Installed, but reload failed: %s" % str(e))

    def exitPlugin(self):
        self.close()


def Plugins(**kwargs):
    return [
        PluginDescriptor(
            name=PLUGIN_NAME,
            description="Installer for T2MI Abertis configuration (Version %s)" % PLUGIN_VERSION,
            where=[PluginDescriptor.WHERE_PLUGINMENU, PluginDescriptor.WHERE_EXTENSIONSMENU],
            icon=ICON_PATH,
            fnc=lambda session, **kwargs: session.open(CiefpSettingsT2miAbertisOpenPLi)
        )
    ]