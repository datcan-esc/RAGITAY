# RAGITAY

RAGITAY, yargı kararları üzerinde doğal dil ile arama yapmayı, ilgili kararları incelemeyi, kararlar hakkında kısa özetler üretmeyi ve seçilen karar üzerinden yapay zeka ile soru-cevap yapmayı sağlayan bir hukuki RAG uygulamasıdır.

Projenin temel amacı, kullanıcının çok sayıda uzun karar metnini tek tek okumadan önce hangi kararların gerçekten işine yarayabileceğini hızlıca anlayabilmesidir. Sistem önce ilgili kararları ve pasajları bulur, ardından yapay zeka katmanını yalnızca daraltılmış ve referanslı bağlam üzerinde çalıştırır.

## Ne Yapar?

- Doğal dilde yazılan hukuki sorularla karar araması yapar.
- Semantic search ve lexical search sonuçlarını birlikte kullanır.
- Kararları yapılandırılmış metadata, bölüm bilgileri ve tam metin ile saklar.
- Karar metinlerini küçük, aranabilir parçalara böler.
- Her parça için embedding üretip `pgvector` üzerinde saklar.
- Sonuçlarda ilgili pasajları ve benzerlik oranını gösterir.
- Arama sonuçları için genel bir yapay zeka özeti üretir.
- Seçilen karar için isteğe bağlı yapay zeka özeti üretir.
- Kullanıcının seçilen karar hakkında soru sormasını sağlar.
- Gereksiz LLM çağrılarını azaltmak için sadece ihtiyaç duyulan bağlamı modele gönderir.

## Sistem Akışı

```text
Kullanıcı sorgusu
  -> Hybrid search
  -> İlgili karar parçaları
  -> Karar bazlı gruplanmış sonuçlar
  -> Opsiyonel genel yapay zeka özeti
  -> Seçilen karar detayı
  -> Opsiyonel karar özeti / karar bazlı soru-cevap
```

Retrieval katmanı ile LLM katmanı ayrı tutulur.

- Retrieval katmanı hangi kararların ve pasajların ilgili olduğunu belirler.
- LLM yalnızca bulunan veya seçilen bağlamı açıklar.
- Karar hakkında soru-cevap akışı tüm veri setiyle değil, yalnızca seçilen karar ile çalışır.

## Mimari

```text
frontend/
  Next.js arayüzü
  Arama ekranı, filtreler, sonuç listesi, karar detayı, AI yardım alanı

backend/
  FastAPI servisi
  Hybrid search API, karar detayı API, özet API, karar bazlı soru-cevap API

infra/
  PostgreSQL + pgvector şeması

ingestion/
  Veri normalizasyonu, veritabanı import, chunking ve embedding yardımcıları

docker-compose.yml
  PostgreSQL, backend ve frontend servisleri
```

## Veri Modeli

RAGITAY kararları iki ana tablo üzerinde saklar.

### `decisions`

Her satır bir yargı kararını temsil eder.

Önemli alanlar:

- `source_name`: karar kaynağı, örneğin `yargitay` veya `uyap_emsal`
- `external_id`: kaynaktaki özgün karar id değeri
- `daire`: daire bilgisi
- `esas_no`: esas numarası
- `karar_no`: karar numarası
- `karar_tarihi`: karar tarihi
- `title`: ekranda gösterilecek karar başlığı
- `mahkeme`: mahkeme veya ilişkili yargı merci bilgisi
- `outcome`: karar sonucu, örneğin `KABULÜNE`, `REDDİNE`, `BOZULMASINA`
- `sections`: karar içindeki bölümlerin JSONB formatında saklanması
- `full_text`: normalize edilmiş tam karar metni
- `document_metadata`: ek metadata alanları

`source_name` ve `external_id` birlikte unique olarak tutulur. Bu sayede aynı karar tekrar işlense bile veritabanında duplicate kayıt oluşmaz.

### `decision_chunks`

Her satır bir kararın aranabilir metin parçasını temsil eder.

Önemli alanlar:

- `decision_id`: bağlı olduğu karar
- `chunk_index`: karar içindeki parça sırası
- `section_name`: parçanın ait olduğu bölüm, örneğin `dava`, `gerekce`, `karar`
- `chunk_text`: aranabilir pasaj metni
- `chunk_chars`: pasaj uzunluğu
- `embedding`: semantic search için `VECTOR(768)` embedding alanı

Bu yapı sayesinde sistem tüm karar metnini tek parça halinde aramak yerine, daha anlamlı ve küçük pasajlar üzerinde arama yapar.

## Normalize Karar Formatı

Sistem, kararların veritabanına aktarılmadan önce aşağıdaki yapıya benzer normalize edilmiş bir formatta olmasını bekler.

```json
{
  "source_name": "yargitay",
  "external_id": "1207018000",
  "daire": "9. Hukuk Dairesi",
  "esas_no": "2025/10011",
  "karar_no": "2026/1059",
  "karar_tarihi": "2026-02-10",
  "title": "9. Hukuk Dairesi 2025/10011 E. , 2026/1059 K.",
  "mahkeme": "İstanbul Bölge Adliye Mahkemesi 41. Hukuk Dairesi",
  "outcome": "",
  "source_url": "https://...",
  "sections": {
    "dava": "Davacı vekili dava dilekçesinde...",
    "ilk_derece_mahkemesi_karari": "İlk Derece Mahkemesinin...",
    "karar": "Açıklanan sebeplerle..."
  },
  "full_text": "Kararın tam metni..."
}
```

