# Denodo Docker Manager

A fully featured FastAPI web interface to manage **Denodo Platform** and **Solution Manager** Docker containers.

It supports running individual containers or docker-compose groups, viewing logs and terminals, importing/exporting configurations, and handling Docker images. Works on Windows (Docker Desktop / Rancher Desktop) or WSL with manual Docker Engine setup.

---

## ✨ Features

* Launch and configure **Denodo** or **Solution Manager** containers
* List and manage running containers
* Pull/import/export Docker images
* Use web terminals and view logs (via WebSocket)
* Import docker-compose groups
* WSL & Windows compatible

---

## 📂 Folder Structure

```bash
.
├── app/                     # FastAPI app logic
│   ├── routers/             # Route files split by concern
│   │   ├── home.py
│   │   ├── containers.py
│   │   ├── databases.py
│   │   ├── images.py
│   │   └── compose.py
│   ├── templates/           # HTML templates (Jinja2)
│   ├── static/              # Static assets (CSS, icons, JS)
│   ├── utils/               # Helper functions (docker utils, validation)
│   └── main.py              # App setup & router registration
├── container-configuration/ # Saved JSON configs per container
├── docker-compose-groups/   # Compose files and metadata
├── volumes/                 # Host bind-mount logs & shared data
├── data/                    # Pulled image tags from Google Cloud
├── requirements.txt
├── startup.bat              # Windows startup script
├── fetch_images.bat         # GCloud image tag fetcher
└── README.md
```

---

## ▶️ Getting Started

### Option 1: Easy Setup (Recommended)

Run the provided `startup.bat` file:

```bat
@echo off
python -m venv venv
call venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
call fetch_images.bat
uvicorn app.main:app --reload --port 5665
```

This will:

1. Create and activate a virtualenv
2. Install Python dependencies
3. Pull image tags from Google Cloud
4. Start the FastAPI web server

Then open:

```
http://127.0.0.1:5665
```

---

### Option 2: Manual Setup

#### 1. Create and activate virtual environment

```bash
python -m venv venv
# On Windows
venv\Scripts\activate
# On WSL/Linux
source venv/bin/activate
```

#### 2. Install requirements

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### 3. Fetch Docker image tags

This step creates two `.txt` files in `data/` folder.

```bat
:: fetch_images.bat
if not exist data mkdir data

echo Fetching denodo-platform tags...
call gcloud container images list-tags gcr.io/denodo-container/denodo-platform > data/denodo_docker_images.txt

echo Fetching solution-manager tags...
call gcloud container images list-tags gcr.io/denodo-container/solution-manager > data/sm_docker_images.txt
```

#### 4. Run the server

```bash
uvicorn app.main:app --reload --port 5665
```

Then visit [http://127.0.0.1:5665](http://127.0.0.1:5665).

---

## 🚀 Using Docker with WSL

If you do not have Docker Desktop or Rancher Desktop on Windows, you can use Docker through WSL.

### Step 1: Enable WSL and Virtualization

1. Open BIOS / UEFI settings
2. Enable **Virtualization (Intel VT-x / AMD-V)**
3. Open Windows Features:

   * Enable: **Windows Subsystem for Linux**
   * Enable: **Virtual Machine Platform**
4. Restart your computer

### Step 2: Install Ubuntu from Microsoft Store

Install a WSL distro like Ubuntu. Launch it and update:

```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg lsb-release
```

### Step 3: Install Docker Engine inside WSL

```bash
# Add GPG key
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Add Docker repo
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

### Step 4: Configure Docker Daemon

Create a file:

```bash
sudo nano /etc/docker/daemon.json
```

And paste this:

```json
{
  "hosts": ["unix:///var/run/docker.sock", "tcp://0.0.0.0:2375"]
}
```

### Step 5: Run Docker Daemon

```bash
sudo dockerd > /mnt/c/Users/<yourname>/denodo/docker.log 2>&1 &
```

### Step 6: Expose Docker to Windows

In WSL:

```bash
export DOCKER_HOST=tcp://localhost:2375
```

In Windows:

```cmd
setx DOCKER_HOST tcp://localhost:2375
```

### Step 7: Auto-Start Docker in WSL

Edit `~/.bashrc`:

```bash
# Auto-start Docker daemon
pgrep dockerd > /dev/null || (nohup sudo dockerd > /mnt/c/Users/<yourname>/denodo/docker.log 2>&1 &)
```

Make sure to add passwordless sudo for `dockerd`:

```bash
sudo visudo
# Add this line:
yourusername ALL=(ALL) NOPASSWD: /usr/bin/dockerd
```

### Step 8: Docker CLI for Windows

To use `docker` command from Windows after exposing WSL engine:

1. Download [docker-28.3.2.zip](https://download.docker.com/win/static/stable/x86_64/)
2. Extract to `C:\tools\docker`
3. Add `C:\tools\docker` to your **PATH**

Now `docker` in CMD will work using the WSL engine.

---

## 📄 API Endpoints

All routes are documented in `main.py` via FastAPI’s auto-generated docs:

* Swagger: `http://127.0.0.1:5665/docs`
* ReDoc:   `http://127.0.0.1:5665/redoc`

You’ll find endpoints for:

* `/containers`, `/images`, `/databases`
* WebSocket terminal: `/ws/terminal/{container_id}`
* Config import/export
* Compose group import & rebuild

---

## 🛠️ Dev Notes

* Works with or without Docker Desktop
* WSL is a fallback for native Docker Engine
* All image tags are pulled via `gcloud`
* Rebuild uses saved `container-configuration/*.json`