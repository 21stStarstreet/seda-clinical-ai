---
name: pulsar-glass
description: Authoritative guide and engineering blueprint to transform any tab bar, segmented control, radio group, or button switch into an ultra-premium, 120 FPS Apple-grade Liquid Glass Segmented Slider (Pulsar Glass) across Vanilla JS, Blazor, React, and Vue.
---

# Pulsar Glass: Liquid Segmented Slider Architecture & Engineering Blueprint

This skill is the authoritative, comprehensive technical manual for building and refactoring user interface selection components into the **Pulsar Glass Liquid Segmented Slider** (developed by Mustafa Tıraş).

Whenever a user requests to:
- Convert existing buttons, radio groups, tab bars, or option toggles into a "liquid glass slider", "apple glass slider", or "pulsar glass",
- Integrate an interactive sliding glass pill with realistic optical refraction and rubber-band physics,
- Debug or enhance an existing segmented control with 120 FPS hardware acceleration,

follow this blueprint rigorously.

---

## 1. Design Philosophy & Optical Physics

Unlike generic CSS sliders that rely on naive linear transitions (`transition: left 0.3s ease`), Pulsar Glass simulates a physical **6-layer optical crown glass lens** hovering above a translucent bezel.

### The Six Optical Glass Layers
1. **Bezel / Tray (`.pg-track`)**: High-translucency glass substrate with heavy backdrop blur (`blur(20px)`), an inner inset shadow for physical depth, and subtle noise/chromatic isolation.
2. **Glass Core (`.pg-lens-bg`)**: Dual-angled linear gradient combined with semi-opaque frosted crystal reflection (`rgba(255, 255, 255, 0.08)` to `rgba(255, 255, 255, 0.03)` in dark mode; `0.92` to `0.75` white in light mode).
3. **Internal Prism Shadows (`.pg-lens-shadow`)**: Four-direction multi-layer inset box-shadow simulating cyan-blue ($480\text{nm}$) and amber-orange ($590\text{nm}$) chromatic dispersion along the interior bevels.
4. **Elevation Caustics**: Subtle diffuse ambient shadow (`0 8px 20px rgba(0, 0, 0, 0.45)`) that expands dynamically when the user presses or drags the slider.
5. **Fixed Specular Crest (`::before`)**: A radial gradient ellipse pinned to the upper $15\%$ of the lens simulating overhead studio lighting, independent of cursor position.
6. **Ultra-Fine Bevel Flare (`::after`)**: A $0.5\text{px}$ horizontal gradient hairline spanning the top perimeter ($8\%$ to $92\%$) representing micro-surface refraction on precision-machined sapphire crystal.

---

## 2. Mathematical Specifications & Physics Engine

All motion in Pulsar Glass is governed by explicit physical and geometric formulas. Never substitute these with generic easing.

```
       Track (Outer Bezel): R_outer
  ┌────────────────────────────────────────────────────────┐
  │  Padding (P)                                           │
  │   ┌──────────────────────┐                             │
  │   │  Slider Lens         │  R_inner = R_outer - P      │
  │   │  (Active Button)     │                             │
  │   └──────────────────────┘                             │
  └────────────────────────────────────────────────────────┘
```

### 2.1. Concentric Geometry Formula
To achieve mathematical perfection across all screen resolutions without optical distortion, the inner slider border radius must be strictly concentric with the outer track:
$$R_{\text{inner}} = R_{\text{outer}} - P_{\text{padding}}$$

#### Standard Concentric Dimension Presets
| Preset | Track Height | Padding ($P$) | Outer Radius ($R_{\text{outer}}$) | Inner Radius ($R_{\text{inner}}$) | Button Padding | Font Size |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Small (`.pg-sm`)** | $\sim 28\text{px}$ | $2.5\text{px}$ | $10.0\text{px}$ | $7.5\text{px}$ | $4\text{px } 14\text{px}$ | $11.5\text{px}$ |
| **Standard (Default)**| $\sim 36\text{px}$ | $3.0\text{px}$ | $12.0\text{px}$ | $9.0\text{px}$ | $6\text{px } 16\text{px}$ | $12.5\text{px}$ |
| **Large (`.pg-lg`)** | $\sim 46\text{px}$ | $4.5\text{px}$ | $16.0\text{px}$ | $11.5\text{px}$ | $9\text{px } 24\text{px}$ | $14.0\text{px}$ |

