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

    const buttons = Array.from(track.querySelectorAll('.rag-pill-btn, .segment-btn'));
    if (!buttons.length) return;
    track._sliderInitialized = true;

    // Önbellek: Buton geometrisi (Layout Thrashing'i önlemek için bir kez ölçülür)
    let buttonMetrics = [];
    function measureMetrics() {
        buttonMetrics = buttons.map(b => {
            const left = b.offsetLeft;
            const width = b.offsetWidth;
            return {
                btn: b,
                label: b.querySelector('.rag-pill-label') || b.querySelector('span') || b,
                left: left,
                width: width,
                right: left + width,
                center: left + width / 2
            };
        });
    }
    measureMetrics();

    let transitionTimer = null;

    function enableRefract() {
        slider.classList.add('has-refract');
    }

    function disableRefract() {
        slider.classList.remove('has-refract');
        buttonMetrics.forEach(m => {
            if (m.label) {
                m.label.classList.remove('is-refracting');
            }
            m.btn.classList.remove('is-illuminated');
        });
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
        return track.querySelector('.rag-pill-btn.active, .segment-btn.active') || buttons[0];
    }

    // Ultra Pürüzsüz Donanım Hızlandırmalı Geçiş (Zero Jank 120 FPS)
    function moveSliderToButton(btn, animate = true) {
        if (!btn) return;
        measureMetrics();
        const m = buttonMetrics.find(x => x.btn === btn) || {
            left: btn.offsetLeft,
            width: btn.offsetWidth
        };

        const targetLeft = m.left;
        const targetWidth = m.width;

        if (targetWidth === 0) {
            requestAnimationFrame(() => {
                const retryBtn = getActiveButton();
                if (retryBtn) moveSliderToButton(retryBtn, false);
            });
            return;
        }

        const isMovingRight = targetLeft > currentSliderLeft;
        const moveDist = Math.abs(targetLeft - currentSliderLeft);

        if (transitionTimer) {
            clearTimeout(transitionTimer);
            transitionTimer = null;
        }

        if (animate && moveDist > 5) {
            slider.style.transition = 'transform 0.35s cubic-bezier(0.16, 1, 0.3, 1), width 0.35s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.16s ease';
            slider.style.transformOrigin = isMovingRight ? 'left center' : 'right center';

            // Yol üstündeki butonları tespit et: SADECE su kırılması dalgasını aktif et
            enableRefract();
            const minX = Math.min(currentSliderLeft, targetLeft);
            const maxX = Math.max(currentSliderLeft + slider.offsetWidth, targetLeft + targetWidth);

            buttonMetrics.forEach(item => {
                const inPath = item.right >= minX && item.left <= maxX;
                if (inPath && item.label) {
                    item.label.classList.add('is-refracting');
                }
            });

            // Geçiş tamamlandığında pürüzsüzce kapat
            transitionTimer = setTimeout(() => {
                disableRefract();
                slider.style.transformOrigin = 'center center';
                transitionTimer = null;
            }, 350);
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

    // İlk konumlandırma - Durgun halde tamamen pürüzsüz (Multi-Frame Settling)
    const doInitialPosition = () => {
        const activeBtn = getActiveButton();
        if (activeBtn) {
            moveSliderToButton(activeBtn, false);
            disableRefract();
        }
    };
    requestAnimationFrame(doInitialPosition);
    setTimeout(doInitialPosition, 40);
    setTimeout(doInitialPosition, 120);

    let isProgrammaticClick = false;

    // Her butona tıklandığında oraya kaysın
    buttons.forEach((btn) => {
        btn.addEventListener('click', (e) => {
            if (hasDragged && !isProgrammaticClick) {
                e.stopPropagation();
                return;
            }
            buttons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            moveSliderToButton(btn, true);
        });
    });

    // ─── Liquid Glass Sürükleme, Büyüme & Kırılma Fiziği (rAF Throttled) ───
    let rafMoveId = null;
    let pendingEvent = null;

    function onPointerDown(e) {
        if (e.button !== undefined && e.button !== 0) return;

        measureMetrics();
        isDragging = true;
        isPressed = true;
        hasDragged = false;
        startPointerX = e.clientX;
        lastX = e.clientX;
        lastTime = performance.now();
        velocityX = 0;

        if (transitionTimer) {
            clearTimeout(transitionTimer);
            transitionTimer = null;
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
        currentScale = 0.98;
        slider.style.transformOrigin = 'center center';
        slider.style.borderRadius = '10px';
        slider.style.transform = `translateX(${currentSliderLeft}px) scale(${currentScale})`;
    }

    function processDragUpdate() {
        rafMoveId = null;
        if (!isDragging || !pendingEvent) return;

        const e = pendingEvent;
        const now = performance.now();
        const dt = Math.max(1, now - lastTime);
        const dx = e.clientX - lastX;
        velocityX = (dx / dt) * 16;
        lastX = e.clientX;
        lastTime = now;

        const deltaX = e.clientX - startPointerX;
        if (Math.abs(deltaX) > 3) {
            hasDragged = true;
            buttons.forEach(b => b.classList.remove('active'));
        }

        if (!hasDragged) {
            return;
        }

        enableRefract();

        const minLeft = buttonMetrics[0].left;
        const maxLeft = buttonMetrics[buttonMetrics.length - 1].left;

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

        // Hareket yönüne ve hızına bağlı sadece o yöne doğru lateral sıkışma
        const speed = Math.abs(velocityX);
        const squish = Math.min(speed * 0.01, 0.12);
        const scaleX = currentScale * (1 - squish);
        const scaleY = currentScale;

        if (velocityX > 0.4) {
            slider.style.transformOrigin = 'left center';
        } else if (velocityX < -0.4) {
            slider.style.transformOrigin = 'right center';
        } else {
            slider.style.transformOrigin = 'center center';
        }
        slider.style.borderRadius = '10px';
        slider.style.transform = `translateX(${newLeft}px) scale(${scaleX.toFixed(3)}, ${scaleY.toFixed(3)})`;

        // Continuous Smoothstep Width Morphing (Önbellek kullanarak sıfır reflow):
        let targetWidth = buttonMetrics[0].width;
        if (buttonMetrics.length >= 2) {
            for (let i = 0; i < buttonMetrics.length - 1; i++) {
                const bLeft = buttonMetrics[i].left;
                const nextLeft = buttonMetrics[i + 1].left;
                const bWidth = buttonMetrics[i].width;
                const nextWidth = buttonMetrics[i + 1].width;

                if (newLeft <= bLeft) {
                    targetWidth = bWidth;
                    break;
                } else if (newLeft >= nextLeft) {
                    targetWidth = nextWidth;
                } else {
                    const progress = Math.max(0, Math.min(1, (newLeft - bLeft) / (nextLeft - bLeft)));
                    const smoothProgress = progress * progress * (3 - 2 * progress);
                    targetWidth = bWidth + (nextWidth - bWidth) * smoothProgress;
                    break;
                }
            }
        }

        slider.style.width = `${targetWidth.toFixed(1)}px`;

        // Buton altı su kırılması & kaydırma esnasında üzerine gelindiğinde parlama
        const sliderLeft = newLeft;
        const sliderRight = newLeft + targetWidth;
        const sliderCenter = newLeft + (targetWidth / 2);

        // Merceğin altındaki tek butonu tespit et (En yüksek temas / merkez kontrolü)
        let hoveredItem = null;
        let maxOverlap = 0;

        buttonMetrics.forEach(item => {
            const overlap = Math.max(0, Math.min(sliderRight, item.right) - Math.max(sliderLeft, item.left));
            if (overlap > maxOverlap) {
                maxOverlap = overlap;
                hoveredItem = item;
            }

            // Su kırılması: Belli bir temas olduğunda aktif
            if (item.label) {
                if (overlap > 8) {
                    item.label.classList.add('is-refracting');
                } else {
                    item.label.classList.remove('is-refracting');
                }
            }
        });

        // SADECE ve SADECE merceğin tam üstünde olduğu buton açık beyaz olsun, diğerleri mat kalsın
        buttonMetrics.forEach(item => {
            if (item === hoveredItem && maxOverlap > (item.width * 0.35)) {
                item.btn.classList.add('is-illuminated');
            } else {
                item.btn.classList.remove('is-illuminated');
            }
        });
    }

    function onPointerMove(e) {
        if (!isDragging) return;
        pendingEvent = e;
        if (!rafMoveId) {
            rafMoveId = requestAnimationFrame(processDragUpdate);
        }
    }

    function onPointerUp(e) {
        if (!isDragging) return;
        isDragging = false;
        isPressed = false;

        if (rafMoveId) {
            cancelAnimationFrame(rafMoveId);
            rafMoveId = null;
        }

        track.classList.remove('is-dragging');
        slider.classList.remove('is-pressed');
        slider.style.borderRadius = '10px';
        slider.style.transformOrigin = 'center center';

        try {
            track.releasePointerCapture(e.pointerId);
        } catch (err) { }

        if (!hasDragged) {
            slider.style.transition = 'transform 0.28s cubic-bezier(0.175, 0.885, 0.32, 1.12), width 0.28s cubic-bezier(0.175, 0.885, 0.32, 1.12)';
            slider.style.transform = `translateX(${currentSliderLeft}px) scale(1)`;
            setTimeout(() => disableRefract(), 200);
            return;
        }

        // Bırakılan konuma en yakın butonu tespit et (Manyetik Hedef)
        const sliderCenter = currentSliderLeft + (slider.offsetWidth / 2);
        let targetBtn = buttonMetrics[0].btn;
        let minDistance = Infinity;

        buttonMetrics.forEach(item => {
            const dist = Math.abs(sliderCenter - item.center);
            if (dist < minDistance) {
                minDistance = dist;
                targetBtn = item.btn;
            }
        });

        // Tüm geçici parlama sınıflarını anında temizle ve SADECE hedefi aktif yap
        buttons.forEach(b => {
            b.classList.remove('is-illuminated');
            b.classList.remove('active');
        });
        targetBtn.classList.add('active');

        // Organik yay ile hedefe oturt (Spring Back & Snap)
        moveSliderToButton(targetBtn, true);

        // Blazor aktif durumunu güncelle
        if (hasDragged) {
            isProgrammaticClick = true;
            targetBtn.click();
            isProgrammaticClick = false;
        }

        setTimeout(() => {
            hasDragged = false;
        }, 80);
    }

    track.addEventListener('pointerdown', onPointerDown);
    track.addEventListener('pointermove', onPointerMove);
    track.addEventListener('pointerup', onPointerUp);
    track.addEventListener('pointercancel', onPointerUp);

    window.addEventListener('resize', () => {
        measureMetrics();
        const activeBtn = getActiveButton();
        moveSliderToButton(activeBtn, false);
    });
};

window.updateSegmentedSlider = function (trackId, sliderId) {
    const track = document.getElementById(trackId);
    const slider = document.getElementById(sliderId);
    if (!track || !slider) return;
    if (track.classList.contains('is-dragging')) return;

    const activeBtn = track.querySelector('.rag-pill-btn.active, .segment-btn.active');
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


