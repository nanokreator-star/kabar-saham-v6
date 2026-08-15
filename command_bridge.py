ga da install dia abis download langsung masuk sini btw itu python 3.13 
saya keluar nya ini
ini hasilnya
c31f36c4-3be0-4420-957e-e0058234bb11.mp4
File
hasilnya

Ya, saya sudah cek videonya. Bot Anda sekarang sudah berjalan dengan benar. ✅

Yang sudah berhasil:

python main.py aktif tanpa error.
RSS parser berjalan.
/latest, /ipo, /rights, dan /ma sudah merespons.
Berita sudah diurutkan dari yang terbaru.
Rights Issue tanggal 13 Agustus 2026 sudah terbaca.
Bot sudah terhubung ke Telegram dan siap melakukan monitoring otomatis setiap 10 menit.

Tulisan:

KeyboardInterrupt
^C

di bagian atas CMD bukan error. Itu muncul karena Anda sebelumnya menghentikan bot dengan Ctrl + C.

Namun dari hasil videonya saya menemukan beberapa hal yang sebaiknya kita tingkatkan sebelum bot dipakai serius.

Pertama, masih ada false positive. Contohnya pada hasil /ipo muncul:

“Masjid Istiqlal: Gerakan ‘Yuk Wakaf Saham’ Bukan IPO”

Karena sistem sekarang membaca kata IPO, berita yang sebenarnya mengatakan bukan IPO tetap terdeteksi sebagai IPO. Ini harus kita filter.

Kedua, klasifikasi Indonesia masih bisa lebih akurat. Contohnya berita emiten BEI seperti CBRE kadang masih ditulis:

Kategori: GLOBAL 🌐

Padahal seharusnya:

Kategori: INDONESIA 🇮🇩

Ketiga, untuk tujuan investasi, format alert sekarang masih terlalu sederhana. Saya ingin nantinya hasilnya lebih seperti ini:

📣 RIGHTS ISSUE ALERT

Ticker: ENRG
Emiten: PT Energi Mega Persada Tbk
Status: Rights Issue
Harga saham: —
Harga Rights: —
Rasio HMETD: —
Potensi Dilusi: —
Dana yang dihimpun: —
Penggunaan Dana: —
Standby Buyer: —

🟢 Corporate Action Score: 78/100

Kesimpulan: Perlu dipantau

🔗 Sumber berita

Begitu juga IPO nantinya bisa menjadi:

🆕 IPO ALERT

Emiten: PT XYZ Tbk
Ticker: XYZA
Harga Bookbuilding: Rp150–Rp180
Saham ditawarkan: 20%
Target dana: Rp500 miliar
Underwriter: ABC Sekuritas
Listing: 25 Agustus 2026
Penggunaan dana: ekspansi 70%, modal kerja 30%
Oversubscribe: 18x

🔥 IPO Score: 84/100

Dan M&A:

🤝 ACQUISITION ALERT

Acquirer: PT ABC Tbk
Ticker: ABCD
Target: XYZ Ltd
Negara: 🇮🇩 → 🇸🇬
Stake: 70%
Nilai: Rp2,3 triliun
Status: SPA Signed
Perubahan pengendali: Ya

🟢 Potential Catalyst

Jadi secara teknis bot Anda sekarang sudah hidup. Tahap selanjutnya bukan lagi memperbaiki instalasi, melainkan meningkatkan kualitas informasi dan akurasi filter.

Saya sarankan kita lanjut ke V4, dengan fokus: anti berita palsu/false positive + ticker saham + hanya emiten BEI + detail IPO/rights issue/M&A + scoring. Itu yang akan membuat “Kabar Saham” benar-benar berguna untuk mencari peluang corporate action, bukan hanya sebagai agregator berita.

env. yang ,mana?
e21e4385-35e6-4837-8f48-b675bce491f0.mp4
File
hasilnya

Saya sudah cek videonya. V4 sudah berjalan dengan baik dan jauh lebih rapi dibanding versi sebelumnya. Beberapa fungsi penting sudah berhasil terbukti:

Rights Issue terdeteksi dengan kategori Indonesia.
Ticker berhasil muncul, misalnya BRNA, BNII, MAPI.
Nilai transaksi berhasil diekstrak, misalnya Rp372,6 miliar, Rp9,32 triliun.
Corporate Action Score sudah muncul dan klasifikasinya terbaca.
M&A, tender offer, IPO, dan rights issue sudah terpisah.
Sumber dan tanggal publikasi sudah tampil.
Tidak terlihat error pada proses bot.

Contoh yang sudah bagus dari hasil Anda:

RIGHTS ISSUE ALERT
Ticker: BRNA
Nilai: Rp372,6 Miliar
Corporate Action Score: 83/100
Klasifikasi: MENARIK

dan:

M&A / TAKEOVER ALERT
Ticker: MAPI
Jenis: TENDER OFFER
Nilai: Rp9,32 Triliun
Kategori: INDONESIA

Namun saya menemukan 2 kelemahan yang layak kita perbaiki di V4.1.

Pertama, filter IPO masih terlalu luas. Contohnya:

“Mengobati Jeri IPO BUMN”

Itu sebenarnya lebih seperti artikel opini/tema IPO, bukan pengumuman emiten yang sedang IPO. Bot tetap memasukkannya karena ada kata IPO.

Kedua, ticker belum selalu muncul. Contohnya berita:

“CBRE Rencanakan Rights Issue Rp1,91 Triliun…”

Ticker CBRE sebenarnya sudah ada di awal judul, tetapi bot belum menangkapnya karena parser saat ini lebih kuat membaca format seperti (MAPI) atau saham BRNA.

Jadi tahap selanjutnya saya sarankan V4.1 Accuracy Upgrade, fokus pada:

1. IPO hanya alert jika ada indikasi nyata:
   - calon emiten
   - bookbuilding
   - prospektus
   - penawaran awal
   - listing
   - harga IPO
   - tanggal efektif
   - saham yang ditawarkan


2. Deteksi ticker diperluas:
   CBRE Rencanakan Rights Issue...
   → Ticker: CBRE


3. Bedakan level berita IPO:
   RUMOR
   RENCANA
   BOOKBUILDING
   OFFERING
   LISTING


4. Rights Issue:
   deteksi rasio
   harga pelaksanaan
   jumlah saham baru
   nilai dana
   standby buyer


5. M&A:
   deteksi acquirer
   target
   stake %
   nilai transaksi
   perubahan pengendali

Setelah itu bot akan mulai terasa seperti terminal corporate action mini, bukan sekadar aggregator berita.

Kalau kita lanjut, saya sarankan langsung buat V4.1 Accuracy Upgrade sekarang.

dbb51991-f261-4bb1-b9bc-eb71996d142c.mp4
File

Saya sudah cek hasil V4.1 dari video yang Anda kirim. Secara umum, upgrade-nya berhasil dan beberapa fitur utama sudah bekerja jauh lebih baik.

Yang sudah bagus: Rights Issue CBRE sekarang terdeteksi sebagai Indonesia, status RENCANA, nilai sekitar Rp1,91 triliun, dan skornya sudah muncul. Ticker seperti AHAP dan BMAS juga berhasil terbaca; bahkan pada AHAP, harga pelaksanaan Rp50 sudah berhasil diekstrak. Ini berarti parser V4.1 untuk ticker dan detail Rights Issue sudah mulai bekerja sesuai tujuan.

Namun saya melihat ada 3 hal yang masih perlu dibenahi sebelum bot kita anggap matang. Pada /ipo, masih muncul artikel seperti “Baru 7 IPO hingga Juli 2026…” yang sebenarnya merupakan rekap pasar, bukan calon IPO baru. Ada juga berita seperti “saham ... jeblok 14 persen di bawah harga IPO”, yang sebenarnya berita pergerakan saham setelah IPO, bukan corporate action IPO baru. Jadi filter IPO masih perlu membedakan IPO baru vs berita yang hanya membahas kata IPO.

Pada Rights Issue juga ada satu masalah kecil: ketika artikel menyebut harga pelaksanaan Rp50, parser kadang menampilkan Rp50 lagi sebagai Nilai/Dana. Seharusnya formatnya cukup:

💵 Harga Pelaksanaan: Rp50
💰 Target Dana: — / belum terdeteksi

bukan:

💵 Harga Pelaksanaan: Rp50
💰 Nilai/Dana: Rp50

Selain itu saya ingin ranking dibuat lebih cerdas. Saat ini semua berita masih relatif setara. Padahal idealnya bot memprioritaskan:

🔥 PRIORITAS TINGGI
IPO BOOKBUILDING / OFFERING
Rights Issue sudah efektif
SPA / akuisisi sudah ditandatangani
Perubahan pengendali
Mandatory Tender Offer


🟡 PRIORITAS MENENGAH
Rencana IPO
Rencana Rights Issue
Rencana akuisisi


⚪ PRIORITAS RENDAH
Rekap pasar
Opini
Berita pasca-IPO
Artikel edukasi

Jadi menurut saya kita lanjut langsung ke V4.2 Precision Upgrade dengan tiga fokus: hapus berita IPO pasca-listing/rekap, pisahkan harga pelaksanaan dari nilai dana, dan buat Priority Level HIGH / MEDIUM / LOW berdasarkan tahap corporate action.

Kalau kita lakukan itu, bot akan semakin mendekati corporate-action scanner, bukan sekadar news aggregator.

Thursday 10:10 PM
21106443-87a5-4b03-80e7-1cac709c646f.mp4
File

Saya sudah cek videonya. V4.2 berhasil jalan dan fitur utamanya bekerja. Hasilnya sudah jauh lebih presisi.

Yang sudah terbukti bekerja:

/high berhasil menyaring corporate action prioritas tinggi.
Tender Offer MAPI → HIGH, kategori Indonesia, perubahan pengendali terindikasi.
Takeover MKNT → ticker terbaca, CHANGE OF CONTROL, stake 80,04%, priority HIGH.
Rights Issue CBRE → ticker terbaca, status RENCANA, nilai Rp1,91 triliun.
Rights Issue lain sudah bisa membedakan priority LOW/MEDIUM.
Berita Indonesia konsisten masuk kategori INDONESIA 🇮🇩.
Corporate Action Score dan klasifikasi tampil normal.
Tidak terlihat error di proses bot.

Namun ada 2 hal yang masih saya lihat perlu dirapikan.

Pertama, pada Rights Issue BRNA terlihat:

Priority: LOW
Corporate Action Score: 76/100
Klasifikasi: MENARIK

Secara sistem ini sebenarnya bisa terjadi karena Priority = seberapa urgent/actionable tahap transaksinya, sedangkan Score = kualitas/kekuatan informasi yang ditemukan. Tetapi bagi pengguna bisa terlihat kontradiktif. Menurut saya nanti formatnya lebih jelas kalau menjadi:

⚡ Urgency: LOW
🎯 Information Score: 76/100
📌 Quality: MENARIK

Jadi tidak membingungkan.

Kedua, filter IPO masih meloloskan berita seperti:

“BEI Kantongi Empat Calon Emiten Baru…”

Itu valid sebagai informasi pipeline IPO, tetapi belum tentu actionable karena belum menunjuk satu calon emiten tertentu. Idealnya kita pisahkan menjadi:

📰 IPO PIPELINE
→ berita umum BEI / jumlah antrean IPO


🆕 IPO CANDIDATE
→ calon emiten spesifik


🔥 IPO ACTIONABLE
→ bookbuilding / harga / offering / listing

Dengan begitu /ipo tetap lengkap, tetapi /high hanya memunculkan IPO yang sudah actionable.

Jadi status bot saat ini menurut saya sudah layak digunakan untuk monitoring otomatis. Tahap berikutnya yang paling bernilai adalah V4.3 Intelligence Layer: pisahkan Urgency vs Information Score, klasifikasi IPO Pipeline/Candidate/Actionable, lalu tambahkan Catalyst: Positive / Neutral / Negative dan alasan singkatnya. Itu akan membuat alert jauh lebih enak dibaca sebagai investor.

4f5145f7-6b93-4937-8c66-3e8bba1f1e6f.mp4
File

Saya sudah cek hasil V4.3 dari videonya. Secara umum, Intelligence Layer sudah bekerja dan peningkatannya terlihat jelas.

Yang sudah benar:

/actionable tidak memaksakan hasil kalau memang belum ada IPO actionable — ini bagus.
/pipeline sudah bisa menandai berita antrean IPO sebagai PIPELINE.
Urgency, Information Score, Information Quality, dan Catalyst sudah terpisah sehingga tidak membingungkan.
Takeover seperti MKNT dan AKSI terbaca sangat baik: CHANGE OF CONTROL, HIGH, stake terdeteksi, Catalyst POSITIVE.
Tender Offer juga sudah masuk kategori HIGH secara konsisten.

Tapi dari video saya masih menemukan 3 edge case yang perlu dibereskan:

Berita seperti “BEI Catat 8 Calon Emiten IPO…” masih masuk CANDIDATE, padahal seharusnya PIPELINE karena itu berita agregat pasar, bukan satu calon emiten spesifik.
Berita “ENRG usai Rights Issue” masih masuk sebagai Rights Issue alert, padahal itu post-event commentary. Seharusnya tidak masuk corporate-action alert baru.
Tender Offer “sepi peminat” tetap diberi Catalyst POSITIVE hanya karena statusnya Tender Offer. Seharusnya konteks seperti sepi peminat, minim partisipasi, atau kurang terserap menurunkan Catalyst menjadi NEUTRAL atau NEGATIVE.

