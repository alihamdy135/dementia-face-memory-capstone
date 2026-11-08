# تشغيل Raspberry Pi 2 Model B

النقطة هنا مستقلة عن موقع الويب عند انقطاع الشبكة: بصمات محلية في SQLite، وملفات WAV يضيفها مقدم الرعاية، وكاميرا CSI أو صورة/فيديو محلي. تستخدم نفس `OpenCVFaceEncoder` و`IdentityMatcher` وإعدادات `face_memory_system/config/model-v1.json`. لا يتضمن الجهاز صور المتطوعين أو قاعدة الموقع كاملة.

## توصيلات العتاد

- `CSI 15-pin → CAMERA`: وصّل الشريط المرن بين منفذ الكاميرا ومنفذ الكاميرا على اللوحة.
- `USB Wi-Fi → USB-A`: أوصل محول USB Wi-Fi بإحدى فتحات USB-A.
- `سماعة → 3.5 mm`: وصل السماعة الفعالة بخرج الصوت 3.5 مم.
- `5V/2.5A → Micro-USB`: استخدم مصدر طاقة ثابت 5V / 2.5A إلى مدخل الطاقة micro-USB.
- `microSD → فتحة الكارت`: ثبّت Raspberry Pi OS Lite 32-bit ثم أدخل البطاقة.

افصل الطاقة قبل تحريك شريط CSI. راجع اتجاه الشريط وعلامة التلامس على اللوحة والكاميرا قبل التشغيل، وتحقق من إصدار اللوحة/الكاميرا الفعلي قبل العرض.

## إعداد Raspberry Pi OS Lite 32-bit

1. ثبّت Raspberry Pi OS Lite 32-bit على microSD، واضبط البلد وWi-Fi وSSH من أداة التصوير.
2. حدّث النظام وثبّت أدوات الكاميرا والصوت:

   ```bash
   sudo apt update
   sudo apt full-upgrade -y
   sudo apt install -y python3-venv python3-pip python3-numpy python3-opencv \
     python3-picamera2 ffmpeg alsa-utils git
   ```

3. انسخ المشروع إلى `/opt/face-memory`. أنشئ بيئة تسمح باستخدام حزم OpenCV وPicamera2 المثبتة من النظام:

   ```bash
   cd /opt/face-memory
   python3 -m venv --system-site-packages .venv
   .venv/bin/python -m pip install --upgrade pip
   ```

4. تأكد أن OpenCV على هذا الإصدار يحتوي `FaceDetectorYN` و`FaceRecognizerSF`. إذا لم يتوفرا، استخدم wheel متوافقًا مع Raspberry Pi OS 32-bit من مصدر موثوق؛ لا تجمع ملفات موديل مختلفة عن التي في `MODELS.md`.
5. شغّل محليًا صورة أو فيديو للاختبار قبل تركيب الكاميرا:

   ```bash
   .venv/bin/python pi/face_memory_pi.py --image /path/to/local-test.jpg
   .venv/bin/python pi/face_memory_pi.py --video /path/to/local-test.mp4 --scan-interval 1.5
   ```

## نقل شخص محدد إلى Pi

1. سجّل الدخول إلى الموقع، وافتح الشخص المطلوب، واختر **تصدير Pi**.
2. انقل ملف `pi-person-<id>.json` بوسيلة محلية موثوقة إلى Pi. الملف خاص ويحتوي بصمات الوجه؛ لا ترفعه إلى Git أو مراسلة عامة.
3. استورده في SQLite المحلية:

   ```bash
   .venv/bin/python pi/face_memory_pi.py \
     --import-person /path/to/pi-person-<id>.json \
     --image /path/to/local-test.jpg
   ```

يمكن استيراد عدة أشخاص بإضافة `--import-person` لكل ملف. JSON لا يحوي الصور الأصلية أو المحادثات. أسماء الملفات الصوتية هي `<personId>.wav` تحت `~/.local/share/face-memory/audio/`. سجّلها بموافقة مقدم الرعاية وبالصوت المطلوب، ثم تحقق من تشغيل WAV:

```bash
aplay ~/.local/share/face-memory/audio/<personId>.wav
```

يُعلن الاسم/الصلة المسجلان في WAV فقط عند تطابق مقبول، مع مهلة تكرار افتراضية 12 ثانية. لا توجد مكبرات صوت أو TTS تلقائية. عدّل زمن المهلة عبر `--cooldown`.

