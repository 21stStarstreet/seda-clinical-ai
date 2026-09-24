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

// ─── RAG Chat: Mesaj Listesini Aşağı Kaydır ──────────────────────────────────
function scrollToBottom(elementId) {
    const el = document.getElementById(elementId);
    if (el) {
        el.scrollTop = el.scrollHeight;
    }
}

// ─── Kılavuz Filtresi: Liquid Glass Sürüklenebilir & Kayan Segmented Slider ───
window.initSegmentedSlider = function (trackId, sliderId) {
    const track = document.getElementById(trackId);
    const slider = document.getElementById(sliderId);
    if (!track || !slider) return;

    if (track._sliderInitialized) {
        window.updateSegmentedSlider(trackId, sliderId);
        return;
    }
    track._sliderInitialized = true;

    const buttons = Array.from(track.querySelectorAll('.rag-pill-btn'));
    if (!buttons.length) return;

    // SVG Cam Prizması: Renk Dağılımı (Lateral Chromatic Aberration) elemanları
    const caRedOffset  = document.getElementById('caRedOffset');
    const caBlueOffset = document.getElementById('caBlueOffset');
    let refractPulseFrame = null;

    // Prizmatik renk dağılımı şiddetini ayarla (dx: kırmızı sola, mavi sağa)
    function setChromaticOffset(dx) {
        const v = Math.max(0, dx);
        if (caRedOffset)  caRedOffset.setAttribute('dx',  (-v).toFixed(2));
        if (caBlueOffset) caBlueOffset.setAttribute('dx',  v.toFixed(2));
    }

    function enableRefract() {
        slider.classList.add('has-refract');
    }

    function disableRefract() {
        slider.classList.remove('has-refract');
        setChromaticOffset(0);
    }

    // Geçişlerde ve bırakıldığında sinüzoidal prizmatik renk pulsu (şekil bozulması olmadan saf renk kırılması)
    function triggerRefractionPulse(peakCA = 3.0, durationMs = 380) {
        if (refractPulseFrame) cancelAnimationFrame(refractPulseFrame);
        enableRefract();
        const startTime = performance.now();

        function tick(now) {
            const elapsed  = now - startTime;
            const progress = Math.min(1, elapsed / durationMs);
            const wave     = Math.sin(progress * Math.PI);  // sinus: 0→1→0
            setChromaticOffset(peakCA * wave);

            if (progress < 1) {
                refractPulseFrame = requestAnimationFrame(tick);
            } else {
                disableRefract();
                refractPulseFrame = null;
            }
        }
        refractPulseFrame = requestAnimationFrame(tick);
    }

    let isDragging = false;
    let hasDragged = false;
    let isPressed = false;
    let startPointerX = 0;
    let startSliderLeft = 0;
    let currentSliderLeft = 0;
    let lastX = 0;
    let lastTime = 0;
    let velocityX = 0;

    let currentScale = 1.0;

    function getActiveButton() {
        return track.querySelector('.rag-pill-btn.active') || buttons[0];
    }

    function updateSpecularPosition(clientX, clientY) {
        const rect = slider.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) return;
        const xPercent = Math.max(0, Math.min(100, ((clientX - rect.left) / rect.width) * 100));
        const yPercent = Math.max(0, Math.min(100, ((clientY - rect.top) / rect.height) * 100));
        slider.style.setProperty('--pointer-x', `${xPercent.toFixed(1)}%`);
        slider.style.setProperty('--pointer-y', `${yPercent.toFixed(1)}%`);
    }

    function moveSliderToButton(btn, animate = true) {
        if (!btn) return;
        const targetLeft = btn.offsetLeft;
        const targetWidth = btn.offsetWidth;
        const isMovingRight = targetLeft > currentSliderLeft;
        const moveDist = Math.abs(targetLeft - currentSliderLeft);

        if (animate) {
            // Eşzamanlı ultra akıcı geçiş: X konumu, genişlik ve saf prizmatik renk kırılması
            slider.style.transition = 'transform 0.42s cubic-bezier(0.16, 1, 0.3, 1), width 0.42s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.2s ease';
            
            if (moveDist > 10) {
                slider.style.transformOrigin = isMovingRight ? 'left center' : 'right center';
                triggerRefractionPulse(3.0, 380);
                setTimeout(() => {
                    slider.style.transformOrigin = 'center center';
                }, 350);
            }
        } else {
            slider.style.transition = 'none';
            slider.style.transformOrigin = 'center center';
            disableRefract();
        }

        slider.style.borderRadius = '10px';
        currentScale = 1.0;
        slider.style.transform = `translateX(${targetLeft}px) scale(1)`;
        slider.style.width = `${targetWidth}px`;
        slider.style.opacity = '1';
        currentSliderLeft = targetLeft;
    }

    track._moveSliderToButton = moveSliderToButton;

    // İlk konumlandırma - Durgun halde tamamen pürüzsüz
    setTimeout(() => {
        const activeBtn = getActiveButton();
        moveSliderToButton(activeBtn, false);
        slider.style.setProperty('--pointer-x', '50%');
        slider.style.setProperty('--pointer-y', '50%');
        disableRefract();
    }, 40);

    // Her butona tıklandığında oraya kaysın
    buttons.forEach((btn) => {
        btn.addEventListener('click', (e) => {
            if (hasDragged) {
                e.stopPropagation();
                return;
            }
            buttons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            moveSliderToButton(btn, true);
        });
    });

    // ─── Hover Işık Takibi (Specular Response) ───────────────────────
    track.addEventListener('pointermove', (e) => {
        if (!isDragging) {
            updateSpecularPosition(e.clientX, e.clientY);
        }
    }, { passive: true });

    track.addEventListener('pointerleave', () => {
        if (!isDragging) {
            slider.style.setProperty('--pointer-x', '50%');
            slider.style.setProperty('--pointer-y', '50%');
        }
    });

    // ─── Liquid Glass Sürükleme, Büyüme & Kırılma Fiziği ──────────────
    function onPointerDown(e) {
        if (e.button !== undefined && e.button !== 0) return;

        isDragging = true;
        isPressed = true;
        hasDragged = false;
        startPointerX = e.clientX;
        lastX = e.clientX;
        lastTime = performance.now();
        velocityX = 0;

        if (refractPulseFrame) {
            cancelAnimationFrame(refractPulseFrame);
            refractPulseFrame = null;
        }

        // Anlık transform pozisyonunu oku
        const matrix = window.getComputedStyle(slider).transform;
        if (matrix && matrix !== 'none') {
            const values = matrix.split('(')[1].split(')')[0].split(',');
            startSliderLeft = parseFloat(values[4]) || 0;
        } else {
            startSliderLeft = slider.offsetLeft;
        }
        currentSliderLeft = startSliderLeft;

        try {
            track.setPointerCapture(e.pointerId);
        } catch (err) { }

        slider.style.transition = 'none';
        track.classList.add('is-dragging');
        slider.classList.add('is-pressed');

        enableRefract();
        // Basılma anında hafif elastik sıkışma
        currentScale = 0.98;
        slider.style.transformOrigin = 'center center';
        slider.style.borderRadius = '10px';
        slider.style.transform = `translateX(${currentSliderLeft}px) scale(${currentScale})`;
        setChromaticOffset(1.5);
        updateSpecularPosition(e.clientX, e.clientY);
    }

    function onPointerMove(e) {
        if (!isDragging) return;

        const now = performance.now();
        const dt = Math.max(1, now - lastTime);
        const dx = e.clientX - lastX;
        velocityX = (dx / dt) * 16;
        lastX = e.clientX;
        lastTime = now;

        const deltaX = e.clientX - startPointerX;
        if (Math.abs(deltaX) > 3) {
            hasDragged = true;
        }

        if (!hasDragged) {
            updateSpecularPosition(e.clientX, e.clientY);
            return;
        }

        enableRefract();

        const minLeft = buttons[0].offsetLeft;
        const lastBtn = buttons[buttons.length - 1];
        const maxLeft = lastBtn.offsetLeft;

        let newLeft = startSliderLeft + deltaX;

        // Uç sınırlarda elastik esneme (rubber-banding)
        if (newLeft < minLeft) {
            newLeft = minLeft + (newLeft - minLeft) * 0.22;
        } else if (newLeft > maxLeft) {
            newLeft = maxLeft + (newLeft - maxLeft) * 0.22;
        }

        currentSliderLeft = newLeft;

        // Sürüklerken butonu akıcı animasyonla büyüt (%16 büyüme)
        currentScale += (1.16 - currentScale) * 0.28;

        // Hareket yönüne ve hızına bağlı sadece o yöne doğru lateral sıkışma (Directional Squish)
        const speed = Math.abs(velocityX);
        const squish = Math.min(speed * 0.012, 0.14);
        const scaleX = currentScale * (1 - squish);
        const scaleY = currentScale;

        // Sadece hareket ettiği yöne doğru sıkışması için transformOrigin (Kenarlar daima pürüzsüz 10px):
        if (velocityX > 0.4) {
            slider.style.transformOrigin = 'left center';
        } else if (velocityX < -0.4) {
            slider.style.transformOrigin = 'right center';
        } else {
            slider.style.transformOrigin = 'center center';
        }
        slider.style.borderRadius = '10px';
        slider.style.transform = `translateX(${newLeft}px) scale(${scaleX.toFixed(3)}, ${scaleY.toFixed(3)})`;

        // Hıza duyarlı saf prizmatik renk kırılması (Chromatic Aberration - Düzensiz şekil bozulması YOK)
        const dynamicCA = Math.min(1.2 + speed * 0.35, 4.0);
        setChromaticOffset(dynamicCA);

        // Continuous Smoothstep Width Morphing:
        // Her iki buton arasındaki genişliği mesafe oranına göre pürüzsüzce enterpole et (Sıfır sert sıçrama!)
        let targetWidth = buttons[0].offsetWidth;
        if (buttons.length >= 2) {
            for (let i = 0; i < buttons.length - 1; i++) {
                const bLeft = buttons[i].offsetLeft;
                const nextLeft = buttons[i + 1].offsetLeft;
                const bWidth = buttons[i].offsetWidth;
                const nextWidth = buttons[i + 1].offsetWidth;

                if (newLeft <= bLeft) {
                    targetWidth = bWidth;
                    break;
                } else if (newLeft >= nextLeft) {
                    targetWidth = nextWidth;
                } else {
                    const progress = Math.max(0, Math.min(1, (newLeft - bLeft) / (nextLeft - bLeft)));
                    // Smoothstep eğrisi (3x^2 - 2x^3) ile ipeksi sıvı cam morflaması
                    const smoothProgress = progress * progress * (3 - 2 * progress);
                    targetWidth = bWidth + (nextWidth - bWidth) * smoothProgress;
                    break;
                }
            }
        }

        slider.style.width = `${targetWidth.toFixed(1)}px`;

        updateSpecularPosition(e.clientX, e.clientY);
    }

    function onPointerUp(e) {
        if (!isDragging) return;
        isDragging = false;
        isPressed = false;

        track.classList.remove('is-dragging');
        slider.classList.remove('is-pressed');
        slider.style.borderRadius = '10px';
        slider.style.transformOrigin = 'center center';

        try {
            track.releasePointerCapture(e.pointerId);
        } catch (err) { }

        if (!hasDragged) {
            // Tıklama olduysa, yay animasyonuyla sıkışmayı serbest bırak
            slider.style.transition = 'transform 0.32s cubic-bezier(0.175, 0.885, 0.32, 1.12), width 0.32s cubic-bezier(0.175, 0.885, 0.32, 1.12)';
            slider.style.transform = `translateX(${currentSliderLeft}px) scale(1)`;
            triggerRefractionPulse(4.0, 2.0, 220);
            return;
        }

        // Bırakılan konuma en yakın butonu tespit et (Manyetik Hedef)
        const sliderCenter = currentSliderLeft + (slider.offsetWidth / 2);
        let targetBtn = buttons[0];
        let minDistance = Infinity;

        buttons.forEach(btn => {
            const btnCenter = btn.offsetLeft + (btn.offsetWidth / 2);
            const dist = Math.abs(sliderCenter - btnCenter);
            if (dist < minDistance) {
                minDistance = dist;
                targetBtn = btn;
            }
        });

        // Organik yay ile hedefe oturt (Spring Back & Snap)
        moveSliderToButton(targetBtn, true);

        // Blazor aktif durumunu güncelle
        const wasActive = targetBtn.classList.contains('active');
        buttons.forEach(b => b.classList.remove('active'));
        targetBtn.classList.add('active');

        if (!wasActive) {
            targetBtn.click();
        }

        setTimeout(() => {
            hasDragged = false;
            slider.style.setProperty('--pointer-x', '50%');
            slider.style.setProperty('--pointer-y', '50%');
        }, 90);
    }

    track.addEventListener('pointerdown', onPointerDown);
    track.addEventListener('pointermove', onPointerMove);
    track.addEventListener('pointerup', onPointerUp);
    track.addEventListener('pointercancel', onPointerUp);

    window.addEventListener('resize', () => {
        const activeBtn = getActiveButton();
        moveSliderToButton(activeBtn, false);
    });
};

window.updateSegmentedSlider = function (trackId, sliderId) {
    const track = document.getElementById(trackId);
    const slider = document.getElementById(sliderId);
    if (!track || !slider) return;

    const activeBtn = track.querySelector('.rag-pill-btn.active');
    if (activeBtn) {
        if (typeof track._moveSliderToButton === 'function') {
            track._moveSliderToButton(activeBtn, true);
        } else {
            const targetLeft = activeBtn.offsetLeft;
            const targetWidth = activeBtn.offsetWidth;
            slider.style.transition = 'transform 0.42s cubic-bezier(0.16, 1, 0.3, 1), width 0.42s cubic-bezier(0.16, 1, 0.3, 1)';
            slider.style.transform = `translateX(${targetLeft}px) scale(1)`;
            slider.style.width = `${targetWidth}px`;
            slider.style.opacity = '1';
        }
    }
};