Jadi V4.3 sudah layak dipakai, tetapi saya sarankan berikutnya kita buat V4.4 Context Awareness Upgrade dengan fokus: deteksi berita agregat → PIPELINE, filter post-event commentary, dan catalyst yang membaca sentimen/konteks transaksi—not just stage.

Kalau lanjut V4.4, itu akan membuat bot jauh lebih pintar dalam membedakan event aktif vs berita setelah kejadian dan corporate action bagus vs corporate action yang respons pasarnya lemah.

85ad7c68-5e28-4f31-95ae-a77c32a9a3c6.mp4
File

Saya sudah cek hasil V4.4 dari videonya. Secara umum, upgrade ini berhasil dan Context Awareness sudah mulai bekerja sesuai tujuan.

Yang sudah terbukti benar:

Berita seperti “BEI simpan empat calon emiten baru…” sekarang masuk IPO Class: PIPELINE dan Context: MARKET PIPELINE. Ini tepat.
Rights Issue seperti CBRE, BRNA, dan AHAP masuk ACTIVE EVENT, bukan pipeline.
Field Urgency, Context, Information Score, Information Quality, dan Catalyst tampil dengan struktur yang jauh lebih jelas.
M&A seperti MAPI dan MKNT tetap terbaca sebagai event aktif dengan HIGH urgency.
Tidak terlihat error di bot.

Contoh yang menurut saya sudah sangat bagus:

Jenis: RIGHTS ISSUE
Ticker: CBRE
Status: RENCANA
Urgency: MEDIUM
Context: ACTIVE EVENT
Nilai/Dana: Rp1,91 Triliun


Information Score: 89/100
Information Quality: SANGAT KUAT
Catalyst: NEUTRAL

Dan untuk IPO pipeline:

Jenis: IPO
Status: RENCANA / PROSPEKTUS
Urgency: MEDIUM
Context: MARKET PIPELINE
IPO Class: PIPELINE


Catalyst: NEUTRAL
• Masih berupa informasi pipeline pasar,
  belum transaksi emiten spesifik.

Ini sudah jauh lebih masuk akal.

Masih ada 3 area kecil yang saya lihat bisa kita sempurnakan berikutnya:

Context: MARKET PIPELINE sudah benar, tetapi Urgency masih MEDIUM. Untuk berita pipeline umum, saya lebih suka otomatis LOW, supaya /high dan ranking tidak terlalu terpengaruh.
Rights Issue seperti AHAP dengan status RIGHTS ISSUE INFO masih LOW. Ini wajar, tapi kalau nanti harga pelaksanaan + rasio + tanggal cum-right sudah ada, urgency sebaiknya otomatis naik ke MEDIUM/HIGH.
Catalyst M&A masih cenderung positif hanya karena CHANGE OF CONTROL/TENDER OFFER. Nanti bisa kita tambahkan analisis harga tender vs harga pasar, supaya lebih berguna bagi investor.

Jadi menurut saya V4.4 sudah layak dipakai sebagai corporate-action monitoring bot.

Tahap berikutnya yang paling bernilai adalah V5 Decision Support, bukan lagi sekadar filter berita. Di V5 kita bisa tambah:

Rights Issue: hitung TERP, dilusi, discount rights, kebutuhan dana tebus.
IPO: valuasi sederhana, market cap implied, penggunaan dana, stage, underwriter.
M&A/Tender: harga tender vs harga pasar, premium/discount, stake, change of control.
Output akhir: Watch / Ignore / High Attention, bukan rekomendasi beli/jual.

Kalau mau, kita bisa langsung gas ke V5 Decision Support.

hasil instal
2531e6a6-1ed6-4ba6-a003-60bcd3fc1885.mp4
File
udah selesai belum?

Sudah, instalasinya selesai dengan sukses. Terlihat jelas ada tulisan:

Successfully installed ...
...
yfinance-1.6.0

dan prompt CMD sudah kembali ke:

C:\Users\ASUS\Downloads\telegram_corporate_action_alert_v2\...>

Jadi sekarang lanjut ke langkah berikutnya.

Buka file .env, lalu pastikan tambahkan:

MARKET_DATA_ENABLED=1
MARKET_CACHE_MINUTES=15
DECISION_LOTS=1
MARKET_ENRICH_LIMIT=5

Setelah disimpan, jalankan:

python main.py

Kalau V5 aktif dengan benar, nanti kita tes:

/status
/market BBCA
/decision
/analyze CBRE

Kirim screenshot hasil python main.py setelah dijalankan.

24fd01f4-37fe-4299-bc6a-794594b4a280.mp4
File

Saya sudah cek videonya. V5 berhasil berjalan dengan baik. Fitur Decision Support yang baru sudah aktif dan tidak terlihat error.

Yang sudah terbukti bekerja dari hasil Anda:

/market BBCA berhasil mengambil harga pasar terakhir, perubahan harian, dan tanggal data pasar.
/decision berhasil membuat V5 Decision Board dan mengurutkan corporate action berdasarkan Monitoring Signal.
M&A/Tender Offer sudah menampilkan:
ticker,
status transaksi,
urgency,
context,
stake,
nilai transaksi,
HIGH ATTENTION,
Information Score,
Catalyst.
/analyze CBRE berhasil menggabungkan berita Rights Issue + harga pasar CBRE.

Contoh CBRE dari hasil Anda sudah bagus:

📣 RIGHTS ISSUE ALERT


Ticker: CBRE
Status: RENCANA
Urgency: MEDIUM
Context: ACTIVE EVENT


Nilai/Dana: Rp1,91 Triliun
Harga Pasar: Rp675
Perubahan Harian: -0,74%


Monitoring Signal:
👀 WATCH


Information Score: 89/100
Information Quality: 🔥 SANGAT KUAT
Catalyst: NEUTRAL
Kenapa CBRE belum muncul TERP?

Ini bukan error.

Untuk menghitung TERP, bot membutuhkan minimal:

Harga saham pasar ✅
Harga pelaksanaan Rights ❌
Rasio HMETD ❌

Rumusnya:

TERP =
(Saham Lama × Harga Pasar)
+
(Saham Baru × Harga Rights)
──────────────────────────
Total Saham Setelah Rights

Karena artikel/snippet CBRE yang terbaca baru memberi informasi target dana Rp1,91 triliun, belum memberikan rasio dan harga pelaksanaan, bot benar dengan tidak mengarang TERP.

Ini justru perilaku yang kita inginkan.

Decision Board juga sudah bekerja

Saya melihat corporate action seperti tender offer sekarang mendapat:

Monitoring Signal:
🔥 HIGH ATTENTION

sementara Rights Issue yang masih tahap rencana:

Monitoring Signal:
👀 WATCH

Ini sudah jauh lebih logis daripada semua corporate action dianggap sama penting.

Satu keterbatasan terbesar V5 sekarang

Bot masih mengambil detail terutama dari:

Google News title + snippet

Padahal informasi penting seperti:

rasio HMETD,
harga pelaksanaan,
tanggal cum-right,
recording date,
jumlah saham baru,
harga tender,
penggunaan dana,
underwriter,
jumlah saham IPO,

sering tidak ditulis lengkap di snippet.

Akibatnya V5 sudah punya mesin kalkulatornya, tetapi kadang bahan perhitungannya belum tersedia.

Jadi tahap berikutnya yang menurut saya paling signifikan bukan menambah rumus lagi, tetapi membuat bot membuka artikel/dokumen sumber dan mengambil detail di dalamnya.

Idealnya nanti:

BERITA TERDETEKSI
       ↓
Baca title + snippet
       ↓
Buka sumber berita
       ↓
Extract detail lengkap
       ↓
┌─────────────────────────┐
│ Harga Rights            │
│ Rasio HMETD             │
│ Jumlah saham baru       │
│ Cum / Ex Right          │
│ Standby Buyer           │
│ Harga Tender            │
│ Underwriter             │
│ Use of Funds            │
└─────────────────────────┘
       ↓
Ambil harga pasar
       ↓
Hitung TERP / Dilusi /
Tender Premium / IPO Value
       ↓
Decision Support Telegram

Jadi status V5 saat ini: berhasil ✅. Market-data layer, Decision Board, /analyze, dan monitoring signal semuanya sudah hidup. Langkah paling bernilai berikutnya adalah V5.1 Deep Article Extraction, supaya perhitungan TERP dan analisis lainnya jauh lebih sering terisi otomatis, bukan hanya ketika angka kebetulan ada di judul/snippet.

a37f78b4-52e9-4813-a046-07dfc8dc6948.mp4
File

Saya sudah cek videonya. V5.1 berhasil aktif dan tidak terlihat error di program, tetapi dari hasil nyata ini kita menemukan satu bottleneck penting.

Yang sudah bekerja:

/status menunjukkan V5.1, Market Data ON, Deep Extraction ON.
/deep CBRE dan /decision berjalan.
Harga pasar ticker masih berhasil diambil.
Decision Support, Information Score, Catalyst, Monitoring Signal, M&A dan Rights Issue tetap berfungsi.
Bot tidak crash saat mencoba membaca artikel.

Namun bagian ini muncul berulang kali:

🔬 Deep Extraction: ⚪ GOOGLE ONLY

Artinya V5.1 menemukan berita dari Google News, tetapi belum berhasil menerjemahkan URL Google News menjadi URL artikel asli publisher. Akibatnya bot belum benar-benar membaca isi penuh artikel CBRE, AHAP, dan berita lain.

Itu menjelaskan kenapa hasil CBRE masih seperti:

Ticker: CBRE ✅
Harga Market: Rp680 ✅
Nilai Dana: Rp1,91 T ✅


Rasio HMETD: belum ada ❌
Harga Pelaksanaan: belum ada ❌
Cum-right / Ex-right: belum ada ❌
Recording Date: belum ada ❌


Deep Extraction: GOOGLE ONLY

Jadi mesin TERP V5 tidak bermasalah. Bahan perhitungannya yang belum berhasil diambil dari publisher.

Saya juga melihat Decision Board sudah bekerja cukup baik. Tender Offer/Change of Control tetap bisa masuk:

Urgency: HIGH
Context: ACTIVE EVENT
Monitoring Signal: HIGH ATTENTION
Catalyst: POSITIVE

sedangkan Rights Issue yang informasinya belum lengkap tetap WATCH. Itu perilaku yang benar.

Upgrade berikutnya harus fokus ke resolver

Menurut saya jangan tambah fitur analisis baru dulu. Yang paling bernilai sekarang adalah V5.2 Source Resolver Upgrade:

Google News RSS
      ↓
Decode / resolve Google News URL
      ↓
Cari canonical publisher URL
      ↓
Buka halaman publisher
      ↓
Parse HTML + JSON-LD
      ↓
Extract:
• Rasio HMETD
• Harga pelaksanaan
• Cum / Ex-right
• Recording date
• Jumlah saham
• Standby buyer
• Harga tender
• Underwriter
• Use of funds
      ↓
Decision Support
      ↓
TERP / Dilusi / Tender Premium

Saya juga akan buat resolver punya beberapa fallback, jadi bukan hanya satu metode. Misalnya:

METHOD 1 → HTTP redirect
METHOD 2 → canonical / og:url
METHOD 3 → publisher domain + exact title matching
METHOD 4 → source URL fallback


Jika tetap gagal:
GOOGLE ONLY

Jadi kesimpulan hasil video Anda:

Telegram Bot ✅
Market Data ✅
Decision Support ✅
V5.1 Engine ✅
Deep Parser ✅
Google News → Publisher Resolver ❌/belum optimal

Yang perlu kita kerjakan berikutnya adalah V5.2 Source Resolver, karena kalau bagian itu berhasil, fungsi TERP dan analisis detail yang sudah kita bangun akan mulai terisi jauh lebih sering.

94db3f64-4a13-4518-99e7-82a2c64fd754.mp4
File
ab6035df-1988-4bdb-95b6-8965649f4585.mp4
File

Saya sudah cek videonya. V5.3 berhasil aktif, tetapi Google News Decoder belum berhasil mendapatkan URL publisher asli.

Bagian paling penting dari hasilnya:

Bot aktif — V5.3 ✅
Deep extraction: ON ✅
Source resolver: ON ✅
Google decoder: ON ✅
Batch decoder: ON ✅

Tetapi ketika Anda menjalankan:

/decode CBRE

hasilnya:

Status: BELUM BERHASIL
Method: BATCH_FAILED
Info: garturlres URL not found.

Kemudian:

/resolve CBRE

masih menghasilkan:

Source Resolver: GOOGLE ONLY
Deep Extraction: GOOGLE ONLY


Resolver attempts:
• GNEWS_DECODER:BATCH_FAILED

Jadi diagnosisnya sekarang sudah sangat spesifik:

Telegram Bot            ✅
RSS Scanner             ✅
Corporate Action Filter ✅
Ticker Detection        ✅
Market Data             ✅
Decision Support        ✅
Deep Extraction Engine  ✅
Source Resolver         ✅ berjalan
Google Batch Request    ✅ terkirim
Response Parser         ❌ belum cocok dengan response live Google

Artinya batchexecute tidak sekadar gagal koneksi. Request-nya sampai, tetapi kode V5.3 tidak menemukan format garturlres yang diharapkan pada respons Google saat ini.

CBRE tetap bisa dianalisis dari snippet:

Ticker           : CBRE
Rights Issue     : Rp1,91 triliun
Harga pasar      : Rp680
Status           : RENCANA
Urgency          : MEDIUM
Monitoring Signal: WATCH

