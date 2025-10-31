// Particles Animation
class ParticleSystem {
    constructor() {
        this.container = document.getElementById('particles');
        this.particles = [];
        this.particleCount = 50;
        this.init();
    }

    init() {
        for (let i = 0; i < this.particleCount; i++) {
            this.createParticle();
        }
        this.animate();
    }

    createParticle() {
        const particle = document.createElement('div');
        particle.className = 'particle';
        
        const size = Math.random() * 4 + 1;
        const x = Math.random() * window.innerWidth;
        const y = Math.random() * window.innerHeight;
        const duration = Math.random() * 20 + 10;
        const delay = Math.random() * 5;
        const opacity = Math.random() * 0.5 + 0.1;

        particle.style.cssText = `
            position: absolute;
            width: ${size}px;
            height: ${size}px;
            background: rgba(255, 255, 255, ${opacity});
            border-radius: 50%;
            left: ${x}px;
            top: ${y}px;
            pointer-events: none;
            animation: particleFloat ${duration}s linear ${delay}s infinite;
        `;

        this.container.appendChild(particle);
        this.particles.push(particle);
    }

    animate() {
        // Add CSS animation dynamically
        if (!document.getElementById('particle-animation')) {
            const style = document.createElement('style');
            style.id = 'particle-animation';
            style.innerHTML = `
                @keyframes particleFloat {
                    0% {
                        transform: translate(0, 0) scale(1);
                        opacity: 0;
                    }
                    10% {
                        opacity: 1;
                    }
                    90% {
                        opacity: 1;
                    }
                    100% {
                        transform: translate(${Math.random() * 100 - 50}px, -100vh) scale(0);
                        opacity: 0;
                    }
                }
            `;
            document.head.appendChild(style);
        }
    }
}

// Mouse movement effect for gradient orbs
class MouseEffects {
    constructor() {
        this.orbs = document.querySelectorAll('.gradient-orb');
        this.init();
    }

    init() {
        document.addEventListener('mousemove', (e) => {
            const x = e.clientX / window.innerWidth;
            const y = e.clientY / window.innerHeight;

            this.orbs.forEach((orb, index) => {
                const speed = (index + 1) * 20;
                const xMove = (x - 0.5) * speed;
                const yMove = (y - 0.5) * speed;

                orb.style.transform = `translate(${xMove}px, ${yMove}px)`;
            });
        });
    }
}

// Smooth scroll for anchor links
class SmoothScroll {
    constructor() {
        this.init();
    }

    init() {
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', (e) => {
                e.preventDefault();
                const target = document.querySelector(anchor.getAttribute('href'));
                if (target) {
                    target.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            });
        });
    }
}

// Button hover effects
class ButtonEffects {
    constructor() {
        this.init();
    }

    init() {
        const buttons = document.querySelectorAll('.btn');
        
        buttons.forEach(btn => {
            btn.addEventListener('mouseenter', (e) => {
                this.createRipple(e);
            });
        });
    }

    createRipple(e) {
        const button = e.currentTarget;
        const ripple = document.createElement('span');
        const rect = button.getBoundingClientRect();
        const size = Math.max(rect.width, rect.height);
        const x = e.clientX - rect.left - size / 2;
        const y = e.clientY - rect.top - size / 2;

        ripple.style.cssText = `
            position: absolute;
            width: ${size}px;
            height: ${size}px;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.1);
            left: ${x}px;
            top: ${y}px;
            pointer-events: none;
            animation: rippleEffect 0.6s ease-out;
        `;

        if (!document.getElementById('ripple-animation')) {
            const style = document.createElement('style');
            style.id = 'ripple-animation';
            style.innerHTML = `
                @keyframes rippleEffect {
                    to {
                        transform: scale(2);
                        opacity: 0;
                    }
                }
            `;
            document.head.appendChild(style);
        }

        button.style.position = 'relative';
        button.style.overflow = 'hidden';
        button.appendChild(ripple);

        setTimeout(() => ripple.remove(), 600);
    }
}

// Scroll reveal animation
class ScrollReveal {
    constructor() {
        this.init();
    }

    init() {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.style.opacity = '1';
                    entry.target.style.transform = 'translateY(0)';
                }
            });
        }, { threshold: 0.1 });

        document.querySelectorAll('.hero-text, .cta-buttons').forEach(el => {
            observer.observe(el);
        });
    }
}

// Initialize all features when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new ParticleSystem();
    new MouseEffects();
    new SmoothScroll();
    new ButtonEffects();
    new ScrollReveal();

    // Add loading complete class
    document.body.classList.add('loaded');
});

// Handle window resize
let resizeTimer;
window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
        // Reinitialize particles on resize if needed
        const container = document.getElementById('particles');
        container.innerHTML = '';
        new ParticleSystem();
    }, 250);
});

// Add performance optimization
if ('IntersectionObserver' in window) {
    const heroObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (!entry.isIntersecting) {
                // Pause animations when not in view
                document.querySelectorAll('.gradient-orb').forEach(orb => {
                    orb.style.animationPlayState = 'paused';
                });
            } else {
                document.querySelectorAll('.gradient-orb').forEach(orb => {
                    orb.style.animationPlayState = 'running';
                });
            }
        });
    });

    heroObserver.observe(document.querySelector('.hero'));
}