### 2.2. Apple Quintic Ease-Out Flight Curve
Used for click/tap flight across segments. It mimics natural deceleration with negligible bounce:
$$f(p) = 1 - (1 - p)^{3.6} \cdot (1 - 0.15p) \quad \text{where } p \in [0, 1]$$

JavaScript implementation:
```javascript
function appleEase(t) {
  var inv = 1 - t;
  return 1 - Math.pow(inv, 3.6) * (1 - 0.15 * t);
}
```

### 2.3. Dynamic Flight Duration
Short hops between adjacent tabs must feel instantaneous; long multi-segment jumps require aerodynamic flight time:
$$T_{\text{flight}} = \text{clamp}\left(T_{\text{min}}, \, T_{\text{base}} + |\Delta x| \cdot S_{\text{scale}}, \, T_{\text{max}}\right)$$
* Recommended constants: $T_{\text{min}} = 340\text{ ms}$, $T_{\text{base}} = 310\text{ ms}$, $S_{\text{scale}} = 0.35$, $T_{\text{max}} = 440\text{ ms}$.

### 2.4. Mid-Flight Volumetric Arc & Aerodynamic Skew
During flight, the glass lens expands slightly (as if lifting off the surface) and leans forward in the direction of motion:
- **Apex Expansion**:
  $$\text{Arc}(p) = \sin(p \cdot \pi)$$
  $$\text{Scale}(p) = 1 + \text{Arc}(p) \cdot 0.16$$
- **Aerodynamic Skew**:
  $$\theta_{\text{skew}} = -\text{dir} \cdot \text{Arc}(p) \cdot 2.8^\circ \quad \text{where } \text{dir} \in \{-1, +1\}$$

### 2.5. Hermite Smoothstep Width Morphing
When buttons have different label lengths, the slider width must smoothly morph as the pill travels between Button 1 ($W_1$) and Button 2 ($W_2$):
$$\mu = \frac{x - x_1}{x_2 - x_1}, \quad S(\mu) = \mu^2 (3 - 2\mu)$$
$$W(x) = W_1 + (W_2 - W_1) \cdot S(\mu)$$

### 2.6. Nonlinear Rubber-Band Overdrag Resistance
When dragging past the track boundaries, apply exponential resistance to simulate physical surface tension:
$$O(d) = M \cdot \left(1 - e^{-d / R}\right)$$
* $d$: raw drag distance past boundary ($px$)
* $M$: maximum overshoot limit (default: $44\text{px}$)
* $R$: pull resistance coefficient (default: $110\text{px}$)

### 2.7. Magnetic Spring Release
When the user releases a drag, do **not** restart a flight from origin. Snap directly from the release position to the target button using an Apple release spring:
```css
transition: transform 0.38s cubic-bezier(0.19, 1.35, 0.32, 1),
            width 0.38s cubic-bezier(0.19, 1.35, 0.32, 1);
```

---

## 3. Optical SVG Filter Pipeline

Pulsar Glass injects two zero-cost SVG filter rigs into the DOM:

