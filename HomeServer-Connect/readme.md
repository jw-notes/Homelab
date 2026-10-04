# HomeServer Connect

A simple tool to quickly access your home server's SMB shares or SSH into it without faffing around.

## Features

- **One-click access**: Opens your server's root share in File Explorer/OS file manager
- **Server management**: Start/stop Samba service and check its status
- **Connection history**: Remembers recent and saved connections
- **Cross-platform**: Works on Windows and Linux

## Installation

### Prerequisites
- Python 3.10+
- PyQt6
- Paramiko

```bash
pip install pyqt6 paramiko cryptography
````

### Build Executable

```bash
# Update spec file if needed
pyinstaller --noconfirm --clean HomeServer-Connect.spec
```

The executable will be in `dist/HomeServer-Connect` directory.

## Usage

1. Enter your server's IP address
2. Provide username/password if required
3. Click "Open Share in Explorer" to access server shares

### Server Management

- __Test Connection__: Quick TCP port check
- __Samba Toggle__: Start/stop Samba service on remote server
- __Open SSH Terminal__: Direct terminal access

External image blocked pending consentSource: `https://via.placeholder.com/400x250?text=HomeServer+Connect+UI`\
Alt: `Screenshot`Load image

## Technical Notes

- Uses Windows `net use` for SMB authentication
- Linux uses GVfs for SMB access
- Configuration stored in `%APPDATA%/HomeServer Connect/config.json` (Windows) or `~/.config/HomeServer Connect/config.json` (Linux
