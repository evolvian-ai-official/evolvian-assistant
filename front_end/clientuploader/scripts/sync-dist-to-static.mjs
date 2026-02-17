import { cpSync, existsSync, mkdirSync, readdirSync, rmSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, "..");
const distDir = path.resolve(projectRoot, "dist");
const staticDir = path.resolve(projectRoot, "..", "..", "static");
const staticAssetsDir = path.resolve(staticDir, "assets");
const distAssetsDir = path.resolve(distDir, "assets");

if (!existsSync(distDir)) {
  throw new Error(`dist not found: ${distDir}`);
}

mkdirSync(staticDir, { recursive: true });
mkdirSync(staticAssetsDir, { recursive: true });

for (const fileName of ["index.html", "widget.html"]) {
  const src = path.resolve(distDir, fileName);
  if (existsSync(src)) {
    cpSync(src, path.resolve(staticDir, fileName));
  }
}

if (!existsSync(distAssetsDir)) {
  throw new Error(`dist/assets not found: ${distAssetsDir}`);
}

for (const entry of readdirSync(staticAssetsDir)) {
  rmSync(path.resolve(staticAssetsDir, entry), { recursive: true, force: true });
}

cpSync(distAssetsDir, staticAssetsDir, { recursive: true });

console.log("Synced dist -> static successfully.");
console.log(`dist: ${distDir}`);
console.log(`static: ${staticDir}`);
