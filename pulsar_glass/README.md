# 🔮 Pulsar Glass — Liquid Glass Segmented Slider & Modal

> **Donanım Hızlandırmalı, Sıvı Cam Fiziğine Sahip Sürüklenebilir & Kayan Segmented Slider ve Glassmorphism Modal Kütüphanesi.**  
> *Mustafa Tıraş tarafından geliştirilmiş, sıfır bağımlılıklı yüksek performanslı UI kütüphanesi.*

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-none-brightgreen.svg)]()
[![Hardware Accelerated](https://img.shields.io/badge/performance-120%20FPS-purple.svg)]()
[![Framework Agnostic](https://img.shields.io/badge/platform-HTML%20%7C%20Blazor%20%7C%20React%20%7C%20Vue-orange.svg)]()

---

## 🌟 Neden Pulsar Glass?

Standart web butonları doğrusal (`linear` veya `ease-in-out`) geçişlerle yetinirken, **Pulsar Glass** arayüzü gerçek bir **"akışkan cam mercek" (liquid glass lens)** simülasyonu olarak işler:

1. **Uçuş Fiziği (Mid-Flight Volume Arc):** Butona tıklandığında mercek sabit kalmaz; mesafeye bağlı dinamik süreyle havalanır, havada parabolik olarak %16 hacimsel genleşir (`Scale Arc`), hareket yönüne göre basılıp uzar (`Squish & Stretch`) ve aerodinamik olarak eğilir (`Skew/Tilt`).
2. **Apple Quintic Ease-Out:** Doğal ivmelenme ve manyetik yay sönümlemesi:  
   $$\text{ease}(p) = 1 - (1 - p)^{3.6} \cdot (1 - 0.15 \cdot p)$$
3. **Elastik Yüzey Gerilimi & Taşma Fiziği (Nonlinear Rubber-Banding):** Buton sınırlarının dışına sürüklendiğinde sertçe durmaz; sıvı yüzey gerilimi formülüyle dışarı taşar ve geri çekilme kuvveti üretir:  
   $$x_{\text{overshoot}} = M \cdot \left(1 - e^{-\frac{d}{R}}\right) \quad (M = 44\text{px}, \, R = 110\text{px})$$
4. **Çift Kademeli Optik Kırılma (GPU Accelerated SVG):**
   - **Kromatik Aberasyon (`#pulsar-glass-refract`):** Hızlı hareket ve sürüklemede mercek ışığı kırmızı, yeşil ve mavi kanallara ayırır (Prizmatik cam kırılması).
   - **Su Altı Dalgalanması (`#pulsar-glass-water`):** Mercek butonun üzerinden geçerken altındaki metin optik olarak hafifçe kırılır ve dalgalanır.
5. **Sabit Speküler Işıma (Fixed Specular Highlight):** Işık yansıması imleçle birlikte kayarak görsel karmaşa yaratmaz; cam merceğin tepe noktasına sabitlenmiş asil bir kristal ışıması sunar.
6. **Sıfır Reflow (Hermite Smoothstep Width Morphing):** Buton genişlikleri farklı olsa dahi önbelleklenmiş koordinatlar ve Hermite eğrisi ($t^2(3 - 2t)$) sayesinde sıfır layout thrashing ile 120 FPS çalışır.

---

## 📁 Paket Yapısı (Folder Structure)

```text
pulsar-glass/
├── dist/
│   ├── pulsar-glass.js        # Saf JS çekirdeği (UMD, bağımsız, sıfır dependency)
│   ├── pulsar-glass.d.ts      # TypeScript tip tanımları
│   └── pulsar-glass.css       # 6 katmanlı cam optiği & CSS değişkenleri
├── blazor/
│   ├── PulsarGlassSegmented.razor # @bind-Value destekli generic Blazor bileşeni
│   ├── PulsarGlassModal.razor     # Liquid Glass popup/modal bileşeni
│   └── PulsarGlassModels.cs       # Boyut enum'ları ve yardımcı modeller
├── skill/
│   └── SKILL.md               # AI / LLM entegrasyon & mimari mühendislik kılavuzu
├── package.json               # NPM paket metadata ve modül tanımları
├── index.html                 # Tüm varyantları içeren interaktif vitrin & test sayfası
├── README.md                  # Kullanım ve dökümantasyon rehberi
├── LICENSE                    # MIT Lisansı
└── .gitignore                 # Git yoksayma kuralları
```

---

## 🚀 Hızlı Başlangıç (Quick Start)

### 1. Test Sayfasını Açma
Paketi indirip doğrudan tarayıcınızda test etmek için:
```bash
# macOS
open index.html

# Linux
xdg-open index.html

# Windows
start index.html
```

---

### 2. Standart HTML / JavaScript Projelerinde Kullanım

#### A. Stil ve Betiği Dahil Edin:
```html
<link rel="stylesheet" href="pulsar-glass/dist/pulsar-glass.css">
<script src="pulsar-glass/dist/pulsar-glass.js"></script>
```

#### B. HTML İskeletini Ekleyin:
```html
<div class="pg-track" id="myTrack">
  <div class="pg-slider" id="mySlider"></div>
  <button class="pg-btn active" data-value="all">
    <span class="pg-label">Tümü</span>
  </button>
  <button class="pg-btn" data-value="analytics">
    <span class="pg-label">Analiz</span>
  </button>
  <button class="pg-btn" data-value="reports">
    <span class="pg-label">Raporlar</span>
  </button>
</div>
```

#### C. JavaScript ile Başlatın:
```javascript
const slider = PulsarGlass.create('#myTrack', {
  onChange: (index, value, element) => {
    console.log(`Seçilen: ${value} (indeks: ${index})`);
  }
});

// Programatik kontrol
slider.selectIndex(1);            // 2. butona uçar
slider.selectByValue('arastirma'); // data-value'ya göre uçar
slider.refresh();                 // Boyut değiştiğinde yeniden hizalar
slider.destroy();                 // Dinleyicileri temizler
```

---

### 3. Blazor Projelerinde Kullanım (`.razor`)

Blazor projelerinizde hem `@bind-Value` desteği hem de modal desteği hazırdır.

#### A. `_Host.cshtml`, `App.razor` veya `index.html` içine ekleyin:
```html
<link rel="stylesheet" href="pulsar-glass/dist/pulsar-glass.css" />
<script src="pulsar-glass/dist/pulsar-glass.js"></script>
```

#### B. Sayfanızda Bileşeni Kullanın:
```razor
@using PulsarGlass.Blazor

<!-- İki yönlü (@bind-Value) seçim -->
<PulsarGlassSegmented TItem="string"
                      Items="@_filtreler"
                      @bind-Value="_secilenFiltre"
                      Size="PulsarGlassSize.Default"
                      OnChanged="@OnFiltreDegisti" />

<p class="mt-4">Seçili Değer: <strong>@_secilenFiltre</strong></p>

@code {
    private List<string> _filtreler = new() { "Tümü", "Özet Rapor", "Detaylı Analiz" };
    private string _secilenFiltre = "Tümü";

    private void OnFiltreDegisti(string yeniFiltre)
    {
        // Filtre değişiminde tetiklenir
    }
}
```

---

### 4. Modal / Popup İçerisinde Kullanım (Zero-Width Çözümü)

Modallar veya gizli tablar açıldığında elemanların genişliği henüz `0` olabilir. Pulsar Glass bunu otomatik olarak algılayabilmekle birlikte, modal açıldığı anda `.refresh()` çağrıldığında kusursuz konumlanır.

#### Saf JS ile Modal İçinde:
```javascript
function modalAcildiginda() {
  document.getElementById('myModal').classList.add('active');
  
  // Modal görünür olduktan 50ms sonra hizala
  setTimeout(() => {
    slider.refresh();
  }, 50);
}
```

#### Blazor Liquid Glass Modal Bileşeni ile:
```razor
<button class="btn btn-primary" @onclick="() => _modalAcik = true">
    Filtre Modalını Aç
</button>

<PulsarGlassModal @bind-IsOpen="_modalAcik" Title="Görünüm Filtreleme">
    <ChildContent>
        <p class="mb-4">İncelemek istediğiniz görünümü seçin:</p>
        
        <PulsarGlassSegmented TItem="string"
                              Items="@_modlar"
                              @bind-Value="_aktifMod" />
    </ChildContent>
    <FooterContent>
        <button class="btn btn-secondary" @onclick="() => _modalAcik = false">Tamam</button>
    </FooterContent>
</PulsarGlassModal>

@code {
    private bool _modalAcik;
    private List<string> _modlar = new() { "Hızlı Görünüm", "Kapsamlı İnceleme" };
    private string _aktifMod = "Hızlı Görünüm";
}
```

---

### 5. React / Vue / Svelte Kullanımı

Saf JavaScript çekirdeği UMD formatındadır ve tüm modern framework'lerde `useEffect` veya `onMounted` içinde 3 satırda çalışır:

```jsx
// React Örneği
import { useEffect, useRef } from 'react';
import 'pulsar_glass/dist/pulsar-glass.css';
import { PulsarGlass } from 'pulsar_glass/dist/pulsar-glass.js';

function SegmentedTabs({ options, onChange }) {
  const trackRef = useRef(null);

  useEffect(() => {
    const slider = PulsarGlass.create(trackRef.current, {
      onChange: (index, val) => onChange(val)
    });
    return () => slider.destroy();
  }, []);

  return (
    <div className="pg-track" ref={trackRef}>
      <div className="pg-slider"></div>
      {options.map((opt, i) => (
        <button key={opt} className={`pg-btn ${i === 0 ? 'active' : ''}`} data-value={opt}>
          <span className="pg-label">{opt}</span>
        </button>
      ))}
    </div>
  );
}
```

---

### 5. Yapay Zekâ ve Ajanlar ile Otomatik Entegrasyon (SKILL.md)

Paket içerisindeki **`skill/SKILL.md`** dosyası; **Antigravity, Claude Code, Cursor, GitHub Copilot** veya benzeri yapay zekâ asistanlarına doğrudan bir **Ajan Yeteneği (Agent Skill)** olarak tanımlanmak üzere hazırlanmış kapsamlı bir mühendislik kılavuzudur.

#### Nasıl Kullanılır?
- **Antigravity & Ajan Sistemleri:** `skill/SKILL.md` dosyasını projenizin `.agents/skills/pulsar-glass/SKILL.md` konumuna yerleştirin.
- **Cursor & Claude Code:** Kodlama yaparken `@skill/SKILL.md` referansını verin veya sistem kurallarınıza dahil edin.
- **Komut:** Ajanınıza yalnızca *"Mevcut tab bar'ı Pulsar Glass sıvı cam slider'a dönüştür"* demeniz yeterlidir. Yapay zekâ; matematiksel eşmerkezli kenar formülünü ($R_{\text{inner}} = R_{\text{outer}} - P_{\text{padding}}$), Hermite genişlik enterpolasyonunu ve donanım hızlandırmalı optik katmanları projenize otomatik olarak uygulayacaktır.

---

## ⚙️ Yapılandırma Seçenekleri (Configuration Options)

`PulsarGlass.create(selector, options)` çağrısına verilebilecek opsiyonlar:

| Parametre | Tip | Varsayılan | Açıklama |
|---|---|---|---|
| `maxOvershoot` | `number` | `44` | Sınır dışına sürüklendiğinde izin verilen maksimum elastik taşma payı (px) |
| `pullResistance` | `number` | `110` | Sıvı yüzey gerilim katsayısı (değer arttıkça sürüklemek zorlaşır) |
| `flightDurationBase` | `number` | `310` | Tıklama uçuş taban süresi (ms) |
| `flightDurationScale`| `number` | `0.35`| Mesafeye bağlı ek süre çarpanı |
| `flightDurationMin`  | `number` | `340` | Minimum uçuş süresi (ms) |
| `flightDurationMax`  | `number` | `440` | Maksimum uçuş süresi (ms) |
| `enableRefraction`   | `boolean`| `true` | SVG kromatik aberasyon prizma kırılması devrede mi? |
| `enableWaterRefraction`| `boolean`| `true`| Buton etiketlerindeki su altı dalgalanması devrede mi? |
| `onChange`           | `function`| `null`| `(index, value, element) => {}` Seçim değişince tetiklenir |

---

## 🎨 Boyutlar & Tema Özelleştirme

### Boyut Varyantları
- `.pg-sm`: Küçük ve kompakt alanlar için (yükseklik ~28px)
- *(varsayılan)*: Standart menüler ve paneller için (yükseklik ~36px)
- `.pg-lg`: Ana sayfa, karşılama ve vurgulu kontroller için (yükseklik ~46px)

### CSS Değişkenleri ile Kolayca Temalama
```css
/* Markanıza göre renkleri saniyeler içinde değiştirin */
:root {
  --pg-track-bg: rgba(30, 41, 59, 0.6);
  --pg-lens-border: rgba(56, 189, 248, 0.2);
  --pg-btn-active-color: #38bdf8;
  --pg-crest-color-center: rgba(56, 189, 248, 0.8);
}

/* Aydınlık tema desteği */
[data-pg-theme="light"] {
  /* Otomatik optimize edilmiş aydınlık cam değerleri kütüphanede hazırdır */
}
```

---

## ♿ Erişilebilirlik (A11y) & Performans

- **Reduced Motion:** Kullanıcının işletim sisteminde `prefers-reduced-motion: reduce` aktifse, tüm uçuş, esneme ve SVG filtreleri otomatik olarak devre dışı kalır ve anında geçiş yapılır.
- **Hardware Acceleration:** Animasyonlar yalnızca `transform` (GPU composite) üzerinden çalışır; `top`, `left`, `margin` kullanılmaz.
- **Layout Thrashing Koruması:** Buton ölçüleri ilk anda önbelleğe alınır, animasyon anında `getBoundingClientRect` veya `offsetWidth` çağrılmaz.

---

## 📄 Geliştirici & Lisans

Bu kütüphane **Mustafa Tıraş** tarafından geliştirilmiş olup **MIT Lisansı** ile lisanslanmıştır. Ticari ve kişisel projelerinizde dilediğiniz gibi kullanabilir, değiştirebilir ve dağıtabilirsiniz.