Tetapi karena:

Deep Extraction: GOOGLE ONLY

maka harga pelaksanaan + rasio HMETD belum didapat, sehingga TERP belum bisa dihitung. Itu perilaku yang benar—bot tidak mengarang angka.

Next fix yang tepat

Jangan tambah fitur investasi dulu. Kita perlu V5.3.1 Live Batchexecute Parser Fix.

Saya akan ubah core menjadi:

Google token
   ↓
batchexecute
   ↓
Simpan diagnostic response secara aman
   ↓
Parser Format A
Parser Format B
Parser nested JSON
Parser escaped JSON
Parser RPC envelope
   ↓
Cari seluruh URL HTTP/HTTPS kandidat
   ↓
Buang URL Google
   ↓
Cocokkan domain publisher + judul
   ↓
Publisher URL
   ↓
Deep Extraction

Dan tambahkan command diagnostik:

/decoderdebug CBRE

Outputnya bukan response mentah yang panjang, tapi cukup:

HTTP Status       : 200
Response Size     : 8.4 KB
RPC Found         : YES
garturlres Found  : NO
URL Candidates    : 3
Best Candidate    : emitennews.com

Dengan begitu kalau Google mengubah envelope lagi, kita bisa melihat di titik mana parser gagal, bukan hanya BATCH_FAILED.

Jadi hasil video ini justru sangat berguna: masalah berikutnya sudah terisolasi sampai ke parser response batchexecute. Tahap yang tepat sekarang adalah V5.3.1 Parser Fix, bukan rombak bot lagi.

32e6beaf-db98-49f0-aff3-ac90f866ebd7.mp4
File

Saya sudah cek videonya. V5.3.1 sudah terpasang dan fitur debug bekerja, tetapi hasil debug menunjukkan masalahnya bukan lagi di parser.

Hasil penting dari /decoderdebug CBRE:

Status: NO FINAL URL
Method: PARSER_NO_URL
HTTP Status: 200
Response Size: 103 bytes
RPC Fbv4je: YES
garturlres: NO
JSON Objects: 1
Nested Strings: 6
URL Candidates: 0
Parser: NONE

Dan /resolve CBRE tetap:

Status: GOOGLE ONLY
Deep Extraction: GOOGLE ONLY


Resolver attempts:
• GNEWS_DECODER:PARSER_NO_URL
• RPC:YES
• GARTURL:NO
• URLS:0
Artinya apa?

Ini sangat membantu karena sekarang jelas:

request ke Google berhasil (HTTP 200) dan RPC Fbv4je dikenali, tetapi responsnya hanya 103 bytes. Itu terlalu kecil untuk membawa URL publisher atau payload artikel yang berguna.

Jadi problemnya sekarang kemungkinan besar ada pada format request garturlreq yang sudah tidak cocok dengan protokol live Google saat ini, bukan pada regex/parser respons.

Urutannya sekarang:

Telegram                ✅
Market Data             ✅
Decision Support        ✅
Deep Parser             ✅
Google request          ✅ HTTP 200
Response parser         ✅ bekerja
RPC terdeteksi          ✅
Publisher URL di response ❌
Jangan tambah parser lagi

Kalau kita terus menambah regex sekarang, hasilnya tetap nol karena memang URL kandidatnya tidak ada di response.

Langkah berikutnya yang benar adalah V5.3.2 Request Protocol Upgrade. Fokusnya akan saya pindahkan ke request:

Google News token
      ↓
Fetch Google News article/read page
      ↓
Ambil runtime values:
• signature
• timestamp
• edition/language context
      ↓
Build garturlreq terbaru
      ↓
batchexecute
      ↓
publisher URL

Saya juga akan buat beberapa request mode fallback:

MODE A → current Fbv4je request
MODE B → signature + timestamp request
MODE C → runtime page context request
MODE D → V5.2 title-search fallback

Jadi hasil video ini bagus untuk debugging: V5.3.1 telah membuktikan parser bukan bottleneck utama lagi. Bottleneck sekarang adalah request payload/protocol ke Google.

Kalau kita lanjut, target berikutnya adalah V5.3.2 Dynamic Google Request Protocol.

c6248a98-ff5c-4032-af0e-a9ddcea15801.mp4
File

Saya sudah cek videonya. V5.3.2 terpasang dengan benar, dan sekarang titik gagalnya sudah sangat jelas.

Hasil /protocoldebug CBRE menunjukkan:

Status: DYNAMIC NOT COMPLETE
Method: DYNAMIC_PARAMS_FAILED


Params Found: NO
Params Mode: PARAMS_NOT_FOUND


ARTICLES      → HTTP 200 → Params NO
RSS_ARTICLES  → HTTP 200 → Params NO
ORIGINAL      → HTTP 200 → Params NO

Jadi Google merespons ketiga halaman dengan HTTP 200, tetapi HTML yang diterima bot tidak mengandung data-n-a-sg dan data-n-a-ts. Akibatnya V5.3.2 tidak pernah sampai ke tahap dynamic Fbv4je.

Kemudian bot melakukan fallback V5.3.1, dan hasil /decode CBRE menjadi:

Method: PARSER_NO_URL
Info: No publisher URL candidate found
in batchexecute response.

Lalu /resolve, /deep, dan /analyze CBRE tetap:

Deep Extraction : GOOGLE ONLY
Source Resolver  : GOOGLE ONLY

Sementara bagian lain normal:

Ticker             : CBRE ✅
Rights Issue       : Rp1,91 T ✅
Harga pasar        : Rp680 ✅
Perubahan harian   : +2,26% ✅
Information Score  : 89/100 ✅
Monitoring Signal  : WATCH ✅
Kesimpulan teknis

Sekarang kita sudah mengeliminasi hampir semuanya:

Telegram Bot              ✅
RSS corporate action      ✅
Ticker detection          ✅
Market data               ✅
Decision Support          ✅
Deep extraction engine    ✅
Dynamic page HTTP          ✅ 200


data-n-a-sg signature      ❌ tidak tersedia
data-n-a-ts timestamp      ❌ tidak tersedia
Publisher URL              ❌

Jadi jangan kita tambahkan regex data-n-a-* lagi. Videonya membuktikan atribut tersebut memang tidak ada pada response HTML yang diterima PC Anda.

Langkah berikutnya

Saya sarankan kita ubah arsitektur resolver di V5.4 supaya Google News internal decoder tidak lagi menjadi jalur utama.

Konsepnya:

Google News RSS
        ↓
Judul berita + nama publisher + ticker
        ↓
PUBLISHER DIRECT RESOLVER
        ↓
1. Domain mapping publisher
2. Search exact title di domain publisher
3. Search ticker + corporate action
4. Validate title similarity
5. Validate tanggal berita
        ↓
Publisher URL
        ↓
Deep Article Extraction

Contohnya dari video:

Judul:
CBRE Rencanakan Rights Issue Rp1,91 Triliun,
Republik Capital Kurangi Porsi


Sumber:
IDX Channel


Ticker:
CBRE

Bot nanti bisa membentuk pencarian spesifik:

site:idxchannel.com
"CBRE Rencanakan Rights Issue Rp1,91 Triliun"

dan fallback:

site:idxchannel.com
CBRE rights issue 1,91 triliun

Setelah kandidat ditemukan, bot melakukan title similarity + ticker verification + tanggal publikasi, baru artikel dibaca.

Menurut saya ini sekarang jauh lebih kuat daripada terus mengejar protokol internal Google yang dapat berubah sewaktu-waktu.

Status V5.3.2: diagnostic berhasil ✅, tetapi dynamic Google decoder tidak viable pada response yang Anda terima. Next yang tepat adalah V5.4 Publisher Direct Resolver.

21494425-8486-4710-b6f5-a63a15c1cfbe.mp4
File

Saya sudah cek videonya. V5.4 akhirnya berhasil menembus masalah utama yang kita kejar dari V5.1 sampai V5.3.2. 🎯

Dari video Anda, hasilnya sudah sangat jelas:

🏢 PUBLISHER DEBUG CBRE


Status: ✅ MATCH FOUND
Method: PUBLISHER_SEARCH
Source: IDX Channel
Domain Hint: idxchannel.com


Best Score: 241
Minimum Score: 70


INTERNAL_SEARCH → 12 candidates
PUBLIC_SEARCH   → 10 candidates

Kemudian /resolve CBRE berhasil:

Status: ✅ PUBLISHER SEARCH
Deep Extraction: ✅ FULL
Publisher: www.idxchannel.com


Resolver attempts:
• PUBLISHER_DIRECT:SUCCESS
• DOMAIN:idxchannel.com
• SCORE:241
• TITLE_SCORE:72

Ini berarti arsitektur Publisher Direct Resolver berhasil. Bot sudah tidak tergantung pada Google News decoder untuk kasus CBRE.

Yang lebih penting lagi, /deep CBRE sekarang berhasil membaca artikel publisher dan mendapatkan:

Ticker              : CBRE
Jenis               : RIGHTS ISSUE
Status              : RENCANA
Saham baru          : 12,76 miliar saham
Nilai/Dana          : Rp1,91 triliun
Deep Extraction     : ✅ FULL
Source Resolver      : ✅ PUBLISHER SEARCH
Publisher Direct    : ✅ idxchannel.com
Resolved Source     : www.idxchannel.com
Harga pasar         : Rp680
Perubahan harian    : +2,26%
Information Score   : 93/100

Saya verifikasi artikel IDX Channel yang sama. Artikel 13 Agustus 2026 memang menyebut CBRE sedang menyiapkan PMHMETD dengan potensi dana sekitar Rp1,91 triliun, maksimal sekitar 12,76 miliar saham baru, dan dokumennya masih dievaluasi OJK.

Kenapa harga rights dan rasio masih kosong?

Ini bukan lagi error bot.

Artikel terbaru yang berhasil dibaca V5.4 memang tidak mencantumkan harga pelaksanaan dan rasio HMETD; artikel itu hanya menegaskan jumlah saham, nilai maksimal, dan progres evaluasi OJK.

Menariknya, artikel IDX Channel yang lebih lama memang pernah menyebut harga pelaksanaan kisaran Rp100–Rp150 dan empat standby buyer. Sumber sebelumnya juga menyebut rencana rasio 90 saham lama : 253 HMETD, harga Rp100–Rp150, serta jadwal perdagangan/pelaksanaan 4–10 Juni 2026.

Tetapi bot tidak boleh langsung mencampur data lama tersebut dengan berita terbaru, karena status rights issue sekarang masih dalam evaluasi OJK dan jadwal/ketentuan lama bisa berubah. Justru saat ini bot berperilaku benar dengan tidak mengarang TERP.

Jadi bottleneck berikutnya sudah berubah

Sebelumnya:

Google News → Publisher ❌

Sekarang:

Google News
    ↓
Publisher Direct ✅
    ↓
Full Article ✅
    ↓
Current article details ✅
    ↓
Historical corporate-action context ❌

Next upgrade yang paling bernilai adalah V5.5 Event Intelligence Fusion.

Konsepnya:

CBRE Rights Issue
       ↓
Artikel terbaru 13 Aug 2026
       +
Artikel 7 Aug 2026
       +
Artikel Mei 2026
       +
Prospektus / keterbukaan
       ↓
EVENT MEMORY
       ↓
Pisahkan:


🟢 CURRENT
12,76 miliar saham
Rp1,91 T
masih evaluasi OJK


🟡 HISTORICAL / PENDING RECONFIRMATION
Harga Rp100–150
Rasio 90:253
Standby buyer
jadwal lama


🔴 SUPERSEDED
jadwal/kondisi yang sudah tidak berlaku
       ↓
Decision Support

Dengan begitu bot bisa menampilkan misalnya:

💰 Harga Pelaksanaan:
Rp100–150
⚠️ Historical plan — belum dikonfirmasi ulang
dalam update terbaru.


📐 Rasio:
90 : 253
⚠️ Previous disclosure.


🏛 Status terkini:
Masih evaluasi OJK.


🧮 TERP:
Belum dihitung sebagai FINAL
sampai terms dikonfirmasi kembali.

Itu akan jauh lebih berguna untuk investasi daripada sekadar membaca satu berita.

Ada dua perbaikan kecil yang juga saya lihat di video: disclaimer bawah masih menulis “V5.1 mencoba membaca...”, seharusnya V5.4; dan Best Score: 241 secara teknis tidak masalah karena raw scoring bersifat kumulatif, tetapi nantinya lebih enak kalau kita tampilkan juga Confidence 0–100%.

Kesimpulannya: V5.4 sukses besar. Publisher resolver-nya akhirnya bekerja. Sekarang kita sudah bisa berhenti mengejar Google decoder dan mulai membangun intelligence yang benar-benar berguna: menggabungkan seluruh riwayat corporate action per emiten sambil membedakan data CURRENT vs HISTORICAL.

ce7ce5ad-0530-4e09-8f11-087e96d73712.mp4
File
maksudnya pake yang ini tapi ga harus berbayar
49a058a5-8824-4b42-a8c8-047acff41acc.mp4
File

Sip, dari video yang Anda kirim folder V6.0 sudah diextract dengan benar. Struktur pentingnya sudah ada, termasuk:

.github/
core/
docs/
state/
tools/


scan_once.py
config.json
requirements.txt
MULAI_DI_SINI_GITHUB.txt

Jadi langkah extract sudah beres. Sekarang lanjut ke tahap GitHub.

