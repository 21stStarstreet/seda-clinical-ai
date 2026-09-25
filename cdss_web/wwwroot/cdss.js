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

    let rafFlightId = null;

    // ─── Tıklama Uçuş Fiziği: Sürükleme Animasyonuyla Hedef Butona Akıcı Geçiş ───
    function animateSliderFlight(targetBtn, onComplete) {
        if (!targetBtn) return;
        measureMetrics();

        const m = buttonMetrics.find(x => x.btn === targetBtn) || {
            left: targetBtn.offsetLeft,
            width: targetBtn.offsetWidth
        };

        const opticalBleed = 2;
        const targetLeft = m.left - opticalBleed;
        const targetWidth = m.width + (opticalBleed * 2);

        if (targetWidth <= 0 || m.width === 0) {
            requestAnimationFrame(() => {
                const retryBtn = getActiveButton();
                if (retryBtn) moveSliderToButton(retryBtn, false);
            });
            return;
        }

        // Anlık pozisyon ve genişliği oku (hareket halindeyken tıklandıysa oradan başlasın)
        let startLeft = currentSliderLeft;
        let startWidth = slider.offsetWidth || targetWidth;

        const matrix = window.getComputedStyle(slider).transform;
        if (matrix && matrix !== 'none') {
            const values = matrix.split('(')[1].split(')')[0].split(',');
            const curX = parseFloat(values[4]);
            if (!isNaN(curX)) {
                startLeft = curX;
            }
        }

        const distance = targetLeft - startLeft;
        if (Math.abs(distance) < 0.5 && Math.abs(targetWidth - startWidth) < 0.5) {
            slider.style.transform = `translateX(${targetLeft.toFixed(1)}px) scale(1) skewX(0deg)`;
            slider.style.width = `${targetWidth.toFixed(1)}px`;
            if (typeof onComplete === 'function') onComplete();
            return;
        }

        if (rafFlightId) {
            cancelAnimationFrame(rafFlightId);
            rafFlightId = null;
        }
        if (transitionTimer) {
            clearTimeout(transitionTimer);
            transitionTimer = null;
        }

        track._isAnimating = true;
        slider.style.transition = 'none';
        track.classList.add('is-dragging');
        slider.classList.add('is-pressed');
        enableRefract();

        const dir = distance >= 0 ? 1 : -1;
        const distAbs = Math.abs(distance);
        // Dinamik uçuş süresi (mesafeye göre 340ms - 440ms arası)
        const duration = Math.min(440, Math.max(340, 310 + distAbs * 0.35));
        const startTime = performance.now();

        function step(now) {
            const elapsed = now - startTime;
            const p = Math.min(1, elapsed / duration);

            // Apple Quintic Ease-Out ile liftoff & magnetic cushion
            const ease = 1 - Math.pow(1 - p, 3.6) * (1 - p * 0.15);

            const curX = startLeft + distance * ease;
            const curW = startWidth + (targetWidth - startWidth) * ease;
            currentSliderLeft = curX;

            // Sürükleme benzeri 3D sıvı kabarcık genleşmesi (Mid-flight %16 büyüme)
            const arc = Math.sin(p * Math.PI);
            const scale = 1.0 + (arc * 0.16);

            // Hıza ve yöne bağlı lateral uzama ve basılma (Squish & Stretch)
            const stretch = 1.0 + (arc * 0.10);
            const squash = 1.0 / stretch;
            const scaleX = scale * stretch;
            const scaleY = scale * squash;

            // Uçuş yönüne doğru dinamik 3D eğilme (Tilt)
            const skewDeg = -dir * arc * 2.8;

            slider.style.transformOrigin = 'center center';
            slider.style.borderRadius = '11px';
            slider.style.transform = `translateX(${curX.toFixed(1)}px) scale(${scaleX.toFixed(3)}, ${scaleY.toFixed(3)}) skewX(${skewDeg.toFixed(2)}deg)`;
            slider.style.width = `${curW.toFixed(1)}px`;

            // Yol üstündeki butonları tespit et: Su kırılması ve anlık parıldama
            const sLeft = curX;
            const sRight = curX + curW;

            let hoveredItem = null;
            let maxOverlap = 0;

            buttonMetrics.forEach(item => {
                const overlap = Math.max(0, Math.min(sRight, item.right) - Math.max(sLeft, item.left));
                if (overlap > maxOverlap) {
                    maxOverlap = overlap;
                    hoveredItem = item;
                }

                if (item.label) {
                    if (overlap > 8) {
                        item.label.classList.add('is-refracting');
                    } else if (item.btn !== targetBtn) {
                        item.label.classList.remove('is-refracting');
                    }
                }
            });

            // Merceğin altından geçen buton anlık açık beyaz parıldasın
            buttonMetrics.forEach(item => {
                if (item === hoveredItem && maxOverlap > (item.width * 0.35)) {
                    item.btn.classList.add('is-illuminated');
                } else if (item.btn !== targetBtn) {
                    item.btn.classList.remove('is-illuminated');
                }
            });

            if (p < 1) {
                rafFlightId = requestAnimationFrame(step);
            } else {
                rafFlightId = null;
                // Uçuş tamamlandı: Hedefe pürüzsüzce otur ve yay animasyonuyla sakinleş
                const springTransition = 'transform 0.44s cubic-bezier(0.19, 1.35, 0.32, 1), width 0.44s cubic-bezier(0.19, 1.35, 0.32, 1), opacity 0.20s ease, box-shadow 0.44s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.44s ease';
                slider.style.transition = springTransition;
                slider.classList.add('is-releasing');
                slider.classList.remove('is-pressed');
                track.classList.remove('is-dragging');

                slider.style.transform = `translateX(${targetLeft.toFixed(1)}px) scale(1) skewX(0deg)`;
                slider.style.width = `${targetWidth.toFixed(1)}px`;
                currentSliderLeft = targetLeft;

                // Hedef butonu aktif yap, diğerlerinin geçici sınıflarını temizle
                buttons.forEach(b => {
                    b.classList.remove('is-illuminated');
                    b.classList.remove('active');
                });
                targetBtn.classList.add('active');

                transitionTimer = setTimeout(() => {
                    slider.classList.remove('is-releasing');
                    disableRefract();
                    track._isAnimating = false;
                    transitionTimer = null;
                }, 380);

                if (typeof onComplete === 'function') {
                    onComplete();
                }
            }
        }

        rafFlightId = requestAnimationFrame(step);
    }

    // Ultra Pürüzsüz Donanım Hızlandırmalı Geçiş (Zero Jank 120 FPS)
    function moveSliderToButton(btn, animate = true) {
        if (!btn) return;
        if (animate) {
            animateSliderFlight(btn);
        } else {
            if (rafFlightId) {
                cancelAnimationFrame(rafFlightId);
                rafFlightId = null;
            }
            if (transitionTimer) {
                clearTimeout(transitionTimer);
                transitionTimer = null;
            }
            measureMetrics();
            const m = buttonMetrics.find(x => x.btn === btn) || {
                left: btn.offsetLeft,
                width: btn.offsetWidth
            };

            const opticalBleed = 2;
            const targetLeft = m.left - opticalBleed;
            const targetWidth = m.width + (opticalBleed * 2);

            slider.style.transition = 'none';
            slider.style.transformOrigin = 'center center';
            slider.classList.remove('is-releasing');
            slider.classList.remove('is-overshooting');
            slider.classList.remove('is-pressed');
            track.classList.remove('is-dragging');
            disableRefract();

            slider.style.borderRadius = '11px';
            currentScale = 1.0;
            slider.style.transform = `translateX(${targetLeft.toFixed(1)}px) scale(1) skewX(0deg)`;
            slider.style.width = `${targetWidth.toFixed(1)}px`;
            slider.style.opacity = '1';
            currentSliderLeft = targetLeft;
        }
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
    let lastHandledTime = 0;
    let lastHandledBtn = null;
    let pointerDownBtn = null;
    let pointerCapturedId = null;

    function handleButtonClick(btn, triggerBlazor = true) {
        if (!btn) return;

        const currentActive = getActiveButton();

        // Zaten aktif olan butona tıklandıysa:
        if (btn === currentActive && !hasDragged) {
            // Zarif mikroskobik dokunsal geri tepme (tactile micro-rebound)
            slider.style.transition = 'transform 0.12s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.12s ease';
            slider.style.transform = `translateX(${currentSliderLeft.toFixed(1)}px) scale(0.96)`;
            setTimeout(() => {
                slider.style.transition = 'transform 0.36s cubic-bezier(0.19, 1.35, 0.32, 1), box-shadow 0.36s ease';
                slider.style.transform = `translateX(${currentSliderLeft.toFixed(1)}px) scale(1)`;
            }, 100);
            return;
        }

        const now = performance.now();
        if (now - lastHandledTime < 150 && lastHandledBtn === btn) {
            return;
        }
        lastHandledTime = now;
        lastHandledBtn = btn;

        // Sıvı cam merceği tam sürükleme uçuş fiziğiyle hedef butona kaydır!
        moveSliderToButton(btn, true);

        // Blazor C# olayını tetikle (@onclick)
        if (triggerBlazor) {
            isProgrammaticClick = true;
            try {
                btn.click();
            } catch (err) { }
            isProgrammaticClick = false;
        }
    }

    // Her butona tıklandığında (klavye, erişilebilirlik veya standart tıklama)
    buttons.forEach((btn) => {
        btn.addEventListener('click', (e) => {
            if (hasDragged && !isProgrammaticClick) {
                e.stopPropagation();
                return;
            }
            if (isProgrammaticClick) {
                return;
            }
            handleButtonClick(btn, false);
        });
    });

    // ─── Liquid Glass Sürükleme, Büyüme & Kırılma Fiziği (rAF Throttled) ───
    let rafMoveId = null;
    let pendingEvent = null;

    function onPointerDown(e) {
        if (e.button !== undefined && e.button !== 0) return;

        measureMetrics();
        isPressed = true;
        isDragging = false;
        hasDragged = false;
        startPointerX = e.clientX;
        startPointerY = e.clientY;
        lastX = e.clientX;
        lastTime = performance.now();
        velocityX = 0;

        pointerDownBtn = e.target.closest('.rag-pill-btn, .segment-btn');

        if (rafFlightId) {
            cancelAnimationFrame(rafFlightId);
            rafFlightId = null;
        }
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

        const opticalBleed = 2;
        const minLeft = buttonMetrics[0].left - opticalBleed;
        const maxLeft = buttonMetrics[buttonMetrics.length - 1].left - opticalBleed;

        let rawLeft = startSliderLeft + deltaX;
        let newLeft = rawLeft;
        let overshoot = 0;
        const maxOvershoot = 44; // Buton kapsamlarının dışına taşma kapasitesi (px)
        const pullResistance = 110; // Doğal sıvı gerilim direnci

        // Buton sınırlarının dışına çıkıldığında fiziksel sıvı gerilimi (Nonlinear Rubber-Banding)
        if (rawLeft < minLeft) {
            const pullDist = minLeft - rawLeft;
            overshoot = -maxOvershoot * (1 - Math.exp(-pullDist / pullResistance));
            newLeft = minLeft + overshoot;
        } else if (rawLeft > maxLeft) {
            const pullDist = rawLeft - maxLeft;
            overshoot = maxOvershoot * (1 - Math.exp(-pullDist / pullResistance));
            newLeft = maxLeft + overshoot;
        }

        currentSliderLeft = newLeft;

        // Sürüklerken butonu akıcı animasyonla büyüt (%16 büyüme)
        currentScale += (1.16 - currentScale) * 0.28;

        // Hareket yönüne ve hızına bağlı lateral sıkışma
        const speed = Math.abs(velocityX);
        const squish = Math.min(speed * 0.01, 0.12);

        // Sınır aşımı (Overshoot) esnasında yüzey gerilimi deformasyonu:
        const tensionRatio = Math.min(1, Math.abs(overshoot) / maxOvershoot);
        if (tensionRatio > 0.05) {
            slider.classList.add('is-overshooting');
        } else {
            slider.classList.remove('is-overshooting');
        }

        // Çekilme yönünde uzama (stretch) ve hacim koruma (squash):
        const stretchX = 1 + (tensionRatio * 0.20);
        const squashY = 1 - (tensionRatio * 0.10);
        const scaleX = currentScale * (1 - squish) * stretchX;
        const scaleY = currentScale * squashY;

        // Gerilme yönüne doğru dinamik 3D eğilme (tilt):
        const skewDeg = (overshoot > 0 ? -1 : 1) * tensionRatio * 3.5;

        slider.style.transformOrigin = 'center center';
        slider.style.borderRadius = '11px';
        slider.style.transform = `translateX(${newLeft.toFixed(1)}px) scale(${scaleX.toFixed(3)}, ${scaleY.toFixed(3)}) skewX(${skewDeg.toFixed(2)}deg)`;

        // Continuous Smoothstep Width Morphing (Önbellek kullanarak sıfır reflow):
        let targetWidth = buttonMetrics[0].width + (opticalBleed * 2);
        if (buttonMetrics.length >= 2) {
            for (let i = 0; i < buttonMetrics.length - 1; i++) {
                const bLeft = buttonMetrics[i].left - opticalBleed;
                const nextLeft = buttonMetrics[i + 1].left - opticalBleed;
                const bWidth = buttonMetrics[i].width + (opticalBleed * 2);
                const nextWidth = buttonMetrics[i + 1].width + (opticalBleed * 2);

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
        if (!isPressed) return;

        const deltaX = e.clientX - startPointerX;

        // Kullanıcı henüz sürüklemediyse, sürükleme eşiğini (threshold: 4px) kontrol et
        if (!hasDragged && Math.abs(deltaX) > 4) {
            hasDragged = true;
            isDragging = true;

            // Sürükleme başladığı anda pointer capture al
            try {
                track.setPointerCapture(e.pointerId);
                pointerCapturedId = e.pointerId;
            } catch (err) { }

            slider.style.transition = 'none';
            track.classList.add('is-dragging');
            slider.classList.add('is-pressed');
            enableRefract();
            buttons.forEach(b => b.classList.remove('active'));
        }

        if (isDragging) {
            pendingEvent = e;
            if (!rafMoveId) {
                rafMoveId = requestAnimationFrame(processDragUpdate);
            }
        }
    }

    function onPointerUp(e) {
        if (!isPressed && !isDragging) return;

        const wasDragging = isDragging || hasDragged;
        isPressed = false;
        isDragging = false;

        if (rafMoveId) {
            cancelAnimationFrame(rafMoveId);
            rafMoveId = null;
        }

        if (pointerCapturedId !== null) {
            try {
                track.releasePointerCapture(pointerCapturedId);
            } catch (err) { }
            pointerCapturedId = null;
        }

        // ─── SENARYO A: BUTONA BASILMA (CLICK / TAP) ───
        if (!wasDragging) {
            let clickedBtn = e.target.closest('.rag-pill-btn, .segment-btn') || pointerDownBtn;
            if (!clickedBtn) {
                // Eğer track kenar boşluğuna tıklandıysa, tıklanan X koordinatına en yakın butona git
                let minD = Infinity;
                buttonMetrics.forEach(item => {
                    const d = Math.abs(e.clientX - item.btn.getBoundingClientRect().left - (item.width / 2));
                    if (d < minD) {
                        minD = d;
                        clickedBtn = item.btn;
                    }
                });
            }

            if (clickedBtn) {
                handleButtonClick(clickedBtn, true);
            }
            return;
        }

        // ─── SENARYO B: SÜRÜKLEME SONRASI BIRAKILMA (DRAG RELEASE) ───
        const springTransition = 'transform 0.48s cubic-bezier(0.19, 1.35, 0.32, 1), width 0.48s cubic-bezier(0.19, 1.35, 0.32, 1), opacity 0.20s ease, box-shadow 0.48s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.48s ease';
        slider.style.transition = springTransition;
        slider.classList.add('is-releasing');
        slider.style.borderRadius = '11px';
        slider.style.transformOrigin = 'center center';

        track.classList.remove('is-dragging');
        slider.classList.remove('is-pressed');
        slider.classList.remove('is-overshooting');

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

        handleButtonClick(targetBtn, true);

        setTimeout(() => {
            hasDragged = false;
        }, 120);
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
    if (track._isAnimating) return;

    const activeBtn = track.querySelector('.rag-pill-btn.active, .segment-btn.active');
    if (activeBtn) {
        if (typeof track._moveSliderToButton === 'function') {
            track._moveSliderToButton(activeBtn, true);
        } else {
            const opticalBleed = 2;
            const targetLeft = activeBtn.offsetLeft - opticalBleed;
            const targetWidth = activeBtn.offsetWidth + (opticalBleed * 2);
            slider.style.transition = 'transform 0.48s cubic-bezier(0.19, 1.35, 0.32, 1), width 0.48s cubic-bezier(0.19, 1.35, 0.32, 1), opacity 0.20s ease, box-shadow 0.48s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.48s ease';
            slider.style.transform = `translateX(${targetLeft.toFixed(1)}px) scale(1) skewX(0deg)`;
            slider.style.width = `${targetWidth.toFixed(1)}px`;
            slider.style.opacity = '1';
        }
    }
};