```html
<svg id="pulsar-glass-svg-filters" style="position:absolute;width:0;height:0;overflow:hidden;pointer-events:none;" aria-hidden="true">
  <defs>
    <!-- Filter 1: Chromatic aberration along slider edges during movement -->
    <filter id="pulsar-glass-refract" x="-20%" y="-20%" width="140%" height="140%">
      <feTurbulence type="fractalNoise" baseFrequency="0.04 0.04" numOctaves="1" result="noise" />
      <feDisplacementMap in="SourceGraphic" in2="noise" scale="3.2" xChannelSelector="R" yChannelSelector="G" result="displaced" />
      <feColorMatrix in="displaced" type="matrix" values="
        1.04 0    0    0 0
        0    1.00 0    0 0
        0    0    1.08 0 0
        0    0    0    1 0" result="prism" />
      <feBlend in="SourceGraphic" in2="prism" mode="screen" />
    </filter>

    <!-- Filter 2: Underwater optical text displacement for labels under lens -->
    <filter id="pulsar-glass-water" x="-10%" y="-10%" width="120%" height="120%">
      <feTurbulence type="turbulence" baseFrequency="0.06 0.06" numOctaves="2" result="waterNoise" />
      <feDisplacementMap in="SourceGraphic" in2="waterNoise" scale="2.2" xChannelSelector="R" yChannelSelector="B" />
    </filter>
  </defs>
</svg>
```

---

## 4. Critical Engineering Rules & Bug Prevention (Gotchas)

> [!CAUTION]
> The following 7 edge cases account for 99% of slider malfunctions in real-world apps. Every AI agent implementing this pattern must follow these rules strictly.

### Rule 1: The `matrix3d` GPU Acceleration Bug
* **The Trap:** On WebKit/Safari, macOS, and Chromium with GPU compositing (`will-change: transform`), `window.getComputedStyle(slider).transform` returns `matrix3d(...)` instead of `matrix(...)`. A naive regex `tr.match(/matrix\(([^)]+)\)/)` returns `null`, resetting `translateX` to `0` and causing dragged sliders to wildly snap back to the first button.
* **The Mandatory Fix:** Always use `DOMMatrix` or `WebKitCSSMatrix` with comprehensive fallback:
```javascript
function getTranslateX(el) {
  if (!el) return 0;
  var st = window.getComputedStyle(el);
  var tr = st.transform || st.webkitTransform || 'none';
  if (!tr || tr === 'none') return 0;
  if (typeof DOMMatrix !== 'undefined' || typeof WebKitCSSMatrix !== 'undefined') {
    try {
      var MatrixClass = window.DOMMatrix || window.WebKitCSSMatrix;
      var mat = new MatrixClass(tr);
      return mat.m41 || 0;
    } catch (_) {}
  }
  var m3d = tr.match(/matrix3d\(([^)]+)\)/);
  if (m3d) return parseFloat(m3d[1].split(',')[12]) || 0;
  var m = tr.match(/matrix\(([^)]+)\)/);
  if (m) return parseFloat(m[1].split(',')[4]) || 0;
  return 0;
}
```

### Rule 2: Pointer Event Bubbling & Pointer Capture
* **The Trap:** `.pg-slider` has `pointer-events: none; z-index: 1;` so that clicks pass through to `.pg-btn` (`z-index: 2;`). If you attach `pointerdown` to both `slider` and `track`, events bubble and handlers run twice, duplicating document move/up listeners and causing pointer jitter.
* **The Mandatory Fix:** Attach `pointerdown` **only** to `.pg-track`. Call `this.track.setPointerCapture(e.pointerId)` on drag threshold crossing ($4\text{px}$).

### Rule 3: Zero-Latency (`onSelect`) vs Settled (`onChange`)
* **The Trap:** If you only trigger UI changes on `onChange` (after the 440ms flight or spring completes), tab panels or forms feel noticeably laggy.
* **The Mandatory Fix:**
  - `onSelect(index, value, btn)`: Fires **immediately** ($0\text{ ms}$) on tap or pointer release. Updates active tabs, panels, and bindings instantly.
  - `onChange(index, value, btn)`: Fires **after** motion settles ($380\text{ ms}$). Use for server persistence or analytics.

### Rule 4: Robust Dataset Value Fallback
* **The Trap:** In modern browsers, `btn.dataset` is an empty object `{}` even if `data-value` is missing. Writing `btn.dataset ? btn.dataset.value : ...` yields `undefined`.
* **The Mandatory Fix:**
```javascript
var value = (btn.dataset && btn.dataset.value !== undefined)
  ? btn.dataset.value
  : (btn.getAttribute('data-value') !== null ? btn.getAttribute('data-value') : idx);
```