Bu kayıt önce `decisions` tablosuna yazılır. Ardından bölüm bilgileri ve tam metin üzerinden `decision_chunks` kayıtları oluşturulur.

## Retrieval Akışı

Arama sistemi hybrid yapıdadır.

- Semantic search: kullanıcı sorgusu embedding vektörüne çevrilir ve karar parçalarının embedding değerleriyle karşılaştırılır.
- Lexical search: sorgu metni karar parçaları ve karar başlıkları üzerinde metinsel olarak eşleştirilir.
- Bölüm ağırlıkları: `gerekce`, `dava`, `ilk_derece_mahkemesi_karari` gibi hukuken daha anlamlı bölümlere öncelik verilir.
- Düşük bilgi taşıyan kısa veya jenerik parçalar sonuçlardan elenir.
- Sonuçlar karar bazında gruplanır ve her karar için en ilgili pasajlar döndürülür.

Kullanıcıya gösterilen benzerlik oranı `0-100%` aralığında sınırlandırılır.

## Yapay Zeka Akışı

RAGITAY tüm veri setini veya çok büyük karar listelerini doğrudan LLM'e göndermez.

Mevcut davranış:

- Arama özeti: en iyi sonuçlardan kısa genel değerlendirme ve öne çıkan noktalar üretir.
- Karar özeti: yalnızca kullanıcı seçilen karar için istediğinde üretilir.
- Karar bazlı soru-cevap: yalnızca seçilen kararın bağlamını kullanır.

Desteklenen sağlayıcılar:

- `gemini`
- `openai`
- `fallback`

LLM anahtarı tanımlı değilse sistem fallback özetlerle temel işlevini sürdürür.

## Backend API

Varsayılan backend adresi:

```text
http://localhost:8000
```

Önemli endpointler:

- `GET /health`
- `POST /api/search`
- `POST /api/search/summary`
- `GET /api/search/decisions/{decision_id}`
- `POST /api/search/decisions/{decision_id}/summary`
- `POST /api/search/decisions/{decision_id}/ask`

Örnek arama isteği:

```bash
curl -X POST http://localhost:8000/api/search \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "whatsapp mesajlarına cevap vermediğim için işten çıkarıldım",
    "source_names": ["yargitay"],
    "daire": "9. Hukuk Dairesi",
    "year_from": 2020,
    "year_to": 2026,
    "top_decisions": 5
  }'
```

## Frontend

Varsayılan frontend adresi:

```text
http://localhost:3000
```

Arayüzde bulunan temel özellikler:

- sade arama giriş ekranı
- filtre modalı
- URL ile paylaşılabilir arama durumu
- genel yapay zeka özeti
- sade karar sonuç listesi
- karar detayı paneli
- seçilen karar içinde tam metin araması
- isteğe bağlı karar özeti üretimi
- seçilen karar hakkında soru-cevap
- açık / koyu tema desteği

## Docker ile Çalıştırma

```bash
docker compose up --build
```

Servisler:

- `postgres`: PostgreSQL + pgvector
- `backend`: FastAPI API servisi
- `frontend`: Next.js arayüzü

Varsayılan portlar:

- frontend: `http://localhost:3000`
- backend: `http://localhost:8000`
- postgres: `localhost:5433`

## Ortam Değişkenleri

Sık kullanılan değişkenler:

```bash
POSTGRES_DB=ragitay
POSTGRES_USER=ragitay
POSTGRES_PASSWORD=ragitay
POSTGRES_PORT=5433

SUMMARY_PROVIDER=gemini
SUMMARY_MODEL_NAME=gemini-2.5-flash
GEMINI_API_KEY=your_key

NEXT_PUBLIC_SEARCH_API_BASE_URL=http://localhost:8000
BACKEND_CORS_ALLOW_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

Docker kullanmadan lokal geliştirme için:

```bash
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload
```

```bash
cd frontend
pnpm install
pnpm dev
```

## CORS Notu

Frontend API çağrılarını tarayıcı üzerinden yaptığı için public API URL değeri tarayıcının erişebileceği backend adresini göstermelidir.

Varsayılan Docker kurulumu için:

```text
NEXT_PUBLIC_SEARCH_API_BASE_URL=http://localhost:8000
BACKEND_CORS_ALLOW_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

Port veya domain değişirse bu iki değer birlikte güncellenmelidir.

## Tasarım İlkeleri

- Retrieval ve generation katmanlarını ayrı tut.
- Kararları yapılandırılmış, tekrar çalıştırılabilir kayıtlar olarak sakla.
- Tüm karar metni yerine küçük ve anlamlı pasajlar üzerinde arama yap.
- LLM'e yalnızca ilgili ve daraltılmış bağlam gönder.
- Yapay zeka cevaplarını karar referanslarıyla sınırlı tut.
- Kullanıcının açmadığı kararlar için gereksiz LLM çağrısı yapma.
- Her zaman tam karar metnine erişim sağlayarak doğrulanabilirliği koru.

## Proje Durumu

RAGITAY şu anda şunları içerir:

- PostgreSQL + pgvector veritabanı şeması
- hybrid legal search backend
- LLM destekli genel özet ve seçilen karar üzerinden soru-cevap
- Next.js frontend
- Docker Compose kurulumu
- açık / koyu tema desteği

Sonraki önemli geliştirmeler arama performansı için vector index optimizasyonu, daha zengin karar içi referanslama ve retrieval kalitesini ölçmek için değerlendirme veri setleri olabilir.