Langkah berikutnya
Buka github.com lalu login.
Klik tombol + di kanan atas → New repository.
Isi:
Repository name:
kabar-saham-v6
Pilih:
Public
Untuk bagian ini jangan centang/tambahkan apa-apa dulu:
Add a README          → OFF
Add .gitignore        → OFF
Choose a license      → None

Karena semua file itu sudah ada di folder V6 kita.

Klik:
Create repository

Setelah repository jadi, biasanya GitHub akan menampilkan halaman kosong dengan pilihan seperti:

Quick setup
creating a new file
uploading an existing file

Pilih:

uploading an existing file

Lalu dari folder yang terlihat di video Anda, upload semua 16 item di dalam folder tersebut.

Yang penting .github harus ikut ter-upload, karena di situ ada workflow otomatis.

Target setelah upload harus terlihat kurang lebih:

.github/
core/
docs/
state/
tools/


.env.example
.gitignore
config.json
MULAI_DI_SINI_GITHUB.txt
README.md
requirements.txt
scan_once.py
SECURITY.md
TEST_SCAN_LOCAL.bat
TEST_TELEGRAM_LOCAL.bat

Folder __pycache__ tidak perlu di-upload. Kalau bisa jangan ikut.

Setelah semua masuk, di bawah halaman isi commit message misalnya:

Initial Kabar Saham V6 setup

lalu klik:

Commit changes

Untuk sekarang cukup sampai situ dulu. Setelah repository berhasil dibuat dan semua file sudah terlihat di GitHub, kirim screenshot/video lagi ke saya. Nanti saya cek struktur repository-nya sebelum kita masuk ke Telegram Secrets.

pilih yang mana
mana yang di pilih dan diisi
kesini kah?
yang mana sih
yang mana yang harus saya matikan cmd nya
3878d354-ec52-4328-8fe4-0becbf58bb14.mp4
File
udah saya refresh juga hasilnya teteap begitu
dah saya masukin ya
masih sama
masih sama
8138e950-f1ec-4118-b6c8-edb899dc2367.mp4
File

Saya sudah cek videonya. Schedule Probe masih 0 run, jadi sekarang kita sudah punya diagnosis yang cukup kuat: masalahnya bukan di bot V6, karena workflow manual sukses, Telegram sukses, dan bahkan workflow probe super-sederhana tidak dipicu otomatis.

GitHub sendiri menyatakan scheduled workflows bisa tertunda atau bahkan ada job yang terlewat saat beban tinggi. Workflow schedule juga hanya berjalan dari default branch, dan konfigurasi kita sudah memenuhi syarat itu.

Supaya kita tidak terus menunggu scheduler GitHub yang tidak konsisten, saya sarankan jangan ubah core V6 lagi. Kita pakai arsitektur ini:

cron-job.org GRATIS
        ↓
setiap 10 menit
        ↓
memicu GitHub Actions
        ↓
scan_once.py V6
        ↓
Corporate Action baru?
        ↓
📲 Telegram

Ini tetap Rp0, laptop boleh mati, dan tidak perlu VPS. cron-job.org menyatakan layanannya gratis, bisa berjalan hingga sekali per menit, dan mendukung custom HTTP method, headers, serta request body.

Yang bagus: kita tidak perlu rename atau upload ulang V6.0. Workflow kita sudah punya workflow_dispatch, jadi cukup dipicu dari luar.

Untuk melakukannya dengan aman, kita buat Fine-grained GitHub Token yang hanya punya akses ke repository kabar-saham-v6 dan permission Actions: Write. GitHub memang mensyaratkan permission Actions (write) untuk endpoint “Create a workflow dispatch event”.

Jadi langkah berikutnya adalah:

1. Buat Fine-grained GitHub Token
2. Batasi hanya untuk kabar-saham-v6
3. Actions = Read and write
4. Buat akun cron-job.org gratis
5. Buat cron setiap 10 menit
6. Cron memanggil workflow V6
7. Test
8. Laptop boleh mati

Tidak ada coding ulang. Tidak ada V6.0 baru. Kita hanya mengganti sumber timer:

GitHub internal schedule ❌


menjadi


cron-job.org → GitHub Actions ✅

Saya sarankan sekarang kita lakukan langkah 1: membuat Fine-grained GitHub Token. Jangan hapus schedule_probe.yml dulu; nanti setelah sistem baru terbukti jalan, baru kita rapikan.

6abb44f5-1572-4e77-a83f-123d0950b2cf.mp4
File
9258bf8e-2dae-4b47-9068-5a3873cd102d.mp4
File
mana ga ada
kesini?
disni?
ini?
b52a3b30-36b1-48ca-a945-d0a9dae330bc.mp4
File

Iya, dari videonya command_bridge.py sudah berhasil masuk ke root repository ✅

Saya lihat sekarang file ini sudah muncul sejajar dengan:

config.json
requirements.txt
scan_once.py
command_bridge.py   ✅

Jadi tahap command_bridge.py sudah selesai.

Sekarang tinggal file ketiga terakhir:

command_state.json

Masuk ke folder:

state

Lalu:

Add file
→ Upload files
→ pilih command_state.json

Commit message:

Add V6.1 command state

Setelah selesai, isi folder state harus punya:

github_state.json      ← V6.0
command_state.json     ← V6.1 BARU

Jangan hapus github_state.json.

Kalau command_state.json sudah masuk, kirim screenshot folder state atau langsung bilang “sudah”. Setelah itu kita lanjut test V6.1 di GitHub Actions.

cron job sebelumnya masih ada, jadi gimana?
f2f25908-ef13-4d38-af4f-af6ad655e0a5.mp4
File

Saya sudah cek videonya. Hampir semuanya sudah benar, termasuk jadwal Every 2 minutes, timezone Asia/Jakarta, method POST, dan body mode: poll. ✅

Tapi ada 1 hal penting yang masih salah:

Di header Authorization, Anda masih menulis teks placeholder:

Bearer TOKEN_GITHUB_YANG_SUDAH_DIP...

Itu harus diganti dengan Fine-grained GitHub Token asli yang sebelumnya Anda pakai untuk cron V6.0.

Jadi:

Key:
Authorization

Value harus seperti:

Bearer github_pat_xxxxxxxxxxxxxxxxx

Bukan tulisan TOKEN_GITHUB_YANG_SUDAH_DIPAKAI.

Yang lain dari video sudah benar:

Schedule       : Every 2 minutes ✅
Crontab        : */2 * * * * ✅
Timezone       : Asia/Jakarta ✅
Method         : POST ✅
Accept         : application/vnd.github+json ✅
Content-Type   : application/json ✅
API Version    : 2026-03-10 ✅
Body mode      : poll ✅

Setelah Authorization diganti dengan token asli:

Jangan screenshot bagian token.
Scroll bawah.
Klik TEST RUN.

Targetnya:

200 OK ✅
Kalau 200 OK, baru kita tes /cloudstatus.

Jadi sekarang cukup ganti value Authorization dengan token GitHub asli dulu. Jangan klik Create sebelum Test Run berhasil.

f4f29211-f972-48d1-b5a7-6b6126583cfc.mp4
File

Nah, V6.1 sekarang terbukti berhasil penuh ✅

Dari screenshot/video Anda, bukan cuma cron dan GitHub yang jalan—command Telegram benar-benar diproses otomatis:

/market BBCA → dibalas Market Data BBCA dengan harga terakhir Rp6.350 ✅
/analyze CBRE → diproses otomatis dan menghasilkan RIGHTS ISSUE ALERT lengkap ✅
Deep Extraction → FULL ✅
Publisher Direct → idxchannel.com ✅
Cron V6.1 jam 22:40 → Successful 200 OK ✅
GitHub Command Bridge run otomatis → Success ✅

Artinya sistem final sekarang:

AUTO ALERT
cron-job.org setiap 10 menit
        ↓
GitHub Actions
        ↓
Corporate Action Scanner
        ↓
📲 Telegram




COMMAND
Anda kirim /market BBCA
        ↓
cron-job.org setiap 2 menit
        ↓
GitHub Command Bridge
        ↓
V5.4 Intelligence Core
        ↓
📲 Telegram membalas

Jadi statusnya:

V6.0 Auto Alert          ✅
V6.1 Command Bridge      ✅
/market                  ✅
/analyze                 ✅
Deep Extraction          ✅
Publisher Direct         ✅
Market Data              ✅
Laptop harus hidup       ❌
CMD harus terbuka        ❌
VPS                      ❌

Satu hal yang terlihat: Anda tadi mengirim /analyze CBRE dua kali, jadi jangan kaget kalau bot memberikan analisis CBRE dua kali juga. Itu bukan error; memang ada dua command yang masuk.

Sekarang tidak perlu mengubah apa pun lagi. Anda bahkan boleh matikan laptop.

Untuk tes penutup, cukup kirim salah satu:

/decision

atau:

/rights

tanpa membuka GitHub atau cron-job.org. Kalau dibalas otomatis, itu sekadar konfirmasi tambahan—secara teknis V6.1 sudah operational sekarang.

b49768fe-df98-421a-ad29-7103e44ed383.mp4
File
iya sudah terkirim meskipun proses nya aga lama, tapi kok kaya ngasih infonya double begitu? lihat kan yang saya videoin itu?

Iya, saya lihat videonya. Memang terasa seperti double, tapi penyebabnya ada dua jenis dan bukan karena cron V6.0 + V6.1 saling bentrok.

Di video, Anda hanya mengirim /decision sekali. Setelah itu bot mengirim:

⏳ V6.1 memproses /decision...
↓
🧠 V5 DECISION BOARD
↓
📢 M&A / TAKEOVER ALERT
↓
📢 M&A / TAKEOVER ALERT
↓
📢 M&A / TAKEOVER ALERT
...

Jadi yang terlihat “double” sebenarnya karena /decision saat ini mengirim beberapa kandidat sebagai kartu lengkap satu per satu. Bahkan beberapa berita berbeda bisa membahas corporate action yang sama, misalnya tender offer/perubahan pengendali yang sama tetapi berasal dari media berbeda. Akibatnya informasi yang substansinya mirip muncul beberapa kali.

Selain itu, sebelumnya Anda memang sempat mengirim /analyze CBRE dua kali, jadi untuk kasus itu bot memang akan memproses dua command terpisah.

Yang saya sarankan kita benahi di V6.1.1 Anti-Duplicate + Compact Decision Board:

SEKARANG
/decision
   ↓
Artikel A → full card
Artikel B → full card
Artikel C → full card
Artikel D → full card

menjadi:

V6.1.1
/decision
   ↓
kelompokkan corporate action yang sama
   ↓
hapus berita duplikat/mirip
   ↓
pilih sumber terbaik
   ↓
TOP 5 EVENT SAJA

Contohnya nanti:

🧠 DECISION BOARD


1. 🔥 EPAC — TENDER OFFER
   Score: 83/100
   Source: IDX Channel
   Related news: 3
   → /analyze EPAC


2. 🔥 DOOH — TENDER OFFER
   Score: 79/100
   Source: Kontan
   Related news: 2
   → /analyze DOOH


3. 🔥 MAPI — TENDER OFFER
   Score: 78/100
   Source: Bisnis
   Related news: 4
   → /analyze MAPI

Jadi satu corporate action = satu entry, walaupun ditemukan dari 3–4 berita.

Saya juga akan tambahkan command anti-repeat, misalnya Anda tidak sengaja mengirim:

/analyze CBRE
/analyze CBRE

dalam beberapa menit, yang kedua akan ditahan dengan pesan seperti:

♻️ Command yang sama baru saja diproses.
Gunakan /analyze CBRE lagi setelah beberapa menit
jika memang ingin refresh.

Dan pesan:

⏳ V6.1 memproses /decision...

bisa tetap ada sebagai indikator proses, tetapi saya akan buat hanya 1 status awal + 1 hasil akhir, supaya Telegram jauh lebih rapi.

Jadi kesimpulannya: iya, yang Anda lihat memang perlu diperbaiki. Bukan error cron, melainkan output /decision terlalu verbose dan belum melakukan event-level deduplication. Saya sarankan kita lanjut V6.1.1 Anti-Duplicate & Compact Output tanpa mengubah V6.0 auto-alert yang sekarang sudah stabil.

upload disini kah?
66527335-b361-4a97-a466-cf08b87b27ab.mp4
File

Iya, saya lihat videonya. Masalah double utama sudah berhasil dibereskan. ✅

Sekarang /decision hanya menghasilkan 1 Decision Board, bukan rentetan full-card seperti sebelumnya. Bahkan terlihat jelas:

Dedup: 26 artikel → 8 event unik
18 artikel digabung
Ditampilkan: Top 5 event

Contoh MAPI juga menunjukkan:

Related news: 2

Artinya dua berita mengenai corporate action yang sama sudah digabung menjadi satu event. Anti-duplicate command juga sudah aktif.

Tapi saya melihat 1 bug kecil yang sebaiknya kita rapikan sebelum cron V6.1.1 diaktifkan kembali:

1. 🔥 34 — TENDER OFFER

34 jelas bukan ticker. Itu berarti extractor salah membaca angka sebagai ticker. Beberapa item lain juga masih memakai potongan judul karena tickernya belum berhasil dideteksi.

Selain itu, run /decision tadi membutuhkan sekitar:

GitHub Actions: 1 menit 1 detik
command-bridge: 55 detik

Jadi sebenarnya hasilnya sudah benar, tetapi masih bisa kita buat lebih bersih dan lebih cepat.

