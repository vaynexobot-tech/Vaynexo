// Demo artifact: VITE_DEMO=1 bilan yig'ib, CSS va JS ni bitta HTML ichiga joylaydi.
// Ishlatish:  node scripts/build-demo.mjs   ->  dist-demo/vaynexo-demo.html
import { execSync } from "node:child_process";
import { readFileSync, readdirSync, writeFileSync } from "node:fs";

execSync("npx vite build --outDir dist-demo --emptyOutDir", { stdio: "inherit", env: { ...process.env, VITE_DEMO: "1" } });
const dir = "dist-demo/assets";
const files = readdirSync(dir);
const css = readFileSync(`${dir}/${files.find((f) => f.endsWith(".css"))}`, "utf8");
const js = readFileSync(`${dir}/${files.find((f) => f.endsWith(".js"))}`, "utf8").replace(/<\/script/gi, "<\\/script");
const html = `<title>VAYNEXO Bot Demo</title>
<meta name="theme-color" content="#0d0e13">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&family=Space+Grotesk:wght@600;700&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
<style>${css}</style>
<div id="root"></div>
<script type="module">${js}</script>
`;
writeFileSync("dist-demo/vaynexo-demo.html", html);
console.log("dist-demo/vaynexo-demo.html", (html.length / 1024).toFixed(0), "KB");
