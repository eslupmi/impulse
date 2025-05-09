// Theme management
export const ThemeManager = {
    // Theme names
    LIGHT: 'light',
    DARK: 'dark',

    // Initialize theme
    init() {
        // Check for saved theme preference
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme) {
            this.setTheme(savedTheme);
        } else {
            // Check system preference
            const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            this.setTheme(prefersDark ? this.DARK : this.LIGHT);
        }

        // Listen for system theme changes
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
            if (!localStorage.getItem('theme')) {
                this.setTheme(e.matches ? this.DARK : this.LIGHT);
            }
        });

        // Setup theme toggle button
        const themeToggle = document.getElementById('theme-toggle');
        if (themeToggle) {
            themeToggle.addEventListener('click', () => this.toggleTheme());
            // Set initial emoji
            const currentTheme = document.documentElement.getAttribute('data-theme') || this.LIGHT;
            this.updateThemeButton(currentTheme);
        }
    },

    // Set theme
    setTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
        this.updateThemeButton(theme);
    },

    // Toggle theme
    toggleTheme() {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === this.DARK ? this.LIGHT : this.DARK;
        this.setTheme(newTheme);
    },

    // Update theme button appearance
    updateThemeButton(theme) {
        const button = document.getElementById('theme-toggle');
        if (button) {
            button.innerHTML = theme === this.DARK ? '☀️' : '🌙';
            button.setAttribute('title', `Switch to ${theme === this.DARK ? 'light' : 'dark'} theme`);
        }
    }
};
