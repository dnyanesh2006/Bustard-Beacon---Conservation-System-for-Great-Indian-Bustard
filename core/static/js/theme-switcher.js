// BUSTARD BEACON — Light Theme Enforcer
document.addEventListener('DOMContentLoaded', () => {
    // Enforce pure light theme across the platform
    document.documentElement.setAttribute('data-theme', 'light');
    try {
        localStorage.setItem('theme', 'light');
    } catch (e) {}
});