### Rule 5: Zero Reflow Performance
* **The Trap:** Reading `btn.offsetWidth` or `getBoundingClientRect()` inside `requestAnimationFrame` forces synchronous layout thrashing (dropping frames from 120 FPS to 30 FPS).
* **The Mandatory Fix:** Cache `{btn, label, left, width, right, center}` in `_metrics` array during init and resize. In drag and flight frames, read **only** from this cache. Only mutate `transform` and `width`.

### Rule 6: Subpixel Accuracy in Dynamic Modals & Drawers
* **The Trap:** Initializing the slider inside a hidden container (`display: none` modal, drawer, or tab) results in `0px` cached coordinates.
* **The Mandatory Fix:** Use `ResizeObserver` on `.pg-track` and trigger multi-frame settling upon reveal:
```javascript
function settle() {
  self._measureMetrics();
  var active = self._getActiveButton();
  if (active) self._moveSliderToButton(active, false);
}
requestAnimationFrame(settle);
setTimeout(settle, 40);
setTimeout(settle, 120);
setTimeout(settle, 300);
```

### Rule 7: CSS Flexbox Shrinkage Prevention
* Buttons inside `.pg-track` must have:
```css
.pg-btn {
  flex: 1 1 0;
  min-width: 0;
  white-space: nowrap;
  touch-action: none;
  user-select: none;
  -webkit-user-select: none;
}
```

---

## 5. Universal Refactoring & Migration Workflow

When an agent is tasked with upgrading an existing UI component:

```
[Existing Component]  ───▶  [1. Audit & Map]  ───▶  [2. Generate DOM]  ───▶  [3. Bind State]
(Radio/Tab/Button)           Extract values,         Inject .pg-track,       Wire onSelect
                             active index,           .pg-slider, .pg-btn     to existing
                             event handlers          & CSS variables         event handler
```

### Step-by-Step Refactor Checklist
1. **Identify the Source Group:**
   - Detect all selectable options (labels, IDs, `data-value`, active indices).
   - Note the existing change event (e.g. `@bind`, `onChange`, `v-model`, `onclick`).
2. **Construct the Concentric Track HTML:**
   - Container gets `class="pg-track"` (or `pg-sm` / `pg-lg`).
   - First child must be `<div class="pg-slider"></div>`.
   - Each option becomes `<button type="button" class="pg-btn" data-value="...">`.
   - Option text/icon is wrapped inside `<span class="pg-label">`.
3. **Inject CSS & SVG Filters:**
   - Ensure `pulsar-glass.css` (or equivalent Tailwind / scoped styles) is loaded.
   - Ensure `#pulsar-glass-svg-filters` is present in DOM once.
4. **Wire Event Handlers:**
   - Connect the existing state dispatcher directly to `onSelect`.

---

## 6. Framework-Native Implementations

### 6.1. Blazor (.NET 8/9 / Razor Component)

