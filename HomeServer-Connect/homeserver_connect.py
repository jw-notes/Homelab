# import statements
import sys
from PyQt6.QtWidgets import (
	QApplication, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout, QFormLayout,
	QMessageBox, QCheckBox, QComboBox, QGroupBox, QFrame
)
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt, QThread, pyqtSignal
import paramiko

import os
import json
import socket
import subprocess
import shutil
import tempfile
import time
import ctypes


MAX_RECENT = 10
IS_WINDOWS = sys.platform.startswith('win')

if IS_WINDOWS:
	from ctypes import wintypes

	# Scopes DPAPI-encrypted config to this app specifically (DPAPI alone only
	# scopes to the Windows user account, so any process running as you could
	# otherwise decrypt it). Not a secret - just extra entropy, not a key.
	_DPAPI_ENTROPY = b'HomeServer-Connect:config.json'

	class _DATA_BLOB(ctypes.Structure):
		_fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_char))]

	def _to_blob(data):
		buf = ctypes.create_string_buffer(data, len(data))
		blob = _DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
		return blob, buf  # buf must outlive the call that reads the blob

	def _dpapi_protect(data, entropy=_DPAPI_ENTROPY):
		in_blob, _buf = _to_blob(data)
		entropy_blob, _entropy_buf = _to_blob(entropy)
		out_blob = _DATA_BLOB()
		ok = ctypes.windll.crypt32.CryptProtectData(
			ctypes.byref(in_blob), None, ctypes.byref(entropy_blob), None, None, 0, ctypes.byref(out_blob)
		)
		if not ok:
			raise ctypes.WinError()
		try:
			return ctypes.string_at(out_blob.pbData, out_blob.cbData)
		finally:
			ctypes.windll.kernel32.LocalFree(out_blob.pbData)

	def _dpapi_unprotect(data, entropy=_DPAPI_ENTROPY):
		in_blob, _buf = _to_blob(data)
		entropy_blob, _entropy_buf = _to_blob(entropy)
		out_blob = _DATA_BLOB()
		ok = ctypes.windll.crypt32.CryptUnprotectData(
			ctypes.byref(in_blob), None, ctypes.byref(entropy_blob), None, None, 0, ctypes.byref(out_blob)
		)
		if not ok:
			raise ctypes.WinError()
		try:
			return ctypes.string_at(out_blob.pbData, out_blob.cbData)
		finally:
			ctypes.windll.kernel32.LocalFree(out_blob.pbData)


def _linux_key_path():
	return os.path.join(config_dir(), '.storage.key')


def _linux_key():
	# No OS-level per-user encryption service on Linux without extra runtime
	# dependencies (Secret Service/kwallet aren't always present), so fall
	# back to a locally generated key file. Filesystem permissions (0600) are
	# the security boundary here, the same as they'd be for an SSH key.
	from cryptography.fernet import Fernet
	key_path = _linux_key_path()
	if os.path.exists(key_path):
		with open(key_path, 'rb') as f:
			return f.read()
	key = Fernet.generate_key()
	with open(key_path, 'wb') as f:
		f.write(key)
	try:
		os.chmod(key_path, 0o600)
	except OSError:
		pass
	return key


def _linux_protect(data):
	from cryptography.fernet import Fernet
	return Fernet(_linux_key()).encrypt(data)


def _linux_unprotect(data):
	from cryptography.fernet import Fernet
	return Fernet(_linux_key()).decrypt(data)


def protect_data(data):
	return _dpapi_protect(data) if IS_WINDOWS else _linux_protect(data)


def unprotect_data(data):
	return _dpapi_unprotect(data) if IS_WINDOWS else _linux_unprotect(data)


def describe_error(e):
	# Translates the low-level exceptions ssh/net use can raise into messages
	# a non-technical user can act on, instead of a raw traceback string.
	if isinstance(e, paramiko.AuthenticationException):
		return 'Authentication failed. Check the username and password.'
	if isinstance(e, paramiko.SSHException):
		return f'SSH error: {e}'
	if isinstance(e, socket.timeout):
		return 'Connection timed out. Check the IP address and that the server is powered on and reachable.'
	if isinstance(e, socket.gaierror):
		return 'Could not resolve that address. Check the IP address or hostname.'
	if isinstance(e, ConnectionRefusedError):
		return 'Connection refused. Is SSH enabled on the server?'
	if isinstance(e, PermissionError):
		return f'Permission denied: {e}'
	if isinstance(e, subprocess.TimeoutExpired):
		return 'The operation timed out. Check the IP address and that the server is reachable.'
	if isinstance(e, OSError):
		return f'Network error: {e}'
	return str(e)


