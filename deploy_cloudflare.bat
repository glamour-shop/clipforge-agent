@echo off
title ClipForge — Cloudflare Worker Deployer
cd /d "%~dp0"
echo ========================================================
echo   ClipForge Autonomous Shorts Agent - Cloudflare Deploy
echo ========================================================
node "F:\G3 import aistudio\node_modules\wrangler\wrangler-dist\cli.js" login
node "F:\G3 import aistudio\node_modules\wrangler\wrangler-dist\cli.js" deploy
pause
