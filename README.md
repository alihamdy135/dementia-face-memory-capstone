# ذاكرة | مساعد التذكّر

نسخة محلية لمشروع Capstone: واجهة عربية RTL، خدمة Next.js App Router وTypeScript، خدمة FastAPI داخلية لمعالجة الصور، وMongoDB Community لتخزين حسابات منفصلة. أداة تقييم YuNet/SFace ونسخة Raspberry Pi 2 تستخدمان `IdentityMatcher` وإعدادات الموديل نفسها.

> **حالة القياس:** لم تُقدّم صور تقييم حقيقية مصرح بها أو manifest موسوم بجلسات التصوير. لذلك `known_top1_accuracy` و`macro_f1` و`unknown_fpir` **غير مقاسة**. قيمة 0.45 في `model-v1.json` حدّ عرض مؤقت فقط، وليست نتيجة معايرة. لا تستخدم التعرف أو الصوت كقرار طبي أو كإجراء سلامة.

## ما يعمل

- حسابات بكلمات مرور مشتقة بـscrypt وجلسة Cookie موقعة؛ كل قراءة وكتابة للملفات الشخصية والنتائج والمحادثات مقيّدة بمعرّف الحساب.
- تسجيل شخص بالاسم والصلة، ورفع 1 إلى 8 صور. تُقبل أو تُرفض كل صورة منفردة حسب وجود وجه واحد، ولا يُحتفظ بالملف الأصلي أو بمساره؛ تُخزن بصمة الوجه وإصدار الموديل.
- تعديل الشخص وحذفه مع البصمات وسجل النتائج والمحادثات المرتبط به.
- التعرف من صورة أو من لقطة واحدة بعد معاينة الكاميرا. لا يوجد تصوير تلقائي. تظهر حالات المعروف، المجهول، الملتبس، بلا وجه، وجوه متعددة، ورفض الإذن.
- تسجيل ملاحظة صوتية فقط بعد تأكيد الشخص وموافقة واضحة. التفريغ العربي اختياري عبر Whisper محلي، والصوت المؤقت لا يُحفظ؛ النص يظهر للمراجعة ولا يدخل السجل إلا بعد تأكيده.
- تصدير شخص مختار وبصماته إلى ملف JSON خاص للاستيراد على Pi؛ لا يُصدّر سجل الصور أو المحادثات.
- دليل تقييم يمنع تسرب جلسات التصوير وفصل الغرباء بين validation وtest، ويفرض استخدام تقرير المعايرة قبل اختبار test.
- طابور SQLite على Pi يرفع حالة الجهاز والنتائج المجهولة وزمن الاستجابة فقط عند الاتصال.

## المتطلبات

- Node.js 20.9 أو أحدث وnpm.
- Python 3.11 أو أحدث.
- MongoDB Community محلي، أو `docker compose` إذا كان محرك Docker متاحًا.
- Compass اختياري لعرض نفس قاعدة MongoDB المحلية.

## تشغيل محلي

من مجلد المشروع:

```bash
cp .env.example .env
```

غيّر `SESSION_SECRET` و`DEVICE_SYNC_TOKEN` إلى قيم عشوائية طويلة. مثال لتوليد القيم محليًا:

```bash
python3 -c 'import secrets; print(secrets.token_hex(32))'
```

ضع الناتج في `.env`، ثم شغّل MongoDB بإحدى الطريقتين.

### MongoDB عبر Docker

```bash
docker compose up -d mongodb
```

تُحفظ البيانات في volume باسم `dementia_mongodb`. Compose يربط المنفذ على الجهاز المحلي فقط.

### MongoDB مثبتة محليًا

شغّل خادم MongoDB بعنوان `127.0.0.1:27017`، ثم اترك:

```dotenv
MONGODB_URI=mongodb://127.0.0.1:27017
MONGODB_DB=dementia_face_memory
```

في MongoDB Compass استخدم URI نفسه: `mongodb://127.0.0.1:27017`، وافتح قاعدة `dementia_face_memory`. يستطيع الموقع وCompass الاتصال بالخادم نفسه. لو غيّرت URI، اجعل القيمة نفسها في خادمي Next.js وPython.

### تثبيت وتشغيل خدمات التطبيق

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ./face_memory_system
npm install
```

نزّل أوزان YuNet وSFace من إصدار OpenCV Zoo المثبّت وتحقق من SHA-256 قبل تشغيل الخدمة. ملفات الأوزان لا تدخل المستودع العام:

```bash
python face_memory_system/models/download_models.py
```

في نافذة طرفية أولى، شغّل خدمة الوجه مرة واحدة؛ تفتح أوزان YuNet وSFace عند الإقلاع وتبقيها في الذاكرة:

```bash
source .venv/bin/activate
uvicorn face_memory.http_service:app --host 127.0.0.1 --port 8001 --workers 1
```

في نافذة ثانية:

```bash
npm run dev
```

افتح [http://localhost:3000](http://localhost:3000). أنشئ حسابًا خاصًا من صفحة البداية. الوصول إلى الكاميرا يعمل على `localhost` بعد موافقة المتصفح.

تحقق من جاهزية خدمة الموديل عبر `http://localhost:3000/api/health`؛ حالة `provisional_not_calibrated` تعني أن الحد 0.45 لم يُعاير بعد.

