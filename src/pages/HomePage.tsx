import React, { useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { Github, MessageSquare, Code, Zap, ArrowRight, Brain, Globe } from 'lucide-react';

// Enhanced StarField Component
const StarField = () => {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    let animationFrameId;
    
    // Set canvas size with device pixel ratio support
    const setCanvasSize = () => {
      const dpr = window.devicePixelRatio || 1;
      const displayWidth = window.innerWidth;
      const displayHeight = window.innerHeight;
      
      canvas.width = displayWidth * dpr;
      canvas.height = displayHeight * dpr;
      
      canvas.style.width = `${displayWidth}px`;
      canvas.style.height = `${displayHeight}px`;
      
      ctx.scale(dpr, dpr);
    };
    
    setCanvasSize();
    window.addEventListener('resize', setCanvasSize);
    
    // Create stars with enhanced properties
    const stars = Array.from({ length: 200 }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      radius: Math.random() * 1.5,
      opacity: Math.random(),
      speed: Math.random() * 0.3
    }));
    
    // Animation loop with galaxy effect
    const animate = () => {
      // Create dark galaxy background with slight transparency
      ctx.fillStyle = 'rgba(0, 0, 15, 0.8)';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      
      // Draw and animate stars
      stars.forEach(star => {
        ctx.beginPath();
        ctx.arc(star.x, star.y, star.radius, 0, Math.PI * 2);
        
        // Create gradient for each star
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
        
        // Reset star position when it goes off screen
        if (star.y > canvas.height) {
          star.y = 0;
          star.x = Math.random() * canvas.width;
        }
      });
      
      animationFrameId = requestAnimationFrame(animate);
    };
    
    animate();
    
    return () => {
      window.removeEventListener('resize', setCanvasSize);
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none"
      style={{
        background: 'linear-gradient(to bottom, #000028, #000011)'
      }}
    />
  );
};