File: `PulsarGlassSlider.razor`
```razor
@inject IJSRuntime JSRuntime
@implements IAsyncDisposable

<div class="pg-track @CssClass" @ref="_trackElement" id="@Id">
    <div class="pg-slider"></div>
    @for (int i = 0; i < Options.Count; i++)
    {
        var opt = Options[i];
        var isActive = (opt.Value == Value);
        <button type="button"
                class="pg-btn @(isActive ? "active" : "")"
                data-value="@opt.Value"
                @onclick="() => SelectOption(opt.Value)">
            <span class="pg-label">
                @if (opt.Icon != null) { @opt.Icon }
                <span>@opt.Label</span>
            </span>
        </button>
    }
</div>

@code {
    [Parameter] public string Id { get; set; } = $"pg_{Guid.NewGuid():N}";
    [Parameter] public string CssClass { get; set; } = "";
    [Parameter] public string Value { get; set; } = "";
    [Parameter] public EventCallback<string> ValueChanged { get; set; }
    [Parameter] public List<PulsarOption> Options { get; set; } = new();

    private ElementReference _trackElement;
    private DotNetObjectReference<PulsarGlassSlider>? _dotNetRef;
    private IJSObjectReference? _jsInstance;

    public record PulsarOption(string Value, string Label, RenderFragment? Icon = null);

    protected override async Task OnAfterRenderAsync(bool firstRender)
    {
        if (firstRender)
        {
            _dotNetRef = DotNetObjectReference.Create(this);
            _jsInstance = await JSRuntime.InvokeAsync<IJSObjectReference>(
                "PulsarGlassBlazor.init", _trackElement, _dotNetRef);
        }
    }

    [JSInvokable]
    public async Task OnJsSelected(string newValue)
    {
        if (Value != newValue)
        {
            Value = newValue;
            await ValueChanged.InvokeAsync(newValue);
        }
    }

    private async Task SelectOption(string newValue)
    {
        if (Value != newValue)
        {
            Value = newValue;
            await ValueChanged.InvokeAsync(newValue);
            if (_jsInstance != null)
            {
                await _jsInstance.InvokeVoidAsync("selectByValue", newValue, true);
            }
        }
    }

    public async ValueTask DisposeAsync()
    {
        if (_jsInstance != null)
        {
            await _jsInstance.InvokeVoidAsync("destroy");
            await _jsInstance.DisposeAsync();
        }
        _dotNetRef?.Dispose();
    }
}
```

Companion JS helper:
```javascript
window.PulsarGlassBlazor = {
  init: function (el, dotNetRef) {
    return PulsarGlass.create(el, {
      onSelect: function (idx, val) {
        dotNetRef.invokeMethodAsync('OnJsSelected', String(val));
      }
    });
  }
};
```

---

### 6.2. React / Next.js (TypeScript / TSX)

File: `PulsarGlass.tsx`
```tsx
import React, { useEffect, useRef } from 'react';
import PulsarGlassCore from './pulsar-glass';
import './pulsar-glass.css';

export interface PulsarOption {
  value: string;
  label: string;
  icon?: React.ReactNode;
}

interface PulsarGlassProps {
  options: PulsarOption[];
  value: string;
  onChange: (value: string) => void;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export const PulsarGlass: React.FC<PulsarGlassProps> = ({
  options,
  value,
  onChange,
  size = 'md',
  className = '',
}) => {
  const trackRef = useRef<HTMLDivElement>(null);
  const instanceRef = useRef<any>(null);

  useEffect(() => {
    if (!trackRef.current) return;

    instanceRef.current = PulsarGlassCore.create(trackRef.current, {
      onSelect: (_: number, val: string) => {
        onChange(val);
      },
    });

    return () => {
      if (instanceRef.current) {
        instanceRef.current.destroy();
        instanceRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (instanceRef.current) {
      instanceRef.current.selectByValue(value, true);
    }
  }, [value]);

  const sizeClass = size === 'sm' ? 'pg-sm' : size === 'lg' ? 'pg-lg' : '';

  return (
    <div ref={trackRef} className={`pg-track ${sizeClass} ${className}`}>
      <div className="pg-slider" />
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          className={`pg-btn ${opt.value === value ? 'active' : ''}`}
          data-value={opt.value}
        >
          <span className="pg-label">
            {opt.icon && <span className="pg-icon">{opt.icon}</span>}
            <span>{opt.label}</span>
          </span>
        </button>
      ))}
    </div>
  );
};
```

---

### 6.3. Vue 3 (Composition API / `<script setup>`)

