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

// ─── Panoya Kopyalama (Clipboard Copy) ───────────────────────────────────────
async function copyToClipboard(text) {
    if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
        return true;
    } else {
        // Fallback for non-https/older browsers
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.left = '-999999px';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        try {
            document.execCommand('copy');
            textArea.remove();
            return true;
        } catch (error) {
            textArea.remove();
            return false;
        }
    }
}

// ─── Tema Yönetimi (Light / Dark Theme) ──────────────────────────────────────
window.getSavedTheme = function () {
    return localStorage.getItem('seda_theme') || 'dark';
};

window.setTheme = function (theme) {
    if (theme !== 'light' && theme !== 'dark') theme = 'dark';
    document.documentElement.setAttribute('data-theme', theme);
    if (document.body) {
        document.body.setAttribute('data-theme', theme);
    }
    localStorage.setItem('seda_theme', theme);
    return theme;
};

window.toggleTheme = function () {
    const current = document.documentElement.getAttribute('data-theme') || window.getSavedTheme();
    const next = current === 'light' ? 'dark' : 'light';
    window.setTheme(next);
    return next;
};

// Sayfa ilk yüklendiğinde beyaz/koyu flaş patlamasını önlemek için anında uygula
(function () {
    try {
        const saved = localStorage.getItem('seda_theme') || 'dark';
        document.documentElement.setAttribute('data-theme', saved);
        if (document.body) {
            document.body.setAttribute('data-theme', saved);
        }
    } catch (e) { }
})();

