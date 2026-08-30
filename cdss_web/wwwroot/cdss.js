/**
 * CDSS — JavaScript Yardımcı Fonksiyonları
 */

// ─── Dosya İndirme ────────────────────────────────────────────────────────────
function downloadFile(fileName, contentType, base64Data) {
    const byteCharacters = atob(base64Data);
    const byteNumbers = new Array(byteCharacters.length);
    for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i);
    }
    const byteArray = new Uint8Array(byteNumbers);
    const blob = new Blob([byteArray], { type: contentType });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}

// ─── Oturum Zaman Aşımı (Session Timeout) ────────────────────────────────────
/**
 * Öğrenme notu:
 * Blazor Server C# tarafı, tarayıcıda ne zaman tıklandığını bilemez.
 * Bu yüzden JS'e "son aktivite zamanını takip et" diyoruz.
 * C# belirli aralıklarla getIdleSeconds() çağırarak kontrol eder.
 */
let _lastActivityTime = Date.now();

// Kullanıcı aktif olduğunda zamanı güncelle
['mousemove', 'keydown', 'click', 'touchstart', 'scroll'].forEach(event => {
    document.addEventListener(event, () => {
        _lastActivityTime = Date.now();
    }, { passive: true });
});

/** Kullanıcının kaç saniyedir boşta olduğunu döndürür. */
function getIdleSeconds() {
    return Math.floor((Date.now() - _lastActivityTime) / 1000);
}

/** Aktivite sayacını manuel sıfırla (giriş yapılınca çağrılır). */
function resetActivity() {
    _lastActivityTime = Date.now();
}

// ─── Akıcı Yükseklik Animasyonu (Smooth Height Transition) ───────────────────
function animateHeightTransition(elementId, durationMs = 500) {
    const el = document.getElementById(elementId);
    if (!el) return;

    // Önceki sabit yüksekliği ölç
    const prevHeight = el.offsetHeight;

    // Yüksekliği geçici olarak serbest bırakıp yeni yüksekliği ölç
    el.style.transition = 'none';
    el.style.height = 'auto';
    const newHeight = el.offsetHeight;

    // Değişim yoksa çık
    if (Math.abs(prevHeight - newHeight) < 2) {
        el.style.height = '';
        return;
    }

    // Başlangıç yüksekliğine sabitle
    el.style.height = prevHeight + 'px';
    el.offsetHeight; // Reflow zorla

    // Yumuşak geçişi başlat
    el.style.transition = `height ${durationMs}ms cubic-bezier(0.25, 1, 0.5, 1)`;
    el.style.height = newHeight + 'px';

    setTimeout(() => {
        el.style.transition = '';
        el.style.height = '';
    }, durationMs);
}
