# RAG Planı

## Hedef
Uygulama, Yargıtay ve UYAP kararları üzerinde çalışan referanslı bir hukuki RAG sistemi olacak.

Kullanıcı akışı:
1. Kullanıcı sorununu doğal dilde yazar.
2. Sistem en ilgili kararları ve pasajları bulur.
3. LLM, bulunan sonuçlardan genel özet ve karar bazlı mini özetler üretir.
4. Kullanıcı bir kararı açar.
5. Kullanıcı seçilen karar hakkında detaylı soru sorar.
6. LLM sadece seçilen kararın temiz bağlamı ile cevap verir.

## Uygulama Sırası

### 1. Retrieval katmanını sabitle
- `search` sonucu kaliteli ve tutarlı olmalı.
- Top kararlar ve top pasajlar güvenilir biçimde dönmeli.
- Detay paneli tek kararın tam metnini açabilmeli.

### 2. Search response şemasını netleştir
- Arama sonucu içinde:
  - genel sonuç listesi
  - karar metadata’sı
  - öne çıkan pasajlar
  - skor
  - kaynak linki
olmalı.

### 3. LLM summary katmanını ekle
- Retrieval sonucu doğrudan kullanıcıya verilmeden önce LLM’e küçük ve temiz bir context hazırlanmalı.
- LLM şunları üretmeli:
  - genel özet
  - karar bazlı mini özetler

### 4. Karar bazlı soru-cevap katmanını ekle
- Kullanıcı bir kararı seçtikten sonra soru sorabilmeli.
- Bu aşamada LLM’e sadece:
  - kullanıcı sorusu
  - seçilen kararın tam metni veya ilgili section’ları
verilmeli.

### 5. Frontend akışını buna göre güncelle
- İlk ekran: sadece karşılama + arama çubuğu
- Arama sonrası:
  - genel AI özeti
  - karar listesi
  - detay paneli
- Karar seçilince:
  - karar hakkında soru sor alanı

### 6. LLM fallback yapısı kur
- LLM summary başarısız olursa extractive summary gösterilmeli.
- Sistem LLM olmadan da temel retrieval ile çalışmaya devam etmeli.

## Teknik Tasarım İlkeleri

### Retrieval
- Önce hybrid search
- Sonra top-k daraltma
- Sonra sadece temiz context ile LLM çağrısı

### LLM context
- Tüm kararları tek çağrıda gönderme
- En fazla seçilmiş birkaç karar ve pasaj gönder
- Her çağrı amaca göre küçük olmalı

### Backend
- `search` ve `summary/chat` katmanları ayrı olmalı
- Önerilen ayrım:
  - `POST /api/search`
  - `POST /api/summary`
  - `POST /api/decisions/{id}/chat`

### Frontend
- UI primitive’ler ayrı
- Domain component’ler ayrı
- Container ve data-fetching mantığı ayrı

## Netleştirilmesi Gereken Kararlar

### 1. LLM sağlayıcısı
Karar vermen gereken:
- OpenAI mi
- Gemini mi
- başka bir sağlayıcı mı
- yoksa yerel model mi

### 2. Genel özet formatı
Karar vermen gereken:
- 2-3 cümle kısa özet mi
- madde madde özet mi
- hem kısa özet hem mini karar özetleri mi

### 3. Karar bazlı mini özet formatı
Karar vermen gereken:
- her karar için 1 kısa paragraf mı
- 2 maddelik özet mi
- “neden ilgili” açıklaması da olsun mu

### 4. Detay soru-cevap sınırı
Karar vermen gereken:
- kullanıcı sadece seçilen karar hakkında mı soru sorsun
- yoksa seçilen 2-3 karar arasında karşılaştırma da yapabilelim mi

### 5. Referans gösterim biçimi
Karar vermen gereken:
- sadece daire/esas/karar no mu gösterilsin
- kaynak linki de her AI cevabında bulunsun mu
- pasaj referansı açıkça gösterilsin mi

### 6. İlk sürüm kapsamı
Karar vermen gereken:
- önce sadece summary mi yapalım
- yoksa summary + karar bazlı chat’i birlikte mi çıkaralım

## Önerilen Sonraki Adım
Önce şu üç şeyi netleştir:
1. Hangi LLM sağlayıcısını kullanacağız
2. Kısa özet alanının tam formatı ne olacak
3. İlk sürümde sadece summary mi, yoksa karar bazlı chat de mi olacak

Bu kararlar netleşince backend `summary` ve `decision chat` katmanına geçilir.
