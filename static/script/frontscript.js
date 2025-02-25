// JavaScript to add interactive animations to images and buttons

// Function to trigger animation for images on scroll
const images = document.querySelectorAll('.info-image');

const imageOnScroll = () => {
    images.forEach(image => {
        const imagePosition = image.getBoundingClientRect().top;
        const windowHeight = window.innerHeight;

        // If the image is in the viewport, add the 'fade-in' class
        if (imagePosition < windowHeight - 100) {
            image.classList.add('fade-in');
        }
    });
};

// Function to trigger animation for text on scroll
const texts = document.querySelectorAll('.info-text');

const textOnScroll = () => {
    texts.forEach(text => {
        const textPosition = text.getBoundingClientRect().top;
        const windowHeight = window.innerHeight;

        // If the text is in the viewport, add the 'fade-in-text' class
        if (textPosition < windowHeight - 100) {
            text.classList.add('fade-in-text');
        }
    });
};

// Event listener for scroll
window.addEventListener('scroll', () => {
    imageOnScroll();
    textOnScroll();
});

// Smooth Scroll for anchor links (if any)
const smoothScrollLinks = document.querySelectorAll('a[href^="#"]');
smoothScrollLinks.forEach(link => {
    link.addEventListener('click', (e) => {
        e.preventDefault();
        const target = document.querySelector(link.getAttribute('href'));
        window.scrollTo({
            top: target.offsetTop,
            behavior: 'smooth'
        });
    });
});

// Hover effect for buttons (just adding a subtle scaling effect)
const buttons = document.querySelectorAll('.button');
buttons.forEach(button => {
    button.addEventListener('mouseenter', () => {
        button.style.transform = 'scale(1.1)';
        button.style.transition = 'transform 0.2s ease-in-out';
    });

    button.addEventListener('mouseleave', () => {
        button.style.transform = 'scale(1)';
    });
});