File: `PulsarGlass.vue`
```vue
<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue';
import PulsarGlassCore from './pulsar-glass';
import './pulsar-glass.css';

interface Option {
  value: string;
  label: string;
}

const props = withDefaults(defineProps<{
  modelValue: string;
  options: Option[];
  size?: 'sm' | 'md' | 'lg';
}>(), {
  size: 'md'
});

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void;
}>();

const trackRef = ref<HTMLElement | null>(null);
let sliderInstance: any = null;

onMounted(() => {
  if (!trackRef.value) return;

  sliderInstance = PulsarGlassCore.create(trackRef.value, {
    onSelect: (_: number, val: string) => {
      emit('update:modelValue', String(val));
    }
  });
});

watch(() => props.modelValue, (newVal) => {
  if (sliderInstance) {
    sliderInstance.selectByValue(newVal, true);
  }
});

onUnmounted(() => {
  if (sliderInstance) {
    sliderInstance.destroy();
    sliderInstance = null;
  }
});
</script>

<template>
  <div
    ref="trackRef"
    class="pg-track"
    :class="{ 'pg-sm': size === 'sm', 'pg-lg': size === 'lg' }"
  >
    <div class="pg-slider"></div>
    <button
      v-for="opt in options"
      :key="opt.value"
      type="button"
      class="pg-btn"
      :class="{ active: opt.value === modelValue }"
      :data-value="opt.value"
    >
      <span class="pg-label">{{ opt.label }}</span>
    </button>
  </div>
</template>
```

---

### 6.4. Vanilla HTML / CSS / JavaScript

```html
<link rel="stylesheet" href="pulsar-glass.css">

<!-- Container -->
<div class="pg-track pg-sm" id="mySlider">
  <div class="pg-slider"></div>
  <button class="pg-btn active" data-value="day"><span class="pg-label">Day</span></button>
  <button class="pg-btn" data-value="week"><span class="pg-label">Week</span></button>
  <button class="pg-btn" data-value="month"><span class="pg-label">Month</span></button>
</div>

<script src="pulsar-glass.js"></script>
<script>
  const slider = PulsarGlass.create('#mySlider', {
    onSelect: (index, value) => {
      console.log('Selected immediately (0ms):', value);
    },
    onChange: (index, value) => {
      console.log('Motion settled (380ms):', value);
    }
  });
</script>
```

---

## 7. Master Configuration Reference

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `trackSelector` | `string` | `'.pg-track'` | Selector for track bezel container |
| `sliderSelector` | `string` | `'.pg-slider'` | Selector for liquid glass pill |
| `buttonSelector` | `string` | `'.pg-btn'` | Selector for segment buttons |
| `labelSelector` | `string` | `'.pg-label'` | Selector for inner label element |
| `activeClass` | `string` | `'active'` | Class applied to selected button |
| `maxOvershoot` | `number` | `44` | Max overdrag rubber-banding distance in pixels |
| `pullResistance`| `number` | `110` | Non-linear drag resistance coefficient |
| `flightDurationBase` | `number` | `310` | Base flight animation duration in ms |
| `flightDurationScale`| `number` | `0.35` | Additional ms per pixel of travel distance |
| `flightDurationMin` | `number` | `340` | Minimum duration clamp for short hops |
| `flightDurationMax` | `number` | `440` | Maximum duration clamp for long leaps |
| `enableRefraction` | `boolean` | `true` | Apply chromatic aberration SVG filter to lens |
| `enableWaterRefraction`| `boolean`| `true` | Apply underwater displacement filter to labels |
| `onSelect` | `function` | `null` | Instant callback: `(index, value, btn) => void` |
| `onChange` | `function` | `null` | Settle callback: `(index, value, btn) => void` |

---

## 8. Verification & QA Protocol

After implementing Pulsar Glass on any view, verify these 5 criteria:
1. **Fluid Drag**: Pointer down on any segment and drag horizontally past either track edge. The lens must scale up ($1.16\times$), stretch horizontally, and smoothly exhibit exponential resistance ($44\text{px}$ limit).
2. **No Origin Jump**: Dragging starting on the 2nd or 3rd button must never jump back to 0px (verifies `DOMMatrix` `matrix3d` handling).
3. **Zero-Latency Pane Switch**: Releasing the slider on a new option must update active views/state in $0\text{ ms}$ via `onSelect`.
4. **Spring Settle**: Releasing from drag must perform a clean `0.38s` cubic-bezier magnetic snap without an unnecessary parabolic flight arc.
5. **Clean Inset**: The glass pill must align symmetrically inside the bezel with uniform concentric margins ($2.5\text{px}$, $3.0\text{px}$, or $4.5\text{px}$).