def explain_net_use_error(raw, user):
	# Translates `net use`'s own opaque "System error N has occurred." text
	# (from cmd.exe/net.exe, not a Python exception) into something actionable.
	lower = raw.lower()
	if '3227320323' in raw or '0xc05d0003' in lower:
		# Windows 11 24H2 / Server 2025 made SMB signing mandatory and reject
		# unsigned guest fallback with this exact opaque code, instead of a
		# normal "wrong password" error.
		return (
			'Windows rejected this as an unsigned guest connection (SMB signing is '
			'mandatory on Windows 11 24H2 / Server 2025).\n\n'
			f'This usually means "{user}" is not a real Samba user on the server yet, so it '
			'silently fell back to guest access. On the server, run:\n'
			f'    sudo smbpasswd -a {user}\n'
			'to set a Samba password for that account, then try again.\n\n'
			"If that account already has a Samba password, you can instead relax this PC's "
			'SMB signing requirement (Admin PowerShell):\n'
			'    Set-SmbClientConfiguration -RequireSecuritySignature $false'
		)
	if 'error 67' in lower and 'network name' in lower:
		# ERROR_BAD_NETNAME: the host was reached, but the name in the UNC path
		# isn't something it serves.
		return (
			'The server was reached, but that network name does not exist there '
			'(Windows error 67: network name not found).\n\n'
			"Check the server's IP/hostname and that Samba is running on it:\n"
			'    sudo systemctl status smbd\n'
			f'    sudo smbclient -L localhost -U {user or "USERNAME"}   # list shares from the server'
		)
	return raw


ACCENT_COLOR = '#4c8bf5'


def app_stylesheet():
	# Shared by MainWindow and the dialogs it opens, so they read as one app instead of the dialog falling back to plain
	# so they read as one app instead of the dialog falling back to plain
	# unstyled Qt widgets. An app-owned accent instead of palette(highlight):
	# the OS accent color (whatever the user picked in Windows/GTK settings)
	# otherwise bleeds into focus rings and checkboxes and can be jarring.
	return '''
		QWidget {
			font-family: "Segoe UI", "Ubuntu", "Cantarell", sans-serif;
			font-size: 13px;
		}
		QGroupBox {
			font-weight: 600;
			border: 1px solid palette(mid);
			border-radius: 8px;
			margin-top: 14px;
			padding: 14px 12px 12px 12px;
			background-color: rgba(127, 127, 127, 18);
		}
		QGroupBox::title {
			subcontrol-origin: margin;
			left: 12px;
			padding: 0 6px;
		}
		QPushButton {
			padding: 7px 14px;
			border: 1px solid palette(mid);
			border-radius: 5px;
			background-color: palette(button);
		}
		QPushButton:hover {
			background-color: palette(light);
			border: 1px solid ACCENT;
		}
		QPushButton:pressed {
			background-color: palette(midlight);
		}
		QPushButton:disabled {
			color: palette(disabled, text);
		}
		QLineEdit, QComboBox {
			padding: 6px;
			border: 1px solid palette(mid);
			border-radius: 4px;
			background-color: palette(base);
		}
		QLineEdit:focus, QComboBox:focus {
			border: 1px solid ACCENT;
		}
		QCheckBox {
			spacing: 6px;
		}
		QCheckBox::indicator {
			width: 15px;
			height: 15px;
			border: 1px solid palette(mid);
			border-radius: 3px;
			background-color: palette(base);
		}
		QCheckBox::indicator:hover {
			border: 1px solid ACCENT;
		}
		QCheckBox::indicator:checked {
			background-color: ACCENT;
			border: 1px solid ACCENT;
		}
		QListWidget {
			border: 1px solid palette(mid);
			border-radius: 6px;
			background-color: palette(base);
			padding: 4px;
			outline: none;
		}
		QListWidget::item {
			padding: 7px 8px;
			border-radius: 4px;
			margin: 1px 0;
		}
		QListWidget::item:hover {
			background-color: palette(light);
		}
		QListWidget::item:selected {
			background-color: ACCENT;
			color: white;
		}
		QLabel#pathLabel {
			background-color: rgba(127, 127, 127, 18);
			border: 1px solid palette(mid);
			border-radius: 5px;
			padding: 6px 8px;
		}
	'''.replace('ACCENT', ACCENT_COLOR)


class Worker(QThread):
	# Runs a blocking callable (ssh/subprocess calls) off the GUI thread so
	# the window stays responsive instead of freezing until it times out.
	succeeded = pyqtSignal(object)
	failed = pyqtSignal(str)

	def __init__(self, fn, parent=None):
		super().__init__(parent)
		self._fn = fn

	def run(self):
		try:
			result = self._fn()
		except Exception as e:
			self.failed.emit(describe_error(e))
		else:
			self.succeeded.emit(result)


def resource_path(relative_path):
	# PyInstaller onefile builds extract data files to sys._MEIPASS at
	# runtime; __file__ doesn't point there, so bundled assets (like the
	# icon) have to be resolved through it explicitly.
	base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
	return os.path.join(base_path, relative_path)