Saya sarankan tahap terakhir menjadi V6.1.2 Fast & Clean Decision Board dengan tiga perbaikan:

✅ Tolak ticker palsu seperti "34"
✅ Deteksi ticker 4 huruf dari judul, misalnya DOOH
✅ /decision dibuat lebih cepat
   → tidak Deep Extraction semua Top 5
   → Deep Analysis baru dilakukan saat /analyze TICKER

Target akhirnya:

SEKARANG
/decision
→ tunggu ±55 detik
→ 34 — TENDER OFFER ❌


V6.1.2
/decision
→ jauh lebih cepat
→ DOOH — TENDER OFFER ✅
→ MAPI — TENDER OFFER ✅
→ event tanpa ticker → nama emiten/judul bersih

Jadi jangan aktifkan cron V6.1 dulu. V6.0 Auto Alert tetap biarkan hidup seperti sekarang.

Secara fungsi anti-double sudah sukses; tinggal kita bersihkan kualitas label dan percepat /decision.

03ee6b9e-6a8e-4bbe-9543-9b73c3a83864.mp4
File
di tes secara manual

Nah, dari tes manual ini V6.2.1 berhasil memperbaiki masalah utama, tetapi saya melihat 1 bagian masih belum bekerja penuh.

✅ Ticker Recovery berhasil. /analyze DOOH yang sebelumnya gagal sekarang menemukan DOOH melalui TITLE_SNIPPET.
✅ Analisis lengkap berhasil jalan: Deep Extraction: FULL, Publisher Direct: kontan.co.id, market data, tender price, stake 51%, dan monitoring signal sudah keluar.
✅ /cloudstatus benar: Ticker Recovery ON, Issuer Resolver ON, Official Source Priority ON, Official Discovery ON.
⚪ /official DOOH belum menemukan sumber resmi. Ini sendiri belum tentu error, karena indeks sumber resmi memang bisa belum tersedia.
⚠️ Issuer Resolver belum berhasil pada kasus DOOH. Buktinya /official DOOH belum menampilkan nama issuer seperti Era Media Sejahtera, dan di /decision disclosure IDX masih muncul sebagai PENGUMUMAN PENGAMBILALIHAN ERA MEDIA SEJAHTERA... alih-alih DOOH — AKUISISI.

Artinya alur sekarang baru sampai:

DOOH
 ↓
TITLE / SNIPPET ✅
 ↓
/analyze berhasil ✅

Yang belum terjadi:

DOOH
 ↓
Era Media Sejahtera
 ↓
Disclosure IDX
 ↓
DOOH — AKUISISI

Ada satu hal lain yang saya ingin benahi sekaligus: hasil /analyze DOOH menampilkan:

Nilai transaksi: Rp700
Harga tender: Rp121
Harga pasar: Rp294

Rp700 terlihat seperti unit nominalnya berpotensi terpotong saat extraction/formatting. Jadi jangan kita biarkan angka itu dianggap Rp700 begitu saja sebelum parser unitnya diperketat.

Menurut saya jangan aktifkan cron dulu. Tahap berikutnya sebaiknya kita buat V6.2.2 — Deep Issuer Resolver + Money Unit Guard.

V6.2.2 akan membuat:

/analyze DOOH
      ↓
Publisher article
      ↓
Deep Extraction
      ↓
Nama perusahaan:
Era Media Sejahtera
      ↓
DOOH ↔ Era Media Sejahtera
      ↓
Cari disclosure IDX berdasarkan
ticker + nama perusahaan
      ↓
Decision Board:
DOOH — AKUISISI
🏛️ Official: ✅ IDX

Sekaligus money parser akan membedakan dengan ketat:

Rp700
Rp700 juta
Rp700 miliar
Rp700 triliun

supaya unit nominal tidak hilang.

Jadi V6.2.1 bukan gagal — justru recovery DOOH sudah berhasil. Kita sekarang sudah tahu titik terakhir yang perlu diperkuat. Kalau gas, berikutnya saya bikin V6.2.2 Deep Issuer Resolver + Money Unit Guard.

gassss buatkan

Gas, V6.2.2 — Deep Issuer Resolver + Money Unit Guard sudah selesai dibuat ✅🔥

Download Kabar Saham V6.2.2 FINAL

command_bridge.py V6.2.2

scan_once.py V6.2.2

core/main.py V6.2.2

Panduan pemasangan V6.2.2

Validation Report

Yang sekarang diperbaiki

1. Deep Issuer Resolver

Targetnya:

/analyze DOOH
      ↓
Ticker Recovery: DOOH
      ↓
baca full artikel publisher
      ↓
PT Era Media Sejahtera Tbk (DOOH)
      ↓
Issuer Resolver:
DOOH ↔ Era Media Sejahtera
      ↓
cari disclosure IDX

Mapping tersebut sekarang juga disimpan ke:

state/command_state.json

Jadi command berikutnya tidak harus belajar ulang dari nol.

Bahkan scanner Auto Alert ikut membaca issuer memory tersebut.

Saya juga menemukan indeks resmi IDX yang memang mengaitkan PT Era Media Sejahtera Tbk dengan kode DOOH, sehingga pendekatan ticker ↔ nama emiten ini relevan untuk kasus yang sedang kita uji.

2. Money Unit Guard

Kasus kemarin:

Harga pasar : Rp294
Harga tender: Rp121
Nilai transaksi: Rp700   ❌

sekarang angka kecil tanpa unit seperti:

Rp294
Rp121
Rp700

tidak otomatis dianggap sebagai nilai transaksi.

Sedangkan:

Rp700 miliar          ✅
Rp1,2 triliun         ✅
Rp700.000.000.000     ✅

tetap bisa diterima.

Dalam simulasi kasus DOOH, hasilnya menjadi:

🛡️ Money Unit Guard:
✅ blocked ambiguous Rp700


💰 Nilai transaksi:
Rp700 miliar
3. Official correlation lebih aman

Sekarang sistem tidak cuma melihat:

nama emitennya sama

lalu menganggap semua disclosure adalah event yang sama.

Untuk M&A sistem juga mencoba membedakan:

Era Media Sejahtera DIAMBIL ALIH

dengan:

Era Media Sejahtera MENGAKUISISI perusahaan lain

Jadi risiko salah menghubungkan corporate action berbeda ditekan.

Hasil validation
Python syntax 3 file              ✅
Deep Issuer Resolver              ✅
DOOH → Era Media Sejahtera        ✅
Issuer Memory persistence         ✅
Auto Alert issuer hydration       ✅
Official target correlation       ✅
Acquirer-role false match guard   ✅


Rp294 sebagai nilai transaksi     ❌ diblok
Rp121 sebagai nilai transaksi     ❌ diblok
Rp700 tanpa unit                  ❌ diblok
Rp700 miliar                      ✅ diterima


Simulasi /analyze DOOH            ✅
Simulasi /official DOOH           ✅


Dependency baru                   ❌ NONE
Workflow GitHub berubah           ❌ NO
Cron schema berubah               ❌ NO

File yang nanti diganti tetap hanya tiga:

ROOT/
├── command_bridge.py
├── scan_once.py
│
└── core/
    └── main.py

.yml, Secrets, config, requirements, serta file state lama jangan dihapus.

Tahap berikutnya tinggal pemasangan V6.2.2 seperti pola sebelumnya: pause dua cron → hapus/commit file lama → upload/commit file baru → test → /cloudstatus → /analyze DOOH → /official DOOH → /decision. 

command_bridge_V6_2_2_REPLACE_ME.py
Code
scan_once_V6_2_2_REPLACE_ME.py
Code
main_V6_2_2_REPLACE_CORE.py
Code
2 more
code kalo saya salin aja dari code yang lama, apa gpp? apa harus hapus file trus isi commit trus upload file baru isi commit lagi

Boleh banget. Malah untuk upgrade V6.2.2 saya lebih menyarankan file lama tetap ada lalu seluruh isinya diganti. Jadi tidak perlu hapus file → commit → upload lagi → commit. Itu hanya metode ekstra aman yang kita pakai sebelumnya.

Cara yang lebih simpel adalah 1 file = 1 commit.

Urutannya:

Pause dulu kedua cron seperti sebelumnya.
Di GitHub buka file lama command_bridge.py.
Klik ikon Edit/pensil.

Di editor tekan:

Ctrl + A

lalu Delete/Backspace sampai seluruh kode lama kosong.

Buka file V6.2.2 dari saya:

command_bridge V6.2.2

Copy seluruh isi code, lalu paste ke editor GitHub.

Penting: jangan ditempel di bawah kode lama. Seluruh isi lama harus diganti.

Klik Commit changes dengan pesan:

Upgrade command bridge to V6.2.2 deep issuer resolver

Lakukan cara yang sama untuk file kedua di ROOT:

scan_once.py

Ganti seluruh isinya dengan:

scan_once V6.2.2

Commit:

Upgrade scanner to V6.2.2 issuer memory

Kemudian file ketiga, masuk ke:

core/
└── main.py

Buka core/main.py lama → Edit → Ctrl+A → hapus → paste seluruh kode baru dari:

core main V6.2.2

Commit:

Upgrade intelligence core to V6.2.2 money guard

Jadi riwayat commit Anda cukup seperti ini:

1. Upgrade command bridge to V6.2.2 deep issuer resolver
2. Upgrade scanner to V6.2.2 issuer memory
3. Upgrade intelligence core to V6.2.2 money guard

Tidak perlu ada commit:

Remove old...

dan tidak perlu hapus file dari repository.

Mana yang saya rekomendasikan?

Pakai metode copy-paste replace ini. Lebih sederhana karena:

Path file tetap sama        ✅
Workflow tidak terganggu    ✅
History GitHub lebih rapi   ✅
Commit lebih sedikit        ✅
Risiko salah folder lebih kecil ✅

Satu-satunya yang harus sangat diperhatikan: copy seluruh kode V6.2.2, bukan hanya sebagian. Kalau Anda sudah sampai halaman edit command_bridge.py, kirim screenshot-nya dan kita bisa lanjut satu per satu.

command_bridge_V6_2_2_REPLACE_ME.py
Code
scan_once_V6_2_2_REPLACE_ME.py
Code
main_V6_2_2_REPLACE_CORE.py
Code