### Whisper المحلي (اختياري)

التفريغ غير مُفعّل إذا لم تتوفر حزمة Whisper وFFmpeg؛ تعرض الواجهة رسالة بذلك. لتجهيزه على جهاز يفي بموارد النموذج:

```bash
sudo apt install ffmpeg
source .venv/bin/activate
python -m pip install openai-whisper scipy
```

يجري تنزيل أوزان Whisper إلى مخبأ المستخدم عند أول استخدام. التسجيل يدعم العربية؛ اختبر مقطعًا قصيرًا على الجهاز الفعلي قبل العرض. تسجيل المتصفح مؤقت في الذاكرة، ويُرسل للتفريغ ثم يُحذف من الواجهة والخدمة.

## التقييم وملفات البوستر

راجع [دليل جمع الصور](docs/data-collection.md). ابدأ بـ[قالب manifest](face_memory_system/examples/manifest_template.csv)؛ خزّن الصور والـmanifest الخاص تحت `private_data/` فقط. الأعمدة المطلوبة `image_path,person_id,split,session_id`. لا تضع أسماء أو صورًا في الفرع العام.

عاير validation أولًا، بحد أقصى 5% FPIR للغرباء:

```bash
source .venv/bin/activate
face-memory-evaluate \
  --manifest private_data/manifest.csv \
  --mode calibrate \
  --max-unknown-fpir 0.05 \
  --camera "اسم الكاميرا والعدسة" \
  --device "اسم اللابتوب ومواصفاته" \
  --output face_memory_system/reports/private/validation.json
```

شغّل test فقط باستخدام تقرير validation المقفول وإصدار الموديل و`min_margin` نفسيهما:

```bash
face-memory-evaluate \
  --manifest private_data/manifest.csv \
  --mode test \
  --validation-report face_memory_system/reports/private/validation.json \
  --camera "اسم الكاميرا والعدسة" \
  --device "اسم اللابتوب ومواصفاته" \
  --output face_memory_system/reports/private/test.json
```

يكتب كل تشغيل JSON كاملًا داخل مسار التقرير، بالإضافة إلى `poster_metrics.csv` وSVG لمصفوفة الالتباس ومنحنى العتبة. اجعل مجلد التقرير خاصًا إذا احتوى JSON على معرفات أو مسارات ملفات. النسخ الجاهزة للملصق الموجودة في `reports/public/` مجهولة الهوية ومعلّمة «في انتظار بيانات الاختبار».

## Raspberry Pi 2

يبدأ التصدير من بطاقة الشخص في الموقع: اختر **تصدير Pi**، ثم على الجهاز انسخ ملف JSON إلى مجلد خاص واستورده:

```bash
python pi/face_memory_pi.py --import-person /path/to/pi-person-<id>.json --image /path/to/local-test.jpg
```

إعداد الكاميرا والتوصيلات والصوت وsystemd واختبار الشبكة مشروحة في [دليل Pi 2](pi/README.md). كل قياسات الصوت والكمون معلّمة **في انتظار الاختبار على Pi 2** حتى تُقاس على العتاد نفسه.

## Atlas وVercel لاحقًا

لا تتصل النسخة الحالية بخدمات عامة تلقائيًا. عند تجهيز نشر حي، غيّر `MONGODB_URI` إلى Atlas بعد النسخ والتحقق، واضبط `MODEL_SERVICE_URL` على عنوان HTTPS لخدمة Python و`MODEL_SERVICE_TOKEN` السر نفسه في خدمة Python وبيئة Vercel. أبقِ الخدمة خلف TLS والتحقق من الرمز؛ لا تعرض endpoint الموديل بلا مصادقة. التفاصيل في [إعداد النشر](docs/vercel-deployment.md).

لنقل قاعدة محلية إلى Atlas، استخدم `mongodump` إلى مجلد خاص ثم `mongorestore` إلى URI الهدف. انقل قاعدة البيانات وحدها بعد مراجعة النطاق؛ فهي تحتوي بصمات وجه وسجلات حسابات وليست مادة عامة.

## الاختبارات الحالية

شغّل الاختبارات المتاحة بعد تثبيت التبعيات:

```bash
python -m unittest discover -s face_memory_system/tests -v
npm run typecheck
npm run build
```

لا يوجد dataset مؤهل في التسليم؛ هذا لا يسمح بإعلان دقة على الوجوه. يجب أن تعرض لوحة القياس القيم الفعلية أو «غير مقاس» بدل استبدالها ببيانات تشغيل تجريبية.

## الترخيص والخصوصية

مصدر أوزان YuNet وSFace المثبّت وتراخيصهما وSHA-256 موثق في `face_memory_system/models/MODELS.md`؛ ينزّلهما `download_models.py` إلى المسار المحلي بعد التحقق. ملف ZIP الموروث وملف Insight PDF وأي صور أو قواعد بيانات لا تدخل النشر العام. `.gitignore` يستثني أسرار البيئة والبيانات المحلية والصوت والصور وقواعد البيانات.
