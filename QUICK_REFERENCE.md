# 🎨 Quick Reference Guide - Modern UI System

## 🚀 Quick Start

### Toast Notifications
```javascript
// Success
window.toast.success('¡Operación exitosa!');

// Error
window.toast.error('Ocurrió un error');

// Warning
window.toast.warning('Ten cuidado');

// Info
window.toast.info('Información importante');
```

### Loading Overlay
```javascript
// Show
window.loadingOverlay.show('Cargando datos...');

// Hide
window.loadingOverlay.hide();

// Update message
window.loadingOverlay.updateMessage('Procesando...');
```

### Common Utility Classes

#### Layout
```html
<div class="flex items-center justify-between gap-4">Content</div>
<div class="grid grid-cols-3 gap-4">Grid content</div>
```

#### Spacing
```html
<div class="p-4 m-2">Padding & Margin</div>
<div class="px-6 py-4">Horizontal & Vertical</div>
<div class="mt-4 mb-8">Top & Bottom</div>
```

#### Colors
```html
<div class="bg-primary text-white">Primary</div>
<div class="bg-success-light text-success">Success</div>
<div class="text-danger">Error text</div>
```

#### Typography
```html
<h1 class="text-3xl font-bold">Large Title</h1>
<p class="text-sm text-muted">Small muted text</p>
<span class="text-lg font-semibold">Semibold</span>
```

#### Borders & Radius
```html
<div class="rounded-lg border border-primary">Bordered</div>
<div class="rounded-full">Circular</div>
```

#### Shadows
```html
<div class="shadow-sm">Small shadow</div>
<div class="shadow-lg">Large shadow</div>
<div class="shadow-primary">Primary colored shadow</div>
```

### Animations

#### Fade
```html
<div class="animate-fade-in">Fade in</div>
<div class="animate-fade-in-up">Fade in from bottom</div>
```

#### Slide
```html
<div class="animate-slide-in-right">Slide from right</div>
<div class="animate-slide-in-left">Slide from left</div>
```

#### Scale
```html
<div class="animate-scale-in">Scale in</div>
<div class="animate-pulse">Pulsing</div>
```

#### Effects
```html
<div class="animate-bounce">Bounce</div>
<div class="animate-shake">Shake</div>
<div class="animate-spin">Spinning</div>
```

#### Hover Effects
```html
<div class="hover-lift">Lift on hover</div>
<div class="hover-scale">Scale on hover</div>
<div class="hover-shadow-lg">Shadow on hover</div>
```

#### Stagger (for lists)
```html
<ul class="animate-stagger">
  <li>Item 1</li>
  <li>Item 2</li>
  <li>Item 3</li>
</ul>
```

### Buttons
```html
<!-- Primary -->
<button class="btn btn-primary">Primary</button>

<!-- Success -->
<button class="btn btn-success">Success</button>

<!-- Danger -->
<button class="btn btn-danger">Danger</button>

<!-- Outline -->
<button class="btn btn-outline-primary">Outline</button>

<!-- Sizes -->
<button class="btn btn-sm">Small</button>
<button class="btn btn-lg">Large</button>
```

### Form Controls
```html
<!-- Input -->
<input type="text" class="form-control" placeholder="Enter text">

<!-- Select -->
<select class="form-select">
  <option>Option 1</option>
</select>

<!-- Textarea -->
<textarea class="form-control" rows="3"></textarea>

<!-- With validation -->
<input type="email" class="form-control is-valid">
<input type="text" class="form-control is-invalid">
```

### Cards
```html
<div class="card">
  <div class="card-header">Header</div>
  <div class="card-body">
    <p>Content goes here</p>
  </div>
  <div class="card-footer">Footer</div>
</div>
```

### Badges
```html
<span class="badge badge-primary">Primary</span>
<span class="badge badge-success">Success</span>
<span class="badge badge-danger">Danger</span>
<span class="badge badge-warning">Warning</span>
```

### Alerts
```html
<div class="alert alert-success">Success message!</div>
<div class="alert alert-error">Error message!</div>
<div class="alert alert-warning">Warning message!</div>
<div class="alert alert-info">Info message!</div>
```

### Responsive Classes
```html
<!-- Hide on mobile -->
<div class="hide-xs">Hidden on mobile</div>

<!-- Show only on mobile -->
<div class="show-xs hide-sm">Mobile only</div>

<!-- Responsive flex -->
<div class="flex flex-sm-column">Row on desktop, column on mobile</div>

<!-- Responsive text -->
<p class="text-left text-sm-center">Left on desktop, center on mobile</p>
```

### Loading States
```html
<!-- Spinner -->
<div class="spinner"></div>
<div class="spinner spinner-sm"></div>
<div class="spinner spinner-lg"></div>

<!-- Loading dots -->
<div class="loading-dots">
  <span></span>
  <span></span>
  <span></span>
</div>

<!-- Skeleton loader -->
<div class="skeleton skeleton-text"></div>
<div class="skeleton skeleton-rect"></div>
<div class="skeleton skeleton-circle"></div>
```