Library
/
command_bridge_V6_2_2_REPLACE_ME.py
"""
Kabar Saham V6.2.2 — Deep Issuer Resolver + Money Guard
==============================================

Purpose
-------
Add cloud Telegram commands on top of the existing V6.0 auto-alert system.

Architecture:
cron-job.org -> GitHub workflow_dispatch -> lightweight Telegram probe
-> install full dependencies ONLY if commands exist -> V5.4 intelligence core
-> Telegram response.

Security:
- Only chat IDs in TELEGRAM_CHAT_IDS are allowed.
- Bot token / chat IDs are never written to repository state.
- Pending Telegram updates are stored only in GitHub runner temp storage.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
STATE_PATH = Path(
    os.getenv(
        "V61_COMMAND_STATE_PATH",
        str(ROOT / "state" / "command_state.json"),
    )
)
PENDING_PATH = Path(
    os.getenv(
        "V61_PENDING_COMMANDS_PATH",
        str(ROOT / "pending_commands_v61.json"),
    )
)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
RAW_CHAT_IDS = os.getenv("TELEGRAM_CHAT_IDS", "").strip()

MAX_UPDATES = max(
    1,
    min(
        100,
        int(os.getenv("V61_COMMAND_MAX_UPDATES", "20")),
    ),
)

TG_API_TIMEOUT_SECONDS = int(
    os.getenv("V61_TELEGRAM_TIMEOUT_SECONDS", "20")
)

SCHEMA_VERSION = 6

# V6.1.1 anti-repeat protection.
COMMAND_DEDUP_SECONDS = max(
    0,
    int(os.getenv("V611_COMMAND_DEDUP_SECONDS", "180")),
)
RECENT_COMMAND_TTL_SECONDS = max(
    3600,
    int(os.getenv("V611_RECENT_COMMAND_TTL_SECONDS", "86400")),
)

# V6.1.1 compact Decision Board.
DECISION_MAX_EVENTS = max(
    1,
    min(8, int(os.getenv("V611_DECISION_MAX_EVENTS", "5"))),
)
DECISION_SCAN_LIMIT = max(
    DECISION_MAX_EVENTS,
    min(50, int(os.getenv("V611_DECISION_SCAN_LIMIT", "30"))),
)

# V6.1.2 Fast & Clean Decision Board.
DECISION_FAST_MODE = (
    os.getenv("V612_DECISION_FAST_MODE", "1").strip().lower()
    not in {"0", "false", "off", "no"}
)
TITLE_TICKER_INFERENCE = (
    os.getenv("V612_TITLE_TICKER_INFERENCE", "1").strip().lower()
    not in {"0", "false", "off", "no"}
)


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_state() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "initialized": False,
        "next_offset": 0,
        "last_state_change_utc": None,
        "last_command_utc": None,
        "updates_seen": 0,
        "commands_processed": 0,
        "recent_commands": {},
        "duplicates_suppressed": 0,
        "issuer_aliases": {},
    }


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return default_state()

    try:
        data = json.loads(
            STATE_PATH.read_text(encoding="utf-8")
        )
    except Exception as exc:
        raise RuntimeError(
            f"command_state.json rusak/tidak valid: {exc}"
        ) from exc

    state = default_state()
    state.update(data)

    if not isinstance(state.get("next_offset"), int):
        state["next_offset"] = 0

    if not isinstance(state.get("recent_commands"), dict):
        state["recent_commands"] = {}

    if not isinstance(state.get("duplicates_suppressed"), int):
        state["duplicates_suppressed"] = 0

    if not isinstance(state.get("issuer_aliases"), dict):
        state["issuer_aliases"] = {}

    # Transparent schema migration: existing V6.1 command_state.json
    # remains valid and does not need to be replaced manually.
    state["schema_version"] = SCHEMA_VERSION

    return state


def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = STATE_PATH.with_suffix(".tmp")
    temp.write_text(
        json.dumps(
            state,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    temp.replace(STATE_PATH)


def authorized_chat_ids() -> set[int]:
    if not RAW_CHAT_IDS:
        raise RuntimeError(
            "TELEGRAM_CHAT_IDS belum tersedia."
        )

    ids: set[int] = set()

    for item in RAW_CHAT_IDS.split(","):
        item = item.strip()
        if not item:
            continue

        try:
            ids.add(int(item))
        except ValueError as exc:
            raise RuntimeError(
                "TELEGRAM_CHAT_IDS harus berupa angka "
                "dipisahkan koma."
            ) from exc

    if not ids:
        raise RuntimeError(
            "TELEGRAM_CHAT_IDS kosong."
        )

    return ids


def require_token() -> str:
    if not TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN belum tersedia."
        )
    return TOKEN


def telegram_call(
    method: str,
    payload: dict[str, Any] | None = None,
) -> Any:
    """
    Telegram Bot API using Python standard library only.
    This lets idle command polling avoid installing the full bot stack.
    """
    token = require_token()
    payload = payload or {}

    encoded: dict[str, str] = {}

    for key, value in payload.items():
        if isinstance(value, (dict, list, tuple)):
            encoded[key] = json.dumps(
                value,
                ensure_ascii=False,
            )
        elif isinstance(value, bool):
            encoded[key] = "true" if value else "false"
        elif value is not None:
            encoded[key] = str(value)

    body = urllib.parse.urlencode(encoded).encode("utf-8")

    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Kabar-Saham-V6.2.2-Deep-Issuer-Money-Guard/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=TG_API_TIMEOUT_SECONDS,
        ) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        body_text = ""
        try:
            body_text = exc.read().decode(
                "utf-8",
                errors="replace",
            )
        except Exception:
            pass

        raise RuntimeError(
            f"Telegram HTTP {exc.code}: "
            f"{body_text[:300]}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Telegram network error: {exc.reason}"
        ) from exc

    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(
            "Telegram response bukan JSON valid."
        ) from exc

    if not data.get("ok"):
        raise RuntimeError(
            "Telegram API error: "
            + str(data.get("description", "unknown"))
        )

    return data.get("result")


def send_message_stdlib(
    chat_id: int,
    text: str,
) -> None:
    telegram_call(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
    )


def write_github_output(
    output_file: str | None,
    **values: Any,
) -> None:
    if not output_file:
        return

    path = Path(output_file)
    with path.open(
        "a",
        encoding="utf-8",
    ) as fh:
        for key, value in values.items():
            if isinstance(value, bool):
                value = "true" if value else "false"
            fh.write(f"{key}={value}\n")


def get_updates(
    offset: int | None = None,
    *,
    limit: int = MAX_UPDATES,
) -> list[dict[str, Any]]:
    payload: dict[str, Any] = {
        "limit": limit,
        "timeout": 0,
        "allowed_updates": ["message"],
    }

    if offset is not None:
        payload["offset"] = offset

    result = telegram_call(
        "getUpdates",
        payload,
    )

    if not isinstance(result, list):
        return []

    return [
        x for x in result
        if isinstance(x, dict)
    ]


def message_info(
    update: dict[str, Any],
) -> tuple[int | None, str]:
    message = update.get("message") or {}
    chat = message.get("chat") or {}

    chat_id = chat.get("id")
    text = (message.get("text") or "").strip()

    try:
        chat_id = int(chat_id)
    except (TypeError, ValueError):
        chat_id = None

    return chat_id, text


def command_name(text: str) -> str:
    if not text.startswith("/"):
        return ""

    head = text.split(maxsplit=1)[0]
    return head.split("@", 1)[0].lower()



def canonical_command_text(text: str) -> str:
    """Normalize command so /analyze cbre and /analyze CBRE are identical."""
    parts = (text or "").strip().split()
    if not parts:
        return ""

    cmd = parts[0].split("@", 1)[0].lower()
    args = [x.upper() for x in parts[1:]]
    return " ".join([cmd, *args]).strip()


def command_fingerprint(chat_id: int, text: str) -> str:
    """
    Persist only a one-way fingerprint. The repository state does not store
    the raw chat ID or raw command text.
    """
    canonical = canonical_command_text(text)
    raw = f"{chat_id}|{canonical}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]


def update_timestamp(update: dict[str, Any]) -> int:
    message = update.get("message") or {}
    value = message.get("date")
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(time.time())


def cleanup_recent_commands(
    recent: dict[str, Any],
    *,
    now_ts: int | None = None,
) -> dict[str, int]:
    now_ts = int(now_ts or time.time())
    cleaned: dict[str, int] = {}

    for key, value in recent.items():
        try:
            ts = int(value)
        except (TypeError, ValueError):
            continue

        age = max(0, now_ts - ts)
        if age <= RECENT_COMMAND_TTL_SECONDS:
            cleaned[str(key)] = ts

    return cleaned


def format_duplicate_notice(commands: list[str]) -> str:
    counts: dict[str, int] = {}
    order: list[str] = []

    for value in commands:
        canonical = canonical_command_text(value)
        if not canonical:
            continue
        if canonical not in counts:
            order.append(canonical)
            counts[canonical] = 0
        counts[canonical] += 1

    lines = [
        "♻️ <b>Command duplikat diabaikan.</b>",
        "",
        f"Proteksi anti-repeat aktif selama ±{COMMAND_DEDUP_SECONDS} detik.",
    ]

    for value in order[:5]:
        suffix = f" ×{counts[value]}" if counts[value] > 1 else ""
        lines.append(
            f"• <code>{html.escape(value)}</code>{suffix}"
        )

    lines += [
        "",
        "Command pertama tetap diproses; pengiriman ulang yang terlalu dekat tidak dijalankan lagi.",
    ]
    return "\n".join(lines)


# ============================================================
# V6.1.1 EVENT-LEVEL DEDUP / COMPACT DECISION BOARD
# ============================================================

TICKER_TITLE_STOPWORDS = {
    "AKAN", "BARU", "BISA", "BUKA", "DANA", "DARI", "DATA", "DEAL",
    "HARI", "JADI", "JUAL", "KENA", "KINI", "LAGI", "LAMA", "MANA",
    "NAIK", "OLEH", "PARA", "PASAR", "PUNYA", "RAYA", "RESMI",
    "SANG", "SIAP", "SINI", "TAHUN", "TURUN", "UNTUK", "WAJIB",
    "YANG", "BANK", "CNBC", "FUND", "NEWS",
}

TITLE_TICKER_PATTERNS = [
    re.compile(r"\(([A-Z]{4})\)"),
    re.compile(
        r"\b(?:saham|emiten|ticker|kode\s+saham|kode)\s+([A-Z]{4})\b",
        flags=re.I,
    ),
    re.compile(
        r"\b([A-Z]{4})\s+(?:saham|emiten)\b",
        flags=re.I,
    ),
]


def _valid_equity_ticker(value: Any) -> str | None:
    """
    Conservative validator for IDX equity ticker shown in Decision Board.
    Accepts MAPI and MAPI.JK; rejects numeric fragments such as "34".
    """
    raw = str(value or "").strip().upper()

    # yfinance-style suffix is acceptable input, but not displayed.
    if raw.endswith(".JK"):
        raw = raw[:-3]

    if not re.fullmatch(r"[A-Z]{4}", raw):
        return None

    if raw in TICKER_TITLE_STOPWORDS:
        return None

    return raw


def _infer_ticker_from_title(title: str) -> str | None:
    if not TITLE_TICKER_INFERENCE:
        return None

    original = str(title or "")

    # Explicit ticker contexts first.
    for pattern in TITLE_TICKER_PATTERNS:
        for match in pattern.finditer(original):
            candidate = _valid_equity_ticker(match.group(1))
            if candidate:
                return candidate

    # Bare 4-letter token only when it is already ALL CAPS in the headline.
    # This prevents ordinary words such as "Baru" from becoming BARU.
    for candidate in re.findall(
        r"(?<![A-Za-z])([A-Z]{4})(?![A-Za-z])",
        original,
    ):
        clean = _valid_equity_ticker(candidate)
        if clean:
            return clean

    return None


def _resolved_ticker(article: dict[str, Any]) -> str | None:
    details = article.setdefault("details", {})

    extracted_ticker = _valid_equity_ticker(details.get("ticker"))
    ticker = extracted_ticker

    # Garbage extractor output (example: 34) is discarded.
    if not ticker:
        ticker = _infer_ticker_from_title(article.get("title", ""))

    if ticker:
        details["ticker"] = ticker
        article["decision_ticker_source"] = (
            "EXTRACTOR" if extracted_ticker else "TITLE"
        )
        return ticker

    details["ticker"] = None
    article["decision_ticker_source"] = "NONE"
    return None


def _norm_identity(value: Any) -> str:
    text = re.sub(r"[^A-Z0-9]+", " ", str(value or "").upper())
    return re.sub(r"\s+", " ", text).strip()


def _decision_family(event_type: str) -> str:
    event = (event_type or "").upper()
    if event == "IPO":
        return "IPO"
    if event == "RIGHTS ISSUE":
        return "RIGHTS"
    return "M&A"


def _title_signature(title: str) -> str:
    stop = {
        "SAHAM", "EMITEN", "AKUISISI", "TENDER", "OFFER", "RIGHTS",
        "ISSUE", "HMETD", "IPO", "PENAWARAN", "PERUSAHAAN", "RESMI",
        "BAKAL", "AKAN", "INI", "DAN", "DI", "KE", "DARI", "UNTUK",
        "THE", "OF", "A", "AN", "TO",
    }
    words = [
        x for x in re.findall(r"[A-Z0-9]{2,}", (title or "").upper())
        if x not in stop
    ]
    return " ".join(words[:7])


def decision_event_key(article: dict[str, Any]) -> str:
    d = article.get("details") or {}
    family = _decision_family(article.get("event_type", ""))
    ticker = _resolved_ticker(article)

    # For listed Indonesian issuers, ticker is the most stable event identity.
    # M&A stages (acquisition -> change of control -> tender offer) are therefore
    # intentionally merged into a single corporate-action event.
    if ticker:
        return f"{family}|TICKER|{ticker}"

    target = _norm_identity(d.get("target"))
    acquirer = _norm_identity(d.get("acquirer"))
    if target or acquirer:
        return f"{family}|PARTIES|{acquirer}|{target}"

    return f"{family}|TITLE|{_title_signature(article.get('title', ''))}"


def group_decision_events(
    articles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}

    for article in articles[:DECISION_SCAN_LIMIT]:
        if article.get("context") == "MARKET PIPELINE":
            continue

        key = decision_event_key(article)
        group = groups.get(key)

        if group is None:
            groups[key] = {
                "key": key,
                "representative": article,
                "articles": [article],
            }
            continue

        group["articles"].append(article)

        current = group["representative"]
        current_rank = (
            {"HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(
                current.get("urgency", current.get("priority", "LOW")), 0
            ),
            current.get("information_score", current.get("ca_score", 0)) or 0,
            current.get("ca_score", 0) or 0,
            current.get("published_dt") or datetime.min.replace(tzinfo=timezone.utc),
        )
        candidate_rank = (
            {"HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(
                article.get("urgency", article.get("priority", "LOW")), 0
            ),
            article.get("information_score", article.get("ca_score", 0)) or 0,
            article.get("ca_score", 0) or 0,
            article.get("published_dt") or datetime.min.replace(tzinfo=timezone.utc),
        )

        if candidate_rank > current_rank:
            group["representative"] = article

    return list(groups.values())



def _article_official_rank(article: dict[str, Any]) -> int:
    try:
        return int(article.get("official_rank", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _group_official_reference(group: dict[str, Any]) -> dict[str, Any] | None:
    refs = []

    for article in group.get("articles") or []:
        rank = _article_official_rank(article)
        if rank <= 0:
            continue

        refs.append({
            "authority": article.get("official_source"),
            "kind": article.get("official_kind"),
            "rank": rank,
            "url": article.get("source_url") or article.get("link"),
            "published_dt": article.get("published_dt"),
        })

    if not refs:
        return None

    refs.sort(
        key=lambda x: (
            x.get("rank", 0),
            x.get("published_dt")
            or datetime.min.replace(tzinfo=timezone.utc),
        ),
        reverse=True,
    )
    return refs[0]


def _signal_icon(signal: str) -> str:
    return {
        "HIGH ATTENTION": "🔥",
        "WATCH": "👀",
        "IGNORE": "⚪",
    }.get((signal or "").upper(), "🔎")


def _clean_entity_label(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip(" -–—|,:;")
    if not text:
        return ""

    if re.fullmatch(r"[\d.,%+\- ]+", text):
        return ""

    return text[:36] + ("…" if len(text) > 36 else "")


def _clean_title_label(title: str) -> str:
    text = re.sub(r"\s+", " ", str(title or "")).strip()
    text = re.sub(
        r"\s+-\s+[A-Za-z0-9_.-]+\.(?:com|co\.id|id|net|org)\s*$",
        "",
        text,
        flags=re.I,
    )
    return text[:46] + ("…" if len(text) > 46 else "")


def _article_label(article: dict[str, Any]) -> str:
    d = article.get("details") or {}
    ticker = _resolved_ticker(article)
    if ticker:
        return ticker

    target = _clean_entity_label(d.get("target"))
    if target:
        return target

    acquirer = _clean_entity_label(d.get("acquirer"))
    if acquirer:
        return acquirer

    return _clean_title_label(
        article.get("title") or "Corporate Action"
    )


def format_compact_decision_board(
    groups: list[dict[str, Any]],
    *,
    scanned_articles: int,
) -> str:
    if not groups:
        return "Belum ada event aktif untuk Decision Board."

    signal_rank = {
        "HIGH ATTENTION": 3,
        "WATCH": 2,
        "IGNORE": 1,
    }

    groups = sorted(
        groups,
        key=lambda g: (
            1 if _group_official_reference(g) else 0,
            (_group_official_reference(g) or {}).get("rank", 0),
            signal_rank.get(
                (g["representative"].get("monitoring_signal") or "").upper(), 0
            ),
            g["representative"].get(
                "information_score",
                g["representative"].get("ca_score", 0),
            ) or 0,
            g["representative"].get("ca_score", 0) or 0,
        ),
        reverse=True,
    )

    selected = groups[:DECISION_MAX_EVENTS]
    collapsed = max(0, scanned_articles - len(groups))

    lines = [
        "🧠 <b>V6.2.2 DECISION BOARD — DEEP ISSUER + OFFICIAL</b>",
        "<i>Event-level deduplication aktif; urutan untuk triase monitoring, bukan rekomendasi investasi.</i>",
        "",
        f"🧹 <b>Dedup:</b> {scanned_articles} artikel → {len(groups)} event unik"
        + (f" ({collapsed} artikel digabung)" if collapsed else ""),
        f"📌 <b>Ditampilkan:</b> Top {len(selected)} event",
        "",
    ]

    for idx, group in enumerate(selected, start=1):
        article = group["representative"]
        d = article.get("details") or {}
        signal = (article.get("monitoring_signal") or "WATCH").upper()
        score = article.get(
            "information_score",
            article.get("ca_score", 0),
        ) or 0
        event = article.get("event_type") or "CORPORATE ACTION"
        stage = article.get("stage") or "-"
        catalyst = article.get("catalyst") or "NEUTRAL"
        source = article.get("source") or "Unknown"
        related = len(group.get("articles") or [])
        label = _article_label(article)
        ticker = _resolved_ticker(article)
        link = article.get("source_url") or article.get("link") or ""

        lines.append(
            f"{idx}. {_signal_icon(signal)} <b>{html.escape(label)} — "
            f"{html.escape(event)}</b>"
        )
        lines.append(
            f"   Signal: <b>{html.escape(signal)}</b> | Score: <b>{score}/100</b>"
        )
        lines.append(
            f"   Status: {html.escape(str(stage))} | Catalyst: "
            f"{html.escape(str(catalyst))}"
        )
        lines.append(
            f"   Sumber terbaik: {html.escape(str(source))} | "
            f"Related news: {related}"
        )

        official_ref = _group_official_reference(group)
        if official_ref:
            authority = html.escape(
                str(official_ref.get("authority") or "OFFICIAL")
            )
            kind = html.escape(
                str(official_ref.get("kind") or "PRIMARY")
            )
            lines.append(
                f"   🏛️ Official: ✅ {authority} — {kind}"
            )
        else:
            lines.append(
                "   🏛️ Official: ⚪ belum ditemukan"
            )

        actions: list[str] = []
        if ticker:
            actions.append(f"<code>/analyze {html.escape(ticker)}</code>")
            actions.append(f"<code>/official {html.escape(ticker)}</code>")
        if link:
            actions.append(
                f'<a href="{html.escape(str(link), quote=True)}">Buka sumber</a>'
            )
        if actions:
            lines.append("   🔎 " + " | ".join(actions))

        lines.append("")

    lines += [
        "🏢 <b>Deep Issuer Resolver:</b> /analyze membaca publisher terlebih dahulu untuk memetakan TICKER ↔ nama emiten; alias disimpan ke command_state. Money Unit Guard mencegah harga saham kecil masuk sebagai nilai transaksi.",
        "💡 Gunakan <code>/analyze TICKER</code> untuk detail lengkap satu event.",
        "♻️ Berita berbeda yang membahas corporate action sama tidak lagi dikirim sebagai kartu terpisah di /decision.",
    ]

    text = "\n".join(lines).strip()
    # Telegram sendMessage limit is 4096 chars. Keep a safety margin.
    return text[:3900]


def _pre_decision_group_rank(group: dict[str, Any]) -> tuple:
    article = group["representative"]
    urgency_rank = {
        "HIGH": 3,
        "MEDIUM": 2,
        "LOW": 1,
    }

    official_ref = _group_official_reference(group)

    return (
        1 if official_ref else 0,
        (official_ref or {}).get("rank", 0),
        urgency_rank.get(
            article.get("urgency", article.get("priority", "LOW")),
            0,
        ),
        article.get(
            "information_score",
            article.get("ca_score", 0),
        ) or 0,
        article.get("ca_score", 0) or 0,
        article.get("published_dt")
        or datetime.min.replace(tzinfo=timezone.utc),
    )


async def send_compact_decision_board(
    core: Any,
    chat_id: int,
) -> None:
    articles = await core.fetch_all_articles()
    active_articles = [
        x for x in articles[:DECISION_SCAN_LIMIT]
        if x.get("context") != "MARKET PIPELINE"
    ]

    if not active_articles:
        await core.send_message(
            chat_id,
            "Belum ada event aktif untuk Decision Board.",
        )
        return

    # Clean tickers before grouping so garbage such as "34"
    # can never become an event identity.
    for article in active_articles:
        _resolved_ticker(article)

    groups = group_decision_events(active_articles)
    groups.sort(
        key=_pre_decision_group_rank,
        reverse=True,
    )

    # Only final Top-N receives cheap snippet-based decision enrichment.
    # Deep extraction and market lookup are intentionally deferred to /analyze.
    candidates = groups[:DECISION_MAX_EVENTS]

    for group in candidates:
        article = group["representative"]

        if DECISION_FAST_MODE:
            await core.enrich_decision_support(
                article,
                use_market=False,
                use_deep=False,
            )
        else:
            await core.enrich_decision_support(
                article,
                use_market=True,
                use_deep=False,
            )

    await core.send_message(
        chat_id,
        format_compact_decision_board(
            groups,
            scanned_articles=len(active_articles),
        ),
    )


def first_baseline(
    state: dict[str, Any],
    chat_ids: set[int],
) -> None:
    """
    Establish a clean Telegram command baseline.

    Telegram supports a negative offset to start from the end of the queue.
    We intentionally discard commands that existed before V6.1 activation
    so old /analyze or /status messages are not replayed.
    """
    latest = get_updates(
        offset=-1,
        limit=1,
    )

    if latest:
        latest_id = int(
            latest[-1].get("update_id", -1)
        )
        state["next_offset"] = max(
            0,
            latest_id + 1,
        )
    else:
        state["next_offset"] = 0

    state["initialized"] = True
    state["last_state_change_utc"] = utc_iso()

    save_state(state)

    notice = (
        "✅ <b>Kabar Saham V6.2.2 Command Bridge aktif.</b>\n\n"
        "Command cloud sudah terhubung.\n"
        "Berita/command lama sebelum aktivasi tidak diproses ulang.\n\n"
        "Coba kirim:\n"
        "• /cloudstatus\n"
        "• /market BBCA\n"
        "• /analyze CBRE\n"
        "• /decision\n\n"
        "⏱ Respons mengikuti interval Command Bridge "
        "di cron-job.org."
    )

    for chat_id in sorted(chat_ids):
        try:
            send_message_stdlib(
                chat_id,
                notice,
            )
        except Exception:
            # Baseline itself remains valid even if one ready notice fails.
            pass


def probe(
    github_output: str | None = None,
) -> None:
    chat_ids = authorized_chat_ids()
    state = load_state()

    PENDING_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    PENDING_PATH.write_text(
        "[]\n",
        encoding="utf-8",
    )

    if not state.get("initialized"):
        first_baseline(
            state,
            chat_ids,
        )
        write_github_output(
            github_output,
            has_commands=False,
            command_count=0,
            baseline_initialized=True,
            state_changed=True,
        )
        print(
            "V6.2.2 command baseline initialized."
        )
        return

    offset = int(
        state.get("next_offset", 0)
    )

    updates = get_updates(
        offset=offset,
    )

    if not updates:
        write_github_output(
            github_output,
            has_commands=False,
            command_count=0,
            baseline_initialized=False,
            state_changed=False,
        )
        print("No Telegram updates.")
        return

    pending: list[dict[str, Any]] = []
    highest_next_offset = offset
    now_ts = int(time.time())

    recent = cleanup_recent_commands(
        state.get("recent_commands", {}),
        now_ts=now_ts,
    )

    duplicates_by_chat: dict[int, list[str]] = {}
    duplicates_count = 0

    for update in updates:
        update_id = update.get("update_id")

        try:
            update_id = int(update_id)
        except (TypeError, ValueError):
            continue

        highest_next_offset = max(
            highest_next_offset,
            update_id + 1,
        )

        chat_id, text = message_info(update)

        if (
            chat_id not in chat_ids
            or not command_name(text)
        ):
            continue

        canonical = canonical_command_text(text)
        fingerprint = command_fingerprint(
            chat_id,
            canonical,
        )
        sent_ts = update_timestamp(update)

        previous_ts = recent.get(fingerprint)
        is_duplicate = False

        if (
            COMMAND_DEDUP_SECONDS > 0
            and previous_ts is not None
        ):
            delta = max(
                0,
                sent_ts - int(previous_ts),
            )
            if delta <= COMMAND_DEDUP_SECONDS:
                is_duplicate = True

        if is_duplicate:
            duplicates_by_chat.setdefault(
                chat_id,
                [],
            ).append(canonical)
            duplicates_count += 1
            continue

        # Register immediately so repeated copies in the SAME polling batch
        # are also suppressed.
        recent[fingerprint] = sent_ts
        pending.append(update)

    state["next_offset"] = highest_next_offset
    state["updates_seen"] = int(
        state.get("updates_seen", 0)
    ) + len(updates)
    state["recent_commands"] = recent
    state["duplicates_suppressed"] = int(
        state.get("duplicates_suppressed", 0)
    ) + duplicates_count
    state["last_state_change_utc"] = utc_iso()
    state["schema_version"] = SCHEMA_VERSION

    # Saved locally now; GitHub commit happens after command execution.
    save_state(state)

    PENDING_PATH.write_text(
        json.dumps(
            pending,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    # Duplicate notice is lightweight and does not require full dependencies.
    for chat_id, duplicate_commands in duplicates_by_chat.items():
        try:
            send_message_stdlib(
                chat_id,
                format_duplicate_notice(
                    duplicate_commands
                ),
            )
        except Exception as exc:
            print(
                "Duplicate notice failed:",
                type(exc).__name__,
            )

    write_github_output(
        github_output,
        has_commands=bool(pending),
        command_count=len(pending),
        baseline_initialized=False,
        state_changed=True,
    )

    print(
        f"Telegram updates: {len(updates)}; "
        f"accepted commands: {len(pending)}; "
        f"duplicates suppressed: {duplicates_count}."
    )


def test_bridge() -> None:
    chat_ids = authorized_chat_ids()

    text = (
        "✅ <b>Kabar Saham V6.2.2 — DEEP ISSUER + MONEY GUARD TEST OK</b>\n\n"
        "GitHub Secrets dan Telegram Bot API berhasil dibaca.\n"
        "Langkah berikutnya: jalankan mode <b>poll</b> "
        "sekali untuk membuat baseline command."
    )

    delivered = 0

    for chat_id in sorted(chat_ids):
        send_message_stdlib(
            chat_id,
            text,
        )
        delivered += 1

    print(
        f"V6.1 test delivered to {delivered} chat(s)."
    )


# ---------------------------------------------------------------------
# Full command execution: imported only when a command actually exists.
# ---------------------------------------------------------------------

HELP_V61 = """
<b>☁️ Kabar Saham V6.2.2 — Deep Issuer Resolver + Money Guard</b>

