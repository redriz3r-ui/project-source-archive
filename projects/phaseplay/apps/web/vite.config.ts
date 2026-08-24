import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [react(), VitePWA({ registerType: "autoUpdate", manifest: { name: "PhasePlay AI", short_name: "PhasePlay", description: "Bankroll and risk-management coaching", theme_color: "#101714", background_color: "#f4f1e9", display: "standalone", start_url: "/" } })],
});
