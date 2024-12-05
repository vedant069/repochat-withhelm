import React, { useEffect, useRef } from 'react';
import { signInWithPopup, GoogleAuthProvider } from 'firebase/auth';
import { auth } from '../firebase';
import { Github } from 'lucide-react';

export default function LoginPage() {
  const canvasRef = useRef(null);

  const handleGoogleLogin = async () => {
    try {
      const provider = new GoogleAuthProvider();
      await signInWithPopup(auth, provider);
    } catch (error) {
      console.error('Error signing in with Google:', error);
    }
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    
    // Resize canvas to full screen
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;

    // Star properties
    const stars = [];
    const starCount = 200;

    // Create stars
    for (let i = 0; i < starCount; i++) {
      stars.push({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        radius: Math.random() * 1.5,
        opacity: Math.random(),
        speed: Math.random() * 0.3
      });
    }

    // Animate stars
    function animateStars() {
      // Clear canvas
      ctx.fillStyle = 'rgba(0, 0, 15, 0.8)';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // Draw and move stars
      stars.forEach(star => {
        ctx.beginPath();
        ctx.arc(star.x, star.y, star.radius, 0, Math.PI * 2);
        
        // Create gradient for star
        const gradient = ctx.createRadialGradient(
          star.x, star.y, 0, 
          star.x, star.y, star.radius
        );
        gradient.addColorStop(0, `rgba(255, 255, 255, ${star.opacity})`);
        gradient.addColorStop(1, 'rgba(255, 255, 255, 0)');
        
        ctx.fillStyle = gradient;
        ctx.fill();

        // Move star
        star.y += star.speed;

        // Reset star position if it goes below screen
        if (star.y > canvas.height) {
          star.y = 0;
          star.x = Math.random() * canvas.width;
        }
      });

      requestAnimationFrame(animateStars);
    }

    // Start animation
    animateStars();

    // Resize handler
    const resizeHandler = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };

    window.addEventListener('resize', resizeHandler);

    // Cleanup
    return () => {
      window.removeEventListener('resize', resizeHandler);
    };
  }, []);

  return (
    <div className="relative min-h-screen overflow-hidden">
      {/* Animated Galaxy Background */}
      <canvas 
        ref={canvasRef} 
        className="absolute inset-0 z-0"
        style={{
          background: 'linear-gradient(to bottom, #000028, #000011)'
        }}
      ></canvas>

      {/* Login Container */}
      <div className="relative z-10 min-h-screen flex items-center justify-center px-4 sm:px-6 lg:px-8">
        <div className="bg-white/10 backdrop-blur-lg border border-white/20 rounded-2xl shadow-2xl p-8 w-full max-w-md relative overflow-hidden">
          {/* Subtle Purple Accent */}
          <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-transparent via-purple-500/50 to-transparent"></div>
          
          <div className="text-center mb-8">
            <div className="flex justify-center mb-4">
              <div className="p-3 bg-white/10 backdrop-blur-md rounded-xl border border-white/20">
                <Github className="w-12 h-12 text-white opacity-80" />
              </div>
            </div>
            <h2 className="text-3xl font-bold text-white mb-2">Welcome to RepoChat</h2>
            <p className="text-white/70 mb-6">
              Sign in with your Google account to explore your GitHub repositories
            </p>
          </div>

          <button
            onClick={handleGoogleLogin}
            className="w-full flex items-center justify-center gap-3 
            bg-white/10 backdrop-blur-md border border-white/20 
            rounded-lg px-6 py-3 text-white 
            hover:bg-white/20 transition-all duration-200 
            focus:outline-none focus:ring-2 focus:ring-purple-500/30"
          >
            <img
              src="https://www.google.com/favicon.ico"
              alt="Google"
              className="w-5 h-5"
            />
            Continue with Google
          </button>

          <div className="mt-8 text-center text-sm">
            <p className="text-white/60">
              By signing in, you agree to our{' '}
              <a href="#" className="text-purple-400/80 hover:underline">
                Terms of Service
              </a>{' '}
              and{' '}
              <a href="#" className="text-purple-400/80 hover:underline">
                Privacy Policy
              </a>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}