import { defineConfig } from 'astro/config';
import tailwindcss from '@tailwindcss/vite';

// https://astro.build/config
export default defineConfig({
  vite: {
    plugins: [tailwindcss()],
    optimizeDeps: {
      include: [
        '@tensorflow/tfjs',
        '@tensorflow-models/coco-ssd',
        '@tensorflow/tfjs-backend-cpu',
        '@tensorflow/tfjs-backend-webgl'
      ]
    }
  }
});