Perintah cloud:
/cloudstatus — status bridge cloud
/status — status intelligence core
/decision — Decision Board Official Priority
/official TICKER — cek sumber resmi IDX/e-IPO/KSEI/OJK
/analyze TICKER — analisis corporate action
/deep TICKER — deep article extraction
/market TICKER — harga pasar terakhir
/publisherdebug TICKER — debug Publisher Direct
/resolve TICKER — resolver diagnostics
/decode TICKER — Google News decoder
/protocoldebug TICKER — dynamic protocol debug
/decoderdebug TICKER — decoder parser debug
/latest — corporate action terbaru
/today — berita 24 jam terakhir
/high — Urgency HIGH
/active — event aktif
/actionable — IPO ACTIONABLE
/pipeline — IPO PIPELINE
/ma — M&A / takeover
/ipo — IPO
/rights — Rights Issue / HMETD
/help — bantuan

Auto-alert V6.0 tetap berjalan terpisah setiap 10 menit.
Command V6.1 diproses saat cron Command Bridge menjalankan GitHub Actions.
""".strip()


async def dispatch_core_command(
    core: Any,
    update: dict[str, Any],
) -> None:
    message = update.get("message") or {}
    chat = message.get("chat") or {}

    chat_id = chat.get("id")
    text = (message.get("text") or "").strip()

    if not chat_id or not text:
        return

    try:
        chat_id = int(chat_id)
    except (TypeError, ValueError):
        return

    parts = text.split()
    command = parts[0].split("@")[0].lower()
    args = parts[1:]

    if command == "/start":
        await core.send_message(
            chat_id,
            "✅ <b>Kabar Saham V6.2.1 Cloud aktif.</b>\n\n"
            "Auto-alert V6.0 dan Interactive Command Bridge V6.1 "
            "sudah terpisah dari laptop.\n\n"
            + HELP_V61,
        )
        return

    if command == "/help":
        await core.send_message(
            chat_id,
            HELP_V61,
        )
        return

    if command == "/cloudstatus":
        await core.send_message(
            chat_id,
            "☁️ <b>Kabar Saham V6.2.2 Cloud Status</b>\n\n"
            "Auto Alert V6.0: ✅ ACTIVE\n"
            "Interactive Command Bridge: ✅ ACTIVE\n"
            "Anti-Duplicate: ✅ ON (±3 menit)\n"
            "Compact Decision Board: ✅ ON\n"
            "Decision FAST Mode: ✅ ON\n"
            "Ticker Guard: ✅ STRICT 4-LETTER\n"
            "Official Source Priority: "
            f"{'✅ ON' if getattr(core, 'OFFICIAL_SOURCE_PRIORITY_ENABLED', False) else '❌ OFF'}\n"
            "Official Discovery: "
            f"{'✅ ON' if getattr(core, 'OFFICIAL_DISCOVERY_ENABLED', False) else '❌ OFF'}\n"
            "Ticker Recovery: "
            f"{'✅ ON' if getattr(core, 'TICKER_RECOVERY_ENABLED', False) else '❌ OFF'}\n"
            "Issuer Resolver: "
            f"{'✅ ON' if getattr(core, 'ISSUER_ALIAS_PROPAGATION_ENABLED', False) else '❌ OFF'}\n"
            "Deep Issuer Resolver: "
            f"{'✅ ON' if getattr(core, 'DEEP_ISSUER_RESOLVER_ENABLED', False) else '❌ OFF'}\n"
            "Money Unit Guard: "
            f"{'✅ ON' if getattr(core, 'MONEY_UNIT_GUARD_ENABLED', False) else '❌ OFF'}\n"
            "Issuer Memory: ✅ command_state\n"
            "Runtime: GitHub Actions\n"
            "Timer: cron-job.org\n"
            "Laptop required: ❌ NO\n"
            "VPS required: ❌ NO\n"
            "Intelligence core: V5.4 Publisher Direct\n"
            "Market Data: "
            f"{'✅ ON' if core.MARKET_DATA_ENABLED and core.YFINANCE_AVAILABLE else '❌ OFF'}\n"
            "Deep Extraction: "
            f"{'✅ ON' if core.DEEP_EXTRACTION_ENABLED and core.BS4_AVAILABLE else '❌ OFF'}\n"
            "Publisher Direct: "
            f"{'✅ ON' if core.PUBLISHER_DIRECT_ENABLED else '❌ OFF'}\n\n"
            "⏱ Command diproses pada interval cron Command Bridge.",
        )
        return

    if command == "/status":
        await core.send_message(
            chat_id,
            "🟢 <b>Bot aktif — V6.2.2 Cloud / V5.4 Intelligence Core</b>\n"
            "Auto Alert: cron-job.org → GitHub Actions\n"
            "Command Bridge: cron-job.org → GitHub Actions\n"
            "Anti-Duplicate: ON (default ±180 detik)\n"
            "Decision Board: FAST + CLEAN + EVENT DEDUP\n"
            "Ticker Guard: STRICT 4-LETTER + TITLE FALLBACK\n"
            f"Official Source Priority: {'ON' if getattr(core, 'OFFICIAL_SOURCE_PRIORITY_ENABLED', False) else 'OFF'}\n"
            f"Official Discovery: {'ON' if getattr(core, 'OFFICIAL_DISCOVERY_ENABLED', False) else 'OFF'}\n"
            f"Ticker Recovery: {'ON' if getattr(core, 'TICKER_RECOVERY_ENABLED', False) else 'OFF'}\n"
            f"Issuer Resolver: {'ON' if getattr(core, 'ISSUER_ALIAS_PROPAGATION_ENABLED', False) else 'OFF'}\n"
            f"Manual search: {core.RECENT_DAYS} hari terakhir\n"
            f"Auto alert freshness: {core.AUTO_ALERT_HOURS} jam\n"
            f"Minimum priority: {core.AUTO_ALERT_MIN_PRIORITY}\n"
            f"Market data: {'ON' if core.MARKET_DATA_ENABLED and core.YFINANCE_AVAILABLE else 'OFF'}\n"
            f"Deep extraction: {'ON' if core.DEEP_EXTRACTION_ENABLED and core.BS4_AVAILABLE else 'OFF'}\n"
            f"Source resolver: {'ON' if core.SOURCE_RESOLVER_ENABLED else 'OFF'}\n"
            f"Google decoder: {'ON' if core.GOOGLE_DECODER_ENABLED else 'OFF'}\n"
            f"Publisher Direct: {'ON' if core.PUBLISHER_DIRECT_ENABLED else 'OFF'}\n"
            f"Query aktif: {len(core.CONFIG.get('queries', []))}",
        )
        return

    heavy = {
        "/decision",
        "/official",
        "/analyze",
        "/deep",
        "/resolve",
        "/decode",
        "/decoderdebug",
        "/protocoldebug",
        "/publisherdebug",
    }

    if command in heavy:
        await core.send_message(
            chat_id,
            f"⏳ <b>V6.2.2 memproses {command}</b>…",
        )

    if command == "/latest":
        await core.send_message(
            chat_id,
            "🔎 Mencari corporate action terbaru…",
        )
        await core.send_filtered(chat_id)

    elif command == "/today":
        await core.send_message(
            chat_id,
            "🕒 Mencari berita 24 jam terakhir…",
        )
        await core.send_filtered(
            chat_id,
            today_only=True,
        )

    elif command == "/high":
        await core.send_message(
            chat_id,
            "🔴 Mencari corporate action Urgency HIGH…",
        )
        await core.send_filtered(
            chat_id,
            high_only=True,
        )

    elif command == "/active":
        await core.send_message(
            chat_id,
            "🟢 Mencari corporate action ACTIVE terbaru…",
        )
        await core.send_filtered(
            chat_id,
            active_only=True,
        )

    elif command == "/actionable":
        await core.send_message(
            chat_id,
            "🔥 Mencari IPO ACTIONABLE terbaru…",
        )
        await core.send_filtered(
            chat_id,
            ipo_class="ACTIONABLE",
        )

    elif command == "/pipeline":
        await core.send_message(
            chat_id,
            "📰 Mencari IPO PIPELINE terbaru…",
        )
        await core.send_filtered(
            chat_id,
            ipo_class="PIPELINE",
        )

    elif command == "/decision":
        await send_compact_decision_board(
            core,
            chat_id,
        )

    elif command == "/official":
        if not args:
            await core.send_message(
                chat_id,
                "Gunakan /official TICKER — contoh /official DOOH",
            )
        else:
            await core.official_ticker(
                chat_id,
                args[0],
            )

    elif command == "/market":
        if not args:
            await core.send_message(
                chat_id,
                "Gunakan /market TICKER — contoh /market BBCA",
            )
        else:
            await core.send_market_quote(
                chat_id,
                args[0],
            )

    elif command in {"/analyze", "/deep"}:
        if not args:
            await core.send_message(
                chat_id,
                f"Gunakan {command} TICKER — contoh {command} CBRE",
            )
        else:
            await core.analyze_ticker(
                chat_id,
                args[0],
            )

    elif command == "/resolve":
        if not args:
            await core.send_message(
                chat_id,
                "Gunakan /resolve TICKER — contoh /resolve CBRE",
            )
        else:
            await core.resolve_ticker_source(
                chat_id,
                args[0],
            )

    elif command == "/decode":
        if not args:
            await core.send_message(
                chat_id,
                "Gunakan /decode TICKER — contoh /decode CBRE",
            )
        else:
            await core.decode_ticker_google_url(
                chat_id,
                args[0],
            )

    elif command == "/decoderdebug":
        if not args:
            await core.send_message(
                chat_id,
                "Gunakan /decoderdebug TICKER — contoh /decoderdebug CBRE",
            )
        else:
            await core.decoder_debug_ticker(
                chat_id,
                args[0],
            )

    elif command == "/protocoldebug":
        if not args:
            await core.send_message(
                chat_id,
                "Gunakan /protocoldebug TICKER — contoh /protocoldebug CBRE",
            )
        else:
            await core.protocol_debug_ticker(
                chat_id,
                args[0],
            )

    elif command == "/publisherdebug":
        if not args:
            await core.send_message(
                chat_id,
                "Gunakan /publisherdebug TICKER — contoh /publisherdebug CBRE",
            )
        else:
            await core.publisher_debug_ticker(
                chat_id,
                args[0],
            )

    elif command == "/ma":
        await core.send_message(
            chat_id,
            "🤝 Mencari M&A / takeover terbaru…",
        )
        await core.send_filtered(
            chat_id,
            "MA",
        )

    elif command == "/ipo":
        await core.send_message(
            chat_id,
            "🆕 Mencari IPO valid terbaru…",
        )
        await core.send_filtered(
            chat_id,
            "IPO",
        )

    elif command == "/rights":
        await core.send_message(
            chat_id,
            "📣 Mencari Rights Issue / HMETD terbaru…",
        )
        await core.send_filtered(
            chat_id,
            "RIGHTS",
        )

    else:
        await core.send_message(
            chat_id,
            "❓ Command tidak dikenali.\n\n"
            + HELP_V61,
        )


def hydrate_issuer_memory(core: Any, state: dict[str, Any]) -> int:
    memory = state.get("issuer_aliases") or {}
    count = 0
    register = getattr(core, "register_ticker_aliases", None)
    if not callable(register):
        return 0
    for ticker, aliases in memory.items():
        if not isinstance(aliases, list):
            continue
        try:
            registered = register(ticker, aliases)
            if registered:
                count += 1
        except Exception:
            continue
    return count


def export_issuer_memory(core: Any) -> dict[str, list[str]]:
    cache = getattr(core, "TICKER_ALIAS_CACHE", {}) or {}
    output: dict[str, list[str]] = {}
    for ticker, values in cache.items():
        if not isinstance(values, dict):
            continue
        aliases = []
        seen = set()
        for item in values.values():
            if not isinstance(item, dict):
                continue
            alias = str(item.get("alias") or "").strip()
            key = re.sub(r"\s+", " ", alias).lower()
            if alias and key not in seen:
                seen.add(key)
                aliases.append(alias)
        if aliases:
            output[str(ticker).upper()] = aliases[:8]
    return output


async def execute_pending() -> None:
    if not PENDING_PATH.exists():
        print("No pending command file.")
        return

    try:
        pending = json.loads(
            PENDING_PATH.read_text(
                encoding="utf-8"
            )
        )
    except Exception as exc:
        raise RuntimeError(
            f"Pending command JSON invalid: {exc}"
        ) from exc

    if not pending:
        print("No pending commands.")
        return

    chat_ids = authorized_chat_ids()

    # Lazy import: full dependencies are only needed when a real command exists.
    core_dir = ROOT / "core"
    sys.path.insert(
        0,
        str(core_dir),
    )

    import main as core  # type: ignore  # noqa: E402

    state = load_state()
    hydrated_aliases = hydrate_issuer_memory(core, state)
    if hydrated_aliases:
        print(f"Issuer memory hydrated: {hydrated_aliases} ticker(s).")
    processed = 0

    for update in pending:
        chat_id, text = message_info(update)

        if (
            chat_id not in chat_ids
            or not command_name(text)
        ):
            continue

        try:
            await dispatch_core_command(
                core,
                update,
            )
        except Exception as exc:
            # A command-level failure is reported to Telegram and then the
            # update is considered handled. The user can explicitly retry.
            try:
                await core.send_message(
                    chat_id,
                    "⚠️ <b>Command V6.1 gagal diproses.</b>\n"
                    f"Jenis error: {type(exc).__name__}\n"
                    "Silakan coba command yang sama pada poll berikutnya.",
                )
            except Exception:
                pass

            print(
                "Command processing error:",
                type(exc).__name__,
            )

        processed += 1

    if processed:
        state["commands_processed"] = int(
            state.get("commands_processed", 0)
        ) + processed
        state["last_command_utc"] = utc_iso()
        state["last_state_change_utc"] = utc_iso()
        state["issuer_aliases"] = export_issuer_memory(core)
        save_state(state)

    print(
        f"Commands processed: {processed}."
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=[
            "probe",
            "execute",
            "test",
        ],
        required=True,
    )
    parser.add_argument(
        "--github-output",
        default=None,
    )

    args = parser.parse_args()

    if args.mode == "probe":
        probe(
            github_output=args.github_output,
        )
        return

    if args.mode == "test":
        test_bridge()
        write_github_output(
            args.github_output,
            has_commands=False,
            command_count=0,
            state_changed=False,
        )
        return

    asyncio.run(
        execute_pending()
    )


if __name__ == "__main__":
    main()