## 🎨 CSS Variables Reference

### Colors
```css
var(--primary-600)      /* Main primary color */
var(--success-600)      /* Success green */
var(--danger-600)       /* Error red */
var(--warning-600)      /* Warning orange */
var(--info-600)         /* Info blue */
```

### Spacing
```css
var(--space-xs)         /* 4px */
var(--space-sm)         /* 8px */
var(--space-md)         /* 16px */
var(--space-lg)         /* 24px */
var(--space-xl)         /* 32px */
var(--space-2xl)        /* 48px */
```

### Border Radius
```css
var(--radius-sm)        /* 4px */
var(--radius-md)        /* 8px */
var(--radius-lg)        /* 12px */
var(--radius-xl)        /* 16px */
var(--radius-full)      /* 9999px */
```

### Shadows
```css
var(--shadow-sm)        /* Small shadow */
var(--shadow-md)        /* Medium shadow */
var(--shadow-lg)        /* Large shadow */
var(--shadow-xl)        /* Extra large shadow */
var(--shadow-primary)   /* Primary colored shadow */
```

### Transitions
```css
var(--transition-fast)  /* 150ms */
var(--transition-base)  /* 250ms */
var(--transition-slow)  /* 350ms */
```

### Typography
```css
var(--font-size-xs)     /* 12px */
var(--font-size-sm)     /* 14px */
var(--font-size-base)   /* 16px */
var(--font-size-lg)     /* 18px */
var(--font-size-xl)     /* 20px */
var(--font-size-2xl)    /* 24px */
```

## 🔧 JavaScript Utilities

### Storage
```javascript
// Save
storage.set('key', { data: 'value' });

// Get
const data = storage.get('key', defaultValue);

// Remove
storage.remove('key');

// Clear all
storage.clear();
```

### Formatters
```javascript
// Currency
formatters.currency(1234.56);        // $1,234.56
formatters.currency(1234.56, 'USD'); // $1,234.56

// Date
formatters.date(new Date());         // 01/12/2025
formatters.date(date, 'long');       // 1 de diciembre de 2025

// Number
formatters.number(1234.567, 2);      // 1,234.57

// Phone
formatters.phone('1234567890');      // (123) 456-7890
```

### Debounce & Throttle
```javascript
// Debounce - waits for pause in calls
const debouncedSearch = debounce(function(query) {
  // Search logic
}, 300);

// Throttle - limits frequency
const throttledScroll = throttle(function() {
  // Scroll logic
}, 200);
```

### Copy to Clipboard
```javascript
copyToClipboard('Text to copy')
  .then(() => console.log('Copied!'));
```

### Form Validation
```javascript
const form = document.querySelector('form');
const validator = new FormValidator(form);
// Automatic validation on blur and submit
```

## 📱 Mobile Optimizations

### Touch Targets
All interactive elements have minimum 44px touch targets on mobile.

### Sidebar
- Collapses off-screen on mobile
- Toggle button always accessible
- Overlay backdrop when open
- Swipe to close (future feature)

### Responsive Breakpoints
- **xs**: < 576px
- **sm**: ≥ 576px
- **md**: ≥ 768px
- **lg**: ≥ 992px
- **xl**: ≥ 1200px

## 🎯 Common Patterns

### Modal/Dialog
```html
<div class="loading-overlay animate-fade-in">
  <div class="loading-content animate-scale-in">
    <p>Content here</p>
  </div>
</div>
```

### Card with Hover Effect
```html
<div class="card hover-lift">
  <div class="card-body">
    <h3 class="text-xl font-bold mb-2">Title</h3>
    <p class="text-muted">Description</p>
  </div>
</div>
```

### Icon Button
```html
<button class="btn btn-primary">
  <i class="bi bi-check"></i>
  <span>Submit</span>
</button>
```

### Flex Container
```html
<div class="flex items-center justify-between p-4 bg-white rounded-lg shadow-md">
  <div class="flex items-center gap-3">
    <i class="bi bi-info-circle text-primary text-xl"></i>
    <span class="font-semibold">Information</span>
  </div>
  <button class="btn btn-sm btn-primary">Action</button>
</div>
```

### Grid Layout
```html
<div class="grid grid-cols-3 gap-4">
  <div class="card">Item 1</div>
  <div class="card">Item 2</div>
  <div class="card">Item 3</div>
</div>
```

## 💡 Tips & Tricks

1. **Combine utilities**: Mix and match classes for quick styling
2. **Use CSS variables**: For consistent theming
3. **Animate with classes**: Add animation classes dynamically with JS
4. **Mobile first**: Design for mobile, enhance for desktop
5. **Accessibility**: Always include ARIA labels
6. **Performance**: Use `transform` and `opacity` for animations
7. **Consistent spacing**: Use the spacing scale (--space-*)
8. **Color semantics**: Use semantic colors (primary, success, danger)
9. **Test responsive**: Check all breakpoints
10. **User preferences**: Respect reduced motion settings

---

**Made with ❤️ for peak frontend performance**
