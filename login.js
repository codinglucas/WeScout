// Login Form Validation and Handling

class LoginForm {
    constructor() {
        this.form = document.getElementById('loginForm');
        this.username = document.getElementById('username');
        this.email = document.getElementById('email');
        this.password = document.getElementById('password');
        this.confirmPassword = document.getElementById('confirmPassword');
        this.errorMessage = document.getElementById('errorMessage');
        this.submitBtn = this.form.querySelector('.btn-submit');
        
        this.init();
    }

    init() {
        // Form submission
        this.form.addEventListener('submit', (e) => this.handleSubmit(e));

        // Real-time validation
        this.password.addEventListener('input', () => this.checkPasswordStrength());
        this.confirmPassword.addEventListener('input', () => this.validatePasswordMatch());
        this.email.addEventListener('blur', () => this.validateEmail());
        this.username.addEventListener('blur', () => this.validateUsername());

        // Input animations
        this.addInputAnimations();
    }

    handleSubmit(e) {
        e.preventDefault();
        
        // Clear previous errors
        this.hideError();

        // Validate all fields
        if (!this.validateAll()) {
            return;
        }

        // Show loading state
        this.setLoading(true);

        // Simulate API call (replace with actual API call)
        setTimeout(() => {
            this.setLoading(false);
            
            // Success - redirect or show success message
            this.showSuccess();
        }, 2000);
    }

    validateAll() {
        let isValid = true;

        // Username validation
        if (this.username.value.trim().length < 3) {
            this.showError('O nome de usuário deve ter pelo menos 3 caracteres');
            this.username.classList.add('error');
            isValid = false;
        }

        // Email validation
        if (!this.isValidEmail(this.email.value)) {
            this.showError('Por favor, insira um email válido');
            this.email.classList.add('error');
            isValid = false;
        }

        // Password validation
        if (this.password.value.length < 6) {
            this.showError('A senha deve ter pelo menos 6 caracteres');
            this.password.classList.add('error');
            isValid = false;
        }

        // Password match validation
        if (this.password.value !== this.confirmPassword.value) {
            this.showError('As senhas não coincidem');
            this.confirmPassword.classList.add('error');
            isValid = false;
        }

        return isValid;
    }

    validateUsername() {
        if (this.username.value.trim().length >= 3) {
            this.username.classList.remove('error');
            this.username.classList.add('success');
        } else {
            this.username.classList.remove('success');
        }
    }

    validateEmail() {
        if (this.isValidEmail(this.email.value)) {
            this.email.classList.remove('error');
            this.email.classList.add('success');
        } else {
            this.email.classList.remove('success');
        }
    }

    isValidEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    }

    validatePasswordMatch() {
        if (this.password.value && this.confirmPassword.value) {
            if (this.password.value === this.confirmPassword.value) {
                this.confirmPassword.classList.remove('error');
                this.confirmPassword.classList.add('success');
                this.hideError();
            } else {
                this.confirmPassword.classList.remove('success');
                this.confirmPassword.classList.add('error');
            }
        }
    }

    checkPasswordStrength() {
        const password = this.password.value;
        const strength = this.calculatePasswordStrength(password);
        
        // Remove existing strength indicator
        let strengthIndicator = this.password.parentElement.querySelector('.password-strength');
        if (strengthIndicator) {
            strengthIndicator.remove();
        }

        // Add new strength indicator
        if (password.length > 0) {
            strengthIndicator = document.createElement('div');
            strengthIndicator.className = 'password-strength';
            
            for (let i = 0; i < 4; i++) {
                const bar = document.createElement('div');
                bar.className = 'strength-bar';
                
                if (i < strength) {
                    bar.classList.add('active');
                    if (strength <= 2) bar.classList.add('weak');
                    else if (strength === 3) bar.classList.add('medium');
                }
                
                strengthIndicator.appendChild(bar);
            }
            
            this.password.parentElement.appendChild(strengthIndicator);
        }
    }

    calculatePasswordStrength(password) {
        let strength = 0;
        
        if (password.length >= 6) strength++;
        if (password.length >= 10) strength++;
        if (/[a-z]/.test(password) && /[A-Z]/.test(password)) strength++;
        if (/[0-9]/.test(password)) strength++;
        if (/[^a-zA-Z0-9]/.test(password)) strength++;
        
        return Math.min(strength, 4);
    }

    showError(message) {
        this.errorMessage.textContent = message;
        this.errorMessage.classList.add('show');
    }

    hideError() {
        this.errorMessage.classList.remove('show');
    }

    setLoading(loading) {
        if (loading) {
            this.submitBtn.classList.add('loading');
            this.submitBtn.disabled = true;
            this.submitBtn.textContent = 'Carregando...';
        } else {
            this.submitBtn.classList.remove('loading');
            this.submitBtn.disabled = false;
            this.submitBtn.textContent = 'Login com Google';
        }
    }

    showSuccess() {
        // Create success message
        const successDiv = document.createElement('div');
        successDiv.className = 'success-message';
        successDiv.style.cssText = `
            padding: 1rem;
            background: rgba(74, 222, 128, 0.2);
            border: 1px solid rgba(74, 222, 128, 0.5);
            border-radius: 8px;
            color: #4ade80;
            text-align: center;
            font-weight: 600;
            animation: fadeIn 0.3s ease;
        `;
        successDiv.textContent = 'Conta criada com sucesso! Redirecionando...';
        
        this.form.appendChild(successDiv);

        // Redirect after 2 seconds (replace with actual redirect)
        setTimeout(() => {
            // window.location.href = 'dashboard.html';
            console.log('Redirecting to dashboard...');
        }, 2000);
    }

    addInputAnimations() {
        const inputs = this.form.querySelectorAll('.form-input');
        
        inputs.forEach(input => {
            // Focus animation
            input.addEventListener('focus', () => {
                input.parentElement.style.transform = 'scale(1.01)';
                input.parentElement.style.transition = 'transform 0.2s ease';
            });

            // Blur animation
            input.addEventListener('blur', () => {
                input.parentElement.style.transform = 'scale(1)';
            });

            // Remove error class on input
            input.addEventListener('input', () => {
                input.classList.remove('error');
                this.hideError();
            });
        });
    }
}

// Initialize login form when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new LoginForm();
});

// Add Google Sign-In functionality (placeholder)
class GoogleAuth {
    constructor() {
        this.init();
    }

    init() {
        // This is a placeholder for Google Sign-In
        // You would need to integrate Google OAuth API here
        console.log('Google Auth initialized');
    }

    signIn() {
        // Implement Google Sign-In logic
        console.log('Google Sign-In triggered');
    }
}

// Enhanced input effects
class InputEffects {
    constructor() {
        this.init();
    }

    init() {
        const inputs = document.querySelectorAll('.form-input');
        
        inputs.forEach(input => {
            // Add floating label effect
            input.addEventListener('focus', () => {
                const label = input.parentElement.querySelector('.form-label');
                if (label) {
                    label.style.color = 'var(--gradient-green)';
                    label.style.transform = 'translateY(-2px)';
                    label.style.transition = 'all 0.3s ease';
                }
            });

            input.addEventListener('blur', () => {
                const label = input.parentElement.querySelector('.form-label');
                if (label) {
                    label.style.color = 'var(--text-white)';
                    label.style.transform = 'translateY(0)';
                }
            });
        });
    }
}

// Initialize input effects
document.addEventListener('DOMContentLoaded', () => {
    new InputEffects();
    new GoogleAuth();
});