## كاميرا CSI والقياس

اختبر الكاميرا أولًا بـ`rpicam-hello --list-cameras` إن توفر، ثم نفذ:

```bash
.venv/bin/python pi/face_memory_pi.py --camera --scan-interval 1.0 --cooldown 12
```

عايرها باستخدام لوحة checkerboard مطبوعة ومقاس مربع معروف: ثبّت الكاميرا على موضع العرض، التقط صورًا في زوايا ومسافات الإضاءة الفعلية، قِس أبعاد الإطار ومجال الرؤية، ثم أعد الاختبار من مسافة الاستخدام. أعد المعايرة إذا تغيّر موضع العدسة أو ارتفاعها.

يعرض البرنامج `response_ms` من قراءة إطار الكاميرا/الصورة حتى بدء WAV، ويسجل `max` و`p95` للعروض الصوتية التي بدأت. نفّذ 30 تجربة على الأقل مع كتابة الإضاءة والمسافة ونوع العدسة؛ احتفظ بسجل CSV من خرج الجهاز وقارن أقصى زمن بهدف ثانيتين. قياسات الصور والفيديو على اللابتوب ليست قياسات Pi. كل النتائج الحالية: **في انتظار الاختبار على Pi 2**.

## فصل الشبكة ثم عودة الاتصال

يمكن إتمام التعرّف والصوت محليًا من دون Wi-Fi. ضع في `/etc/face-memory-pi.env` القيم التالية لرفع الأحداث بعد عودة الاتصال:

```dotenv
FACE_MEMORY_PI_DB=/home/pi/.local/share/face-memory/face-memory.sqlite3
FACE_MEMORY_PI_AUDIO_DIR=/home/pi/.local/share/face-memory/audio
FACE_MEMORY_DEVICE_ID=pi2-classroom-01
FACE_MEMORY_SYNC_URL=https://your-next-service.example.com
FACE_MEMORY_DEVICE_TOKEN=secret-configured-on-server
```

النتائج المجهولة والحالة ووقت الاستجابة تنتظر في `event_queue` داخل SQLite عند انقطاع الشبكة. تعيد الخدمة محاولة الرفع في دورة الكاميرا التالية؛ عند نجاح HTTP 202 تحذف الصف المرفوع فقط. لا يرفع Pi صورة أو embedding أو اسم الشخص.

اختبار الشبكة: اقطع Wi-Fi، شغّل لقطة محلية أو الكاميرا وتأكد أن WAV يعمل وأن صف الحدث زاد في SQLite. أعد Wi-Fi، ثم تأكد أن عدد الصفوف يقل وأن endpoint يعيد قبول الأحداث. نفّذ ذلك دون متطوعين غير موافقين، وسجّل نجاح الصوت وتزامن الصفوف كلًّا على حدة.

## تشغيل تلقائي بـsystemd

انسخ `pi/systemd/face-memory-pi.service` إلى `/etc/systemd/system/face-memory-pi.service`، أنشئ `/etc/face-memory-pi.env` بصلاحية `0600`، ثم:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now face-memory-pi
sudo systemctl status face-memory-pi
sudo journalctl -u face-memory-pi -f
```

اسم المستخدم في الملف هو `pi`؛ عدّله إذا كان حساب النظام مختلفًا. لا تضف قاعدة البيانات أو WAV أو ملف التصدير إلى المستودع.

## مراجع العتاد والكاميرا

- [مواصفات Raspberry Pi 2 Model B ومنافذه](https://www.raspberrypi.com/documentation/computers/sbcs.html): CAMERA هو منفذ CSI ذي 15 pin، واللوحة توفر USB-A وفتحة microSD وخرج AV 3.5 مم.
- [تثبيت واستخدام Picamera2](https://www.raspberrypi.com/documentation/accessories/camera-software.html): Raspberry Pi OS Lite يتضمن مسار Picamera2 المناسب؛ استخدم حزم النظام وتحقق من اتجاه شريط الكاميرا.
- [اختيار Raspberry Pi OS 32-bit](https://www.raspberrypi.com/documentation/computers/os.html): موصى به للأجهزة ذات معالج 32-bit مثل Raspberry Pi 2.
- [طاقة Raspberry Pi 2](https://www.raspberrypi.com/documentation/computers/getting-started.html): مزود 5V/2.5A بموصل micro-USB.
