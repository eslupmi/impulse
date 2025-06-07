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

        // Setup theme toggle checkbox
        const themeToggle = document.getElementById('theme-toggle');
        if (themeToggle) {
            // Set initial checkbox state
            themeToggle.checked = document.documentElement.getAttribute('data-theme') === this.DARK;
            
            // Add change event listener
            themeToggle.addEventListener('change', () => {
                this.setTheme(themeToggle.checked ? this.DARK : this.LIGHT);
            });
        }
    },

    // Set theme
    setTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
        
        // Update checkbox state
        const themeToggle = document.getElementById('theme-toggle');
        if (themeToggle) {
            themeToggle.checked = theme === this.DARK;
        }
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