def config_dir():
	# %APPDATA% (Windows) / XDG_CONFIG_HOME or ~/.config (Linux) survive
	# across runs and reinstalls; sys._MEIPASS (used for resource_path) is a
	# throwaway extraction folder wiped after the app closes, so saved
	# connections would otherwise vanish every session.
	if IS_WINDOWS:
		base_dir = os.environ.get('APPDATA', os.path.expanduser('~'))
	else:
		base_dir = os.environ.get('XDG_CONFIG_HOME', os.path.join(os.path.expanduser('~'), '.config'))
	directory = os.path.join(base_dir, 'HomeServer-Connect')
	os.makedirs(directory, exist_ok=True)
	return directory


def config_path():
	return os.path.join(config_dir(), 'config.json')

# Main Window class
class MainWindow(QWidget):
	def __init__(self):
		super().__init__()
		self.setWindowTitle('HomeServer Connect')
		self.storage_path = config_path()
		self.saved_connections = []
		self.recent_connections = []
		self.last_connection = {}
		self.setup_ui()
		self.load_storage()
		self.update_combos()

	def _wrap(self, layout):
		# QFormLayout rows take a single widget; wrap a multi-widget row
		# (e.g. field + its show/hide checkbox) in a plain container.
		layout.setContentsMargins(0, 0, 0, 0)
		container = QWidget()
		container.setLayout(layout)
		return container

	def setup_ui(self):
		# Labels and fields

		self.ip_label = QLabel('Server IP:')
		self.ip_input = QLineEdit()
		self.ip_input.setPlaceholderText('192.168.1.x')
		self.ip_input.setToolTip('The IP address or hostname of the home server on your network.')
		self.ip_show = QCheckBox('Hide')
		self.ip_show.setChecked(False)
		self.ip_show.stateChanged.connect(self.toggle_ip)
		self.ip_input.setEchoMode(QLineEdit.EchoMode.Normal)

		self.user_label = QLabel('Username:')
		self.user_input = QLineEdit()
		self.user_input.setPlaceholderText('pi')
		self.user_input.setToolTip('The SSH username on the server (e.g. pi).')
		self.user_show = QCheckBox('Hide')
		self.user_show.setChecked(False)
		self.user_show.stateChanged.connect(self.toggle_user)
		self.user_input.setEchoMode(QLineEdit.EchoMode.Normal)

		self.pass_label = QLabel('Password:')
		self.pass_input = QLineEdit()
		self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)
		self.pass_input.setToolTip('The SSH password for that user. Used for SSH, sudo commands, and the Samba share login.')
		self.pass_show = QCheckBox('Show')
		self.pass_show.setChecked(False)
		self.pass_show.stateChanged.connect(self.toggle_pass)
		self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)

		self.remember_pass_checkbox = QCheckBox('Remember password (encrypted, this PC/account only)')
		self.remember_pass_checkbox.setChecked(False)
		self.remember_pass_checkbox.setToolTip(
			"Stores the password in the config file, encrypted with Windows DPAPI so only this PC and\n"
			"your Windows account can decrypt it."
		)

		self.name_label = QLabel('Connection Name:')
		self.name_input = QLineEdit()
		self.name_input.setPlaceholderText('e.g. Living Room Server')
		self.name_input.setToolTip('A friendly name used when you save this connection to the Saved list.')

		self.recent_label = QLabel('Recent:')
		self.recent_combo = QComboBox()
		self.recent_combo.setToolTip('Recently used connections, saved automatically.')
		self.recent_combo.currentIndexChanged.connect(self.load_recent_selection)

		self.saved_label = QLabel('Saved:')
		self.saved_combo = QComboBox()
		self.saved_combo.setToolTip('Connections you saved under a name.')
		self.saved_combo.currentIndexChanged.connect(self.load_saved_selection)
		self.delete_saved_button = QPushButton('Delete')
		self.delete_saved_button.setToolTip('Delete the selected saved connection.')
		self.delete_saved_button.clicked.connect(self.delete_saved_connection)

		# Buttons
		self.test_button = QPushButton('Test Connection')
		self.test_button.setToolTip('Quick reachability check (TCP port 22) - does not log in.')
		self.test_button.clicked.connect(self.test_connection)

		self.samba_toggle = QPushButton('Samba: Unknown (click to toggle)')
		self.samba_toggle.setCheckable(True)
		self.samba_toggle.setToolTip(
			"Starts or stops the Samba (SMB file-sharing) service on the REMOTE server over SSH.\n"
			"This does not enable or disable any file sharing on this PC."
		)
		self.samba_toggle.clicked.connect(self.on_samba_toggle_clicked)

		self.samba_status_button = QPushButton('⟳')
		self.samba_status_button.setFixedWidth(42)
		self.samba_status_button.setToolTip("Check the server's current Samba status without changing it.")
		self.samba_status_button.clicked.connect(self.check_samba_status)

		self.smb_button = QPushButton('Open Share in Explorer')
		self.smb_button.setToolTip(
			"Logs this PC into the server's SMB service and opens it in File Explorer (Windows, "
			"showing every share) or your default file manager (Linux, which prompts for credentials)."
		)
		self.smb_button.clicked.connect(self.open_samba_share)

		self.ssh_term_button = QPushButton('Open SSH Terminal')
		self.ssh_term_button.setToolTip(
			'Opens an interactive SSH terminal: PuTTY plink on Windows, or your terminal + sshpass on Linux, '
			'falling back to the system ssh client (prompts for the password) if those are unavailable.'
		)
		self.ssh_term_button.clicked.connect(self.open_ssh_terminal)

		self.save_button = QPushButton('Save Named Connection')
		self.save_button.setToolTip('Save the current details as a named connection you can reload later.')
		self.save_button.clicked.connect(self.save_named_connection)
		self.load_button = QPushButton('Save Last Used')
		self.load_button.setToolTip('Remember these details and auto-fill them next time the app opens.')
		self.load_button.clicked.connect(self.save_config)

		# Layouts

		connection_group = QGroupBox('Connection')
		connection_form = QFormLayout()
		connection_form.setSpacing(8)

		ip_row = QHBoxLayout()
		ip_row.addWidget(self.ip_input)
		ip_row.addWidget(self.ip_show)
		connection_form.addRow(self.ip_label, self._wrap(ip_row))

		user_row = QHBoxLayout()
		user_row.addWidget(self.user_input)
		user_row.addWidget(self.user_show)
		connection_form.addRow(self.user_label, self._wrap(user_row))

		pass_row = QHBoxLayout()
		pass_row.addWidget(self.pass_input)
		pass_row.addWidget(self.pass_show)
		connection_form.addRow(self.pass_label, self._wrap(pass_row))

		connection_form.addRow(self.remember_pass_checkbox)
		connection_form.addRow(self.name_label, self.name_input)
		connection_group.setLayout(connection_form)

		connections_group = QGroupBox('Saved && Recent')
		connections_form = QFormLayout()
		connections_form.setSpacing(8)
		connections_form.addRow(self.recent_label, self.recent_combo)
		saved_row = QHBoxLayout()
		saved_row.addWidget(self.saved_combo)
		saved_row.addWidget(self.delete_saved_button)
		connections_form.addRow(self.saved_label, self._wrap(saved_row))
		connections_group.setLayout(connections_form)

		actions_group = QGroupBox('Server Actions')
		actions_layout = QVBoxLayout()
		actions_layout.setSpacing(6)
		actions_layout.addWidget(self.test_button)
		samba_row = QHBoxLayout()
		samba_row.addWidget(self.samba_toggle)
		samba_row.addWidget(self.samba_status_button)
		actions_layout.addLayout(samba_row)
		actions_layout.addWidget(self.smb_button)
		actions_layout.addWidget(self.ssh_term_button)
		actions_group.setLayout(actions_layout)

		save_layout = QHBoxLayout()
		save_layout.addWidget(self.save_button)
		save_layout.addWidget(self.load_button)

		self.status_label = QLabel('Ready')
		self.status_label.setWordWrap(True)
		self.status_label.setStyleSheet('color: palette(text); font-size: 11px;')

		main_layout = QVBoxLayout()
		main_layout.setContentsMargins(18, 16, 18, 16)
		main_layout.setSpacing(12)
		title = QLabel('HomeServer Connect')
		title.setStyleSheet('font-size: 19px; font-weight: 600;')
		subtitle = QLabel('by J.W (https://github.com/jw-notes)')
		subtitle.setStyleSheet('font-size: 10px; color: palette(mid);')
		separator = QFrame()
		separator.setFrameShape(QFrame.Shape.HLine)
		separator.setFrameShadow(QFrame.Shadow.Sunken)
		main_layout.addWidget(title)
		main_layout.addWidget(subtitle)
		main_layout.addWidget(separator)
		main_layout.addWidget(connection_group)
		main_layout.addWidget(connections_group)
		main_layout.addWidget(actions_group)
		main_layout.addLayout(save_layout)
		main_layout.addWidget(self.status_label)
		self.setLayout(main_layout)
		# Fixed-size window: pins the layout to its size hint and disables
		# manual resizing/maximizing, so the UI is never scaled or squashed.
		main_layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)
		self.setStyleSheet(app_stylesheet())

	def toggle_ip(self):
		if self.ip_show.isChecked():
			self.ip_input.setEchoMode(QLineEdit.EchoMode.Password)
			self.ip_show.setText('Show')
		else:
			self.ip_input.setEchoMode(QLineEdit.EchoMode.Normal)
			self.ip_show.setText('Hide')

	def toggle_user(self):
		if self.user_show.isChecked():
			self.user_input.setEchoMode(QLineEdit.EchoMode.Password)
			self.user_show.setText('Show')
		else:
			self.user_input.setEchoMode(QLineEdit.EchoMode.Normal)
			self.user_show.setText('Hide')

	def toggle_pass(self):
		if self.pass_show.isChecked():
			self.pass_input.setEchoMode(QLineEdit.EchoMode.Normal)
			self.pass_show.setText('Hide')
		else:
			self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)
			self.pass_show.setText('Show')

	def _begin_busy(self, button, message):
		button.setEnabled(False)
		self.status_label.setStyleSheet('color: palette(text); font-size: 11px;')
		self.status_label.setText(message)
		QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

	def _finish_busy(self, button):
		button.setEnabled(True)
		QApplication.restoreOverrideCursor()

	def closeEvent(self, event):
		self.persist_storage()
		# Worker threads block on ssh/subprocess calls rather than running an
		# event loop, so quit() can't stop them gracefully; terminate() is
		# safe here since the whole process is exiting anyway.
		thread_attrs = (
			'_samba_thread', '_share_thread', '_status_thread', '_test_thread',
		)
		for thread in (getattr(self, attr, None) for attr in thread_attrs):
			if thread is not None and thread.isRunning():
				thread.terminate()
				thread.wait(1000)
		super().closeEvent(event)

	def _update_samba_toggle_visual(self, is_on):
		self.samba_toggle.blockSignals(True)
		self.samba_toggle.setChecked(is_on)
		self.samba_toggle.blockSignals(False)
		if is_on:
			self.samba_toggle.setText('Samba: ON  (click to stop)')
			self.samba_toggle.setStyleSheet('background-color: #2e8b57; color: white; font-weight: bold; padding: 6px 12px; border-radius: 4px;')
		else:
			self.samba_toggle.setText('Samba: OFF  (click to start)')
			self.samba_toggle.setStyleSheet('padding: 6px 12px; border-radius: 4px;')

	def on_samba_toggle_clicked(self):
		desired_on = self.samba_toggle.isChecked()
		ip = self.ip_input.text().strip()
		user = self.user_input.text().strip()
		password = self.pass_input.text().strip()
		if not ip or not user:
			QMessageBox.warning(self, 'Missing Info', 'IP and username are required.')
			self._update_samba_toggle_visual(not desired_on)
			return
		action = 'start' if desired_on else 'stop'

		def task():
			ssh = paramiko.SSHClient()
			ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
			ssh.connect(ip, username=user, password=password, timeout=10)
			try:
				# Use `sudo -S` so sudo reads the password from stdin instead of
				# requiring a tty (exec_command has no pty, so plain `sudo` just
				# fails with "no tty present" and silently no-ops).
				stdin, stdout, _ = ssh.exec_command(f'sudo -S systemctl {action} smbd')
				stdin.write(password + '\n')
				stdin.flush()
				stdout.channel.recv_exit_status()
				_, status_stdout, _ = ssh.exec_command('systemctl is-active smbd')
				return status_stdout.read().decode().strip()
			finally:
				ssh.close()

		self._begin_busy(self.samba_toggle, f'{"Starting" if desired_on else "Stopping"} Samba on {ip}…')
		self._samba_thread = Worker(task)
		self._samba_thread.succeeded.connect(lambda state: self._on_samba_toggled(state, ip, user, desired_on))
		self._samba_thread.failed.connect(lambda msg: self._on_samba_toggle_failed(msg, desired_on))
		self._samba_thread.finished.connect(lambda: self._finish_busy(self.samba_toggle))
		self._samba_thread.start()

	def _on_samba_toggled(self, state, ip, user, desired_on):
		is_active = state == 'active'
		self._update_samba_toggle_visual(is_active)
		if is_active == desired_on:
			self.status_label.setText(f'Samba is now {"ON" if is_active else "OFF"} on {ip}.')
			self.status_label.setStyleSheet('color: #2e8b57; font-size: 11px;')
			self.add_recent(ip, user)
		else:
			self.status_label.setText('Samba state did not change as expected. Check the server configuration.')
			self.status_label.setStyleSheet('color: #c0392b; font-size: 11px;')

	def _on_samba_toggle_failed(self, message, desired_on):
		self._update_samba_toggle_visual(not desired_on)
		self.status_label.setText('Samba operation failed.')
		self.status_label.setStyleSheet('color: #c0392b; font-size: 11px;')
		QMessageBox.critical(self, 'SSH Error', message)

	def check_samba_status(self):
		ip = self.ip_input.text().strip()
		user = self.user_input.text().strip()
		password = self.pass_input.text().strip()
		if not ip or not user:
			QMessageBox.warning(self, 'Missing Info', 'IP and username are required.')
			return

		def task():
			ssh = paramiko.SSHClient()
			ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
			ssh.connect(ip, username=user, password=password, timeout=10)
			try:
				_, status_stdout, _ = ssh.exec_command('systemctl is-active smbd')
				return status_stdout.read().decode().strip()
			finally:
				ssh.close()

		self._begin_busy(self.samba_status_button, f'Checking Samba status on {ip}…')
		self._status_thread = Worker(task)
		self._status_thread.succeeded.connect(self._on_status_checked)
		self._status_thread.failed.connect(self._on_samba_check_failed)
		self._status_thread.finished.connect(lambda: self._finish_busy(self.samba_status_button))
		self._status_thread.start()

	def _on_status_checked(self, state):
		is_active = state == 'active'
		self._update_samba_toggle_visual(is_active)
		self.status_label.setText(f'Samba is currently {"ON" if is_active else "OFF"}.')
		self.status_label.setStyleSheet('color: palette(text); font-size: 11px;')

	def _on_samba_check_failed(self, message):
		self.status_label.setText('Could not check Samba status.')
		self.status_label.setStyleSheet('color: #c0392b; font-size: 11px;')
		QMessageBox.critical(self, 'SSH Error', message)

	def test_connection(self):
		ip = self.ip_input.text().strip()
		if not ip:
			QMessageBox.warning(self, 'Missing Info', 'Enter an IP address first.')
			return

		def task():
			start = time.monotonic()
			with socket.create_connection((ip, 22), timeout=3):
				pass
			return time.monotonic() - start

		self._begin_busy(self.test_button, f'Testing connection to {ip}…')
		self._test_thread = Worker(task)
		self._test_thread.succeeded.connect(lambda elapsed: self._on_test_succeeded(ip, elapsed))
		self._test_thread.failed.connect(self._on_test_failed)
		self._test_thread.finished.connect(lambda: self._finish_busy(self.test_button))
		self._test_thread.start()

	def _on_test_succeeded(self, ip, elapsed):
		self.status_label.setText(f'{ip} is reachable ({elapsed * 1000:.0f} ms, port 22 open).')
		self.status_label.setStyleSheet('color: #2e8b57; font-size: 11px;')

	def _on_test_failed(self, message):
		self.status_label.setText(f'Server is not reachable: {message}')
		self.status_label.setStyleSheet('color: #c0392b; font-size: 11px;')

	def open_samba_share(self):
		# Opens the SERVER root in the OS file manager: \\<ip> on Windows (which
		# lists every share) or smb://user@ip/ on Linux. `clicked` passes a bool,
		# which a zero-argument slot simply ignores.
		ip = self.ip_input.text().strip()
		user = self.user_input.text().strip()
		password = self.pass_input.text().strip()
		if not ip:
			QMessageBox.warning(self, 'Missing Info', 'IP is required to open the share.')
			return

		if IS_WINDOWS:
			# Opening \\ip lists every share. Auth goes through IPC$ because
			# `net use \\ip` on its own isn't a valid target without a share name.
			target = f'\\\\{ip}'
			auth_target = f'\\\\{ip}\\IPC$'

			def task():
				if user:
					# Authenticate the session first (mirrors `net use ... /user:pi`);
					# just opening Explorer on the UNC path never logs in, so it
					# only works if Windows already has a cached session for the server.
					net_cmd = ['net', 'use', auth_target]
					if password:
						net_cmd.append(password)
					net_cmd.append(f'/user:{user}')
					result = subprocess.run(net_cmd, capture_output=True, text=True, timeout=20)
					if result.returncode != 0 and 'multiple connections' not in result.stderr.lower():
						raw = result.stderr.strip() or result.stdout.strip() or 'Could not authenticate to the server.'
						raise RuntimeError(explain_net_use_error(raw, user))
		else:
			userpart = f'{user}@' if user else ''
			target = f'smb://{userpart}{ip}/'

			def task():
				# No client-side auth step on Linux: the desktop's file manager
				# (via GVfs) prompts for credentials itself when it opens the URI.
				return None

		self._begin_busy(self.smb_button, f'Opening {target}…')
		self._share_thread = Worker(task)
		self._share_thread.succeeded.connect(lambda _: self._on_share_succeeded(target, ip, user))
		self._share_thread.failed.connect(self._on_share_failed)
		self._share_thread.finished.connect(lambda: self._finish_busy(self.smb_button))
		self._share_thread.start()

	def _on_share_succeeded(self, target, ip, user):
		self.status_label.setText('Server opened.')
		self.status_label.setStyleSheet('color: #2e8b57; font-size: 11px;')
		try:
			if IS_WINDOWS:
				subprocess.Popen(['explorer', target])
			else:
				subprocess.Popen(['xdg-open', target])
			self.add_recent(ip, user)
		except Exception as e:
			QMessageBox.critical(self, 'Error', f'Could not open the server:\n{e}')

	def _on_share_failed(self, message):
		self.status_label.setText('Could not open the server.')
		self.status_label.setStyleSheet('color: #c0392b; font-size: 11px;')
		QMessageBox.warning(self, 'Samba Login', f'Could not open the server:\n{message}')

	def build_entry(self, extra=None):
		entry = {
			'ip': self.ip_input.text().strip(),
			'user': self.user_input.text().strip(),
		}
		if extra:
			entry.update(extra)
		if self.remember_pass_checkbox.isChecked():
			entry['password'] = self.pass_input.text().strip()
		return entry

	def save_config(self):
		# legacy single save; also persist storage structure
		entry = self.build_entry()
		self.persist_storage(last=entry)
		QMessageBox.information(self, 'Saved', 'Last used connection saved to config.json.')

	def save_named_connection(self):
		name = self.name_input.text().strip()
		if not name:
			QMessageBox.warning(self, 'Missing Name', 'Enter a connection name before saving.')
			return
		entry = self.build_entry({'name': name})
		# replace if name exists
		self.saved_connections = [c for c in self.saved_connections if c.get('name') != name]
		self.saved_connections.insert(0, entry)
		self.persist_storage(last=entry)
		self.update_combos()
		QMessageBox.information(self, 'Saved', f'Saved connection "{name}".')

	def delete_saved_connection(self):
		index = self.saved_combo.currentIndex()
		if index <= 0:
			QMessageBox.warning(self, 'No Selection', 'Select a saved connection to delete first.')
			return
		entry = self.saved_connections[index - 1]
		label = entry.get('name') or f"{entry.get('ip','')} ({entry.get('user','')})"
		confirm = QMessageBox.question(
			self, 'Delete Saved Connection', f'Delete saved connection "{label}"?',
			QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No
		)
		if confirm != QMessageBox.StandardButton.Yes:
			return
		del self.saved_connections[index - 1]
		self.persist_storage()
		self.update_combos()

	def load_recent_selection(self, index):
		if index <= 0:
			return
		entry = self.recent_connections[index - 1]
		self.apply_entry(entry)

	def load_saved_selection(self, index):
		if index <= 0:
			return
		entry = self.saved_connections[index - 1]
		self.apply_entry(entry)
		self.name_input.setText(entry.get('name', ''))

	def apply_entry(self, entry):
		self.ip_input.setText(entry.get('ip', ''))
		self.user_input.setText(entry.get('user', ''))
		if 'password' in entry:
			self.pass_input.setText(entry.get('password', ''))
			self.remember_pass_checkbox.setChecked(True)
		else:
			self.pass_input.setText('')
			self.remember_pass_checkbox.setChecked(False)

	def add_recent(self, ip, user):
		entry = {'ip': ip, 'user': user}
		if self.remember_pass_checkbox.isChecked():
			entry['password'] = self.pass_input.text().strip()
		self.recent_connections = [c for c in self.recent_connections if not (c.get('ip') == ip and c.get('user') == user)]
		self.recent_connections.insert(0, entry)
		self.recent_connections = self.recent_connections[:MAX_RECENT]
		self.persist_storage(last=entry)
		self.update_combos()

	def open_ssh_terminal(self):
		ip = self.ip_input.text().strip()
		user = self.user_input.text().strip()
		password = self.pass_input.text().strip()
		if not ip or not user:
			QMessageBox.warning(self, 'Missing Info', 'IP and username are required to open SSH.')
			return
		try:
			if IS_WINDOWS:
				plink_path = shutil.which('plink')
				if password and plink_path:
					inner_cmd = f'"{plink_path}" -ssh {user}@{ip} -pw "{password}"'
				elif password and not plink_path:
					QMessageBox.information(self, 'Note', 'PuTTY plink not found; falling back to ssh which will prompt for the password.')
					inner_cmd = f'ssh {user}@{ip}'
				else:
					inner_cmd = f'ssh {user}@{ip}'
				self._launch_windows_console(inner_cmd)
			else:
				self._open_linux_ssh_terminal(ip, user, password)
		except Exception as e:
			QMessageBox.critical(self, 'Error', f'Could not open SSH terminal:\n{e}')

	def _launch_windows_console(self, inner_cmd):
		# Routed through a temp .bat rather than nesting `cmd /c "..."` inside
		# the outer `start` call: cmd.exe's nested-quote-stripping rules are
		# fragile once the inner command has its own quotes (a plink path
		# with spaces, a quoted password), and a real file sidesteps that
		# entirely. `chcp 65001` here (in the SAME console ssh/plink runs in,
		# which a codepage change in the launching process wouldn't reach)
		# fixes UTF-8 box-drawing characters (lsblk, tree, etc.) showing as
		# garbled text. Self-deletes after running so temp files don't pile up.
		fd, bat_path = tempfile.mkstemp(suffix='.bat', prefix='hsc_ssh_')
		with os.fdopen(fd, 'w') as f:
			f.write('@echo off\r\n')
			f.write('chcp 65001 >nul\r\n')
			f.write(inner_cmd + '\r\n')
			f.write('del "%~f0"\r\n')
		subprocess.Popen(f'start "" "{bat_path}"', shell=True)

	def _open_linux_ssh_terminal(self, ip, user, password):
		sshpass_path = shutil.which('sshpass')
		env = os.environ.copy()
		if password and sshpass_path:
			# Pass the password via env var, not `-p`/argv, so it isn't visible
			# to other local users through `ps`.
			env['SSHPASS'] = password
			ssh_cmd = [sshpass_path, '-e', 'ssh', f'{user}@{ip}']
		else:
			if password:
				QMessageBox.information(self, 'Note', "'sshpass' not found; falling back to ssh which will prompt for the password.")
			ssh_cmd = ['ssh', f'{user}@{ip}']

		terminal_candidates = (
			('x-terminal-emulator', ('-e',)),
			('gnome-terminal', ('--',)),
			('konsole', ('-e',)),
			('xfce4-terminal', ('-e',)),
			('xterm', ('-e',)),
		)
		for terminal, flag_args in terminal_candidates:
			terminal_path = shutil.which(terminal)
			if terminal_path:
				subprocess.Popen([terminal_path, *flag_args, *ssh_cmd], env=env)
				return
		QMessageBox.warning(
			self, 'No Terminal Found',
			'Could not find a terminal emulator to launch. Run this manually in a terminal:\n' + ' '.join(ssh_cmd)
		)

	def update_combos(self):
		self.recent_combo.blockSignals(True)
		self.saved_combo.blockSignals(True)
		self.recent_combo.clear()
		self.saved_combo.clear()
		self.recent_combo.addItem('Select recent')
		for c in self.recent_connections:
			label = f"{c.get('ip','')} ({c.get('user','')})"
			self.recent_combo.addItem(label)
		self.saved_combo.addItem('Select saved')
		for c in self.saved_connections:
			label = c.get('name') or f"{c.get('ip','')} ({c.get('user','')})"
			self.saved_combo.addItem(label)
		self.recent_combo.blockSignals(False)
		self.saved_combo.blockSignals(False)

	def load_storage(self):
		if not os.path.exists(self.storage_path):
			return
		try:
			with open(self.storage_path, 'rb') as f:
				raw = f.read()
			try:
				data = json.loads(unprotect_data(raw).decode('utf-8'))
			except Exception:
				# Fall back to plain JSON so configs saved before encryption
				# was added still load; the next save re-writes it encrypted.
				data = json.loads(raw.decode('utf-8'))
			if isinstance(data, dict) and 'ip' in data:
				# legacy single entry
				self.apply_entry(data)
				self.saved_connections = []
				self.recent_connections = []
				self.last_connection = {k: v for k, v in data.items() if k in ('ip', 'user', 'password')}
			else:
				self.saved_connections = [{k: v for k, v in c.items() if k in ('ip', 'user', 'name', 'password')} for c in (data.get('saved', []) if isinstance(data, dict) else [])]
				self.recent_connections = [{k: v for k, v in c.items() if k in ('ip', 'user', 'password')} for c in (data.get('recent', []) if isinstance(data, dict) else [])]
				last = data.get('last', {}) if isinstance(data, dict) else {}
				if isinstance(last, dict):
					self.last_connection = last
				if last:
					self.apply_entry({k: v for k, v in last.items() if k in ('ip', 'user', 'password')})
		except Exception as e:
			QMessageBox.warning(self, 'Config', f'Could not read config.json:\n{e}')

	def persist_storage(self, last=None):
		def scrub(entry):
			return {k: v for k, v in entry.items() if k in ('ip', 'user', 'name', 'password')}
		if last is not None:
			self.last_connection = last
		data = {
			'saved': [scrub(c) for c in self.saved_connections],
			'recent': [scrub(c) for c in self.recent_connections],
			'last': scrub(self.last_connection or self.build_entry()),
		}
		encrypted = protect_data(json.dumps(data).encode('utf-8'))
		with open(self.storage_path, 'wb') as f:
			f.write(encrypted)


if __name__ == '__main__':
	app = QApplication(sys.argv)
	# Fusion renders identically on Windows and Linux, so the custom QSS above
	# (built on palette() tokens) looks the same on both instead of drifting
	# with whatever native GTK/Windows theme happens to be active.
	app.setStyle('Fusion')
	icon_path = resource_path('ehnm.ico')
	if os.path.exists(icon_path):
		app.setWindowIcon(QIcon(icon_path))
	window = MainWindow()
	if os.path.exists(icon_path):
		window.setWindowIcon(QIcon(icon_path))
	window.show()
	sys.exit(app.exec())
