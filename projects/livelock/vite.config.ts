import {defineConfig} from 'vite';
export default defineConfig({publicDir:false,build:{outDir:process.env.LIVELOCK_OUT_DIR||(process.env.LIVELOCK_SIMULATOR==='1'?'dist-dev':'dist'),emptyOutDir:true,rollupOptions:{input:{popup:'popup.html',options:'options.html',blocked:'blocked.html'}}}});
