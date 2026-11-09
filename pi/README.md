# Raspberry Pi 2 Model B Setup

The Pi runs the recognition and spoken-reminder path locally when the network is unavailable. It stores face embeddings in SQLite, caregiver-recorded WAV files on disk, and uses a CSI camera or a local image/video. It uses the same `OpenCVFaceEncoder`, `IdentityMatcher`, and model settings as `face_memory_system/config/model-v1.json`. The device does not contain the website's full database or the original evaluation images.

## Hardware connections

- `15-pin CSI ribbon → CAMERA`: connect the camera ribbon to the board's camera connector.
- `USB Wi-Fi adapter → USB-A`: connect a USB Wi-Fi adapter to either USB-A port if Wi-Fi is needed.
- `Powered speaker → 3.5 mm audio`: connect an amplified speaker to the analog audio output.
- `5 V / 2.5 A power supply → Micro-USB`: use a stable 5 V / 2.5 A supply for the Pi 2.
- `microSD → card slot`: write Raspberry Pi OS Lite 32-bit to the card and insert it.

Disconnect power before moving the CSI ribbon. Check the ribbon orientation and contact markings on both the board and camera. Verify the actual board and camera revision before a demonstration.

## Install Raspberry Pi OS Lite 32-bit

1. Install Raspberry Pi OS Lite 32-bit on the microSD card. Set the locale, Wi-Fi, and SSH options in the imaging tool.
2. Update the system and install camera and audio packages:

   ```bash
   sudo apt update
   sudo apt full-upgrade -y
   sudo apt install -y python3-venv python3-pip python3-numpy python3-opencv \
     python3-picamera2 ffmpeg alsa-utils git
   ```

3. Copy the project to `/opt/face-memory`. Create an environment that can use the system-installed OpenCV and Picamera2 packages:

   ```bash
   cd /opt/face-memory
   python3 -m venv --system-site-packages .venv
   .venv/bin/python -m pip install --upgrade pip
   ```

4. Confirm this OpenCV build has `FaceDetectorYN` and `FaceRecognizerSF`. If not, use a trusted wheel compatible with 32-bit Raspberry Pi OS. Use the model files listed in `face_memory_system/models/MODELS.md`.
5. Try a local image or video before connecting the camera:

   ```bash
   .venv/bin/python pi/face_memory_pi.py --image /path/to/local-test.jpg
   .venv/bin/python pi/face_memory_pi.py --video /path/to/local-test.mp4 --scan-interval 1.5
   ```

## Transfer one person to the Pi

1. Sign in to the website, open the person, and choose **Export to Pi**.
2. Transfer the private `pi-person-<id>.json` file to the Pi using a trusted local method. It contains face embeddings; do not upload it to Git or share it publicly.
3. Import it into the local SQLite database:

   ```bash
   .venv/bin/python pi/face_memory_pi.py \
     --import-person /path/to/pi-person-<id>.json \
     --image /path/to/local-test.jpg
   ```

Import additional people by repeating `--import-person`. The JSON file does not include original photos or conversation history. The expected audio filename is `<personId>.wav` under `~/.local/share/face-memory/audio/`. Record it with the caregiver's consent, then test playback:

```bash
aplay ~/.local/share/face-memory/audio/<personId>.wav
```

The Pi plays the caregiver-recorded name and relationship only after an accepted match, with a default 12-second repeat delay. It does not use automatic text-to-speech. Change the delay with `--cooldown`.

## Camera and timing

Check the camera first with `rpicam-hello --list-cameras` if available, then run:

```bash
.venv/bin/python pi/face_memory_pi.py --camera --scan-interval 1.0 --cooldown 12
```

Calibrate the camera with a printed checkerboard of known square size. Fix the camera at its demonstration position, capture images across the actual viewing distances, angles, and lighting, then measure the frame dimensions and field of view. Repeat the check at the normal use distance. Recalibrate if the lens position or height changes.

The program records `response_ms` from reading an image/camera frame until WAV playback starts. It reports `max` and `p95` for audio reminders that started. Run at least 30 trials and note the lighting, distance, and lens. Save the CSV output and compare the maximum time with the two-second target. Laptop image or video timings are not Pi timings. Pi measurements are **pending a test on the actual Pi 2 hardware**.

## Offline use and event sync

Recognition and audio can work locally without Wi-Fi. To upload queued device events after connectivity returns, create `/etc/face-memory-pi.env` with:

```dotenv
FACE_MEMORY_PI_DB=/home/pi/.local/share/face-memory/face-memory.sqlite3
FACE_MEMORY_PI_AUDIO_DIR=/home/pi/.local/share/face-memory/audio
FACE_MEMORY_DEVICE_ID=pi2-classroom-01
FACE_MEMORY_SYNC_URL=https://your-next-service.example.com
FACE_MEMORY_DEVICE_TOKEN=secret-configured-on-server
```

When offline, unknown-result status, device status, and response time wait in the SQLite `event_queue`. The service retries during the next camera cycle. After HTTP 202, only the uploaded row is removed. The Pi does not upload an image, embedding, or person name.

To check sync, disconnect Wi-Fi, run a local image or the camera, confirm audio playback, and confirm that the queued row count increases. Reconnect Wi-Fi and confirm the count drops and the endpoint accepts events. Use only consented participants, and record audio and sync results separately.

## Start automatically with systemd

Copy `pi/systemd/face-memory-pi.service` to `/etc/systemd/system/face-memory-pi.service`. Create `/etc/face-memory-pi.env` with permissions `0600`, then run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now face-memory-pi
sudo systemctl status face-memory-pi
sudo journalctl -u face-memory-pi -f
```

The service file uses the account `pi`; update it if the operating-system account is different. Do not add the database, WAV files, or person export files to the repository.

## Hardware and camera references

- [Raspberry Pi 2 Model B specifications and ports](https://www.raspberrypi.com/documentation/computers/sbcs.html): CAMERA is a 15-pin CSI connector; the board includes USB-A, a microSD slot, and 3.5 mm AV output.
- [Install and use Picamera2](https://www.raspberrypi.com/documentation/accessories/camera-software.html): use the Raspberry Pi OS camera packages and confirm the ribbon orientation.
- [Raspberry Pi OS 32-bit](https://www.raspberrypi.com/documentation/computers/os.html): suitable for 32-bit devices such as Raspberry Pi 2.
- [Raspberry Pi 2 power supply](https://www.raspberrypi.com/documentation/computers/getting-started.html): 5 V / 2.5 A supply with a micro-USB connector.
