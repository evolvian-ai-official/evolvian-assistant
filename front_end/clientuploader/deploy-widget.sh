#!/bin/bash
set -e

echo "🚀 Borrando antiguos assets..."
supabase storage rm ss:///public_assets/widget.html --experimental || true
supabase storage rm ss:///public_assets/assets --experimental -r || true
supabase storage rm ss:///public_assets/embed-floating.js --experimental || true
supabase storage rm ss:///public_assets/embed-floating.css --experimental || true

echo "📦 Subiendo HTML..."
supabase storage cp ./dist/widget.html ss:///public_assets/widget.html --experimental --content-type "text/html"

echo "📦 Subiendo JS (bundles)..."
for f in ./dist/assets/*.js; do
  fname=$(basename "$f")
  echo " → $fname"
  supabase storage cp "$f" ss:///public_assets/assets/$fname --experimental --content-type "application/javascript"
done

echo "📦 Subiendo CSS (bundles)..."
for f in ./dist/assets/*.css; do
  fname=$(basename "$f")
  echo " → $fname"
  supabase storage cp "$f" ss:///public_assets/assets/$fname --experimental --content-type "text/css"
done

echo "📦 Subiendo embed-floating.js..."
supabase storage cp ./dist/embed-floating.js ss:///public_assets/embed-floating.js --experimental --content-type "application/javascript"


echo "✅ Deploy completado!"