export default function HomePage() {
  return (
    <div className="min-h-screen relative overflow-hidden">
      <StarField />

      {/* Navigation with glass effect */}
      <nav className="py-6 sticky top-0 backdrop-blur-md bg-black/10 z-50 border-b border-white/10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center">
            <Link to="/" className="flex items-center gap-2 group">
              <Github className="w-8 h-8 text-white transition-transform group-hover:rotate-12" />
              <span className="text-xl font-bold text-white">RepoChat</span>
            </Link>
            <div className="flex items-center gap-4">
              <Link
                to="/login"
                className="px-4 py-2 text-white/90 hover:text-white transition-colors"
              >
                Sign In
              </Link>
              <Link
                to="/login"
                className="px-4 py-2 bg-white/10 text-white rounded-lg hover:bg-white/20 transition-all duration-300 hover:shadow-lg hover:-translate-y-0.5 backdrop-blur-sm"
              >
                Get Started
              </Link>
            </div>
          </div>
        </div>
      </nav>

      {/* Hero Section with cosmic theme */}
      <section className="py-32 relative">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative">
          <div className="text-center max-w-3xl mx-auto">
            <h1 className="text-6xl font-bold text-white mb-6 animate-slide-up">
              Chat with Your GitHub Repositories Using{' '}
              <span className="text-blue-400 animate-pulse">AI</span>
            </h1>
            <p className="text-xl text-gray-300 mb-8 animate-fade-in opacity-0 [animation-delay:200ms]">
              Transform the way you understand code. Get instant insights, explanations, and answers 
              about your repositories through natural conversations.
            </p>
            <div className="flex items-center justify-center gap-4 animate-fade-in opacity-0 [animation-delay:400ms]">
              <Link
                to="/login"
                className="px-8 py-4 bg-blue-500/80 backdrop-blur-sm text-white rounded-lg hover:bg-blue-600/80 transition-all duration-300 hover:shadow-lg hover:-translate-y-0.5 flex items-center gap-2 group"
              >
                Start Chatting
                <ArrowRight className="w-5 h-5 transition-transform duration-300 group-hover:translate-x-1" />
              </Link>
              <a
                href="https://github.com"
                target="_blank"
                rel="noopener noreferrer"
                className="px-8 py-4 border border-white/20 text-white rounded-lg hover:bg-white/10 transition-all duration-300 hover:shadow-lg hover:-translate-y-0.5 flex items-center gap-2 group backdrop-blur-sm"
              >
                View on GitHub
                <Github className="w-5 h-5 transition-transform duration-300 group-hover:rotate-12" />
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* Features Grid with glass cards */}
      <section className="py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16 animate-fade-in">
            <h2 className="text-4xl font-bold text-white mb-4">
              Powerful Features
            </h2>
            <p className="text-xl text-gray-300">
              Everything you need to understand and work with your code better
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {[
              {
                icon: Brain,
                title: "AI-Powered Analysis",
                description: "Advanced AI understands your code context and provides intelligent responses to your questions."
              },
              {
                icon: MessageSquare,
                title: "Natural Conversations",
                description: "Chat naturally about your code, ask questions, and get detailed explanations in plain English."
              },
              {
                icon: Code,
                title: "Code Understanding",
                description: "Get deep insights into your codebase, including architecture explanations and best practices."
              }
            ].map((feature, index) => (
              <div 
                key={feature.title}
                className="group backdrop-blur-md bg-white/5 p-8 rounded-xl transition-all duration-300 hover:shadow-xl hover:-translate-y-1 animate-fade-in opacity-0 border border-white/10 hover:bg-white/10"
                style={{ animationDelay: `${index * 200}ms` }}
              >
                <div className="w-12 h-12 bg-blue-500/20 rounded-lg flex items-center justify-center mb-6 group-hover:scale-110 transition-transform duration-300">
                  <feature.icon className="w-6 h-6 text-blue-400" />
                </div>
                <h3 className="text-xl font-semibold text-white mb-4">
                  {feature.title}
                </h3>
                <p className="text-gray-300">
                  {feature.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How It Works section with cosmic theme */}
      <section className="py-20 relative">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold text-white mb-4">
              How It Works
            </h2>
            <p className="text-xl text-gray-300">
              Get started in three simple steps
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {[
              {
                icon: Github,
                title: "1. Connect Repository",
                description: "Simply paste your GitHub repository URL to get started"
              },
              {
                icon: MessageSquare,
                title: "2. Start Chatting",
                description: "Ask questions about your code in natural language"
              },
              {
                icon: Zap,
                title: "3. Get Insights",
                description: "Receive detailed explanations and suggestions"
              }
            ].map((step, index) => (
              <div 
                key={step.title}
                className="text-center animate-fade-in opacity-0"
                style={{ animationDelay: `${index * 200}ms` }}
              >
                <div className="w-16 h-16 bg-blue-500/20 rounded-full flex items-center justify-center mx-auto mb-6 transition-transform duration-300 hover:scale-110">
                  <step.icon className="w-8 h-8 text-blue-400" />
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">
                  {step.title}
                </h3>
                <p className="text-gray-300">
                  {step.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer with cosmic theme */}
      <footer className="py-12 backdrop-blur-md bg-black/20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col items-center text-center">
            <div className="flex items-center gap-2 mb-4 group">
              <Github className="w-8 h-8 text-blue-400 transition-transform duration-300 group-hover:rotate-12" />
              <span className="text-xl font-bold text-white">RepoChat</span>
            </div>
            <p className="text-gray-300 mb-8 max-w-md">
              Making code understanding easier with AI-powered conversations.
            </p>
            <div className="flex items-center gap-6">
              <a href="#" className="text-gray-300 hover:text-blue-400 transition-transform duration-300 hover:scale-110">
                <Globe className="w-6 h-6" />
              </a>
              <a href="#" className="text-gray-300 hover:text-blue-400 transition-transform duration-300 hover:scale-110">
                <Github className="w-6 h-6" />
              </a>
            </div>
            <div className="border-t border-white/10 mt-8 pt-8 text-gray-300">
              © 2024 RepoChat. All rights reserved.
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}